"""
Downloads and caches the pyannote diarization pipeline at Docker build time.

The pipeline pulls in two gated models:
  - pyannote/speaker-diarization-3.1
  - pyannote/segmentation-3.0

You must have accepted their user conditions on Hugging Face and pass a
valid HF_TOKEN as a build arg. After this runs, the model is cached in the
image and no token is needed at runtime.
"""
import os
import sys

from pyannote.audio import Pipeline

MODEL_ID = os.getenv("MODEL_ID", "pyannote/speaker-diarization-3.1")
HF_TOKEN = os.getenv("HF_TOKEN")

if not HF_TOKEN:
    print("ERROR: HF_TOKEN not set. Pass it as a build arg.", file=sys.stderr)
    sys.exit(1)

print(f"Downloading pipeline {MODEL_ID} ...")
pipeline = Pipeline.from_pretrained(MODEL_ID, use_auth_token=HF_TOKEN)
print("Pipeline downloaded and cached successfully.")
