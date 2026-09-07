"""
FastAPI service for pyannote/speaker-diarization-3.1.

Exposes a REST API that accepts an audio file and returns speaker
diarization segments (who spoke when).
"""
import os
import tempfile
import logging

import torch
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
from pyannote.audio import Pipeline

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("diarization")

# Where the model was baked into the image (see Dockerfile).
MODEL_ID = os.getenv("MODEL_ID", "pyannote/speaker-diarization-3.1")
HF_TOKEN = os.getenv("HF_TOKEN")  # only needed if model is not cached

app = FastAPI(
    title="Speaker Diarization API",
    description="pyannote/speaker-diarization-3.1 served over HTTP.",
    version="1.0.0",
)

pipeline = None


@app.on_event("startup")
def load_model():
    """Load the diarization pipeline once at startup."""
    global pipeline
    logger.info("Loading pipeline %s ...", MODEL_ID)
    kwargs = {}
    if HF_TOKEN:
        kwargs["use_auth_token"] = HF_TOKEN
    pipeline = Pipeline.from_pretrained(MODEL_ID, **kwargs)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    pipeline.to(torch.device(device))
    logger.info("Pipeline loaded on %s", device)


@app.get("/")
def root():
    return {
        "service": "Speaker Diarization API",
        "model": MODEL_ID,
        "endpoints": {
            "GET /health": "health check",
            "POST /diarize": "upload an audio file, get speaker segments",
        },
    }


@app.get("/health")
def health():
    return {"status": "ok", "model_loaded": pipeline is not None}


@app.post("/diarize")
async def diarize(
    file: UploadFile = File(...),
    num_speakers: int = None,
    min_speakers: int = None,
    max_speakers: int = None,
):
    """Run speaker diarization on an uploaded audio file."""
    if pipeline is None:
        raise HTTPException(status_code=503, detail="Model not loaded yet")

    suffix = os.path.splitext(file.filename or "")[1] or ".wav"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    try:
        params = {}
        if num_speakers is not None:
            params["num_speakers"] = num_speakers
        if min_speakers is not None:
            params["min_speakers"] = min_speakers
        if max_speakers is not None:
            params["max_speakers"] = max_speakers

        diarization = pipeline(tmp_path, **params)

        segments = [
            {
                "start": round(turn.start, 3),
                "end": round(turn.end, 3),
                "speaker": speaker,
            }
            for turn, _, speaker in diarization.itertracks(yield_label=True)
        ]
        speakers = sorted({s["speaker"] for s in segments})

        return JSONResponse(
            {
                "num_speakers": len(speakers),
                "speakers": speakers,
                "segments": segments,
            }
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Diarization failed")
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        os.unlink(tmp_path)
