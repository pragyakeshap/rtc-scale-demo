#!/usr/bin/env bash
# Test runner script for WebRTC GPU Application
set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log() {
    echo -e "${GREEN}[$(date +'%H:%M:%S')] $1${NC}"
}

warn() {
    echo -e "${YELLOW}[$(date +'%H:%M:%S')] WARNING: $1${NC}"
}

error() {
    echo -e "${RED}[$(date +'%H:%M:%S')] ERROR: $1${NC}"
}

info() {
    echo -e "${BLUE}[$(date +'%H:%M:%S')] INFO: $1${NC}"
}

# Configuration
TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$TEST_DIR")"
SERVER_URL="${SERVER_URL:-http://localhost:8080}"
NAMESPACE="${NAMESPACE:-rtc}"

# Test types
RUN_UNIT_TESTS="${RUN_UNIT_TESTS:-true}"
RUN_LOAD_TESTS="${RUN_LOAD_TESTS:-false}"
RUN_K8S_TESTS="${RUN_K8S_TESTS:-false}"
RUN_INTEGRATION_TESTS="${RUN_INTEGRATION_TESTS:-true}"

# Load test parameters
LOAD_TEST_REQUESTS="${LOAD_TEST_REQUESTS:-50}"
LOAD_TEST_CONCURRENCY="${LOAD_TEST_CONCURRENCY:-10}"

usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --unit           Run unit tests only"
    echo "  --load           Run load tests only" 
    echo "  --k8s            Run Kubernetes integration tests only"
    echo "  --integration    Run integration tests only"
    echo "  --all            Run all tests (default)"
    echo "  --server-url URL Server URL for testing (default: http://localhost:8080)"
    echo "  --namespace NS   Kubernetes namespace (default: rtc)"
    echo "  --help           Show this help"
    echo ""
    echo "Environment variables:"
    echo "  LOAD_TEST_REQUESTS    Number of requests for load test (default: 50)"
    echo "  LOAD_TEST_CONCURRENCY Concurrency for load test (default: 10)"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --unit)
            RUN_UNIT_TESTS=true
            RUN_LOAD_TESTS=false
            RUN_K8S_TESTS=false
            RUN_INTEGRATION_TESTS=false
            shift
            ;;
        --load)
            RUN_UNIT_TESTS=false
            RUN_LOAD_TESTS=true
            RUN_K8S_TESTS=false
            RUN_INTEGRATION_TESTS=false
            shift
            ;;
        --k8s)
            RUN_UNIT_TESTS=false
            RUN_LOAD_TESTS=false
            RUN_K8S_TESTS=true
            RUN_INTEGRATION_TESTS=false
            shift
            ;;
        --integration)
            RUN_UNIT_TESTS=false
            RUN_LOAD_TESTS=false
            RUN_K8S_TESTS=false
            RUN_INTEGRATION_TESTS=true
            shift
            ;;
        --all)
            RUN_UNIT_TESTS=true
            RUN_LOAD_TESTS=true
            RUN_K8S_TESTS=true
            RUN_INTEGRATION_TESTS=true
            shift
            ;;
        --server-url)
            SERVER_URL="$2"
            shift 2
            ;;
        --namespace)
            NAMESPACE="$2"
            shift 2
            ;;
        --help)
            usage
            exit 0
            ;;
        *)
            error "Unknown option: $1"
            usage
            exit 1
            ;;
    esac
done

# Check if we're in the right directory
if [ ! -f "$PROJECT_ROOT/app/server.py" ]; then
    error "Please run this script from the project root or tests directory"
    exit 1
fi

log "Starting WebRTC GPU Application Test Suite"
log "===================================="
info "Test directory: $TEST_DIR"
info "Project root: $PROJECT_ROOT"
info "Server URL: $SERVER_URL"
info "Kubernetes namespace: $NAMESPACE"

# Check if Python virtual environment exists
if [ ! -d "$PROJECT_ROOT/venv" ]; then
    warn "Python virtual environment not found. Run setup_dev.sh first."
fi

# Install test dependencies if needed
if [ -f "$TEST_DIR/requirements.txt" ]; then
    log "Installing test dependencies..."
    pip install -r "$TEST_DIR/requirements.txt" || warn "Failed to install test dependencies"
fi

# Track test results
UNIT_TEST_RESULT=0
LOAD_TEST_RESULT=0
K8S_TEST_RESULT=0
INTEGRATION_TEST_RESULT=0

# Run unit tests
if [ "$RUN_UNIT_TESTS" = "true" ]; then
    log "Running Unit Tests"
    echo "==================="
    cd "$PROJECT_ROOT"
    
    if python3 "$TEST_DIR/test_server.py"; then
        log "✅ Unit tests PASSED"
        UNIT_TEST_RESULT=1
    else
        error "❌ Unit tests FAILED"
    fi
    echo ""
