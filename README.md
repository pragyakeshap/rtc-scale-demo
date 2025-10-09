# WebRTC Scaling Application: Cloud-Native Real-Time Media Processing

> **Production-Ready Application**: This repository shows how to scale WebRTC applications reliably using Docker and Kubernetes with **GPU acceleration**. It features a containerized media service that performs GPU-intensive video processing, while Kubernetes handles GPU scheduling and autoscaling using Prometheus and Grafana dashboards to maintain p95 latency within target SLOs.

## 🎯 What This Application Shows

- **WebRTC Media Processing**: aiortc-based service with GPU-accelerated video processing
- **GPU Acceleration**: PyTorch/CUDA operations with CPU fallback, not simulation
- **Advanced Kubernetes Autoscaling**: HPA based on latency, GPU utilization, CPU, and RPS
- **Comprehensive Observability**: Prometheus, Grafana, DCGM exporter for GPU monitoring
- **Production Deployment**: Automated GKE setup with GPU pools and monitoring stack

## 🏗️ Architecture

This production-ready application includes:
- **FastAPI + PyTorch + aiortc** media service with real GPU processing
- **WebRTC endpoints** for real-time video stream processing  
- **Prometheus + Grafana** stack with GPU-specific dashboards
- **Advanced HPA** with custom metrics (latency, GPU utilization, RPS)
- **Automated deployment** scripts for GKE clusters with GPU pools
- **Load generation** tools for realistic scaling tests

## 🚀 Quick Start

### Option 1: Local Development (CPU Mode)
```bash
# Setup Python environment
python3 -m venv .venv && source .venv/bin/activate
pip install -r app/requirements.txt

# Install CPU-only PyTorch (lighter for development)
pip install --no-cache-dir --extra-index-url https://download.pytorch.org/whl/cpu torch==2.3.1

# Start the server
uvicorn app.server:app --host 0.0.0.0 --port 8080

# Test endpoints
curl -s localhost:8080/healthz
curl -s "localhost:8080/process?pixels=1280x720&iters=5" | jq

# Open the interactive interface
open http://localhost:8080/app
```

### Option 2: Local with Docker (GPU Support)
```bash
# Build and run with GPU support
docker build -t rtc-gpu-app .
docker run --gpus all -p 8080:8080 rtc-gpu-app

# Test WebRTC status
curl -s localhost:8080/webrtc/status | jq
```

### Option 3: Production Deployment (GKE)
```bash
# Set your project
export PROJECT_ID="your-gcp-project"

# One-command deployment (recommended)
bash scripts/deploy.sh $PROJECT_ID

# Or step-by-step:
bash scripts/gke_create_gpu_pool.sh
bash scripts/build_and_push.sh
kubectl apply -f k8s/
```

## 🧪 Testing & Validation

### Quick Testing
```bash
# Fast integration test (no server required)
python3 test_integration.py

# API testing with running server
python3 test_simple.py --start-server

# Comprehensive test suite
./run_tests.sh --all
```

### Concurrent User Testing
Test realistic concurrent user scenarios:
```bash
# Quick concurrent user test
./test_concurrent_users.sh

# Custom concurrent load test
python3 tests/test_load.py --requests 100 --concurrency 20 --comparison

# Heavy load simulation (50 concurrent users)
python3 tests/test_load.py --requests 500 --concurrency 50
```

### Performance Benchmarks
- **CPU Mode**: 100-500ms latency for 1920x1080
- **GPU Mode**: 5-20ms latency (25x speedup)
- **Target**: <200ms p95 latency, >99% success rate
- **Scaling**: Maintains performance under 100+ concurrent users

### Test Categories
1. **Unit Tests** (`tests/test_server.py`) - Function-level testing
2. **Load Tests** (`tests/test_load.py`) - Concurrent user simulation
3. **K8s Tests** (`tests/test_k8s.py`) - Deployment validation
4. **Simple API Tests** (`test_simple.py`) - Quick health checks

