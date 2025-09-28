# 🎤 Live Demo Script: WebRTC Scaling with Kubernetes

## Pre-Demo Setup Checklist
- [ ] GKE cluster with GPU node pool running
- [ ] Prometheus and Grafana installed and accessible  
- [ ] Application deployed and healthy
- [ ] Grafana dashboard imported
- [ ] Load generation script ready

## Demo Flow (15-20 minutes)

### 1. Introduction (2 minutes)
**"Today I'll show you how to make WebRTC applications scale reliably in production using cloud-native patterns."**

**Show the architecture:**
```bash
# Quick health check
kubectl -n rtc get pods
kubectl -n rtc get svc
```

**Explain the service:**
- Simulates real-time video processing (background blur, translation, etc.)
- GPU-accelerated with PyTorch
- Exposes Prometheus metrics for observability

### 2. Baseline State (3 minutes)
**"Let's start with our baseline - a single replica handling minimal load."**

```bash
# Show current state
kubectl -n rtc get hpa
kubectl -n rtc get pods
```

**Open Grafana dashboard and explain key metrics:**
- Request latency (p95)
- Request rate
- Pod count
- GPU utilization (if available)

**Make a few test requests:**
```bash
SVC_IP=$(kubectl -n rtc get svc gpu-media -o jsonpath='{.spec.clusterIP}')
curl -s "http://${SVC_IP}/process?pixels=1280x720&iters=5" | jq
```

### 3. Load Generation & Scaling Demo (8 minutes)
**"Now let's simulate a traffic spike and watch Kubernetes automatically scale our service."**

**Start monitoring (in separate terminals):**
```bash
# Terminal 1: Watch HPA
kubectl -n rtc get hpa -w

# Terminal 2: Watch pods
kubectl -n rtc get pods -w
```

**Generate heavy load:**
```bash
# Start with moderate load
bash scripts/load_gen.sh "http://${SVC_IP}/process?pixels=1920x1080&iters=10" 20 300

# Increase to heavy load
bash scripts/load_gen.sh "http://${SVC_IP}/process?pixels=1920x1080&iters=15" 40 600
```

**Narrate while watching Grafana:**
- "Notice how latency is increasing..."
- "HPA detects the latency breach..."
- "New pods are being scheduled..."
- "GPU resources are being allocated..."
- "Latency comes back down as load distributes..."

### 4. Scaling Policies Deep Dive (4 minutes)
**"Let's look at what makes this scaling intelligent."**

**Show the HPA configuration:**
```bash
kubectl -n rtc describe hpa gpu-media-latency
```

**Explain the scaling logic:**
- Target: p95 latency < 100ms
- Scale up: When latency exceeds target for 30s
- Scale down: Gradual scale-down to prevent thrashing
- Max replicas: Bounded to control costs

**Show metrics being used:**
```bash
# For KEDA version
kubectl get scaledobject -n rtc

# For Prometheus Adapter version  
kubectl get --raw "/apis/custom.metrics.k8s.io/v1beta1/namespaces/rtc/pods/*/app_latency_p95_seconds"
```

### 5. Production Considerations (3 minutes)
**"In production, you'd also want these additional safeguards..."**

**Show security policies:**
```bash
# Network policies
cat k8s/policy/networkpolicy.yaml

# Gatekeeper constraints
cat k8s/policy/gatekeeper-sample-constraint.yaml
```

**Highlight key production features:**
- Non-root container execution
- Resource limits and requests
- Network isolation
- Image security scanning
- Multi-zone deployment (in real clusters)

### 6. Wrap-up (2 minutes)
**"Let's watch the system scale back down as load decreases."**

```bash
# Stop load generation (Ctrl+C the load scripts)
# Watch scale-down
kubectl -n rtc get hpa -w
```

**Key takeaways:**
- WebRTC workloads can be containerized and scaled like any cloud-native app
- Custom metrics (latency) provide better scaling signals than just CPU
- Kubernetes + Prometheus + GPU scheduling = production-ready WebRTC
- Observable, scalable, and resilient real-time media processing

## Quick Recovery Commands
If something goes wrong during demo:

```bash
# Reset deployment
kubectl -n rtc rollout restart deployment/gpu-media

# Check logs
kubectl -n rtc logs -l app=gpu-media --tail=50

# Verify metrics endpoint
kubectl -n rtc port-forward svc/gpu-media 8080:80
curl localhost:8080/metrics
```

## Demo URLs to Bookmark
- Grafana Dashboard: `http://grafana-url/d/webrtc-scaling`
- Prometheus: `http://prometheus-url`
- Application metrics: `http://service-ip/metrics`
