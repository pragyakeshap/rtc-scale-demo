import os, time, re
from collections import deque
from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST

# Optional GPU work using PyTorch
try:
    import torch
except Exception as e:
    torch = None

app = FastAPI(title="rtc-gpu-media")

REQUESTS = Counter("app_requests_total", "Total requests", ["endpoint"])
LATENCY = Histogram(
    "app_request_latency_seconds",
    "Request latency (seconds)",
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2, 5)
)
# Rolling p95 gauge for Prometheus Adapter demo
LATENCY_P95 = Gauge("app_request_latency_p95_seconds", "Rolling p95 of request latency (seconds)")
_last_latencies = deque(maxlen=512)

CUDA_WANTED = os.getenv("CUDA_WANTED", "true").lower() == "true"

def device_str():
    if torch is None:
        return "cpu"
    if CUDA_WANTED and torch.cuda.is_available():
        return "cuda"
    return "cpu"

DEVICE = device_str()

@app.get("/healthz")
def healthz():
    REQUESTS.labels(endpoint="healthz").inc()
    return {
        "ok": True,
        "device": DEVICE,
        "torch_imported": torch is not None,
        "cuda_available": (torch.cuda.is_available() if (torch is not None) else False)
    }

def parse_pixels(p: str):
    m = re.match(r"^(\d+)[xX](\d+)$", p)
    if not m:
        raise ValueError("pixels must be like 1280x720")
    return int(m.group(1)), int(m.group(2))

def p95(values):
    if not values:
        return 0.0
    s = sorted(values)
    idx = int(0.95 * (len(s) - 1))
    return float(s[idx])

@app.post("/process")
def process(pixels: str = "1280x720", iters: int = 5):
    REQUESTS.labels(endpoint="process").inc()
    start = time.perf_counter()
    try:
        w, h = parse_pixels(pixels)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # If torch is present, simulate GPU/CPU work
    if torch is not None:
        dev = "cuda" if (DEVICE == "cuda") else "cpu"
        c = 3
        tensor = torch.rand((1, c, h // 2, w // 2), device=dev)
        for _ in range(max(1, iters)):
            tensor = torch.nn.functional.avg_pool2d(tensor, kernel_size=3, stride=1, padding=1)
            a = torch.rand((256, 256), device=dev)
            b = torch.rand((256, 256), device=dev)
            _ = a @ b
        if dev == "cuda":
            torch.cuda.synchronize()
    else:
        # Fallback: mimic work via pure Python loops
        acc = 0.0
        for _ in range(max(1, iters * 50000)):
            acc += (3.14159 * 2.71828) % 1.61803

    dur = time.perf_counter() - start
    LATENCY.observe(dur)
    _last_latencies.append(dur)
    LATENCY_P95.set(p95(list(_last_latencies)))

    return {
        "ok": True,
        "device": DEVICE,
        "pixels": f"{w}x{h}",
        "iters": iters,
        "duration_sec": round(dur, 4)
    }

@app.get("/metrics")
def metrics():
    data = generate_latest()
    return PlainTextResponse(data, media_type=CONTENT_TYPE_LATEST)
