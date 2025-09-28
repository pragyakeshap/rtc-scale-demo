# WebRTC Scaling Demo: Cloud-Native Real-Time Media Processing

> **Demo Overview**: This repository demonstrates how to scale WebRTC applications reliably using Docker and Kubernetes with GPU acceleration. We'll show a containerized media service that simulates real-time video effects (like background blur or translation), while Kubernetes handles GPU scheduling and autoscaling using Prometheus and Grafana dashboards to maintain p95 latency within target SLOs.

## 🎯 What This Demo Shows

- **WebRTC Media Processing**: Containerized service simulating real-time video effects
- **GPU Acceleration**: CUDA-enabled processing with CPU fallback
- **Kubernetes Autoscaling**: HPA based on CPU utilization and custom latency metrics
- **Observability**: Real-time monitoring with Prometheus metrics and Grafana dashboards
- **Production Resilience**: How cloud-native patterns make WebRTC workloads scalable and resilient

## 🏗️ Architecture

This demo includes:
- **FastAPI + PyTorch** media service with GPU acceleration
- **Prometheus metrics** for monitoring request latency and throughput
- **Kubernetes manifests** for deployment and autoscaling
- **KEDA or Prometheus Adapter** for latency-based scaling
- **Load generation scripts** to demonstrate scaling behavior
- **Grafana dashboards** for real-time visualization

## Quickstart

### Local (CPU)
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r app/requirements.txt
pip install --no-cache-dir --extra-index-url https://download.pytorch.org/whl/cpu torch==2.3.1
uvicorn app.server:app --host 0.0.0.0 --port 8080
curl -s localhost:8080/healthz
bash scripts/load_gen.sh "http://localhost:8080/process?pixels=1280x720&iters=5" 20 200
```

### Build & Push
```bash
export REGISTRY=gcr.io/YOUR_PROJECT
export IMAGE=gpu-media
export TAG=v1
bash scripts/build_and_push.sh
```

### Cluster (GKE example) & GPU pool
```bash
bash scripts/gke_create_gpu_pool.sh
kubectl apply -f k8s/namespace.yaml
```

### Deploy app & service
```bash
kubectl -n rtc apply -f k8s/gpu-media-deployment.yaml
kubectl -n rtc apply -f k8s/gpu-media-service.yaml
```

### CPU-based HPA (simple fallback)
```bash
kubectl -n rtc apply -f k8s/hpa-cpu.yaml
```

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

### Presentation-Ready Demo
For live presentations, use the enhanced demo script:
```bash
# Start with baseline load
./scripts/demo_load_gen.sh baseline

# Moderate load to trigger scaling
./scripts/demo_load_gen.sh moderate  

# Heavy load for dramatic scaling demo
./scripts/demo_load_gen.sh heavy
```

## 🎤 Presentation Materials

This repository includes presentation-ready materials:

- **[📋 DEMO_SCRIPT.md](DEMO_SCRIPT.md)** - Complete step-by-step demo script with timing and talking points
- **[🏗️ ARCHITECTURE.md](ARCHITECTURE.md)** - Visual architecture diagrams and system overview  
- **[🎯 scripts/demo_load_gen.sh](scripts/demo_load_gen.sh)** - Enhanced load generator with colored output and scenarios

## Security Notes
- Use a private registry (sample Gatekeeper constraint provided).
- Apply NetworkPolicies to restrict access.
- Run as non-root (Dockerfile).
- Keep CUDA & PyTorch versions aligned for GPU.