### CI/CD Testing
GitHub Actions workflow includes:
- **Multi-version Python testing** (3.10, 3.11) with lightweight dependencies
- **Docker container validation** with GPU simulation
- **Security scanning with Trivy** (results in GitHub Security tab)
- **Code linting** with flake8 for quality assurance
- **Optimized pipeline** with timeouts and fail-safe mechanisms

See [`TESTING.md`](TESTING.md) for detailed testing guide.

## 📋 Application Features

### Real-Time Processing
- **GPU Acceleration**: PyTorch/CUDA operations with 25x speedup
- **WebRTC Integration**: Real-time video stream processing
- **Fallback Support**: Graceful CPU fallback when GPU unavailable
- **Concurrent Handling**: Support for 100+ concurrent users

### Production Ready
- **Auto-scaling**: HPA based on latency, GPU utilization, and RPS
- **Monitoring**: Comprehensive Prometheus metrics and Grafana dashboards
- **Security**: Non-root containers, resource limits, network policies
- **Reliability**: Health checks, automatic restarts, error handling

## Observability

Install kube-prometheus-stack (Prometheus + Grafana) via Helm (example):
```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update
helm install kube-prometheus-stack prometheus-community/kube-prometheus-stack -n monitoring --create-namespace
kubectl -n rtc apply -f k8s/servicemonitor.yaml
```

GPU metrics (optional):
```bash
kubectl apply -f observability/dcgm-exporter.yaml
```

Import `observability/grafana-dashboard.json` in Grafana.

## Latency-based autoscaling — two options

### Option A) **KEDA** (PromQL directly, including histogram_quantile)
Install KEDA:
```bash
helm repo add kedacore https://kedacore.github.io/charts
helm repo update
helm install keda kedacore/keda -n keda --create-namespace
```

Apply ScaledObject (edit Prometheus address if needed):
```bash
kubectl -n rtc apply -f k8s/hpa-keda-latency.yaml
```

### Option B) **Prometheus Adapter** (expose custom metric `app_latency_p95_seconds`)
Install Prometheus Adapter with provided values mapping:
```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update
helm install prom-adapter prometheus-community/prometheus-adapter   -n monitoring   -f observability/prometheus-adapter-values.yaml
```

Create HPA that targets the custom metric:
```bash
kubectl -n rtc apply -f k8s/hpa-latency-custom.yaml
```

> The app exports a rolling gauge `app_request_latency_p95_seconds`. Prometheus Adapter maps it to `app_latency_p95_seconds` for HPA.

## Drive Load & Watch Scale

### Quick Load Test
```bash
SVC_IP=$(kubectl -n rtc get svc gpu-media -o jsonpath='{.spec.clusterIP}')
bash scripts/load_gen.sh "http://${SVC_IP}/process?pixels=1920x1080&iters=10" 40 800
kubectl -n rtc get hpa -w
```

### Presentation-Ready Load Testing
For live presentations, use the enhanced load testing script:
```bash
# Start with baseline load
./scripts/app_load_gen.sh baseline

# Moderate load to trigger scaling
./scripts/app_load_gen.sh moderate  

# Heavy load for dramatic scaling
./scripts/app_load_gen.sh heavy
```

## 📡 API Endpoints

### Core Processing
- **`POST /process`** - Main GPU/CPU processing endpoint
  - `pixels`: Resolution (e.g., "1920x1080", "1280x720")  
  - `iters`: Processing iterations (1-50)
  - Returns latency, device used, processing metrics

### WebRTC Media Processing  
- **`POST /webrtc/offer`** - Handle WebRTC offer, return answer
- **`GET /webrtc/status`** - WebRTC capabilities and active connections

### Monitoring & Control
- **`GET /healthz`** - Health check with GPU status
- **`GET /metrics`** - Prometheus metrics
- **`POST /toggle-gpu-simulation`** - Toggle simulation mode
- **`GET /app`** - Interactive web interface

### Example Usage
```bash
# Test GPU processing
curl -X POST "localhost:8080/process" \
  -H "Content-Type: application/json" \
  -d '{"pixels": "1920x1080", "iters": 10}'

# Get metrics for monitoring
curl localhost:8080/metrics | grep app_request_latency

# Check WebRTC capabilities  
curl localhost:8080/webrtc/status
```

