# rtc-gpu-media app

Endpoints:
- `GET /healthz`
- `POST /process?pixels=1280x720&iters=5`
- `GET /metrics` (Prometheus)

## Local run (CPU)
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r app/requirements.txt
# Optional: CPU PyTorch (for local dev)
pip install --no-cache-dir --extra-index-url https://download.pytorch.org/whl/cpu torch==2.3.1
uvicorn app.server:app --host 0.0.0.0 --port 8080
```

## Test
```bash
curl -s localhost:8080/healthz
curl -s -X POST "http://localhost:8080/process?pixels=1280x720&iters=5"
curl -s localhost:8080/metrics | head
```
