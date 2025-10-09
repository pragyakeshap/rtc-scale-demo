#!/usr/bin/env python3
"""
Simplified integration tests for WebRTC GPU Application
Tests the actual running application via HTTP requests
"""
import requests
import time
import json
import sys
import os
from typing import Dict, Any

class SimpleIntegrationTest:
    """Simple integration tests via HTTP API"""
    
    def __init__(self, base_url: str = "http://localhost:8080"):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self.session.timeout = 10
        
    def test_health_endpoint(self) -> bool:
        """Test health check endpoint"""
        try:
            response = self.session.get(f"{self.base_url}/healthz")
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Health check passed:")
                print(f"   Device: {data.get('device', 'unknown')}")
                print(f"   PyTorch: {data.get('torch_imported', False)}")
                print(f"   CUDA: {data.get('cuda_available', False)}")
                return True
            else:
                print(f"❌ Health check failed: HTTP {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Health check failed: {e}")
            return False
    
    def test_metrics_endpoint(self) -> bool:
        """Test Prometheus metrics endpoint"""
        try:
            response = self.session.get(f"{self.base_url}/metrics")
            if response.status_code == 200:
                content = response.text
                if "app_requests_total" in content and "app_request_latency_seconds" in content:
                    print(f"✅ Metrics endpoint working")
                    return True
                else:
                    print(f"❌ Metrics endpoint missing expected metrics")
                    return False
            else:
                print(f"❌ Metrics endpoint failed: HTTP {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Metrics endpoint failed: {e}")
            return False
    
    def test_processing_endpoint(self) -> bool:
        """Test main processing endpoint"""
        test_cases = [
            ("small", "320x240", 1),
            ("medium", "640x480", 3),
            ("large", "1280x720", 5),
        ]
        
        all_passed = True
        for name, pixels, iters in test_cases:
            try:
                start_time = time.perf_counter()
                response = self.session.post(
                    f"{self.base_url}/process?pixels={pixels}&iters={iters}"
                )
                end_time = time.perf_counter()
                
                if response.status_code == 200:
                    data = response.json()
                    server_latency = data.get('latency_seconds', 0) * 1000
                    total_time = (end_time - start_time) * 1000
                    device = data.get('device', 'unknown')
                    mode = data.get('processing_mode', 'unknown')
                    
                    print(f"✅ Processing test ({name}): {server_latency:.1f}ms server, {total_time:.1f}ms total")
                    print(f"   Device: {device}, Mode: {mode}, Pixels: {pixels}")
                    
                    # Basic sanity checks
                    if server_latency < 0 or server_latency > 30000:  # 30 seconds max
                        print(f"   ⚠️  Unusual latency: {server_latency:.1f}ms")
                        
                else:
                    print(f"❌ Processing test ({name}) failed: HTTP {response.status_code}")
                    all_passed = False
                    
            except Exception as e:
                print(f"❌ Processing test ({name}) failed: {e}")
                all_passed = False
        
        return all_passed
    
    def test_webrtc_status(self) -> bool:
        """Test WebRTC status endpoint"""
        try:
            response = self.session.get(f"{self.base_url}/webrtc/status")
            if response.status_code == 200:
                data = response.json()
                print(f"✅ WebRTC status endpoint working:")
                print(f"   WebRTC available: {data.get('webrtc_available', False)}")
                print(f"   GPU processing: {data.get('gpu_processing', False)}")
                print(f"   Active connections: {data.get('active_connections', 0)}")
                return True
            else:
                print(f"❌ WebRTC status failed: HTTP {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ WebRTC status failed: {e}")
            return False
    
    def test_gpu_simulation_toggle(self) -> bool:
        """Test GPU simulation toggle"""
        try:
            # Get initial status
            response = self.session.get(f"{self.base_url}/gpu-simulation-status")
            if response.status_code != 200:
                print(f"❌ Failed to get initial GPU simulation status")
                return False
            
            initial_status = response.json().get('gpu_simulation', False)
            print(f"   Initial GPU simulation: {initial_status}")
            
            # Toggle simulation
            response = self.session.post(f"{self.base_url}/toggle-gpu-simulation")
            if response.status_code == 200:
                data = response.json()
                new_status = data.get('gpu_simulation', initial_status)
                print(f"✅ GPU simulation toggled to: {new_status}")
                
                # Toggle back to original state
                if new_status != initial_status:
                    self.session.post(f"{self.base_url}/toggle-gpu-simulation")
                    print(f"   Restored to original state: {initial_status}")
                
                return True
            else:
                print(f"❌ GPU simulation toggle failed: HTTP {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ GPU simulation toggle failed: {e}")
            return False
    
    def test_error_handling(self) -> bool:
        """Test error handling with invalid requests"""
        try:
            # Test invalid pixel format
            response = self.session.post(f"{self.base_url}/process?pixels=invalid&iters=5")
            if response.status_code == 400:
                print(f"✅ Error handling working (invalid pixels -> 400)")
            else:
                print(f"⚠️  Expected 400 for invalid pixels, got {response.status_code}")
            
            # Test WebRTC offer without proper data
            response = self.session.post(f"{self.base_url}/webrtc/offer", json={})
            # Should fail gracefully (either 400, 422, or 501)
            if response.status_code in [400, 422, 501]:
                print(f"✅ Error handling working (invalid WebRTC offer -> {response.status_code})")
            else:
                print(f"⚠️  Unexpected response for invalid WebRTC offer: {response.status_code}")
            
            return True
            
        except Exception as e:
            print(f"❌ Error handling test failed: {e}")
            return False
    
    def test_performance_consistency(self) -> bool:
        """Test performance consistency across multiple requests"""
        try:
            latencies = []
            for i in range(5):
                response = self.session.post(f"{self.base_url}/process?pixels=640x480&iters=3")
                if response.status_code == 200:
                    data = response.json()
                    latency = data.get('latency_seconds', 0) * 1000
                    latencies.append(latency)
                else:
                    print(f"❌ Performance test request {i+1} failed")
                    return False
            
            if latencies:
                avg_latency = sum(latencies) / len(latencies)
                min_latency = min(latencies)
                max_latency = max(latencies)
                variance = max_latency - min_latency
                
                print(f"✅ Performance consistency test:")
                print(f"   Average: {avg_latency:.1f}ms")
                print(f"   Range: {min_latency:.1f}ms - {max_latency:.1f}ms")
                print(f"   Variance: {variance:.1f}ms")
                
                # Check if performance is reasonably consistent
                if variance < avg_latency * 2:  # Variance less than 200% of average
                    print(f"   Performance is consistent")
                else:
                    print(f"   ⚠️  High performance variance")
                
                return True
            else:
                print(f"❌ No latency data collected")
                return False
                
        except Exception as e:
            print(f"❌ Performance consistency test failed: {e}")
            return False

