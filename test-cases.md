# Test Cases — Speaker Diarization API

Every command below was run against the live deployment and works. There are
two ways to test:

- **A. From outside** — hit the endpoint exposed at `http://localhost:8080`.
- **B. From inside the pod** — `kubectl exec` into the running container and
  test `http://localhost:8000` directly (the pod has `python` but **not**
  `curl`, so in-pod HTTP tests use python).

> ⏱️ **`/diarize` is SLOW on CPU — do NOT press Ctrl+C.** Inference runs on CPU
> here, so a single `/diarize` call can take **~30-60 seconds** (a ~30s audio
> clip measured ~44s). With `curl -s` you see nothing while it works, so it
> *looks* frozen but it is not. Just wait. Use `time curl ...` to watch the
> elapsed time, or drop `-s` to see curl's transfer progress. `/health` and
> `/` are instant; only `/diarize` is slow.

Get the pod name once and reuse it:

```bash
POD=$(kubectl get pods -l app=speaker-diarization -o jsonpath='{.items[0].metadata.name}')
echo "$POD"
```

---

## A. Tests from outside (via the exposed endpoint)

### A1. Health check
```bash
curl -s http://localhost:8080/health
```
**Expected:**
```json
{"status":"ok","model_loaded":true}
```

### A2. Service info (root)
```bash
curl -s http://localhost:8080/
```
**Expected:** JSON with `"service": "Speaker Diarization API"` and the list of endpoints.

### A3. Diarize a real speech file
Use any local `.wav`/`.mp3`/`.flac`. If you don't have one, download a sample
**once**:
```bash
curl -sL -o speech.wav \
  "https://github.com/pyannote/pyannote-audio/raw/develop/tutorials/assets/sample.wav"
```
Then diarize the local file directly (the `@` means "read this local file"):
```bash
# use `time` so you can see it is working, not frozen (takes ~30-60s on CPU)
time curl -s -F "file=@speech.wav" http://localhost:8080/diarize
```
**Do not Ctrl+C — wait for it.** **Expected:** JSON with detected speakers, e.g.
```json
{"num_speakers":3,"speakers":["SPEAKER_00","SPEAKER_01","SPEAKER_02"],"segments":[...]}
```

### A4. Diarize with a fixed number of speakers
```bash
curl -s -F "file=@speech.wav" "http://localhost:8080/diarize?num_speakers=2"
```
**Expected:** exactly 2 speakers in the response.

### A5. Diarize with a speaker range
```bash
curl -s -F "file=@speech.wav" "http://localhost:8080/diarize?min_speakers=1&max_speakers=3"
```
**Expected:** between 1 and 3 speakers.

### A6. Error handling — no file uploaded
```bash
curl -s -o /dev/null -w "%{http_code}\n" -X POST http://localhost:8080/diarize
```
**Expected:** `422` (FastAPI validation error — `file` field is required).

---

## B. Tests from inside the pod

> **IMPORTANT — where you run each command:**
> - `kubectl ...` commands (including `kubectl exec` and `kubectl cp`) run on
>   **your Mac**, NOT inside the pod. `kubectl` does not exist inside the
>   container.
> - Once you are inside the pod (prompt looks like
>   `root@speaker-diarization-...:/app#`), run commands **directly** —
>   just `python`, `ls`, etc. Do NOT prefix them with `kubectl` or `$POD`.
>
> Two ways to run an in-pod test:
> - **One-shot from the Mac:** `kubectl exec "$POD" -- <command>`
> - **Interactive:** `kubectl exec -it "$POD" -- bash`, then run `<command>` directly.

### B1. Exec into the pod (interactive shell)
```bash
kubectl exec -it "$POD" -- bash
```
You're now inside the container. Exit any time with `exit`.

### B2. Health check from inside (uses python, no curl)
```bash
kubectl exec "$POD" -- python -c \
"import urllib.request; print(urllib.request.urlopen('http://localhost:8000/health').read().decode())"
```
**Expected:**
```json
{"status":"ok","model_loaded":true}
```

