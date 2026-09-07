#!/usr/bin/env bash
#
# deploy.sh — build and deploy the speaker-diarization API end-to-end.
#
# Anyone can run this to put the model into their own kind cluster:
#   1. Put your Hugging Face token in a .env file (see .env.example)
#   2. ./deploy.sh
#
# Requires: docker, kind, kubectl installed and docker running.

set -euo pipefail

IMAGE="speaker-diarization:latest"
CLUSTER="controlplane"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# --- Load HF token from .env (never hardcoded) ---
if [[ -f .env ]]; then
  # shellcheck disable=SC1091
  set -a; source .env; set +a
fi

if [[ -z "${HF_TOKEN:-}" ]]; then
  echo "ERROR: HF_TOKEN not set. Copy .env.example to .env and add your token."
  echo "Get a Read token at https://huggingface.co/settings/tokens"
  echo "Also accept the license on both model pages (see README.md)."
  exit 1
fi

echo "==> [1/5] Building Docker image (downloads PyTorch + model, takes a while)..."
DOCKER_BUILDKIT=1 docker build --secret id=hf_token,env=HF_TOKEN -t "$IMAGE" .

echo "==> [2/5] Ensuring kind cluster '$CLUSTER' exists..."
if ! kind get clusters | grep -qx "$CLUSTER"; then
  kind create cluster --config k8s/kind-cluster.yaml
else
  echo "    Cluster '$CLUSTER' already exists, reusing it."
fi

echo "==> [3/5] Loading image into the cluster..."
kind load docker-image "$IMAGE" --name "$CLUSTER"

echo "==> [4/5] Applying Kubernetes manifests..."
kubectl apply -f k8s/deployment.yaml

echo "==> [5/5] Waiting for the deployment to become ready..."
kubectl rollout status deployment/speaker-diarization --timeout=600s

echo ""
echo "Done! The API is live at: http://localhost:8080"
echo "Try it:"
echo "  curl http://localhost:8080/health"
echo "  curl -F \"file=@sample.wav\" http://localhost:8080/diarize"
