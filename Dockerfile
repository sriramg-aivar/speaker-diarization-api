# syntax=docker/dockerfile:1.7
FROM python:3.11-slim

# System deps: ffmpeg + libsndfile for audio decoding
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps (CPU torch wheels)
COPY requirements.txt .
RUN pip install --no-cache-dir --extra-index-url https://download.pytorch.org/whl/cpu -r requirements.txt

# Bake the model into the image at build time.
# The HF token is passed as a BuildKit *secret* so it is NEVER stored in any
# image layer or environment variable. Build with:
#   docker build --secret id=hf_token,env=HF_TOKEN -t speaker-diarization:latest .
ENV HF_HOME=/app/hf_cache
COPY download_model.py .
RUN --mount=type=secret,id=hf_token \
    HF_TOKEN="$(cat /run/secrets/hf_token)" python download_model.py

COPY app.py .

EXPOSE 8000

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
