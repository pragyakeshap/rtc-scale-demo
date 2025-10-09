import os, time, re
from collections import deque
from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST

# GPU processing libraries
try:
    import torch
    import torch.nn.functional as F
    import torchvision.transforms as transforms
    import numpy as np
except Exception as e:
    torch = None
    F = None
    transforms = None
    np = None

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
# Rolling p95 gauge for Prometheus Adapter
LATENCY_P95 = Gauge("app_request_latency_p95_seconds", "Rolling p95 of request latency (seconds)")
_last_latencies = deque(maxlen=512)

CUDA_WANTED = os.getenv("CUDA_WANTED", "true").lower() == "true"
# GPU Simulation Mode - allows running without actual GPU hardware
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

def real_gpu_process(width: int, height: int, iterations: int):
    """Perform actual GPU-intensive image processing operations."""
    if not torch.cuda.is_available():
        raise RuntimeError("GPU not available for processing")
    
    device = torch.device('cuda')
    
    # Create realistic input tensor (simulating video frame)
    # Use float32 for GPU efficiency
    input_tensor = torch.randn(1, 3, height, width, dtype=torch.float32, device=device)
    
    # Realistic GPU operations for video/image processing
    for i in range(iterations):
        # Convolution operation (common in video processing)
        conv_kernel = torch.randn(16, 3, 3, 3, device=device)
        processed = F.conv2d(input_tensor, conv_kernel, padding=1)
        
        # Non-linear activation
        processed = F.relu(processed)
        
        # Batch normalization (common in neural networks)
        processed = F.batch_norm(processed, 
                                torch.ones(16, device=device),
                                torch.zeros(16, device=device),
                                training=True)
        
        # Max pooling and upsampling (resize operations)
        if i % 2 == 0:
            processed = F.max_pool2d(processed, 2)
            processed = F.interpolate(processed, scale_factor=2, mode='bilinear', align_corners=False)
        
        # Keep only first 3 channels for next iteration
        input_tensor = processed[:, :3, :, :]
        
        # Matrix multiplication (common in ML inference)
        if i % 3 == 0:
            flattened = input_tensor.view(1, -1)
            weight_matrix = torch.randn(flattened.shape[1], flattened.shape[1], device=device)
            result = torch.mm(flattened, weight_matrix)
            input_tensor = result.view(input_tensor.shape)
    
    # Force GPU synchronization to measure actual processing time
    torch.cuda.synchronize()
    
    return input_tensor.shape

def cpu_intensive_process(width: int, height: int, iterations: int):
    """CPU fallback with realistic computational load."""
    if np is None:
        # Fallback to basic computation if numpy not available
        total = 0
        for i in range(iterations * width * height // 1000):
            total += i * 0.001
        return (1, 3, height, width)
    
    # Use numpy for CPU-intensive operations
    input_array = np.random.randn(3, height, width).astype(np.float32)
    
    for i in range(iterations):
        # Simulate convolution with numpy
        kernel = np.random.randn(3, 3, 3).astype(np.float32)
        
        # Manual convolution (CPU intensive)
        result = np.zeros_like(input_array)
        for c in range(3):
            for h in range(1, height-1):
                for w in range(1, width-1):
                    result[c, h, w] = np.sum(input_array[:, h-1:h+2, w-1:w+2] * kernel[c])
        
        # Non-linear operations
        input_array = np.maximum(0, result)  # ReLU
        
        # Matrix operations
        if i % 2 == 0:
            reshaped = input_array.reshape(-1)
            weight_matrix = np.random.randn(len(reshaped), len(reshaped) // 4).astype(np.float32)
            transformed = np.dot(reshaped, weight_matrix)
            # Reshape back (simplified)
            input_array = np.resize(transformed, input_array.shape)
    
    return input_array.shape

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

    # Determine processing mode and execute
    result_shape = None
    
    if GPU_SIMULATION:
        # Keep simulation mode for testing purposes
        import random
        base_gpu_time = 0.003 + (iters * 0.0005) + (w * h * 0.000000001)
        variation = random.uniform(-GPU_CONSISTENCY_FACTOR, GPU_CONSISTENCY_FACTOR)
        simulated_gpu_duration = base_gpu_time * (1 + variation)
        simulated_gpu_duration = max(0.002, min(0.015, simulated_gpu_duration))
        time.sleep(simulated_gpu_duration)
        result_shape = (1, 3, h, w)
        
    elif DEVICE == "cuda" and torch is not None and torch.cuda.is_available():
        # Real GPU processing
        try:
            result_shape = real_gpu_process(w, h, iters)
        except Exception as e:
            # Fallback to CPU if GPU processing fails
            print(f"GPU processing failed: {e}, falling back to CPU")
            result_shape = cpu_intensive_process(w, h, iters)
            
    else:
        # CPU processing fallback
        result_shape = cpu_intensive_process(w, h, iters)

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
        "latency_seconds": dur,
        "processing_mode": "gpu" if DEVICE == "cuda" else "cpu",
        "result_shape": result_shape,
        "concurrent_requests": _concurrent_requests,
        "duration_sec": round(dur, 4)
    }

@app.get("/metrics")
def metrics():
    data = generate_latest()
    return PlainTextResponse(data, media_type=CONTENT_TYPE_LATEST)

@app.post("/toggle-gpu-simulation")
def toggle_gpu_simulation():
    """Toggle GPU simulation mode for testing purposes"""
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

@app.get("/app")
def app_interface():
    """Serve the HTML application interface"""
    return FileResponse("app/webrtc-application.html", media_type="text/html")

# WebRTC GPU processing integration
try:
    from webrtc_processor import webrtc_manager, AIORTC_AVAILABLE
except ImportError:
    webrtc_manager = None
    AIORTC_AVAILABLE = False

@app.post("/webrtc/offer")
async def webrtc_offer(offer: dict):
    """Handle WebRTC offer for real-time video processing"""
    if not AIORTC_AVAILABLE or not webrtc_manager:
        raise HTTPException(status_code=501, detail="WebRTC not available")
    
    try:
        pc = await webrtc_manager.create_peer_connection()
        if not pc:
            raise HTTPException(status_code=500, detail="Failed to create peer connection")
        
        answer = await webrtc_manager.process_offer(pc, offer)
        return answer
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"WebRTC processing failed: {str(e)}")

@app.get("/webrtc/status")
def webrtc_status():
    """Get WebRTC capabilities and status"""
    return {
        "webrtc_available": AIORTC_AVAILABLE,
        "gpu_processing": torch.cuda.is_available() if torch is not None else False,
        "active_connections": len(webrtc_manager.connections) if webrtc_manager else 0,
        "device": DEVICE
    }

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup WebRTC connections on shutdown"""
    if webrtc_manager:
        await webrtc_manager.cleanup()