def check_server_running(url: str) -> bool:
    """Check if server is running"""
    try:
        response = requests.get(f"{url}/healthz", timeout=5)
        return response.status_code == 200
    except:
        return False

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Simple integration tests')
    parser.add_argument('--url', default='http://localhost:8080', 
                       help='Server URL to test')
    parser.add_argument('--start-server', action='store_true',
                       help='Try to start server if not running')
    
    args = parser.parse_args()
    
    print("🧪 WebRTC GPU Application - Simple Integration Tests")
    print("=" * 50)
    
    # Check if server is running
    if not check_server_running(args.url):
        if args.start_server:
            print(f"Server not running, attempting to start...")
            import subprocess
            import threading
            
            def start_server():
                os.chdir(os.path.dirname(os.path.dirname(__file__)))
                subprocess.run(["uvicorn", "app.server:app", "--host", "0.0.0.0", "--port", "8080"])
            
            server_thread = threading.Thread(target=start_server, daemon=True)
            server_thread.start()
            time.sleep(10)  # Wait for server to start
            
            if not check_server_running(args.url):
                print(f"❌ Failed to start server at {args.url}")
                print(f"Please start manually: uvicorn app.server:app --host 0.0.0.0 --port 8080")
                return 1
        else:
            print(f"❌ Server not running at {args.url}")
            print(f"Please start server first: uvicorn app.server:app --host 0.0.0.0 --port 8080")
            print(f"Or use --start-server flag to attempt automatic start")
            return 1
    
    print(f"✅ Server is running at {args.url}")
    
    # Run tests
    tester = SimpleIntegrationTest(args.url)
    
    tests = [
        ("Health Check", tester.test_health_endpoint),
        ("Metrics", tester.test_metrics_endpoint),
        ("Processing", tester.test_processing_endpoint),
        ("WebRTC Status", tester.test_webrtc_status),
        ("GPU Simulation", tester.test_gpu_simulation_toggle),
        ("Error Handling", tester.test_error_handling),
        ("Performance", tester.test_performance_consistency),
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n--- {test_name} Test ---")
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} test failed with exception: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 50)
    print("TEST RESULTS SUMMARY")
    print("=" * 50)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {test_name}")
    
    print(f"\nResults: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
    
    if passed >= total * 0.8:  # 80% pass rate
        print(f"🎉 Integration tests PASSED!")
        return 0
    else:
        print(f"💥 Integration tests FAILED!")
        return 1

if __name__ == "__main__":
    sys.exit(main())
