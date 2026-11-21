# Third-party notices

Bucket Studio is MIT-licensed. It builds on the open-source projects and models below, each under its
own license. Model weights are **not** shipped in this repository or in the container images: they are
downloaded from their upstream sources on first use.

## Models (downloaded at runtime)

| Model | Used for | Source | License |
|---|---|---|---|
| BiRefNet (`birefnet-*`) | Background removal (default) | [ZhengPeng7/BiRefNet](https://github.com/ZhengPeng7/BiRefNet) | MIT |
| U²-Net (`u2net`, `u2netp`, `silueta`) | Background removal (optional) | [xuebinqin/U-2-Net](https://github.com/xuebinqin/U-2-Net) | Apache-2.0 |
| IS-Net (`isnet-general-use`) | Background removal (optional) | [xuebinqin/DIS](https://github.com/xuebinqin/DIS) | Apache-2.0 |
| Real-ESRGAN x4plus | Upscaling | [xinntao/Real-ESRGAN](https://github.com/xinntao/Real-ESRGAN) | BSD-3-Clause |

`backend/app/core/esrgan.py` reimplements the RRDBNet generator after
[BasicSR](https://github.com/XPixelGroup/BasicSR) (Apache-2.0) and the tiled inference after
[Real-ESRGAN](https://github.com/xinntao/Real-ESRGAN) (BSD-3-Clause); neither package is a dependency.

## Key libraries

| Library | License |
|---|---|
| [rembg](https://github.com/danielgatis/rembg) | MIT |
| [ONNX Runtime](https://github.com/microsoft/onnxruntime) | MIT |
| [PyTorch](https://github.com/pytorch/pytorch) | BSD-3-Clause |
| [FastAPI](https://github.com/fastapi/fastapi) | MIT |
| [SQLAlchemy](https://github.com/sqlalchemy/sqlalchemy) | MIT |
| [Pillow](https://github.com/python-pillow/Pillow) | MIT-CMU |
| [React](https://github.com/facebook/react) | MIT |
| [Ant Design](https://github.com/ant-design/ant-design) | MIT |

The complete dependency lists are in [`backend/requirements.txt`](backend/requirements.txt) and
[`frontend/pnpm-lock.yaml`](frontend/pnpm-lock.yaml).

## Optional external services

When you configure an OpenAI or Google Gemini API key, images you choose to process with those engines
are sent to that provider and are subject to its terms and data policies. Nothing is sent to any third
party unless you configure a key and select that engine.
