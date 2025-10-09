#!/usr/bin/env bash
# Production deployment script for GPU-accelerated WebRTC latency application
# This script deploys the complete stack with monitoring and auto-scaling

set -euo pipefail

# Configuration
PROJECT_ID="${1:-your-project-id}"
CLUSTER_NAME="${CLUSTER_NAME:-rtc-gpu-cluster}"
REGION="${REGION:-us-central1}"
IMAGE_TAG="${IMAGE_TAG:-v2}"
NAMESPACE="${NAMESPACE:-rtc}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

warn() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING: $1${NC}"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $1${NC}"
    exit 1
}

# Check prerequisites
check_prerequisites() {
    log "Checking prerequisites..."
    
    command -v gcloud >/dev/null 2>&1 || error "gcloud CLI not found"
    command -v kubectl >/dev/null 2>&1 || error "kubectl not found"
    command -v docker >/dev/null 2>&1 || error "docker not found"
    
    # Check if authenticated
    gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q . || error "Not authenticated with gcloud"
    
    # Check if project is set
    CURRENT_PROJECT=$(gcloud config get-value project 2>/dev/null || echo "")
    if [ "$CURRENT_PROJECT" != "$PROJECT_ID" ]; then
        warn "Setting project to $PROJECT_ID"
        gcloud config set project "$PROJECT_ID"
    fi
    
    log "Prerequisites check passed"
}

# Build and push container image
build_and_push() {
    log "Building and pushing container image..."
    
    IMAGE_URL="gcr.io/$PROJECT_ID/gpu-media:$IMAGE_TAG"
    
    # Configure Docker for GCR
    gcloud auth configure-docker gcr.io --quiet
    
    # Build image
    log "Building Docker image: $IMAGE_URL"
    docker build -t "$IMAGE_URL" .
    
    # Push image
    log "Pushing image to GCR..."
    docker push "$IMAGE_URL"
    
    log "Image pushed successfully: $IMAGE_URL"
}

# Create or update GKE cluster
setup_cluster() {
    log "Setting up GKE cluster..."
    
    # Check if cluster exists
    if gcloud container clusters describe "$CLUSTER_NAME" --region="$REGION" --project="$PROJECT_ID" >/dev/null 2>&1; then
        log "Cluster $CLUSTER_NAME already exists, updating..."
        # Get credentials
        gcloud container clusters get-credentials "$CLUSTER_NAME" --region="$REGION" --project="$PROJECT_ID"
    else
        log "Creating new cluster: $CLUSTER_NAME"
        ./scripts/gke_create_gpu_pool.sh "$PROJECT_ID"
    fi
    
    # Verify cluster is ready
    kubectl cluster-info >/dev/null || error "Cannot connect to cluster"
    log "Cluster setup complete"
}

# Deploy monitoring stack
deploy_monitoring() {
    log "Deploying monitoring stack..."
    
    # Create namespace if it doesn't exist
    kubectl create namespace "$NAMESPACE" --dry-run=client -o yaml | kubectl apply -f -
    
    # Deploy Prometheus
    log "Deploying Prometheus..."
    kubectl apply -f k8s/prometheus-config.yaml
    kubectl apply -f k8s/prometheus-deployment.yaml
    
    # Deploy Grafana
    log "Deploying Grafana..."
    kubectl apply -f k8s/grafana-deployment.yaml
    
    # Wait for monitoring to be ready
    log "Waiting for monitoring stack to be ready..."
    kubectl wait --for=condition=available --timeout=300s deployment/prometheus -n "$NAMESPACE"
    kubectl wait --for=condition=available --timeout=300s deployment/grafana -n "$NAMESPACE"
    
    log "Monitoring stack deployed successfully"
}

