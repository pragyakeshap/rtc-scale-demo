#!/usr/bin/env python3
"""
Load testing script for WebRTC GPU application
Tests performance under various load conditions
"""
import asyncio
import aiohttp
import time
import statistics
import json
import argparse
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Tuple
import sys

class LoadTester:
    """Load testing utility for the WebRTC GPU application"""
    
    def __init__(self, base_url: str = "http://localhost:8080"):
        self.base_url = base_url.rstrip('/')
        self.results = []
        
    async def single_request(self, session: aiohttp.ClientSession, 
                           pixels: str = "1280x720", iterations: int = 5) -> Dict:
        """Make a single request and measure response time"""
        start_time = time.perf_counter()
        
        try:
            url = f"{self.base_url}/process?pixels={pixels}&iters={iterations}"
            async with session.post(url) as response:
                if response.status == 200:
                    data = await response.json()
                    end_time = time.perf_counter()
                    
                    return {
                        'success': True,
                        'status_code': response.status,
                        'response_time': end_time - start_time,
                        'server_latency': data.get('latency_seconds', 0),
                        'device': data.get('device', 'unknown'),
                        'processing_mode': data.get('processing_mode', 'unknown'),
                        'concurrent_requests': data.get('concurrent_requests', 0)
                    }
                else:
                    end_time = time.perf_counter()
                    return {
                        'success': False,
                        'status_code': response.status,
                        'response_time': end_time - start_time,
                        'error': f"HTTP {response.status}"
                    }
                    
        except Exception as e:
            end_time = time.perf_counter()
            return {
                'success': False,
                'status_code': 0,
                'response_time': end_time - start_time,
                'error': str(e)
            }
    
    async def concurrent_load_test(self, concurrency: int, total_requests: int,
                                 pixels: str = "1280x720", iterations: int = 5) -> List[Dict]:
        """Run concurrent load test"""
        print(f"Starting load test: {total_requests} requests, {concurrency} concurrent")
        print(f"Parameters: pixels={pixels}, iterations={iterations}")
        
        async with aiohttp.ClientSession() as session:
            # Create semaphore to limit concurrency
            semaphore = asyncio.Semaphore(concurrency)
            
            async def bounded_request():
                async with semaphore:
                    return await self.single_request(session, pixels, iterations)
            
            # Create all tasks
            tasks = [bounded_request() for _ in range(total_requests)]
            
            # Execute with progress reporting
            start_time = time.perf_counter()
            results = []
            
            for i, coro in enumerate(asyncio.as_completed(tasks), 1):
                result = await coro
                results.append(result)
                
                # Progress report every 10 requests or at the end
                if i % 10 == 0 or i == total_requests:
                    elapsed = time.perf_counter() - start_time
                    rps = i / elapsed if elapsed > 0 else 0
                    print(f"Progress: {i}/{total_requests} ({i/total_requests*100:.1f}%) - {rps:.1f} RPS")
            
            return results
    
    def analyze_results(self, results: List[Dict]) -> Dict:
        """Analyze load test results"""
        successful = [r for r in results if r['success']]
        failed = [r for r in results if not r['success']]
        
        if not successful:
            return {
                'total_requests': len(results),
                'successful_requests': 0,
                'failed_requests': len(failed),
                'success_rate': 0.0,
                'error': 'No successful requests'
            }
        
        response_times = [r['response_time'] for r in successful]
        server_latencies = [r['server_latency'] for r in successful if 'server_latency' in r]
        
        # Get device info from successful requests
        devices = [r.get('device', 'unknown') for r in successful]
        device_counts = {}
        for device in devices:
            device_counts[device] = device_counts.get(device, 0) + 1
        
        analysis = {
            'total_requests': len(results),
            'successful_requests': len(successful),
            'failed_requests': len(failed),
            'success_rate': len(successful) / len(results) * 100,
            
            # Response time analysis (total time including network)
            'response_time': {
                'mean': statistics.mean(response_times),
                'median': statistics.median(response_times),
                'p95': self._percentile(response_times, 95),
                'p99': self._percentile(response_times, 99),
                'min': min(response_times),
                'max': max(response_times)
            },
            
            # Server processing time analysis
            'server_latency': {},
            'device_usage': device_counts
        }
        
        if server_latencies:
            analysis['server_latency'] = {
                'mean': statistics.mean(server_latencies),
                'median': statistics.median(server_latencies),
                'p95': self._percentile(server_latencies, 95),
                'p99': self._percentile(server_latencies, 99),
                'min': min(server_latencies),
                'max': max(server_latencies)
            }
        
        # Error analysis
        if failed:
            error_types = {}
            for failure in failed:
                error = failure.get('error', f"HTTP {failure.get('status_code', 'unknown')}")
                error_types[error] = error_types.get(error, 0) + 1
            analysis['errors'] = error_types
        
        return analysis
    
    def _percentile(self, data: List[float], percentile: float) -> float:
        """Calculate percentile of data"""
        if not data:
            return 0.0
        sorted_data = sorted(data)
        index = (percentile / 100) * (len(sorted_data) - 1)
        if index == int(index):
            return sorted_data[int(index)]
        else:
            lower = sorted_data[int(index)]
            upper = sorted_data[int(index) + 1]
            return lower + (upper - lower) * (index - int(index))
    
    def print_results(self, analysis: Dict):
        """Print formatted test results"""
        print("\n" + "="*60)
        print("LOAD TEST RESULTS")
        print("="*60)
        
        print(f"Total Requests: {analysis['total_requests']}")
        print(f"Successful: {analysis['successful_requests']}")
        print(f"Failed: {analysis['failed_requests']}")
        print(f"Success Rate: {analysis['success_rate']:.1f}%")
        
        if 'device_usage' in analysis:
            print(f"\nDevice Usage:")
            for device, count in analysis['device_usage'].items():
                percentage = count / analysis['successful_requests'] * 100
                print(f"  {device}: {count} requests ({percentage:.1f}%)")
        
        if 'response_time' in analysis:
            rt = analysis['response_time']
            print(f"\nResponse Time (including network):")
            print(f"  Mean: {rt['mean']*1000:.1f}ms")
            print(f"  Median: {rt['median']*1000:.1f}ms")
            print(f"  P95: {rt['p95']*1000:.1f}ms")
            print(f"  P99: {rt['p99']*1000:.1f}ms")
            print(f"  Min: {rt['min']*1000:.1f}ms")
            print(f"  Max: {rt['max']*1000:.1f}ms")
        
        if analysis.get('server_latency'):
            sl = analysis['server_latency']
            print(f"\nServer Processing Time:")
            print(f"  Mean: {sl['mean']*1000:.1f}ms")
            print(f"  Median: {sl['median']*1000:.1f}ms")
            print(f"  P95: {sl['p95']*1000:.1f}ms")
            print(f"  P99: {sl['p99']*1000:.1f}ms")
            print(f"  Min: {sl['min']*1000:.1f}ms")
            print(f"  Max: {sl['max']*1000:.1f}ms")
        
        if 'errors' in analysis:
            print(f"\nErrors:")
            for error, count in analysis['errors'].items():
                print(f"  {error}: {count} occurrences")
    
    async def health_check(self) -> bool:
        """Check if server is healthy before testing"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.base_url}/healthz") as response:
                    if response.status == 200:
                        data = await response.json()
                        print(f"Server health check passed:")
                        print(f"  Device: {data.get('device', 'unknown')}")
                        print(f"  PyTorch: {data.get('torch_imported', False)}")
                        print(f"  CUDA: {data.get('cuda_available', False)}")
                        return True
                    else:
                        print(f"Health check failed: HTTP {response.status}")
                        return False
        except Exception as e:
            print(f"Health check failed: {e}")
            return False
    
    async def performance_comparison_test(self):
        """Compare CPU vs GPU performance if available"""
        print("\n" + "="*60)
        print("PERFORMANCE COMPARISON TEST")
        print("="*60)
        
        # Test parameters
        test_cases = [
            ("Small", "640x480", 3, 5, 10),
            ("Medium", "1280x720", 5, 5, 10),
            ("Large", "1920x1080", 8, 3, 10),
        ]
        
        for name, pixels, iters, concurrency, requests in test_cases:
            print(f"\n{name} workload ({pixels}, {iters} iterations):")
            results = await self.concurrent_load_test(concurrency, requests, pixels, iters)
            analysis = self.analyze_results(results)
            
            if analysis['successful_requests'] > 0:
                avg_latency = analysis['server_latency'].get('mean', 0) * 1000
                p95_latency = analysis['server_latency'].get('p95', 0) * 1000
                print(f"  Average latency: {avg_latency:.1f}ms")
                print(f"  P95 latency: {p95_latency:.1f}ms")
                print(f"  Device mix: {analysis.get('device_usage', {})}")


async def main():
    parser = argparse.ArgumentParser(description='Load test WebRTC GPU application')
    parser.add_argument('--url', default='http://localhost:8080', 
                       help='Base URL of the server')
    parser.add_argument('--requests', type=int, default=50,
                       help='Total number of requests')
    parser.add_argument('--concurrency', type=int, default=10,
                       help='Number of concurrent requests')
    parser.add_argument('--pixels', default='1280x720',
                       help='Image resolution for testing')
    parser.add_argument('--iterations', type=int, default=5,
                       help='Processing iterations per request')
    parser.add_argument('--comparison', action='store_true',
                       help='Run performance comparison test')
    
    args = parser.parse_args()
    
    tester = LoadTester(args.url)
    
    # Health check first
    print("Performing health check...")
    if not await tester.health_check():
        print("Server health check failed. Please ensure server is running.")
        sys.exit(1)
    
    if args.comparison:
        # Run performance comparison
        await tester.performance_comparison_test()
    else:
        # Run standard load test
        print(f"\nRunning load test against {args.url}")
        results = await tester.concurrent_load_test(
            args.concurrency, args.requests, args.pixels, args.iterations
        )
        
        analysis = tester.analyze_results(results)
        tester.print_results(analysis)
        
        # Performance assessment
        if analysis['successful_requests'] > 0:
            avg_latency = analysis.get('server_latency', {}).get('mean', 0) * 1000
            p95_latency = analysis.get('server_latency', {}).get('p95', 0) * 1000
            
            print(f"\nPerformance Assessment:")
            if p95_latency < 200:
                print(f"✅ P95 latency ({p95_latency:.1f}ms) is within target (<200ms)")
            else:
                print(f"⚠️  P95 latency ({p95_latency:.1f}ms) exceeds target (200ms)")
                
            if analysis['success_rate'] >= 99:
                print(f"✅ Success rate ({analysis['success_rate']:.1f}%) is excellent")
            elif analysis['success_rate'] >= 95:
                print(f"⚠️  Success rate ({analysis['success_rate']:.1f}%) is acceptable")
            else:
                print(f"❌ Success rate ({analysis['success_rate']:.1f}%) is poor")

if __name__ == "__main__":
    asyncio.run(main())
