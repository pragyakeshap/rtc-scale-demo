import os, time, re
from collections import deque
from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST

# Optional GPU work using PyTorch
try:
    import torch
except Exception as e:
    torch = None

app = FastAPI(title="rtc-gpu-media")

# Add CORS middleware to allow requests from file:// and localhost
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# Global load tracking for CPU performance simulation
_concurrent_requests = 0

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
# GPU Simulation Mode - allows demo without actual GPU hardware
GPU_SIMULATION = os.getenv("GPU_SIMULATION", "false").lower() == "true"
# GPU speedup factor for simulation (GPUs are typically 10-50x faster for ML workloads)
GPU_SPEEDUP_FACTOR = float(os.getenv("GPU_SPEEDUP_FACTOR", "25.0"))
# GPU consistency factor - GPUs maintain performance better under load
GPU_CONSISTENCY_FACTOR = 0.15  # Very low variation in GPU timing

def device_str():
    if GPU_SIMULATION:
        return "cuda-simulated"
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
    global _concurrent_requests
    _concurrent_requests += 1
    
    REQUESTS.labels(endpoint="process").inc()
    start = time.perf_counter()
    try:
        w, h = parse_pixels(pixels)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Simulate different processing modes
    if GPU_SIMULATION:
        # GPU Simulation: Dramatically faster and more consistent performance
        import random
        
        # Base GPU processing time (much faster and consistent)
        base_gpu_time = 0.003 + (iters * 0.0005) + (w * h * 0.000000001)
        
        # Add minimal variation for realism (GPUs are very consistent)
        variation = random.uniform(-GPU_CONSISTENCY_FACTOR, GPU_CONSISTENCY_FACTOR)
        simulated_gpu_duration = base_gpu_time * (1 + variation)
        
        # Ensure minimum realistic GPU time (very fast and stable)
        simulated_gpu_duration = max(0.002, min(0.015, simulated_gpu_duration))
        
        # Sleep for the simulated GPU processing time
        time.sleep(simulated_gpu_duration)
            
    elif torch is not None:
        # Real GPU or CPU processing
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
        # CPU-only processing: more variable and slower under load
        import random
        if torch is not None:
            c = 3
            tensor = torch.rand((1, c, h // 2, w // 2), device="cpu")
            for _ in range(max(1, iters)):
                tensor = torch.nn.functional.avg_pool2d(tensor, kernel_size=3, stride=1, padding=1)
                a = torch.rand((256, 256), device="cpu")
                b = torch.rand((256, 256), device="cpu")
                _ = a @ b
                
                # Simulate CPU getting slower under concurrent load
                load_factor = min(_concurrent_requests / 10.0, 3.0)  # More load = more delays
                delay_chance = 0.2 + (load_factor * 0.3)  # 20-80% chance of delay based on load
                
                if random.random() < delay_chance:
                    base_delay = 0.002 + (load_factor * 0.005)  # 2-17ms extra delay
                    time.sleep(random.uniform(0.001, base_delay))
        else:
            # CPU fallback: mimic work via pure Python loops with load simulation
            acc = 0.0
            base_iterations = max(1, iters * 50000)
            
            # Simulate CPU performance degradation under load
            load_factor = min(_concurrent_requests / 5.0, 4.0)  # Scale with concurrent requests
            load_multiplier = 1 + random.uniform(0, 0.3 + load_factor * 0.4)  # Up to 190% more work under high load
            iterations = int(base_iterations * load_multiplier)
            
            for _ in range(iterations):
                acc += (3.14159 * 2.71828) % 1.61803

    dur = time.perf_counter() - start
    _concurrent_requests -= 1  # Decrement when request completes
    
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

@app.post("/toggle-gpu-simulation")
def toggle_gpu_simulation():
    """Toggle GPU simulation mode for demo purposes"""
    global GPU_SIMULATION, DEVICE
    GPU_SIMULATION = not GPU_SIMULATION
    DEVICE = device_str()  # Update device string
    return {
        "gpu_simulation": GPU_SIMULATION,
        "device": DEVICE,
        "speedup_factor": GPU_SPEEDUP_FACTOR,
        "message": f"GPU simulation {'enabled' if GPU_SIMULATION else 'disabled'}"
    }

@app.get("/gpu-simulation-status")
def gpu_simulation_status():
    """Get current GPU simulation status"""
    return {
        "gpu_simulation": GPU_SIMULATION,
        "device": DEVICE,
        "speedup_factor": GPU_SPEEDUP_FACTOR
    }

@app.get("/demo")
def demo():
    """Serve the HTML demo page"""
    return FileResponse("app/webrtc-latency-demo.html", media_type="text/html")
