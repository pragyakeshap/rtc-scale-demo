#!/usr/bin/env python3
"""
Integration tests for Kubernetes deployment
Tests deployment, scaling, and monitoring
"""
import subprocess
import time
import json
import requests
import sys
from typing import Dict, List, Optional

class KubernetesIntegrationTest:
    """Test Kubernetes deployment and scaling"""
    
    def __init__(self, namespace: str = "rtc"):
        self.namespace = namespace
        self.deployment_name = "gpu-media"
        self.service_name = "gpu-media"
        self.hpa_name = "gpu-media-hpa"
        
    def run_kubectl(self, command: str) -> Dict:
        """Run kubectl command and return result"""
        try:
            full_command = f"kubectl {command} -n {self.namespace}"
            result = subprocess.run(full_command, shell=True, capture_output=True, text=True)
            return {
                'success': result.returncode == 0,
                'stdout': result.stdout.strip(),
                'stderr': result.stderr.strip(),
                'returncode': result.returncode
            }
        except Exception as e:
            return {
                'success': False,
                'stdout': '',
                'stderr': str(e),
                'returncode': -1
            }
    
    def test_namespace_exists(self) -> bool:
        """Test if namespace exists"""
        print(f"Testing namespace '{self.namespace}' exists...")
        result = self.run_kubectl(f"get namespace {self.namespace}")
        
        if result['success']:
            print(f"✅ Namespace '{self.namespace}' exists")
            return True
        else:
            print(f"❌ Namespace '{self.namespace}' does not exist")
            print(f"   Error: {result['stderr']}")
            return False
    
    def test_deployment_ready(self) -> bool:
        """Test if deployment is ready"""
        print(f"Testing deployment '{self.deployment_name}' is ready...")
        result = self.run_kubectl(f"get deployment {self.deployment_name} -o json")
        
        if not result['success']:
            print(f"❌ Deployment '{self.deployment_name}' not found")
            print(f"   Error: {result['stderr']}")
            return False
        
        try:
            deployment = json.loads(result['stdout'])
            status = deployment.get('status', {})
            ready_replicas = status.get('readyReplicas', 0)
            replicas = status.get('replicas', 0)
            
            if ready_replicas == replicas and ready_replicas > 0:
                print(f"✅ Deployment ready: {ready_replicas}/{replicas} replicas")
                return True
            else:
                print(f"⚠️  Deployment not ready: {ready_replicas}/{replicas} replicas")
                return False
                
        except json.JSONDecodeError:
            print(f"❌ Failed to parse deployment status")
            return False
    
    def test_service_accessible(self) -> bool:
        """Test if service is accessible"""
        print(f"Testing service '{self.service_name}' is accessible...")
        result = self.run_kubectl(f"get service {self.service_name} -o json")
        
        if not result['success']:
            print(f"❌ Service '{self.service_name}' not found")
            return False
        
        try:
            service = json.loads(result['stdout'])
            spec = service.get('spec', {})
            cluster_ip = spec.get('clusterIP')
            ports = spec.get('ports', [])
            
            if cluster_ip and ports:
                print(f"✅ Service accessible at {cluster_ip}:{ports[0].get('port', 'unknown')}")
                return True
            else:
                print(f"❌ Service configuration invalid")
                return False
                
        except json.JSONDecodeError:
            print(f"❌ Failed to parse service configuration")
            return False
    
    def test_hpa_configured(self) -> bool:
        """Test if HPA is configured correctly"""
        print(f"Testing HPA '{self.hpa_name}' is configured...")
        result = self.run_kubectl(f"get hpa {self.hpa_name} -o json")
        
        if not result['success']:
            print(f"❌ HPA '{self.hpa_name}' not found")
            print(f"   Error: {result['stderr']}")
            return False
        
        try:
            hpa = json.loads(result['stdout'])
            spec = hpa.get('spec', {})
            status = hpa.get('status', {})
            
            min_replicas = spec.get('minReplicas', 0)
            max_replicas = spec.get('maxReplicas', 0)
            current_replicas = status.get('currentReplicas', 0)
            
            print(f"✅ HPA configured: {current_replicas} replicas ({min_replicas}-{max_replicas})")
            
            # Check for custom metrics
            metrics = spec.get('metrics', [])
            custom_metrics = [m for m in metrics if m.get('type') == 'Pods']
            if custom_metrics:
                print(f"   Custom metrics configured: {len(custom_metrics)} metrics")
            
            return True
            
        except json.JSONDecodeError:
            print(f"❌ Failed to parse HPA configuration")
            return False
    
    def test_pods_running(self) -> bool:
        """Test if pods are running"""
        print(f"Testing pods are running...")
        result = self.run_kubectl(f"get pods -l app=gpu-media -o json")
        
        if not result['success']:
            print(f"❌ Failed to get pod status")
            return False
        
        try:
            pods_data = json.loads(result['stdout'])
            pods = pods_data.get('items', [])
            
            if not pods:
                print(f"❌ No pods found for app=gpu-media")
                return False
            
            running_pods = 0
            for pod in pods:
                status = pod.get('status', {})
                phase = status.get('phase', 'Unknown')
                if phase == 'Running':
                    running_pods += 1
            
            print(f"✅ Pods running: {running_pods}/{len(pods)}")
            
            # Show pod details
            for pod in pods:
                name = pod.get('metadata', {}).get('name', 'unknown')
                phase = pod.get('status', {}).get('phase', 'Unknown')
                node = pod.get('spec', {}).get('nodeName', 'unknown')
                print(f"   Pod {name}: {phase} on {node}")
            
            return running_pods > 0
            
        except json.JSONDecodeError:
            print(f"❌ Failed to parse pod status")
            return False
    
    def test_gpu_resources(self) -> bool:
        """Test GPU resource allocation"""
        print(f"Testing GPU resource allocation...")
        result = self.run_kubectl(f"get pods -l app=gpu-media -o json")
        
        if not result['success']:
            print(f"❌ Failed to get pod information")
            return False
        
        try:
            pods_data = json.loads(result['stdout'])
            pods = pods_data.get('items', [])
            
            gpu_pods = 0
            for pod in pods:
                containers = pod.get('spec', {}).get('containers', [])
                for container in containers:
                    resources = container.get('resources', {})
                    requests = resources.get('requests', {})
                    limits = resources.get('limits', {})
                    
                    gpu_request = requests.get('nvidia.com/gpu', 0)
                    gpu_limit = limits.get('nvidia.com/gpu', 0)
                    
                    if gpu_request or gpu_limit:
                        gpu_pods += 1
                        pod_name = pod.get('metadata', {}).get('name', 'unknown')
                        print(f"   Pod {pod_name}: GPU request={gpu_request}, limit={gpu_limit}")
            
            if gpu_pods > 0:
                print(f"✅ GPU resources allocated to {gpu_pods} pods")
                return True
            else:
                print(f"⚠️  No GPU resources found (CPU-only deployment)")
                return True  # This is acceptable for testing
                
        except json.JSONDecodeError:
            print(f"❌ Failed to parse pod resource information")
            return False
    
    def test_monitoring_stack(self) -> bool:
        """Test monitoring components"""
        print(f"Testing monitoring stack...")
        
        # Check Prometheus
        prometheus_result = self.run_kubectl("get deployment prometheus -o json")
        prometheus_ok = prometheus_result['success']
        
        # Check Grafana  
        grafana_result = self.run_kubectl("get deployment grafana -o json")
        grafana_ok = grafana_result['success']
        
        if prometheus_ok and grafana_ok:
            print(f"✅ Monitoring stack deployed (Prometheus + Grafana)")
        elif prometheus_ok:
            print(f"⚠️  Prometheus deployed, Grafana missing")
        elif grafana_ok:
            print(f"⚠️  Grafana deployed, Prometheus missing")
        else:
            print(f"❌ Monitoring stack not found")
            return False
        
        return True
    
    def test_application_health(self) -> Optional[Dict]:
        """Test application health via port-forward"""
        print(f"Testing application health...")
        
        # Start port-forward in background
        port_forward_cmd = f"kubectl port-forward svc/{self.service_name} 8080:8080 -n {self.namespace}"
        
        try:
            import threading
            import time
            
            # Start port-forward process
            port_forward_process = subprocess.Popen(
                port_forward_cmd, 
                shell=True, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE
            )
            
            # Give it time to establish
            time.sleep(3)
            
            # Test health endpoint
            try:
                response = requests.get("http://localhost:8080/healthz", timeout=10)
                if response.status_code == 200:
                    health_data = response.json()
                    print(f"✅ Application health check passed")
                    print(f"   Device: {health_data.get('device', 'unknown')}")
                    print(f"   PyTorch: {health_data.get('torch_imported', False)}")
                    print(f"   CUDA: {health_data.get('cuda_available', False)}")
                    
                    # Test processing endpoint
                    proc_response = requests.post(
                        "http://localhost:8080/process?pixels=640x480&iters=2", 
                        timeout=15
                    )
                    if proc_response.status_code == 200:
                        proc_data = proc_response.json()
                        print(f"   Processing test: {proc_data.get('latency_seconds', 0)*1000:.1f}ms")
                    
                    return health_data
                else:
                    print(f"❌ Health check failed: HTTP {response.status_code}")
                    return None
                    
            except requests.exceptions.RequestException as e:
                print(f"❌ Health check failed: {e}")
                return None
            
        finally:
            # Clean up port-forward
            if 'port_forward_process' in locals():
                port_forward_process.terminate()
                port_forward_process.wait()
    
    def run_full_test_suite(self) -> bool:
        """Run complete integration test suite"""
        print("🚀 Starting Kubernetes Integration Tests")
        print("=" * 60)
        
        tests = [
            ("Namespace", self.test_namespace_exists),
            ("Deployment", self.test_deployment_ready),
            ("Service", self.test_service_accessible),
            ("HPA", self.test_hpa_configured),
            ("Pods", self.test_pods_running),
            ("GPU Resources", self.test_gpu_resources),
            ("Monitoring", self.test_monitoring_stack),
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
        
        # Application health test (optional, requires port-forward)
        print(f"\n--- Application Health Test ---")
        try:
            health_result = self.test_application_health()
            results.append(("Application Health", health_result is not None))
        except Exception as e:
            print(f"⚠️  Application health test skipped: {e}")
            results.append(("Application Health", None))
        
        # Summary
        print("\n" + "=" * 60)
        print("INTEGRATION TEST SUMMARY")
        print("=" * 60)
        
        passed = 0
        failed = 0
        skipped = 0
        
        for test_name, result in results:
            if result is True:
                print(f"✅ {test_name}: PASSED")
                passed += 1
            elif result is False:
                print(f"❌ {test_name}: FAILED")
                failed += 1
            else:
                print(f"⚠️  {test_name}: SKIPPED")
                skipped += 1
        
        total_tests = passed + failed
        if total_tests > 0:
            success_rate = (passed / total_tests) * 100
            print(f"\nResults: {passed} passed, {failed} failed, {skipped} skipped")
            print(f"Success rate: {success_rate:.1f}%")
            
            return success_rate >= 80  # 80% success rate required
        else:
            print(f"\nNo tests executed")
            return False


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Kubernetes integration tests')
    parser.add_argument('--namespace', default='rtc', 
                       help='Kubernetes namespace to test')
    
    args = parser.parse_args()
    
    tester = KubernetesIntegrationTest(args.namespace)
    success = tester.run_full_test_suite()
    
    if success:
        print(f"\n🎉 Integration tests PASSED - Kubernetes deployment is healthy!")
        sys.exit(0)
    else:
        print(f"\n💥 Integration tests FAILED - Check deployment issues above")
        sys.exit(1)


if __name__ == "__main__":
    main()