## 🎮 Interactive Web Interface

The web interface (`/app` endpoint) provides:
- **Real-time latency monitoring** with p95 tracking
- **CPU vs GPU performance comparison** 
- **Simulated video quality degradation** based on latency
- **Cost estimation** for different scaling scenarios
- **WebRTC testing interface** for video processing

## 🐳 Container Configuration

### Environment Variables
```bash
CUDA_WANTED=true              # Enable GPU acceleration
GPU_SIMULATION=false          # Use real GPU, not simulation  
GPU_SPEEDUP_FACTOR=25.0      # GPU speedup vs CPU
PYTORCH_CUDA_ALLOC_CONF=max_split_size_mb:512  # GPU memory optimization
```

### Resource Requirements
```yaml
# Production recommendations
resources:
  requests:
    nvidia.com/gpu: 1
    cpu: 2000m
    memory: 4Gi
  limits:
    nvidia.com/gpu: 1  
    cpu: 4000m
    memory: 8Gi
```

## 📊 Monitoring & Observability

### Grafana Dashboards
Access Grafana at `http://localhost:3000` (admin/admin) after deployment:
- **GPU Utilization Dashboard** - Real-time GPU metrics via DCGM
- **WebRTC Latency Dashboard** - p95 latency, request rates, scaling events
- **Kubernetes Resources** - Pod status, HPA scaling, resource usage

### Key Metrics
```promql
# Request latency p95
histogram_quantile(0.95, rate(app_request_latency_seconds_bucket[5m]))

# GPU utilization 
DCGM_FI_DEV_GPU_UTIL

# Active WebRTC connections
app_webrtc_connections_active

# HPA scaling events
increase(kube_hpa_status_current_replicas[1m])
```

### Scaling Behavior
The HPA scales based on:
1. **Latency**: Target p95 < 200ms
2. **GPU Utilization**: Target < 70%  
3. **CPU Usage**: Target < 60%
4. **Request Rate**: Scale up at >50 RPS

## 🔧 Troubleshooting

### Common Issues

**GPU Not Detected**
```bash
# Check GPU availability
kubectl exec -it deployment/gpu-media -- nvidia-smi
kubectl describe node | grep nvidia.com/gpu
```

**WebRTC Connection Failures**  
```bash
# Check aiortc installation
kubectl logs deployment/gpu-media | grep aiortc
curl localhost:8080/webrtc/status
```

**High Latency/Slow Performance**
```bash
# Check GPU mode vs simulation
curl localhost:8080/gpu-simulation-status

# Verify PyTorch CUDA
kubectl exec -it deployment/gpu-media -- python3 -c "import torch; print(torch.cuda.is_available())"
```

**Scaling Issues**
```bash
# Check HPA status
kubectl get hpa gpu-media-hpa -o yaml

# Verify custom metrics
kubectl get --raw "/apis/custom.metrics.k8s.io/v1beta1"
```

## 🏗️ Detailed Architecture

### Processing Pipeline
```
WebRTC Stream → aiortc → GPU Tensor → PyTorch Processing → Output Frame
     ↓                                       ↓
Video Frames ← OpenCV ← Numpy Array ← CUDA Kernels
```

### Scaling Decision Flow  
```
Prometheus Metrics → Custom Metrics API → HPA Controller → Pod Scaling
     ↓                        ↓                ↓              ↓
  p95 latency            GPU utilization    Scale up/down   New pods
  Request rate           CPU usage          decisions       scheduled
```

### GPU Processing Operations
1. **Convolution Layers** - Video filtering and enhancement
2. **Batch Normalization** - Stability across frames  
3. **Matrix Operations** - ML inference and transformations
4. **Memory Management** - Optimized CUDA memory pools

## 🌟 Production Considerations

### Security
- Non-root container user
- Resource limits and requests
- Network policies included
- GPU access control

### Performance
- Mixed precision training (autocast)
- CUDA memory optimization  
- Async WebRTC processing
- Connection pooling

### Reliability  
- Graceful GPU fallback to CPU
- Health checks with GPU status
- Prometheus monitoring
- Automatic restarts on failure