### B3. Confirm the model weights are baked into the image
```bash
kubectl exec "$POD" -- ls /root/.cache/torch/pyannote/
```
**Expected:** three cached models —
```
models--pyannote--speaker-diarization-3.1
models--pyannote--segmentation-3.0
models--pyannote--wespeaker-voxceleb-resnet34-LM
```
This proves the pod runs fully offline (no Hugging Face download at runtime).

### B4. Copy an audio file into the pod and diarize it

The file must exist **inside** the pod before you can diarize it. The copy
step runs on your Mac; the diarize step runs inside the pod.

**Step 1 — on your Mac** (copy the file in):
```bash
POD=$(kubectl get pods -l app=speaker-diarization -o jsonpath='{.items[0].metadata.name}')
kubectl cp speech.wav "$POD":/tmp/speech.wav
```

**Step 2a — one-shot from your Mac** (diarize the copied file):
```bash
kubectl exec "$POD" -- python -c "
import urllib.request, uuid
boundary=uuid.uuid4().hex
with open('/tmp/speech.wav','rb') as f: data=f.read()
body=(b'--'+boundary.encode()+b'\r\nContent-Disposition: form-data; name=\"file\"; filename=\"speech.wav\"\r\nContent-Type: audio/wav\r\n\r\n'+data+b'\r\n--'+boundary.encode()+b'--\r\n')
req=urllib.request.Request('http://localhost:8000/diarize', data=body,
    headers={'Content-Type':'multipart/form-data; boundary='+boundary})
print(urllib.request.urlopen(req).read().decode())
"
```

**Step 2b — OR interactively from inside the pod** (after `kubectl exec -it "$POD" -- bash`,
run this directly, WITHOUT `kubectl` or `$POD`):
```bash
python -c "
import urllib.request, uuid
boundary=uuid.uuid4().hex
with open('/tmp/speech.wav','rb') as f: data=f.read()
body=(b'--'+boundary.encode()+b'\r\nContent-Disposition: form-data; name=\"file\"; filename=\"speech.wav\"\r\nContent-Type: audio/wav\r\n\r\n'+data+b'\r\n--'+boundary.encode()+b'--\r\n')
req=urllib.request.Request('http://localhost:8000/diarize', data=body,
    headers={'Content-Type':'multipart/form-data; boundary='+boundary})
print(urllib.request.urlopen(req).read().decode())
"
```
**Expected:** same diarization JSON as A3 (e.g. 3 speakers with segments).
Give it a few seconds — CPU inference is not instant.

Clean up afterwards (from your Mac):
```bash
kubectl exec "$POD" -- rm -f /tmp/speech.wav
```

### B5. Run the model directly in python (bypassing the API)
Useful to confirm the pipeline itself loads from the baked cache:
```bash
kubectl exec "$POD" -- python -c "
from pyannote.audio import Pipeline
p = Pipeline.from_pretrained('pyannote/speaker-diarization-3.1')
print('pipeline loaded OK:', p is not None)
"
```
**Expected:** `pipeline loaded OK: True` (no token needed — served from cache).

---

## C. Cluster / pod inspection

### C1. Pod status
```bash
kubectl get pods -l app=speaker-diarization
```
**Expected:** `1/1  Running`.

### C2. Service and port mapping
```bash
kubectl get svc speaker-diarization
```
**Expected:** `NodePort  80:30080/TCP` (mapped to host `localhost:8080`).

### C3. Live logs (watch requests as they come in)
```bash
kubectl logs -f "$POD"
```
Send a request from another terminal and watch it get logged.

### C4. Readiness/liveness probe status
```bash
kubectl describe pod "$POD" | grep -A2 -E "Readiness|Liveness"
```
**Expected:** both probes hitting `/health` on port 8000.

---

## Notes

- Synthetic tones (pure sine waves) return `num_speakers: 0` — the model detects
  **human speech**, not arbitrary audio. Use real speech to see speakers.
- First request after a fresh pod start may take longer while the pipeline warms up.
- **Inference runs on CPU here, so `/diarize` takes ~30-60 seconds** (a ~30s clip
  measured ~44s). This is expected — do not Ctrl+C. Longer audio takes longer.
  A GPU would make it much faster, but this local kind setup uses CPU only.
- You do NOT need to re-download the sample every time — reuse the local
  `speech.wav` with `-F "file=@speech.wav"` (or give a full path).
