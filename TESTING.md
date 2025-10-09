# Testing Guide for WebRTC GPU Application

This guide covers all testing approaches for the WebRTC GPU scaling application, from unit tests to full Kubernetes integration tests.

## 🧪 Test Suite Overview

The testing framework includes:

1. **Unit Tests** - Test individual functions and components
2. **Integration Tests** - Test system components working together
3. **Load Tests** - Test performance under various load conditions  
4. **Kubernetes Tests** - Test deployment and scaling in K8s
5. **Simple API Tests** - Quick verification of running application

## 🚀 Quick Testing

### Fastest: Simple API Tests (Running Server Required)
```bash
# Start server first
uvicorn app.server:app --host 0.0.0.0 --port 8080

# In another terminal, run simple tests
python3 test_simple.py
```

### Basic: Integration Tests (No Server Required)
```bash
python3 test_integration.py
```

### Comprehensive: All Tests
```bash
./run_tests.sh --all
```

## 📋 Test Categories

### 1. Unit Tests (`tests/test_server.py`)
Tests individual functions in isolation:
- Pixel parsing validation
- P95 calculation accuracy
- Device detection logic
- CPU/GPU processing functions
- Error handling scenarios

**Run with:**
```bash
python3 tests/test_server.py
# or
./run_tests.sh --unit
```

**Requirements:**
- Python environment with dependencies
- No running server needed

### 2. Simple API Tests (`test_simple.py`)
Tests actual HTTP endpoints of running server:
- Health check functionality
- Processing endpoint performance
- WebRTC status and capabilities
- Error handling with invalid inputs
- Performance consistency across requests

**Run with:**
```bash  
python3 test_simple.py --url http://localhost:8080
# or with auto-start
python3 test_simple.py --start-server
```

**Requirements:**
- Running server at specified URL
- Network connectivity

### 3. Load Tests (`tests/test_load.py`)
Tests performance under concurrent load:
- Concurrent request handling
- Latency distribution analysis
- CPU vs GPU performance comparison
- Scaling behavior validation
- Error rate under load

**Run with:**
```bash
python3 tests/test_load.py --url http://localhost:8080 --requests 100 --concurrency 20
# or
./run_tests.sh --load
```

**Performance comparison:**
```bash
python3 tests/test_load.py --comparison
```

**Requirements:**
- Running server
- aiohttp library for async requests

### 4. Kubernetes Integration Tests (`tests/test_k8s.py`)
Tests Kubernetes deployment:
- Namespace and deployment status
- Service accessibility
- HPA configuration
- Pod health and GPU allocation
- Monitoring stack deployment
- Application health via port-forward

**Run with:**
```bash
python3 tests/test_k8s.py --namespace rtc
# or  
./run_tests.sh --k8s
```

**Requirements:**
- kubectl configured for target cluster
- Deployed application in Kubernetes
- Appropriate RBAC permissions

### 5. Integration Tests (`test_integration.py`)
Tests system without external dependencies:
- Module import verification
- Dependency availability checks
- Basic functionality without server
- WebRTC component availability

**Run with:**
```bash
python3 test_integration.py
```

**Requirements:**
- Python environment only
- No external services needed

## 🎯 Test Scenarios

### Development Testing
Quick feedback during development:
```bash
# Check basic functionality
python3 test_integration.py

# Test API while developing
python3 test_simple.py --start-server
```

### Pre-deployment Testing
Comprehensive testing before deployment:
```bash
# Run all local tests
./run_tests.sh --unit --integration --load

# Build and test container
docker build -t rtc-gpu-app .
docker run -d -p 8080:8080 rtc-gpu-app
python3 test_simple.py
```

### Production Validation
Test deployed system:
```bash
# Test Kubernetes deployment
./run_tests.sh --k8s --namespace production

# Load test production system
python3 tests/test_load.py --url https://your-domain.com --requests 500 --concurrency 50
```

### CI/CD Pipeline
Automated testing in CI:
```bash
# Fast tests for PR validation
./run_tests.sh --unit --integration

# Full suite for main branch
./run_tests.sh --all
```

## 📊 Performance Benchmarks

### Expected Latencies
- **CPU Mode**: 100-500ms for 1920x1080, 10 iterations
- **GPU Mode**: 5-20ms for same workload  
- **Simulation Mode**: 2-15ms (consistent timing)

### Performance Thresholds
- **P95 Latency Target**: <200ms
- **Success Rate Target**: >99%
- **Concurrent Request Handling**: Up to 100 concurrent
- **HPA Scaling Target**: Maintain <200ms p95 under any load

### Load Test Scenarios
```bash
# Light load (development)
python3 tests/test_load.py --requests 20 --concurrency 5

# Medium load (staging)  
python3 tests/test_load.py --requests 100 --concurrency 20

# Heavy load (production validation)
python3 tests/test_load.py --requests 500 --concurrency 50

# Stress test (capacity planning)
python3 tests/test_load.py --requests 1000 --concurrency 100
```

## 🔧 Troubleshooting Tests

### Import Errors
```bash
# Check Python path
export PYTHONPATH="${PYTHONPATH}:$(pwd)/app"

# Install missing dependencies
pip install -r app/requirements.txt
pip install -r tests/requirements.txt
```

### Server Connection Issues
```bash
# Check server status
curl -f http://localhost:8080/healthz

# Check firewall/networking
netstat -tulpn | grep 8080

# Check server logs
uvicorn app.server:app --log-level debug
```

### Kubernetes Test Failures
```bash
# Check cluster connectivity
kubectl cluster-info

# Check namespace
kubectl get ns rtc

# Check pod status
kubectl get pods -n rtc

# Check logs
kubectl logs -f deployment/gpu-media -n rtc
```

### Load Test Issues
```bash
# Reduce concurrency for debugging
python3 tests/test_load.py --requests 10 --concurrency 2

# Check server resources
top -p $(pgrep -f uvicorn)

# Monitor during test
watch 'curl -s localhost:8080/metrics | grep -E "(latency|requests)"'
```

## 📈 Test Reports

### Understanding Results

**Unit Test Results:**
- Function-level correctness
- Edge case handling
- Input validation

**Load Test Results:**
- Response time percentiles (P50, P95, P99)
- Request success rates
- Concurrent request handling
- Device utilization (CPU vs GPU)

**Kubernetes Test Results:**
- Deployment health
- Resource allocation
- Scaling configuration
- Monitoring setup

### Performance Analysis
```bash
# Generate detailed load test report
python3 tests/test_load.py --comparison > load_test_report.txt

# Analyze Kubernetes metrics
kubectl top pods -n rtc
kubectl get hpa -n rtc

# Check Prometheus metrics
curl localhost:8080/metrics | grep -E "latency|requests|gpu"
```

## 🎉 Success Criteria

### Development Phase
- [x] All unit tests pass
- [x] Integration tests pass  
- [x] Basic API functionality works
- [x] CPU and GPU modes functional

### Staging Phase
- [x] Load tests meet performance targets
- [x] Error handling works correctly
- [x] Performance is consistent
- [x] Container builds and runs

### Production Phase
- [x] Kubernetes deployment healthy
- [x] HPA scaling functions correctly
- [x] Monitoring and alerting active
- [x] Production load tests pass

The test suite provides comprehensive coverage from development to production, ensuring the WebRTC GPU application performs reliably at scale.
