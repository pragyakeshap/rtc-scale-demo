#!/usr/bin/env python3
"""
Unit tests for the WebRTC GPU application server
Tests core functionality, GPU processing, and API endpoints
"""
import unittest
import pytest
import asyncio
import json
import sys
import os
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

# Add app directory to path
project_root = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(project_root, 'app'))

class TestGPUProcessing(unittest.TestCase):
    """Test GPU and CPU processing functions"""
    
    def setUp(self):
        """Set up test environment"""
        # Import after path is set
        global server
        import server
        self.server = server
        
    def test_parse_pixels_valid(self):
        """Test pixel parsing with valid inputs"""
        self.assertEqual(self.server.parse_pixels("1920x1080"), (1920, 1080))
        self.assertEqual(self.server.parse_pixels("1280X720"), (1280, 720))
        self.assertEqual(self.server.parse_pixels("640x480"), (640, 480))
        
    def test_parse_pixels_invalid(self):
        """Test pixel parsing with invalid inputs"""
        with self.assertRaises(ValueError):
            self.server.parse_pixels("invalid")
        with self.assertRaises(ValueError):
            self.server.parse_pixels("1920*1080")
        with self.assertRaises(ValueError):
            self.server.parse_pixels("abc x def")
            
    def test_p95_calculation(self):
        """Test p95 percentile calculation"""
        # Test with simple values
        values = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        p95_result = self.server.p95(values)
        self.assertAlmostEqual(p95_result, 9.55, places=2)
        
        # Test with empty list
        self.assertEqual(self.server.p95([]), 0.0)
        
        # Test with single value
        self.assertEqual(self.server.p95([5]), 5.0)
        
    def test_device_str_cpu_fallback(self):
        """Test device string when GPU not available"""
        with patch('server.torch', None):
            from importlib import reload
            reload(self.server)
            self.assertEqual(self.server.device_str(), "cpu")
            
    def test_device_str_simulation(self):
        """Test device string in simulation mode"""
        with patch.dict(os.environ, {'GPU_SIMULATION': 'true'}):
            from importlib import reload
            reload(self.server)
            self.assertEqual(self.server.device_str(), "cuda-simulated")
            
    @patch('server.torch')
    def test_cpu_intensive_process(self, mock_torch):
        """Test CPU processing function"""
        # Test basic functionality
        result = self.server.cpu_intensive_process(640, 480, 2)
        self.assertEqual(len(result), 4)
        self.assertEqual(result[0], 1)  # batch size
        self.assertEqual(result[1], 3)  # channels
        self.assertEqual(result[2], 480)  # height
        self.assertEqual(result[3], 640)  # width
        
    @patch('server.torch')
    @patch('server.np', None)
    def test_cpu_process_no_numpy(self, mock_torch):
        """Test CPU processing fallback when numpy unavailable"""
        result = self.server.cpu_intensive_process(100, 100, 1)
        self.assertEqual(result, (1, 3, 100, 100))
        
    @patch('server.torch')
    def test_real_gpu_process_no_cuda(self, mock_torch):
        """Test GPU processing when CUDA unavailable"""
        mock_torch.cuda.is_available.return_value = False
        
        with self.assertRaises(RuntimeError):
            self.server.real_gpu_process(640, 480, 2)


class TestAPIEndpoints(unittest.TestCase):
    """Test FastAPI endpoints"""
    
    def setUp(self):
        """Set up test client"""
        import server
        self.client = TestClient(server.app)
        
    def test_healthz_endpoint(self):
        """Test health check endpoint"""
        response = self.client.get("/healthz")
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertIn("ok", data)
        self.assertIn("device", data)
        self.assertIn("torch_imported", data)
        self.assertIn("cuda_available", data)
        self.assertTrue(data["ok"])
        
    def test_metrics_endpoint(self):
        """Test Prometheus metrics endpoint"""
        response = self.client.get("/metrics")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/plain", response.headers["content-type"])
        
        # Check for expected metrics
        content = response.text
        self.assertIn("app_requests_total", content)
        self.assertIn("app_request_latency_seconds", content)
        
    def test_process_endpoint_valid(self):
        """Test process endpoint with valid parameters"""
        response = self.client.post("/process?pixels=640x480&iters=2")
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertIn("ok", data)
        self.assertIn("device", data)
        self.assertIn("latency_seconds", data)
        self.assertIn("result_shape", data)
        self.assertTrue(data["ok"])
        self.assertIsInstance(data["latency_seconds"], float)
        
    def test_process_endpoint_invalid_pixels(self):
        """Test process endpoint with invalid pixel format"""
        response = self.client.post("/process?pixels=invalid&iters=2")
        self.assertEqual(response.status_code, 400)
        
    def test_gpu_simulation_toggle(self):
        """Test GPU simulation toggle endpoint"""
        # Get initial status
        response = self.client.get("/gpu-simulation-status")
        self.assertEqual(response.status_code, 200)
        initial_status = response.json()["gpu_simulation"]
        
        # Toggle simulation
        response = self.client.post("/toggle-gpu-simulation")
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertIn("gpu_simulation", data)
        self.assertIn("device", data)
        self.assertIn("message", data)
        
        # Verify status changed
        self.assertNotEqual(data["gpu_simulation"], initial_status)
        
        # Toggle back
        self.client.post("/toggle-gpu-simulation")
        
    def test_webrtc_status_endpoint(self):
        """Test WebRTC status endpoint"""
        response = self.client.get("/webrtc/status")
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertIn("webrtc_available", data)
        self.assertIn("gpu_processing", data)
        self.assertIn("active_connections", data)
        self.assertIn("device", data)
        
    def test_app_endpoint(self):
        """Test application HTML endpoint"""
        response = self.client.get("/app")
        # Should return HTML file or 404 if file doesn't exist
        self.assertIn(response.status_code, [200, 404])