fi

# Run integration tests
if [ "$RUN_INTEGRATION_TESTS" = "true" ]; then
    log "Running Integration Tests"
    echo "=========================="
    cd "$PROJECT_ROOT"
    
    if python3 test_integration.py; then
        log "✅ Integration tests PASSED"
        INTEGRATION_TEST_RESULT=1
    else
        error "❌ Integration tests FAILED"
    fi
    echo ""
fi

# Run load tests
if [ "$RUN_LOAD_TESTS" = "true" ]; then
    log "Running Load Tests"
    echo "=================="
    
    # Check if server is running
    if curl -s "$SERVER_URL/healthz" > /dev/null 2>&1; then
        log "Server is running, starting load tests..."
        
        cd "$PROJECT_ROOT"
        if python3 "$TEST_DIR/test_load.py" \
            --url "$SERVER_URL" \
            --requests "$LOAD_TEST_REQUESTS" \
            --concurrency "$LOAD_TEST_CONCURRENCY" \
            --comparison; then
            log "✅ Load tests PASSED"
            LOAD_TEST_RESULT=1
        else
            error "❌ Load tests FAILED"
        fi
    else
        warn "Server not running at $SERVER_URL, skipping load tests"
        warn "Start server with: uvicorn app.server:app --host 0.0.0.0 --port 8080"
    fi
    echo ""
fi

# Run Kubernetes tests
if [ "$RUN_K8S_TESTS" = "true" ]; then
    log "Running Kubernetes Integration Tests"
    echo "===================================="
    
    # Check if kubectl is available
    if command -v kubectl >/dev/null 2>&1; then
        # Check if namespace exists
        if kubectl get namespace "$NAMESPACE" >/dev/null 2>&1; then
            log "Kubernetes cluster and namespace available, running tests..."
            
            if python3 "$TEST_DIR/test_k8s.py" --namespace "$NAMESPACE"; then
                log "✅ Kubernetes tests PASSED"
                K8S_TEST_RESULT=1
            else
                error "❌ Kubernetes tests FAILED"
            fi
        else
            warn "Namespace '$NAMESPACE' not found, skipping Kubernetes tests"
            warn "Deploy first with: bash scripts/deploy.sh your-project-id"
        fi
    else
        warn "kubectl not found, skipping Kubernetes tests"
    fi
    echo ""
fi

# Summary
log "Test Results Summary"
echo "===================="

TOTAL_SUITES=0
PASSED_SUITES=0

if [ "$RUN_UNIT_TESTS" = "true" ]; then
    TOTAL_SUITES=$((TOTAL_SUITES + 1))
    if [ $UNIT_TEST_RESULT -eq 1 ]; then
        echo "✅ Unit Tests: PASSED"
        PASSED_SUITES=$((PASSED_SUITES + 1))
    else
        echo "❌ Unit Tests: FAILED"
    fi
fi

if [ "$RUN_INTEGRATION_TESTS" = "true" ]; then
    TOTAL_SUITES=$((TOTAL_SUITES + 1))
    if [ $INTEGRATION_TEST_RESULT -eq 1 ]; then
        echo "✅ Integration Tests: PASSED"
        PASSED_SUITES=$((PASSED_SUITES + 1))
    else
        echo "❌ Integration Tests: FAILED"
    fi
fi

if [ "$RUN_LOAD_TESTS" = "true" ]; then
    TOTAL_SUITES=$((TOTAL_SUITES + 1))
    if [ $LOAD_TEST_RESULT -eq 1 ]; then
        echo "✅ Load Tests: PASSED"
        PASSED_SUITES=$((PASSED_SUITES + 1))
    else
        echo "❌ Load Tests: FAILED/SKIPPED"
    fi
fi

if [ "$RUN_K8S_TESTS" = "true" ]; then
    TOTAL_SUITES=$((TOTAL_SUITES + 1))
    if [ $K8S_TEST_RESULT -eq 1 ]; then
        echo "✅ Kubernetes Tests: PASSED"
        PASSED_SUITES=$((PASSED_SUITES + 1))
    else
        echo "❌ Kubernetes Tests: FAILED/SKIPPED"
    fi
fi

echo ""
if [ $TOTAL_SUITES -eq 0 ]; then
    warn "No tests were run"
    exit 1
elif [ $PASSED_SUITES -eq $TOTAL_SUITES ]; then
    log "🎉 All test suites PASSED ($PASSED_SUITES/$TOTAL_SUITES)"
    exit 0
else
    error "💥 Some test suites FAILED ($PASSED_SUITES/$TOTAL_SUITES passed)"
    exit 1
fi
