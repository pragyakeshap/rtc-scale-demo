#!/usr/bin/env bash
# Enhanced load generation script for GPU scaling application
# Tests both CPU and GPU modes with realistic WebRTC workloads

set -euo pipefail

# Configuration
URL="${1:-http://localhost:8080}"
CONCURRENCY="${2:-20}"
DURATION="${3:-300}"  # 5 minutes default
RAMP_UP="${4:-30}"    # Ramp up time in seconds

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log() {
    echo -e "${GREEN}[$(date +'%H:%M:%S')] $1${NC}"
}

warn() {
    echo -e "${YELLOW}[$(date +'%H:%M:%S')] $1${NC}"
}

error() {
    echo -e "${RED}[$(date +'%H:%M:%S')] $1${NC}"
}

# Test different workload patterns
PIXEL_SIZES=("1280x720" "1920x1080" "2560x1440")
ITERATION_COUNTS=(5 10 15 20)

# Worker function for load generation
worker() {
    local worker_id=$1
    local requests_per_worker=0
    local worker_success=0
    local worker_failed=0
    local worker_latency=0
    
    while [ -f "/tmp/load_test_running" ]; do
        # Randomize workload parameters
        pixels=${PIXEL_SIZES[$((RANDOM % ${#PIXEL_SIZES[@]}))]}
        iters=${ITERATION_COUNTS[$((RANDOM % ${#ITERATION_COUNTS[@]}))]}
        
        # Measure request latency
        start_time=$(date +%s.%N)
        
        if response=$(curl -s -w "%{http_code}" -X POST "$URL/process?pixels=$pixels&iters=$iters" 2>/dev/null); then
            http_code="${response: -3}"
            if [ "$http_code" = "200" ]; then
                ((worker_success++))
            else
                ((worker_failed++))
            fi
        else
            ((worker_failed++))
        fi
        
        end_time=$(date +%s.%N)
        latency=$(echo "$end_time - $start_time" | bc -l 2>/dev/null || echo "0")
        worker_latency=$(echo "$worker_latency + $latency" | bc -l 2>/dev/null || echo "0")
        
        ((requests_per_worker++))
        
        # Variable sleep to simulate realistic usage patterns
        sleep_time=$(echo "scale=3; 0.05 + ($RANDOM % 100) / 10000" | bc -l 2>/dev/null || echo "0.1")
        sleep "$sleep_time"
    done
    
    # Write worker stats to temp files
    echo "$requests_per_worker" > "/tmp/worker_${worker_id}_requests"
    echo "$worker_success" > "/tmp/worker_${worker_id}_success"
    echo "$worker_failed" > "/tmp/worker_${worker_id}_failed"
    echo "$worker_latency" > "/tmp/worker_${worker_id}_latency"
}

# Statistics collection function
collect_stats() {
    while [ -f "/tmp/load_test_running" ]; do
        sleep 10
        
        # Collect current metrics from server
        if metrics=$(curl -s "$URL/healthz" 2>/dev/null); then
            if command -v jq >/dev/null 2>&1; then
                device=$(echo "$metrics" | jq -r '.device // "unknown"')
                log "Current mode: $device"
            fi
        fi
        
        # Show current load
        active_connections=$(ss -tn state established 2>/dev/null | grep -c ":8080" || echo "0")
        log "Active connections: $active_connections"
    done
}

# GPU mode testing function
test_gpu_mode() {
    log "Testing GPU mode performance..."
    
    # Enable GPU simulation
    curl -s -X POST "$URL/toggle-gpu-simulation" >/dev/null 2>&1 || warn "Could not toggle GPU mode"
    sleep 2
    
    # Run test for 1/3 of duration
    gpu_duration=$((DURATION / 3))
    log "Running GPU mode test for ${gpu_duration}s with $CONCURRENCY workers"
    
    touch "/tmp/load_test_running"
    
    # Start workers
    for i in $(seq 1 "$CONCURRENCY"); do
        worker "$i" &
    done
    
    # Run for specified duration
    sleep "$gpu_duration"
    
    # Stop workers
    rm -f "/tmp/load_test_running"
    wait
    
    log "GPU mode test completed"
}

# CPU mode testing function  
test_cpu_mode() {
    log "Testing CPU mode performance..."
    
    # Disable GPU simulation (switch to CPU)
    curl -s -X POST "$URL/toggle-gpu-simulation" >/dev/null 2>&1 || warn "Could not toggle CPU mode"
    sleep 2
    
    # Run test for 1/3 of duration
    cpu_duration=$((DURATION / 3))
    log "Running CPU mode test for ${cpu_duration}s with $CONCURRENCY workers"
    
    touch "/tmp/load_test_running"
    
    # Start workers  
    for i in $(seq 1 "$CONCURRENCY"); do
        worker "$i" &
    done
    
    # Run for specified duration
    sleep "$cpu_duration"
    
    # Stop workers
    rm -f "/tmp/load_test_running"
    wait
    
    log "CPU mode test completed"
}

# Scaling test function
test_scaling() {
    log "Testing auto-scaling behavior..."
    
    # Gradual ramp up
    scaling_duration=$((DURATION / 3))
    log "Running scaling test for ${scaling_duration}s"
    
    touch "/tmp/load_test_running"
    
    # Ramp up gradually
    for phase in $(seq 1 5); do
        current_workers=$((CONCURRENCY * phase / 5))
        log "Phase $phase: Starting $current_workers workers"
        
        for i in $(seq 1 "$current_workers"); do
            worker "scale_${phase}_${i}" &
        done
        
        sleep $((scaling_duration / 5))
        
        # Kill previous phase workers
        if [ $phase -gt 1 ]; then
            prev_phase=$((phase - 1))
            pkill -f "worker scale_${prev_phase}_" 2>/dev/null || true
        fi
    done
    
    # Stop all workers
    rm -f "/tmp/load_test_running"
    wait
    
    log "Scaling test completed"
}

# Cleanup function
cleanup() {
    log "Cleaning up load test..."
    rm -f /tmp/load_test_running
    rm -f /tmp/worker_*
    pkill -P $$ 2>/dev/null || true
}

# Set trap for cleanup
trap cleanup EXIT

# Main test execution
main() {
    log "Starting enhanced load testing for GPU scaling application"
    log "Target: $URL"
    log "Concurrency: $CONCURRENCY workers"
    log "Total Duration: ${DURATION}s"
    
    # Check if server is available
    if ! curl -s "$URL/healthz" >/dev/null 2>&1; then
        error "Server not available at $URL"
        exit 1
    fi
    
    # Start statistics collection in background
    collect_stats &
    STATS_PID=$!
    
    # Run comprehensive tests
    log "Phase 1: GPU Mode Performance Test"
    test_gpu_mode
    
    sleep 10  # Cool down between tests
    
    log "Phase 2: CPU Mode Performance Test"  
    test_cpu_mode
    
    sleep 10  # Cool down between tests
    
    log "Phase 3: Auto-scaling Test"
    test_scaling
    
    # Stop statistics collection
    kill $STATS_PID 2>/dev/null || true
    
    # Collect final statistics
    log "Collecting final statistics..."
    
    total_requests=0
    total_success=0
    total_failed=0
    
    for worker_file in /tmp/worker_*_requests; do
        [ -f "$worker_file" ] || continue
        worker_requests=$(cat "$worker_file" 2>/dev/null || echo "0")
        total_requests=$((total_requests + worker_requests))
    done
    
    for worker_file in /tmp/worker_*_success; do
        [ -f "$worker_file" ] || continue
        worker_success=$(cat "$worker_file" 2>/dev/null || echo "0")
        total_success=$((total_success + worker_success))
    done
    
    for worker_file in /tmp/worker_*_failed; do
        [ -f "$worker_file" ] || continue  
        worker_failed=$(cat "$worker_file" 2>/dev/null || echo "0")
        total_failed=$((total_failed + worker_failed))
    done
    
    # Calculate success rate
    if [ $total_requests -gt 0 ]; then
        success_rate=$(echo "scale=2; $total_success * 100 / $total_requests" | bc -l 2>/dev/null || echo "0")
    else
        success_rate=0
    fi
    
    log "📊 Load Test Results:"
    echo "   Total Requests: $total_requests"
    echo "   Successful: $total_success"
    echo "   Failed: $total_failed"
    echo "   Success Rate: ${success_rate}%"
    echo "   Average RPS: $(echo "scale=2; $total_requests / $DURATION" | bc -l 2>/dev/null || echo "0")"
    
    log "🎯 Check Kubernetes scaling:"
    echo "   kubectl get hpa -n rtc"
    echo "   kubectl get pods -n rtc"
    echo "   kubectl top pods -n rtc"
}

# Handle different test modes
case "${5:-full}" in
    "gpu")
        log "Running GPU-only test"
        collect_stats &
        STATS_PID=$!
        test_gpu_mode
        kill $STATS_PID 2>/dev/null || true
        ;;
    "cpu")
        log "Running CPU-only test"  
        collect_stats &
        STATS_PID=$!
        test_cpu_mode
        kill $STATS_PID 2>/dev/null || true
        ;;
    "scale")
        log "Running scaling test only"
        collect_stats &
        STATS_PID=$!
        test_scaling
        kill $STATS_PID 2>/dev/null || true
        ;;
    "full"|"")
        main
        ;;
    *)
        echo "Usage: $0 [URL] [CONCURRENCY] [DURATION] [RAMP_UP] [gpu|cpu|scale|full]"
        echo ""
        echo "Examples:"
        echo "  $0                                    # Full test with defaults"
        echo "  $0 http://localhost:8080 50 600      # 50 workers for 10 minutes"
        echo "  $0 http://localhost:8080 20 300 30 gpu # GPU test only"
        exit 1
        ;;
esac
