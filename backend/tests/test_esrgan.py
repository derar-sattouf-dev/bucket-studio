"""The in-repo Real-ESRGAN network: checkpoint layout and tiled inference (tiny random weights)."""

import numpy as np
import torch

from app.core.esrgan import SCALE, RRDBNet, Upscaler


def _tiny_model() -> RRDBNet:
    torch.manual_seed(0)
    return RRDBNet(num_feat=4, num_block=2, num_grow_ch=2).eval()


def _image(height: int, width: int) -> np.ndarray:
    return np.random.default_rng(0).integers(0, 256, (height, width, 3), dtype=np.uint8)


def test_layer_names_match_the_published_checkpoint():
    names = set(_tiny_model().state_dict())
    expected = {
        "conv_first.weight",
        "body.0.rdb1.conv1.weight",
        "body.1.rdb3.conv5.bias",
        "conv_body.weight",
        "conv_up1.weight",
        "conv_up2.weight",
        "conv_hr.weight",
        "conv_last.bias",
    }
    assert expected <= names


def test_tiles_cover_the_whole_image():
    image = _image(13, 22)  # not a multiple of the tile size
    result = Upscaler(_tiny_model(), tile=8, tile_pad=2).upscale_4x(image)
    assert result.shape == (13 * SCALE, 22 * SCALE, 3)
    assert result.dtype == np.uint8


def test_a_single_tile_equals_running_the_network_directly():
    image = _image(9, 11)
    model = _tiny_model()
    with torch.no_grad():
        direct = model(torch.from_numpy(image.astype(np.float32) / 255.0).permute(2, 0, 1).unsqueeze(0))
    expected = (direct.squeeze(0).clamp(0, 1).permute(1, 2, 0).numpy() * 255.0).round().astype(np.uint8)
    result = Upscaler(model, tile=64, tile_pad=4).upscale_4x(image)
    assert np.array_equal(result, expected)
