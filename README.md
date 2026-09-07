# Speaker Diarization API

Serve [`pyannote/speaker-diarization-3.1`](https://huggingface.co/pyannote/speaker-diarization-3.1)
as a REST API, containerized with Docker and deployed on a local
[kind](https://kind.sigs.k8s.io/) Kubernetes cluster.

Upload an audio file, get back **who spoke when**.

## API

| Method | Path        | Description                                  |
|--------|-------------|----------------------------------------------|
| GET    | `/`         | Service info                                 |
| GET    | `/health`   | Health check                                 |
| POST   | `/diarize`  | Upload audio file → speaker segments (JSON)  |

`POST /diarize` accepts a multipart file field `file` and optional query
params `num_speakers`, `min_speakers`, `max_speakers`.

Example response:

```json
{
  "num_speakers": 2,
  "speakers": ["SPEAKER_00", "SPEAKER_01"],
  "segments": [
    {"start": 0.5, "end": 3.2, "speaker": "SPEAKER_00"},
    {"start": 3.4, "end": 6.1, "speaker": "SPEAKER_01"}
  ]
}
```

## Prerequisites

1. A [Hugging Face account](https://huggingface.co/join) + access token.
2. Accept the user conditions on **both** model pages:
   - https://huggingface.co/pyannote/speaker-diarization-3.1
   - https://huggingface.co/pyannote/segmentation-3.0
3. Docker, kind, and kubectl installed.

## Quick start (one command)

The easiest way — anyone can deploy this into their own kind cluster:

```bash
cp .env.example .env      # then edit .env and paste your HF token
./deploy.sh
```

That builds the image (baking in the model), creates/reuses the `controlplane`
kind cluster, loads the image, deploys, and waits until the API is live at
`http://localhost:8080`.

## Build (manual)

The model is baked into the image at build time (works offline afterwards).
The HF token is passed as a BuildKit **secret**, so it is never stored in any
image layer:

```bash
export HF_TOKEN=hf_your_token_here
DOCKER_BUILDKIT=1 docker build --secret id=hf_token,env=HF_TOKEN -t speaker-diarization:latest .
```

## Run locally with Docker

```bash
docker run -p 8000:8000 speaker-diarization:latest
curl -F "file=@sample.wav" http://localhost:8000/diarize
```

## Deploy to kind

```bash
# 1. Create the reusable cluster (once)
kind create cluster --config k8s/kind-cluster.yaml

# 2. Load the image into the cluster
kind load docker-image speaker-diarization:latest --name controlplane

# 3. Deploy
kubectl apply -f k8s/deployment.yaml

# 4. Wait until ready
kubectl rollout status deployment/speaker-diarization
```

The endpoint is exposed at `http://localhost:8080` on your machine:

```bash
curl -F "file=@sample.wav" http://localhost:8080/diarize
```

## Notes

- The image is large (~several GB) because of PyTorch + the model weights.
- Inference runs on CPU here; it works but is slower than on GPU.
