#!/usr/bin/env bash
# Complete deployment script for GPU-accelerated WebRTC scaling application

set -euo pipefail

PROJECT_ID=${1:-""}
CLUSTER_NAME="rtc-gpu-cluster"
REGION="us-central1"

if [[ -z "$PROJECT_ID" ]]; then
    echo "Usage: $0 <project_id>"
    echo "Example: $0 my-gcp-project"
    exit 1
fi

echo "🚀 Deploying GPU-accelerated WebRTC scaling application to GCP project: $PROJECT_ID"
echo "=================================================="

# Phase 1: Infrastructure Setup
echo "📋 Phase 1: Setting up GKE cluster with GPU support..."
export PROJECT_ID CLUSTER=$CLUSTER_NAME REGION
./scripts/gke_create_gpu_pool.sh "$PROJECT_ID"

# Phase 2: Build and Push Container
echo "📋 Phase 2: Building and pushing container image..."
CONTAINER_IMAGE="gcr.io/$PROJECT_ID/gpu-media:v2"

echo "Building container image..."
docker build -t "$CONTAINER_IMAGE" .

echo "Pushing to Google Container Registry..."
docker push "$CONTAINER_IMAGE"

# Phase 3: Deploy Monitoring Stack  
echo "📋 Phase 3: Deploying monitoring infrastructure..."
kubectl apply -f k8s/prometheus-config.yaml
kubectl apply -f k8s/prometheus-deployment.yaml
kubectl apply -f k8s/grafana-deployment.yaml

# Wait for monitoring to be ready
echo "Waiting for monitoring stack to be ready..."
kubectl wait --for=condition=available --timeout=300s deployment/prometheus -n rtc
kubectl wait --for=condition=available --timeout=300s deployment/grafana -n rtc

# Phase 4: Deploy Application
echo "📋 Phase 4: Deploying GPU media processing application..."
# Update deployment image
sed "s|gcr.io/YOUR_PROJECT/gpu-media:v2|$CONTAINER_IMAGE|g" k8s/gpu-media-deployment.yaml | kubectl apply -f -
kubectl apply -f k8s/gpu-media-service.yaml

# Wait for application to be ready
echo "Waiting for application to be ready..."
kubectl wait --for=condition=available --timeout=300s deployment/gpu-media -n rtc

# Phase 5: Deploy Auto-scaling
echo "📋 Phase 5: Setting up GPU-based auto-scaling..."
kubectl apply -f k8s/hpa-latency-custom.yaml

# Phase 6: Setup Port Forwards for Access
echo "📋 Phase 6: Setting up access..."
echo "Setting up port forwards (running in background)..."

# Kill any existing port-forwards
pkill -f "kubectl port-forward" || true

# Start port forwards in background
kubectl port-forward -n rtc svc/grafana 3000:3000 &
GRAFANA_PID=$!
kubectl port-forward -n rtc svc/prometheus 9090:9090 &
PROMETHEUS_PID=$!
kubectl port-forward -n rtc svc/gpu-media 8080:8080 &
APP_PID=$!

# Store PIDs for cleanup
echo $GRAFANA_PID > /tmp/grafana.pid
echo $PROMETHEUS_PID > /tmp/prometheus.pid  
echo $APP_PID > /tmp/app.pid

sleep 5

# Phase 7: Verify Deployment
echo "📋 Phase 7: Verifying deployment..."
echo "Checking application health..."
if curl -f http://localhost:8080/healthz > /dev/null 2>&1; then
    echo "✅ Application is healthy"
else
    echo "❌ Application health check failed"
fi

echo "Checking HPA status..."
kubectl get hpa -n rtc

echo "Checking GPU nodes..."
kubectl get nodes -l accelerator=nvidia-tesla-t4

echo ""
echo "🎉 Deployment Complete!"
echo "=================================================="
echo ""
echo "🌐 Access URLs:"
echo "• Application:         http://localhost:8080/app"
echo "• Grafana Dashboard:   http://localhost:3000 (admin/admin123)"
echo "• Prometheus:          http://localhost:9090"
echo "• Application API:     http://localhost:8080"
echo ""
echo "📊 Key Endpoints:"
echo "• Health Check:        curl http://localhost:8080/healthz"
echo "• Metrics:             curl http://localhost:8080/metrics"
echo "• GPU Toggle:          curl -X POST http://localhost:8080/toggle-gpu-simulation"
echo "• Processing:          curl -X POST 'http://localhost:8080/process?pixels=1920x1080&iters=10'"
echo ""
echo "🎮 Testing Commands:"
echo "• Load Test:           ./scripts/load_gen.sh"
echo "• Watch Scaling:       watch kubectl get pods,hpa -n rtc"
echo "• Check GPU Usage:     kubectl top nodes"
echo ""
echo "🔧 Management:"
echo "• View Logs:           kubectl logs -f deployment/gpu-media -n rtc"
echo "• Scale Manually:      kubectl scale deployment gpu-media --replicas=5 -n rtc"
echo "• Stop Port Forwards:  kill \$(cat /tmp/*.pid); rm /tmp/*.pid"
echo ""
echo "⚠️  Note: Port forwards are running in background. To stop them:"
echo "   kill \$(cat /tmp/grafana.pid /tmp/prometheus.pid /tmp/app.pid) && rm /tmp/*.pid"
echo ""
echo "🚀 Ready for GPU-accelerated WebRTC scaling application!"
