# Production Deployment Guide

This comprehensive guide covers deploying the WebRTC GPU Application in production environments with best practices for reliability, security, and scalability.

## 🚀 Quick Deployment Options

### Option 1: Automated GKE Deployment (Recommended)
```bash
export PROJECT_ID="your-gcp-project"
./scripts/deploy.sh $PROJECT_ID
```

### Option 2: Manual Step-by-Step Deployment
```bash
# 1. Create GKE cluster with GPU pool
./scripts/gke_create_gpu_pool.sh

# 2. Build and push container
./scripts/build_and_push.sh

# 3. Deploy Kubernetes resources
kubectl apply -f k8s/

# 4. Install monitoring stack
./scripts/install_monitoring.sh
```

### Option 3: Local Development
```bash
./setup_dev.sh
uvicorn app.server:app --host 0.0.0.0 --port 8080
```

## 🏗️ Infrastructure Requirements

### Minimum Requirements
- **CPU**: 2 vCPUs per instance
- **Memory**: 4GB RAM per instance
- **GPU**: NVIDIA T4 or equivalent (optional but recommended)
- **Network**: 1Gbps bandwidth
- **Storage**: 10GB persistent storage

### Recommended Production Setup
- **CPU**: 4 vCPUs per instance
- **Memory**: 8GB RAM per instance
- **GPU**: NVIDIA V100 or A100
- **Network**: 10Gbps bandwidth
- **Storage**: 50GB SSD persistent storage
- **Replicas**: 3-10 instances (based on load)

## ☁️ Cloud Provider Configurations

### Google Cloud Platform (GKE)
```yaml
# Cluster configuration
cluster:
  name: rtc-gpu-cluster
  zone: us-central1-a
  nodePool:
    machineType: n1-standard-4
    acceleratorType: nvidia-tesla-t4
    acceleratorCount: 1
    diskSize: 50GB
    diskType: pd-ssd
```

### Amazon EKS
```yaml
# EKS nodegroup configuration
nodeGroup:
  instanceType: p3.2xlarge
  amiType: AL2_x86_64_GPU
  scalingConfig:
    minSize: 2
    maxSize: 10
    desiredSize: 3
```

### Microsoft AKS
```yaml
# AKS node pool configuration
agentPool:
  vmSize: Standard_NC6s_v3
  osType: Linux
  mode: User
  nodeCount: 3
  maxCount: 10
```

## 🔧 Configuration Management

### Environment Variables
```bash
# Production environment variables
export CUDA_WANTED=true
export GPU_SIMULATION=false
export GPU_SPEEDUP_FACTOR=25.0
export PYTORCH_CUDA_ALLOC_CONF=max_split_size_mb:512
export PROMETHEUS_MULTIPROC_DIR=/tmp/prometheus_multiproc
export LOG_LEVEL=INFO
export WORKERS=1
```

### Kubernetes ConfigMap
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: gpu-app-config
  namespace: rtc
data:
  CUDA_WANTED: "true"
  GPU_SIMULATION: "false"
  LOG_LEVEL: "INFO"
  PROMETHEUS_MULTIPROC_DIR: "/tmp/prometheus_multiproc"
```

### Secrets Management
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: gpu-app-secrets
  namespace: rtc
type: Opaque
data:
  api-key: <base64-encoded-api-key>
  database-url: <base64-encoded-db-url>
```

## 📊 Monitoring & Observability

### Prometheus Configuration
```yaml
# prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
- job_name: 'gpu-application'
  static_configs:
  - targets: ['gpu-media:8080']
  metrics_path: /metrics
  scrape_interval: 5s
```

### Grafana Dashboards
1. **GPU Utilization Dashboard**
   - GPU memory usage
   - GPU temperature
   - CUDA operations/second
   - Power consumption

2. **Application Performance Dashboard**
   - Request latency (p50, p95, p99)
   - Throughput (RPS)
   - Error rates
   - WebRTC connection status

3. **Kubernetes Resources Dashboard**
   - Pod CPU/Memory usage
   - HPA scaling events
   - Node resource utilization
   - Persistent volume usage

### Alerting Rules
```yaml
# alerting.yml
groups:
- name: gpu-application
  rules:
  - alert: HighLatency
    expr: histogram_quantile(0.95, rate(app_request_latency_seconds_bucket[5m])) > 0.2
    for: 2m
    labels:
      severity: warning
    annotations:
      summary: "High request latency detected"

  - alert: GPUUtilizationHigh
    expr: DCGM_FI_DEV_GPU_UTIL > 90
    for: 5m
    labels:
      severity: critical
    annotations:
      summary: "GPU utilization critically high"
```

