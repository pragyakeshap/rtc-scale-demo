# Performance Optimization Guide

This guide covers performance optimization strategies for the WebRTC GPU application across different deployment scenarios.

## 🚀 Performance Overview

### Key Performance Metrics
- **Processing Latency**: <20ms GPU, <200ms CPU (p95)
- **Throughput**: 1000+ requests/second per GPU
- **Concurrent Users**: 100+ simultaneous connections
- **Memory Usage**: <4GB per instance
- **GPU Utilization**: 60-80% optimal range

## ⚡ GPU Optimization

### CUDA Configuration
```bash
# Environment variables for optimal GPU performance
export CUDA_LAUNCH_BLOCKING=0
export PYTORCH_CUDA_ALLOC_CONF=max_split_size_mb:512
export CUDA_DEVICE_ORDER=PCI_BUS_ID
```

### Memory Management
```python
# Optimal PyTorch GPU settings
torch.backends.cudnn.benchmark = True
torch.backends.cudnn.deterministic = False
torch.cuda.empty_cache()  # Periodic cleanup
```

### GPU Workload Patterns
```yaml
# Optimal resource allocation
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

## 🔧 Application Optimization

### FastAPI Performance
```python
# Production ASGI server configuration
import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=8080,
        workers=1,  # Single worker for GPU sharing
        loop="uvloop",  # High-performance event loop
        http="httptools",  # Fast HTTP parser
        access_log=False,  # Disable in production
        server_header=False
    )
```

### Connection Pooling
```python
# Optimal aiohttp session configuration
connector = aiohttp.TCPConnector(
    limit=100,  # Total connection limit
    limit_per_host=30,  # Per-host connection limit
    ttl_dns_cache=300,  # DNS cache TTL
    use_dns_cache=True,
    keepalive_timeout=30
)
```

## 📊 Scaling Strategies

### Horizontal Pod Autoscaler (HPA)
```yaml
# Optimized HPA configuration
spec:
  minReplicas: 2
  maxReplicas: 10
  targetCPUUtilizationPercentage: 60
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 60
      policies:
      - type: Percent
        value: 100
        periodSeconds: 15
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
      - type: Percent
        value: 10
        periodSeconds: 60
```

### Vertical Pod Autoscaler (VPA)
```yaml
apiVersion: autoscaling.k8s.io/v1
kind: VerticalPodAutoscaler
metadata:
  name: gpu-media-vpa
spec:
  targetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: gpu-media
  updatePolicy:
    updateMode: "Auto"
  resourcePolicy:
    containerPolicies:
    - containerName: gpu-media
      maxAllowed:
        cpu: 4
        memory: 8Gi
```

## 🌐 Network Optimization

### Load Balancing
```yaml
# NGINX Ingress optimizations
metadata:
  annotations:
    nginx.ingress.kubernetes.io/upstream-hash-by: "$request_uri"
    nginx.ingress.kubernetes.io/proxy-connect-timeout: "5"
    nginx.ingress.kubernetes.io/proxy-send-timeout: "300"
    nginx.ingress.kubernetes.io/proxy-read-timeout: "300"
    nginx.ingress.kubernetes.io/proxy-body-size: "10m"
```

### CDN Integration
```bash
# CloudFlare optimization
Cache-Control: public, max-age=300
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 1; mode=block
```

## 📈 Monitoring & Profiling

### GPU Metrics
```promql
# Key GPU performance queries
gpu_utilization = DCGM_FI_DEV_GPU_UTIL
gpu_memory_used = DCGM_FI_DEV_FB_USED / DCGM_FI_DEV_FB_TOTAL * 100
gpu_temperature = DCGM_FI_DEV_GPU_TEMP
gpu_power_usage = DCGM_FI_DEV_POWER_USAGE
```

### Application Metrics
```python
# Custom performance metrics
PROCESSING_TIME = Histogram(
    'gpu_processing_seconds',
    'Time spent in GPU processing',
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0)
)

CONCURRENT_PROCESSING = Gauge(
    'concurrent_gpu_operations',
    'Number of concurrent GPU operations'
)
```

## 🔬 Performance Testing

### Load Testing Scenarios
```bash
# Baseline performance test
python3 tests/test_load.py --requests 100 --concurrency 10

# Stress test
python3 tests/test_load.py --requests 1000 --concurrency 50

# Endurance test (30 minutes)
timeout 1800 python3 tests/test_load.py --requests 10000 --concurrency 20
```

### Profiling Tools
```bash
# GPU profiling with nvidia-smi
nvidia-smi dmon -s pucvmet -d 1

# PyTorch profiler
python3 -m torch.profiler profile_gpu_processing.py

# Memory profiling
python3 -m memory_profiler server.py
```

## 🎯 Environment-Specific Tuning

### Development
- Single GPU instance
- Debug logging enabled
- Smaller batch sizes
- Frequent garbage collection

### Staging
- Multi-GPU setup
- Production-like load patterns
- Performance regression testing
- Capacity planning validation

### Production
- Optimized GPU clusters
- Minimal logging overhead
- Tuned kernel parameters
- Advanced monitoring

## 📋 Performance Checklist

### Pre-deployment
- [ ] GPU drivers optimized
- [ ] CUDA toolkit updated
- [ ] Memory limits configured
- [ ] Network policies optimized
- [ ] Load testing completed

### Runtime Optimization
- [ ] HPA/VPA configured
- [ ] Resource utilization monitored
- [ ] Performance alerts active
- [ ] Bottlenecks identified
- [ ] Scaling validated

### Continuous Improvement
- [ ] Performance metrics tracked
- [ ] Optimization opportunities identified
- [ ] Regular performance reviews
- [ ] Capacity planning updated
- [ ] Team performance training
