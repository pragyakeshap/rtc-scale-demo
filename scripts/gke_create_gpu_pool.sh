#!/usr/bin/env bash
# Enhanced script to create production-ready GKE cluster with GPU support for WebRTC application
# Requires: gcloud auth, a project set, and APIs enabled

set -euo pipefail

PROJECT_ID=${1:-"your-project-id"}
CLUSTER="${CLUSTER:-rtc-gpu-cluster}"
REGION="${REGION:-us-central1}"
ZONE="${ZONE:-us-central1-a}"
POOL="${POOL:-gpu-pool}"
ACCEL="${ACCEL:-nvidia-tesla-t4}"
COUNT="${COUNT:-0}"  # Start with 0 for autoscaling

echo "Creating production-ready GKE cluster with GPU support..."

# Create regional cluster for high availability
gcloud container clusters create "${CLUSTER}" \
  --project="$PROJECT_ID" \
  --region="$REGION" \
  --machine-type=e2-standard-4 \
  --num-nodes=2 \
  --enable-autoscaling \
  --min-nodes=2 \
  --max-nodes=10 \
  --enable-network-policy \
  --enable-ip-alias \
  --enable-autorepair \
  --enable-autoupgrade \
  --disk-size=50GB \
  --disk-type=pd-ssd \
  --node-labels=workload-type=cpu \
  --enable-shielded-nodes \
  --enable-monitoring \
  --enable-logging \
  --logging=SYSTEM,WORKLOAD,API_SERVER \
  --monitoring=SYSTEM,WORKLOAD

echo "Adding GPU node pool..."
# Add GPU node pool with preemptible instances for cost optimization
gcloud container node-pools create "${POOL}" \
  --cluster="${CLUSTER}" \
  --region="$REGION" \
  --machine-type=n1-standard-4 \
  --accelerator="type=${ACCEL},count=1" \
  --num-nodes="$COUNT" \
  --enable-autoscaling \
  --min-nodes=0 \
  --max-nodes=5 \
  --disk-size=100GB \
  --disk-type=pd-ssd \
  --preemptible \
  --node-labels=workload-type=gpu,accelerator="$ACCEL",nvidia.com/gpu.present=true \
  --node-taints=nvidia.com/gpu=present:NoSchedule \
  --enable-autorepair \
  --enable-autoupgrade

echo "Getting cluster credentials..."
gcloud container clusters get-credentials "${CLUSTER}" --region="$REGION" --project="$PROJECT_ID"

echo "Installing NVIDIA GPU drivers..."
kubectl apply -f https://raw.githubusercontent.com/GoogleCloudPlatform/container-engine-accelerators/master/nvidia-driver-installer/cos/daemonset-preloaded-latest.yaml

echo "Installing NVIDIA device plugin..."
kubectl apply -f https://raw.githubusercontent.com/NVIDIA/k8s-device-plugin/v0.15.0/nvidia-device-plugin.yml

echo "Installing DCGM GPU metrics exporter..."
kubectl apply -f - <<EOF
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: dcgm-exporter
  namespace: kube-system
  labels:
    app: dcgm-exporter
spec:
  selector:
    matchLabels:
      app: dcgm-exporter
  template:
    metadata:
      labels:
        app: dcgm-exporter
    spec:
      nodeSelector:
        accelerator: $ACCEL
      tolerations:
      - key: nvidia.com/gpu
        operator: Exists
        effect: NoSchedule
      containers:
      - name: dcgm-exporter
        image: nvidia/dcgm-exporter:3.1.8-3.1.5-ubuntu20.04
        ports:
        - containerPort: 9400
          name: metrics
        securityContext:
          runAsNonRoot: false
          runAsUser: 0
        volumeMounts:
        - name: proc
          mountPath: /host/proc
          readOnly: true
        - name: sys
          mountPath: /host/sys
          readOnly: true
      volumes:
      - name: proc
        hostPath:
          path: /proc
      - name: sys
        hostPath:
          path: /sys
      hostNetwork: true
      hostPID: true
EOF

echo "Creating namespace for our application..."
kubectl create namespace rtc || echo "Namespace rtc already exists"

echo "GPU cluster setup complete!"
echo ""
echo "Next steps:"
echo "1. Build and push your container: docker build -t gcr.io/$PROJECT_ID/gpu-media:v2 ."
echo "2. Push to registry: docker push gcr.io/$PROJECT_ID/gpu-media:v2"
echo "3. Deploy monitoring: kubectl apply -f k8s/prometheus-config.yaml -f k8s/prometheus-deployment.yaml -f k8s/grafana-deployment.yaml"
echo "4. Deploy the application: kubectl apply -f k8s/gpu-media-deployment.yaml -f k8s/gpu-media-service.yaml -f k8s/hpa-latency-custom.yaml"
echo "5. Monitor with: kubectl get pods -n rtc -w"
echo ""
echo "Access services:"
echo "- Grafana: kubectl port-forward -n rtc svc/grafana 3000:3000"
echo "- Prometheus: kubectl port-forward -n rtc svc/prometheus 9090:9090"
echo "- App: kubectl port-forward -n rtc svc/gpu-media 8080:8080"
