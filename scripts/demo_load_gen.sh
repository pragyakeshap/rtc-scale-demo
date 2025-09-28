#!/usr/bin/env bash
set -euo pipefail

# Enhanced load generation for presentation demos
# Usage: ./demo_load_gen.sh [scenario] [service_ip]

SCENARIO="${1:-moderate}"
SERVICE_IP="${2:-$(kubectl -n rtc get svc gpu-media -o jsonpath='{.spec.clusterIP}' 2>/dev/null || echo 'localhost:8080')}"

# Color output for presentation
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${BLUE}[$(date +'%H:%M:%S')] $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Test connectivity first
print_status "Testing connectivity to $SERVICE_IP..."
if curl -s -f "http://$SERVICE_IP/healthz" > /dev/null; then
    print_success "Service is healthy and reachable"
else
    print_error "Cannot reach service at $SERVICE_IP"
    exit 1
fi

case $SCENARIO in
    "baseline")
        print_status "🔄 Running BASELINE load (low traffic)..."
        CONCURRENCY=5
        REQUESTS=50
        PIXELS="1280x720"
        ITERS=3
        DURATION=60
        ;;
    "moderate")
        print_status "🔄 Running MODERATE load (normal traffic spike)..."
        CONCURRENCY=20
        REQUESTS=200
        PIXELS="1920x1080"
        ITERS=8
        DURATION=120
        ;;
    "heavy")
        print_status "🔥 Running HEAVY load (stress test - will trigger scaling!)..."
        CONCURRENCY=50
        REQUESTS=500
        PIXELS="1920x1080"
        ITERS=15
        DURATION=300
        ;;
    "sustained")
        print_status "⏰ Running SUSTAINED load (long-term test)..."
        CONCURRENCY=30
        REQUESTS=1000
        PIXELS="1920x1080"
        ITERS=10
        DURATION=600
        ;;
    *)
        print_error "Unknown scenario: $SCENARIO"
        echo "Available scenarios: baseline, moderate, heavy, sustained"
        exit 1
        ;;
esac

URL="http://$SERVICE_IP/process?pixels=$PIXELS&iters=$ITERS"

print_status "Configuration:"
echo "  • Target: $URL"
echo "  • Concurrency: $CONCURRENCY parallel requests"
echo "  • Total requests: $REQUESTS"
echo "  • Video resolution: $PIXELS"
echo "  • Processing iterations: $ITERS"
echo "  • Expected duration: ~${DURATION}s"
echo ""

print_warning "Starting load generation in 3 seconds... (Press Ctrl+C to stop)"
sleep 3

print_status "🚀 Load generation starting now!"
echo "📊 Watch the metrics at:"
echo "   • kubectl -n rtc get hpa -w"
echo "   • kubectl -n rtc get pods -w"
echo "   • Your Grafana dashboard"
echo ""

START_TIME=$(date +%s)

# Run the load with progress indication
seq "${REQUESTS}" | xargs -n1 -P"${CONCURRENCY}" -I{} bash -c '
    # Use a temporary file to separate response body from curl metrics
    TEMP_FILE=$(mktemp)
    METRICS=$(curl -s -w "HTTPCODE:%{http_code}|TIME:%{time_total}" -X POST "'$URL'" -o "$TEMP_FILE" 2>/dev/null)
    
    HTTP_CODE=$(echo "$METRICS" | sed "s/.*HTTPCODE:\([0-9]*\).*/\1/")
    TIME_TOTAL=$(echo "$METRICS" | sed "s/.*TIME:\([0-9.]*\).*/\1/")
    
    rm -f "$TEMP_FILE"
    
    if [ "$HTTP_CODE" = "200" ]; then
        echo "✓ Request completed in ${TIME_TOTAL}s"
    else
        echo "✗ Request failed with HTTP status $HTTP_CODE"
    fi
' | while IFS= read -r line; do
    echo "$line"
    # Show progress every 10 requests
    if (( $(echo "$line" | grep -c "Request") % 10 == 0 )); then
        CURRENT_TIME=$(date +%s)
        ELAPSED=$((CURRENT_TIME - START_TIME))
        print_status "⏱️  ${ELAPSED}s elapsed..."
    fi
done

END_TIME=$(date +%s)
TOTAL_TIME=$((END_TIME - START_TIME))

print_success "Load generation completed!"
echo "📈 Summary:"
echo "  • Total time: ${TOTAL_TIME}s"
if [ "$TOTAL_TIME" -gt 0 ]; then
    echo "  • Average RPS: $((REQUESTS / TOTAL_TIME))"
else
    echo "  • Average RPS: Very fast (< 1 second total)"
fi
echo "  • Scenario: $SCENARIO"
echo ""
print_status "💡 Check your monitoring dashboards to see the scaling behavior!"
