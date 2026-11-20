# syntax=docker/dockerfile:1.7
FROM python:3.11-slim

LABEL org.opencontainers.image.title="Bucket Studio backend" \
      org.opencontainers.image.description="Self-hosted image pipeline for S3 buckets (API + workers)" \
      org.opencontainers.image.licenses="MIT"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    MODELS_DIR=/models \
    NUMBA_CACHE_DIR=/tmp/numba_cache \
    MPLCONFIGDIR=/tmp/matplotlib

# ── System deps: OpenMP for onnxruntime/torch, glib for OpenCV, curl for the healthcheck ──
RUN apt-get update && apt-get install -y --no-install-recommends libglib2.0-0 libgomp1 curl \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --uid 10001 appuser
WORKDIR /app

# ── Python deps ───────────────────────────────────────────────────────────────
# CPU-only torch first (avoids ~2 GB of CUDA wheels), then the lock file.
# basicsr depends on the GUI build of OpenCV, which needs X11/OpenGL system libraries.
# A server only needs the headless build, so it replaces the GUI one (same cv2 API).
COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install torch==2.6.0 torchvision==0.21.0 --index-url https://download.pytorch.org/whl/cpu \
    && pip install -r requirements.txt \
    && pip uninstall -y opencv-python \
    && pip install --force-reinstall --no-deps "$(grep -i '^opencv-python-headless==' requirements.txt)" \
    && python -c "import cv2, numpy; assert numpy.__version__.startswith('2.'), numpy.__version__"

# ── App code ──────────────────────────────────────────────────────────────────
COPY alembic.ini ./
COPY app/ ./app/

# ML models are downloaded on first use into $MODELS_DIR (mount a volume there to keep them).
RUN mkdir -p /app/data /models && chown -R appuser:appuser /app/data /models
USER appuser

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/health || exit 1

# Single worker: job/task state is in-process (see docs/architecture.md).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--no-server-header"]