# Deploy application
deploy_app() {
    log "Deploying GPU media application..."
    
    # Update image in deployment
    IMAGE_URL="gcr.io/$PROJECT_ID/gpu-media:$IMAGE_TAG"
    sed -i.bak "s|gcr.io/YOUR_PROJECT/gpu-media:v2|$IMAGE_URL|g" k8s/gpu-media-deployment.yaml
    
    # Deploy application components
    kubectl apply -f k8s/gpu-media-deployment.yaml
    kubectl apply -f k8s/gpu-media-service.yaml
    
    # Wait for deployment to be ready
    log "Waiting for application to be ready..."
    kubectl wait --for=condition=available --timeout=600s deployment/gpu-media -n "$NAMESPACE"
    
    # Deploy HPA (after app is running)
    log "Deploying horizontal pod autoscaler..."
    kubectl apply -f k8s/hpa-latency-custom.yaml
    
    # Restore original deployment file
    mv k8s/gpu-media-deployment.yaml.bak k8s/gpu-media-deployment.yaml
    
    log "Application deployed successfully"
}

# Verify deployment
verify_deployment() {
    log "Verifying deployment..."
    
    # Check pod status
    kubectl get pods -n "$NAMESPACE" -l app=gpu-media
    
    # Check services
    kubectl get services -n "$NAMESPACE"
    
    # Check HPA
    kubectl get hpa -n "$NAMESPACE"
    
    # Test application health
    log "Testing application health..."
    kubectl port-forward -n "$NAMESPACE" svc/gpu-media 8080:8080 &
    PF_PID=$!
    sleep 5
    
    if curl -f http://localhost:8080/healthz >/dev/null 2>&1; then
        log "Health check passed"
    else
        warn "Health check failed"
    fi
    
    kill $PF_PID 2>/dev/null || true
    
    log "Deployment verification complete"
}

# Display access information
show_access_info() {
    log "Deployment complete! Access information:"
    echo ""
    echo "📊 Grafana Dashboard:"
    echo "   kubectl port-forward -n $NAMESPACE svc/grafana 3000:3000"
    echo "   Then visit: http://localhost:3000 (admin/admin123)"
    echo ""
    echo "📈 Prometheus:"
    echo "   kubectl port-forward -n $NAMESPACE svc/prometheus 9090:9090"
    echo "   Then visit: http://localhost:9090"
    echo ""
    echo "🚀 GPU Media App:"
    echo "   kubectl port-forward -n $NAMESPACE svc/gpu-media 8080:8080"
    echo "   Then visit: http://localhost:8080/app"
    echo ""
    echo "🔍 Monitor deployment:"
    echo "   kubectl get pods -n $NAMESPACE -w"
    echo "   kubectl logs -f deployment/gpu-media -n $NAMESPACE"
    echo ""
    echo "📊 Check HPA status:"
    echo "   kubectl get hpa -n $NAMESPACE"
    echo "   kubectl describe hpa gpu-media-hpa-advanced -n $NAMESPACE"
    echo ""
    echo "🎯 Load testing:"
    echo "   ./scripts/load_gen.sh"
    echo ""
}

# Cleanup function
cleanup() {
    log "Cleaning up port forwards..."
    pkill -f "kubectl port-forward" 2>/dev/null || true
}

# Set trap for cleanup
trap cleanup EXIT

# Main deployment flow
main() {
    log "Starting production deployment for GPU-accelerated WebRTC application"
    log "Project: $PROJECT_ID, Cluster: $CLUSTER_NAME, Region: $REGION"
    
    check_prerequisites
    build_and_push
    setup_cluster
    deploy_monitoring
    deploy_app
    verify_deployment
    show_access_info
    
    log "🎉 Production deployment completed successfully!"
}

# Handle command line arguments
case "${1:-deploy}" in
    "build")
        check_prerequisites
        build_and_push
        ;;
    "cluster")
        check_prerequisites
        setup_cluster
        ;;
    "monitoring")
        deploy_monitoring
        ;;
    "app")
        deploy_app
        ;;
    "verify")
        verify_deployment
        ;;
    "deploy"|"")
        main
        ;;
    *)
        echo "Usage: $0 [build|cluster|monitoring|app|verify|deploy]"
        echo ""
        echo "Commands:"
        echo "  build      - Build and push container image only"
        echo "  cluster    - Set up GKE cluster only"
        echo "  monitoring - Deploy monitoring stack only"
        echo "  app        - Deploy application only"
        echo "  verify     - Verify deployment only"
        echo "  deploy     - Full deployment (default)"
        exit 1
        ;;
esac
