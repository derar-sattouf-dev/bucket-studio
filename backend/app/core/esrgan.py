"""Real-ESRGAN x4plus inference: the RRDBNet generator and tiled upscaling on the CPU.

The network is a small, fixed architecture, so it is defined here instead of pulling in the
`basicsr` / `realesrgan` packages (training frameworks with a long, unmaintained dependency tail).
Layer names match the published checkpoint, which is loaded as plain tensors (`weights_only=True`).

Architecture from ESRGAN (Wang et al., 2018) as implemented in BasicSR (Apache-2.0); tiling follows
Real-ESRGAN (BSD-3-Clause). See THIRD_PARTY_NOTICES.md.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import torch
from numpy.typing import NDArray
from torch import Tensor, nn
from torch.nn import functional

SCALE = 4
_RESIDUAL_SCALE = 0.2
_LEAKY_SLOPE = 0.2


def _lrelu(x: Tensor) -> Tensor:
    return functional.leaky_relu(x, _LEAKY_SLOPE)


def _nearest_2x(x: Tensor) -> Tensor:
    return functional.interpolate(x, scale_factor=2, mode="nearest")


class _ResidualDenseBlock(nn.Module):
    def __init__(self, num_feat: int, num_grow_ch: int) -> None:
        super().__init__()
        self.conv1 = nn.Conv2d(num_feat, num_grow_ch, 3, 1, 1)
        self.conv2 = nn.Conv2d(num_feat + num_grow_ch, num_grow_ch, 3, 1, 1)
        self.conv3 = nn.Conv2d(num_feat + 2 * num_grow_ch, num_grow_ch, 3, 1, 1)
        self.conv4 = nn.Conv2d(num_feat + 3 * num_grow_ch, num_grow_ch, 3, 1, 1)
        self.conv5 = nn.Conv2d(num_feat + 4 * num_grow_ch, num_feat, 3, 1, 1)

    def forward(self, x: Tensor) -> Tensor:
        x1 = _lrelu(self.conv1(x))
        x2 = _lrelu(self.conv2(torch.cat((x, x1), 1)))
        x3 = _lrelu(self.conv3(torch.cat((x, x1, x2), 1)))
        x4 = _lrelu(self.conv4(torch.cat((x, x1, x2, x3), 1)))
        x5 = self.conv5(torch.cat((x, x1, x2, x3, x4), 1))
        return x5 * _RESIDUAL_SCALE + x


class _RRDB(nn.Module):
    """Residual-in-residual dense block."""

    def __init__(self, num_feat: int, num_grow_ch: int) -> None:
        super().__init__()
        self.rdb1 = _ResidualDenseBlock(num_feat, num_grow_ch)
        self.rdb2 = _ResidualDenseBlock(num_feat, num_grow_ch)
        self.rdb3 = _ResidualDenseBlock(num_feat, num_grow_ch)

    def forward(self, x: Tensor) -> Tensor:
        out = self.rdb3(self.rdb2(self.rdb1(x)))
        return out * _RESIDUAL_SCALE + x


class RRDBNet(nn.Module):
    """The x4 generator (3 → 3 channels, 23 blocks of 64 features in the x4plus checkpoint)."""

    def __init__(self, num_feat: int = 64, num_block: int = 23, num_grow_ch: int = 32) -> None:
        super().__init__()
        self.conv_first = nn.Conv2d(3, num_feat, 3, 1, 1)
        self.body = nn.Sequential(*(_RRDB(num_feat, num_grow_ch) for _ in range(num_block)))
        self.conv_body = nn.Conv2d(num_feat, num_feat, 3, 1, 1)
        self.conv_up1 = nn.Conv2d(num_feat, num_feat, 3, 1, 1)
        self.conv_up2 = nn.Conv2d(num_feat, num_feat, 3, 1, 1)
        self.conv_hr = nn.Conv2d(num_feat, num_feat, 3, 1, 1)
        self.conv_last = nn.Conv2d(num_feat, 3, 3, 1, 1)

    def forward(self, x: Tensor) -> Tensor:
        feat = self.conv_first(x)
        feat = feat + self.conv_body(self.body(feat))
        feat = _lrelu(self.conv_up1(_nearest_2x(feat)))
        feat = _lrelu(self.conv_up2(_nearest_2x(feat)))
        out: Tensor = self.conv_last(_lrelu(self.conv_hr(feat)))
        return out


class Upscaler:
    """Runs the network over an image in tiles, which keeps peak memory flat for any input size."""

    def __init__(self, model: RRDBNet, tile: int, tile_pad: int) -> None:
        self._model = model
        self._tile = tile
        self._tile_pad = tile_pad

    def upscale_4x(self, rgb: NDArray[np.uint8]) -> NDArray[np.uint8]:
        """`rgb` is HxWx3 uint8; returns the 4Hx4Wx3 uint8 result."""
        img = torch.from_numpy(rgb.astype(np.float32) / 255.0).permute(2, 0, 1).unsqueeze(0)
        with torch.no_grad():
            output = self._run_tiles(img)
        hwc = output.squeeze(0).clamp_(0, 1).permute(1, 2, 0).numpy()
        result: NDArray[np.uint8] = (hwc * 255.0).round().astype(np.uint8)
        return result

    def _run_tiles(self, img: Tensor) -> Tensor:
        _, channels, height, width = img.shape
        output = img.new_zeros((1, channels, height * SCALE, width * SCALE))
        tile, pad = self._tile, self._tile_pad
        for row in range(math.ceil(height / tile)):
            for col in range(math.ceil(width / tile)):
                top, left = row * tile, col * tile
                bottom, right = min(top + tile, height), min(left + tile, width)
                # Each tile is run with a border of real neighbouring pixels, which is cut off
                # again afterwards, so the seams between tiles do not show.
                pad_top, pad_left = max(top - pad, 0), max(left - pad, 0)
                pad_bottom, pad_right = min(bottom + pad, height), min(right + pad, width)
                upscaled = self._model(img[:, :, pad_top:pad_bottom, pad_left:pad_right])
                crop_top, crop_left = (top - pad_top) * SCALE, (left - pad_left) * SCALE
                rows, cols = (bottom - top) * SCALE, (right - left) * SCALE
                kept = upscaled[:, :, crop_top : crop_top + rows, crop_left : crop_left + cols]
                output[:, :, top * SCALE : bottom * SCALE, left * SCALE : right * SCALE] = kept
        return output


def load_upscaler(weights: Path, *, tile: int, tile_pad: int) -> Upscaler:
    """Build the network and load a Real-ESRGAN x4plus checkpoint (CPU, inference mode)."""
    checkpoint = torch.load(weights, map_location="cpu", weights_only=True)
    state = checkpoint.get("params_ema") or checkpoint["params"]
    model = RRDBNet()
    model.load_state_dict(state, strict=True)
    model.eval()
    return Upscaler(model, tile=tile, tile_pad=tile_pad)
