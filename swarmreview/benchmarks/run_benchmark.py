"""
run_benchmark.py

Run this against YOUR local Ollama instance to get real sequential-vs-parallel
numbers. Do not put a number in your README that you didn't get from actually
running this on your own machine -- a made-up benchmark is worse than no
benchmark, because it's the first thing someone technical will try to verify.

Usage:
    python benchmarks/run_benchmark.py
"""

import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.security_agent import SecurityAgent
from agents.performance_agent import PerformanceAgent
from agents.architecture_agent import ArchitectureAgent
from concurrent.futures import ThreadPoolExecutor

SAMPLE_DIFF_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                 "sample", "example.diff")


def run_sequential(diff: str):
    security = SecurityAgent()
    performance = PerformanceAgent()
    architecture = ArchitectureAgent()
    t0 = time.time()
    security.review(diff)
    performance.review(diff)
    architecture.review(diff)
    return time.time() - t0


def run_parallel(diff: str):
    security = SecurityAgent()
    performance = PerformanceAgent()
    architecture = ArchitectureAgent()
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = [
            pool.submit(security.review, diff),
            pool.submit(performance.review, diff),
            pool.submit(architecture.review, diff),
        ]
        [f.result() for f in futures]
    return time.time() - t0


def main():
    with open(SAMPLE_DIFF_PATH) as f:
        diff = f.read()

    print("Running sequential pass (3 calls, one after another)...")
    sequential_time = run_sequential(diff)
    print(f"  Sequential: {sequential_time:.2f}s")

    print("Running parallel pass (3 calls concurrently)...")
    parallel_time = run_parallel(diff)
    print(f"  Parallel:   {parallel_time:.2f}s")

    speedup = sequential_time / parallel_time if parallel_time > 0 else float("inf")
    print(f"\nSpeedup: {speedup:.2f}x")
    print("\nThis number is specific to your machine, your model, and your Ollama")
    print("config. Re-run before quoting it anywhere -- don't reuse this run's number")
    print("after changing models, hardware, or agent prompts.")


if __name__ == "__main__":
    main()