## 🔄 CI/CD Pipeline

### GitHub Actions Workflow
```yaml
name: Production Deployment
on:
  push:
    branches: [main]
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4
    - name: Build and Deploy
      run: |
        gcloud auth configure-docker
        docker build -t gcr.io/$PROJECT_ID/gpu-app:$GITHUB_SHA .
        docker push gcr.io/$PROJECT_ID/gpu-app:$GITHUB_SHA
        kubectl set image deployment/gpu-media gpu-media=gcr.io/$PROJECT_ID/gpu-app:$GITHUB_SHA
```

### GitLab CI/CD
```yaml
# .gitlab-ci.yml
stages:
  - build
  - test
  - deploy

build:
  stage: build
  script:
    - docker build -t $CI_REGISTRY_IMAGE:$CI_COMMIT_SHA .
    - docker push $CI_REGISTRY_IMAGE:$CI_COMMIT_SHA

deploy:
  stage: deploy
  script:
    - kubectl set image deployment/gpu-media gpu-media=$CI_REGISTRY_IMAGE:$CI_COMMIT_SHA
  only:
    - main
```

## 🛡️ Security Hardening

### Container Security
```yaml
# Security context
securityContext:
  runAsNonRoot: true
  runAsUser: 1000
  runAsGroup: 1000
  fsGroup: 1000
  readOnlyRootFilesystem: true
  allowPrivilegeEscalation: false
  capabilities:
    drop:
      - ALL
```

### Network Policies
```yaml
# Network policy for production
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: gpu-app-netpol
spec:
  podSelector:
    matchLabels:
      app: gpu-media
  policyTypes:
  - Ingress
  - Egress
  ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          name: monitoring
    - namespaceSelector:
        matchLabels:
          name: ingress-nginx
    ports:
    - protocol: TCP
      port: 8080
```

## 📈 Scaling Configuration

### Horizontal Pod Autoscaler
```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: gpu-media-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: gpu-media
  minReplicas: 3
  maxReplicas: 20
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 60
  - type: Pods
    pods:
      metric:
        name: app_latency_p95_seconds
      target:
        type: AverageValue
        averageValue: "0.2"
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

### Cluster Autoscaler
```yaml
# Cluster autoscaler for GPU nodes
apiVersion: v1
kind: ConfigMap
metadata:
  name: cluster-autoscaler-status
  namespace: kube-system
data:
  nodes.max: "50"
  nodes.min: "3"
  scale-down-delay-after-add: "10m"
  scale-down-unneeded-time: "10m"
```

## 🔍 Troubleshooting Guide

### Common Issues

**GPU Not Available**
```bash
# Check GPU nodes
kubectl get nodes -l accelerator=nvidia-tesla-t4

# Check GPU resources
kubectl describe node <gpu-node-name>

# Verify NVIDIA drivers
kubectl exec -it <pod-name> -- nvidia-smi
```

**High Memory Usage**
```bash
# Check memory usage
kubectl top pods -n rtc

# Analyze memory leaks
kubectl exec -it <pod-name> -- python3 -m memory_profiler server.py
```

**WebRTC Connection Issues**
```bash
# Check WebRTC status
curl http://localhost:8080/webrtc/status

# Verify STUN/TURN configuration
kubectl logs <pod-name> | grep WebRTC
```

### Performance Optimization
```bash
# GPU memory optimization
export PYTORCH_CUDA_ALLOC_CONF=max_split_size_mb:512

# CPU optimization
export OMP_NUM_THREADS=4
export MKL_NUM_THREADS=4

# Network optimization
echo 'net.core.rmem_max = 16777216' >> /etc/sysctl.conf
echo 'net.core.wmem_max = 16777216' >> /etc/sysctl.conf
```

## 📋 Production Checklist

### Pre-deployment
- [ ] GPU drivers installed and verified
- [ ] Container security scan passed
- [ ] Resource limits configured
- [ ] Monitoring and alerting configured
- [ ] Backup and recovery procedures tested
- [ ] Load testing completed
- [ ] Security audit passed

### Post-deployment
- [ ] Health checks passing
- [ ] Metrics collection working
- [ ] Auto-scaling functioning
- [ ] Alerts configured and tested
- [ ] Documentation updated
- [ ] Team training completed
- [ ] Incident response procedures verified

### Regular Maintenance
- [ ] Weekly security updates
- [ ] Monthly performance reviews
- [ ] Quarterly capacity planning
- [ ] Semi-annual disaster recovery testing
- [ ] Annual security audits