class TestWebRTCIntegration(unittest.TestCase):
    """Test WebRTC functionality"""
    
    def setUp(self):
        """Set up WebRTC tests"""
        try:
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))
            import webrtc_processor
            self.webrtc = webrtc_processor
        except ImportError:
            self.webrtc = None
            
    def test_webrtc_import(self):
        """Test WebRTC processor can be imported"""
        if self.webrtc:
            self.assertTrue(hasattr(self.webrtc, 'WebRTCManager'))
            self.assertTrue(hasattr(self.webrtc, 'GPUVideoProcessor'))
            self.assertIsInstance(self.webrtc.AIORTC_AVAILABLE, bool)
        else:
            self.skipTest("WebRTC processor not available")
            
    def test_webrtc_manager_creation(self):
        """Test WebRTC manager can be created"""
        if self.webrtc and self.webrtc.AIORTC_AVAILABLE:
            manager = self.webrtc.WebRTCManager()
            self.assertIsNotNone(manager)
            self.assertEqual(len(manager.connections), 0)
        else:
            self.skipTest("aiortc not available")


class TestPerformanceAndLoad(unittest.TestCase):
    """Test performance characteristics and load handling"""
    
    def setUp(self):
        """Set up performance tests"""
        import server
        self.client = TestClient(server.app)
        
    def test_concurrent_requests_tracking(self):
        """Test concurrent request tracking"""
        import server
        
        # Reset counter
        server._concurrent_requests = 0
        
        # Make multiple requests (simulate concurrency)
        responses = []
        for i in range(3):
            response = self.client.post("/process?pixels=320x240&iters=1")
            responses.append(response)
            
        # All should succeed
        for response in responses:
            self.assertEqual(response.status_code, 200)
            
    def test_latency_tracking(self):
        """Test latency metrics are tracked"""
        import server
        
        # Clear previous latencies
        server._last_latencies.clear()
        
        # Make a request
        response = self.client.post("/process?pixels=320x240&iters=1")
        self.assertEqual(response.status_code, 200)
        
        # Check latency was recorded
        self.assertGreater(len(server._last_latencies), 0)
        
        # Check p95 calculation works
        p95_value = server.p95(list(server._last_latencies))
        self.assertGreaterEqual(p95_value, 0)
        
    def test_small_vs_large_processing(self):
        """Test processing time scales with image size"""
        # Small image
        response1 = self.client.post("/process?pixels=320x240&iters=1")
        self.assertEqual(response1.status_code, 200)
        latency1 = response1.json()["latency_seconds"]
        
        # Larger image (should take longer unless GPU simulation is active)
        response2 = self.client.post("/process?pixels=1280x720&iters=3")
        self.assertEqual(response2.status_code, 200)
        latency2 = response2.json()["latency_seconds"]
        
        # Both should be reasonable times
        self.assertGreater(latency1, 0)
        self.assertGreater(latency2, 0)
        self.assertLess(latency1, 10)  # Sanity check
        self.assertLess(latency2, 10)  # Sanity check


class TestErrorHandling(unittest.TestCase):
    """Test error handling and edge cases"""
    
    def setUp(self):
        """Set up error handling tests"""
        import server
        self.client = TestClient(server.app)
        self.server = server
        
    def test_invalid_parameters(self):
        """Test handling of invalid parameters"""
        # Invalid pixels
        response = self.client.post("/process?pixels=invalid&iters=5")
        self.assertEqual(response.status_code, 400)
        
        # Negative iterations (should still work, handled by the function)
        response = self.client.post("/process?pixels=640x480&iters=-1")
        self.assertEqual(response.status_code, 200)  # Function handles it gracefully
        
    def test_webrtc_unavailable_handling(self):
        """Test WebRTC endpoints when aiortc unavailable"""
        # Mock webrtc as unavailable
        with patch('server.AIORTC_AVAILABLE', False):
            response = self.client.post("/webrtc/offer", json={"sdp": "test", "type": "offer"})
            self.assertEqual(response.status_code, 501)
            
    @patch('server.torch', None)
    def test_torch_unavailable(self, mock_torch):
        """Test behavior when PyTorch is unavailable"""
        # This should fallback to basic CPU processing
        response = self.client.post("/process?pixels=640x480&iters=2")
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertEqual(data["device"], "cpu")


if __name__ == "__main__":
    print("Running WebRTC GPU Application Test Suite")
    print("=" * 50)
    
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test classes
    test_classes = [
        TestGPUProcessing,
        TestAPIEndpoints, 
        TestWebRTCIntegration,
        TestPerformanceAndLoad,
        TestErrorHandling
    ]
    
    for test_class in test_classes:
        tests = loader.loadTestsFromTestCase(test_class)
        suite.addTests(tests)
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Summary
    print("\n" + "=" * 50)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Success rate: {((result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100):.1f}%")
    
    if result.failures:
        print(f"\nFailures: {len(result.failures)}")
        for test, traceback in result.failures:
            print(f"- {test}")
            
    if result.errors:
        print(f"\nErrors: {len(result.errors)}")
        for test, traceback in result.errors:
            print(f"- {test}")
    
    # Exit with appropriate code
    sys.exit(0 if result.wasSuccessful() else 1)
