"""
NeuroLab AI: Reproducible Performance Benchmark Harness
Problem 21: Benchmark claims need reproducible evidence.
Measures and records:
- Hardware environment: CPU, RAM, OS, Python and library versions.
- Workload parameters: Runs, warm-up iterations, dataset size.
- Latency metrics: Median (p50), Mean, p95, p99, Min, Max, and Standard Deviation.
- Throughput: Frames per second (FPS), queries per second (QPS).
- Resource consumption: Process CPU usage and memory footprint (RSS).
"""

import argparse
import asyncio
import base64
import json
import os
import platform
import statistics
import sys
import time
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

import cv2
import numpy as np

# Ensure backend root is on sys.path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(SCRIPT_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.machine_learning.cv_service import CVTracker
from app.ai_agent.tutor_service import AITutorService
from app.core_backend.database.supabase_db import DatabaseManager
from app.core_backend.repositories.memory_repository import MemoryRepository


def get_system_environment() -> Dict[str, Any]:
    """Inspects and records system hardware and software platform details."""
    cpu_count = os.cpu_count() or 1
    import psutil
    mem = psutil.virtual_memory()

    return {
        "platform": platform.platform(),
        "system": platform.system(),
        "release": platform.release(),
        "architecture": platform.machine(),
        "processor": platform.processor() or "Unknown CPU",
        "cpu_count_logical": cpu_count,
        "total_ram_gb": round(mem.total / (1024 ** 3), 2),
        "available_ram_gb": round(mem.available / (1024 ** 3), 2),
        "python_version": platform.python_version(),
        "opencv_version": cv2.__version__,
        "numpy_version": np.__version__,
    }


def compute_statistics(durations_ms: List[float]) -> Dict[str, float]:
    """Calculates min, mean, median, p95, p99, max, and stdev for a latency series."""
    if not durations_ms:
        return {}

    sorted_d = sorted(durations_ms)
    n = len(sorted_d)

    def percentile(p: float) -> float:
        idx = int(round(p * (n - 1)))
        return sorted_d[min(n - 1, max(0, idx))]

    return {
        "runs": n,
        "min_ms": round(sorted_d[0], 2),
        "median_ms": round(statistics.median(sorted_d), 2),
        "mean_ms": round(statistics.mean(sorted_d), 2),
        "p95_ms": round(percentile(0.95), 2),
        "p99_ms": round(percentile(0.99), 2),
        "max_ms": round(sorted_d[-1], 2),
        "stdev_ms": round(statistics.stdev(sorted_d), 2) if n > 1 else 0.0,
    }


def create_test_frame_b64(width: int = 640, height: int = 480, cx: int = 320, cy: int = 240) -> str:
    """Generates a synthetic test frame with a red circle."""
    img = np.zeros((height, width, 3), dtype=np.uint8)
    cv2.circle(img, (cx, cy), 35, (0, 0, 255), -1)
    _, buf = cv2.imencode(".jpg", img)
    return base64.b64encode(buf.tobytes()).decode("utf-8")


def benchmark_cv_method(
    tracker: CVTracker,
    method: str,
    runs: int = 50,
    warmup: int = 5,
    width: int = 640,
    height: int = 480,
) -> Dict[str, Any]:
    """Benchmarks a specific CV tracking method (color, optical_flow, yolo)."""
    # 1. Warm-up procedure
    for i in range(warmup):
        frame = create_test_frame_b64(width, height, cx=100 + i * 10, cy=100)
        tracker.process_frame(frame, tracking_method=method, color_target="red")

    # 2. Timed runs
    durations = []
    for i in range(runs):
        cx = 100 + (i % 200)
        cy = 100 + (i % 100)
        frame = create_test_frame_b64(width, height, cx=cx, cy=cy)
        t0 = time.perf_counter()
        tracker.process_frame(frame, tracking_method=method, color_target="red")
        durations.append((time.perf_counter() - t0) * 1000.0)

    stats = compute_statistics(durations)
    stats["fps_throughput"] = round(1000.0 / stats["mean_ms"], 1) if stats["mean_ms"] > 0 else 0.0
    return stats


def benchmark_hybrid_retrieval(
    runs: int = 50,
    warmup: int = 5,
    corpus_size: int = 100,
) -> Dict[str, Any]:
    """Benchmarks hybrid vector + keyword memory retrieval performance."""
    db = DatabaseManager()
    repo = MemoryRepository(db)
    user_id = "bench_user_001"
    session_id = "bench_session_xyz"

    # Prepopulate corpus of conversation memories
    for i in range(corpus_size):
        vector = list(np.random.normal(0, 0.1, 768).astype(float))
        text = f"Physics experiment record {i}: analyzing pendulum period with length {0.1 * i:.2f} meters and gravity."
        repo.save_memory(
            session_id=session_id,
            text=text,
            embedding=vector,
            user_id=user_id,
            embedding_model_version="text-embedding-004",
        )

    # Warm-up
    query_vector = list(np.random.normal(0, 0.1, 768).astype(float))
    for _ in range(warmup):
        repo.search_memories(
            query_embedding=query_vector,
            query_text="pendulum period length",
            user_id=user_id,
            top_k=3,
        )

    # Timed runs
    durations = []
    for i in range(runs):
        t0 = time.perf_counter()
        repo.search_memories(
            query_embedding=query_vector,
            query_text="pendulum period gravity",
            user_id=user_id,
            top_k=3,
        )
        durations.append((time.perf_counter() - t0) * 1000.0)

    stats = compute_statistics(durations)
    stats["qps_throughput"] = round(1000.0 / stats["mean_ms"], 1) if stats["mean_ms"] > 0 else 0.0
    stats["corpus_size"] = corpus_size
    return stats


def benchmark_ai_tutor_generation(
    runs: int = 20,
    warmup: int = 3,
) -> Dict[str, Any]:
    """Benchmarks AI tutor generation response latency and throughput."""
    db = DatabaseManager()
    tutor = AITutorService(db=db)
    prompts = [
        "Explain Newton's second law of motion F=ma.",
        "How does a simple pendulum period depend on length?",
        "What is conservation of mechanical energy?",
    ]

    async def _generate_once(prompt_text: str):
        req = type("Req", (), {
            "prompt": prompt_text,
            "session_id": "bench_sess_ai",
            "concept": None,
            "question": None,
        })()
        chunks = []
        async for chunk in tutor.stream_chat(req, user_id="bench_user_001"):
            chunks.append(chunk)
        return "".join(chunks)

    # Warm-up
    for i in range(warmup):
        asyncio.run(_generate_once(prompts[i % len(prompts)]))

    # Timed runs
    durations = []
    for i in range(runs):
        p = prompts[i % len(prompts)]
        t0 = time.perf_counter()
        asyncio.run(_generate_once(p))
        durations.append((time.perf_counter() - t0) * 1000.0)

    stats = compute_statistics(durations)
    stats["rps_throughput"] = round(1000.0 / stats["mean_ms"], 1) if stats["mean_ms"] > 0 else 0.0
    return stats


def run_full_benchmark_suite(
    runs: int = 50,
    warmup: int = 5,
    output_file: Optional[str] = None,
) -> Dict[str, Any]:
    """Orchestrates end-to-end benchmark suite and prints formatted results."""
    import psutil
    process = psutil.Process()
    cpu_before = psutil.cpu_percent(interval=0.1)
    mem_before_mb = process.memory_info().rss / (1024 * 1024)

    env_info = get_system_environment()

    print("\n" + "=" * 78)
    print(" NeuroLab AI: Reproducible Performance Benchmark")
    print("=" * 78)
    print(f"Platform:      {env_info['platform']}")
    print(f"CPU:           {env_info['processor']} ({env_info['cpu_count_logical']} logical cores)")
    print(f"RAM:           {env_info['total_ram_gb']} GB")
    print(f"Python:        {env_info['python_version']} (OpenCV {env_info['opencv_version']})")
    print(f"Config:        runs={runs}, warmup={warmup}")
    print("-" * 78)

    tracker = CVTracker()

    print("1/5 Benchmarking Color Tracking (HSV Segmentation)...")
    color_stats = benchmark_cv_method(tracker, "color", runs=runs, warmup=warmup)

    print("2/5 Benchmarking Optical Flow Tracking (Lucas-Kanade)...")
    optical_flow_stats = benchmark_cv_method(tracker, "optical_flow", runs=runs, warmup=warmup)

    print("3/5 Benchmarking YOLOv8 Detection Tracking...")
    yolo_stats = benchmark_cv_method(tracker, "yolo", runs=runs, warmup=warmup)

    print("4/5 Benchmarking Hybrid Vector + Text Retrieval...")
    retrieval_stats = benchmark_hybrid_retrieval(runs=runs, warmup=warmup)

    print("5/5 Benchmarking AI Tutor Pedagogical Generation...")
    ai_stats = benchmark_ai_tutor_generation(runs=max(10, runs // 2), warmup=warmup)

    cpu_after = psutil.cpu_percent(interval=0.1)
    mem_after_mb = process.memory_info().rss / (1024 * 1024)

    results = {
        "benchmark_timestamp": datetime.now(timezone.utc).isoformat(),
        "environment": env_info,
        "parameters": {"runs": runs, "warmup": warmup},
        "resources": {
            "initial_memory_mb": round(mem_before_mb, 2),
            "final_memory_mb": round(mem_after_mb, 2),
            "memory_delta_mb": round(mem_after_mb - mem_before_mb, 2),
            "cpu_utilization_percent": round((cpu_before + cpu_after) / 2.0, 1),
        },
        "benchmarks": {
            "cv_color_tracking": color_stats,
            "cv_optical_flow_tracking": optical_flow_stats,
            "cv_yolo_tracking": yolo_stats,
            "hybrid_memory_retrieval": retrieval_stats,
            "ai_tutor_generation": ai_stats,
        },
    }

    # Print clean Markdown summary table
    print("\n" + "=" * 78)
    print(" BENCHMARK RESULTS SUMMARY")
    print("=" * 78)
    print(f"| {'Component / Subsystem':<32} | {'Median (p50)':<12} | {'p95 Latency':<12} | {'Throughput':<14} |")
    print(f"|{'-' * 34}|{'-' * 14}|{'-' * 14}|{'-' * 16}|")
    print(f"| {'CV: Color Tracking (HSV)':<32} | {color_stats['median_ms']:>8.2f} ms | {color_stats['p95_ms']:>8.2f} ms | {color_stats['fps_throughput']:>8.1f} FPS |")
    print(f"| {'CV: Optical Flow (Lucas-Kanade)':<32} | {optical_flow_stats['median_ms']:>8.2f} ms | {optical_flow_stats['p95_ms']:>8.2f} ms | {optical_flow_stats['fps_throughput']:>8.1f} FPS |")
    print(f"| {'CV: YOLOv8 Detection':<32} | {yolo_stats['median_ms']:>8.2f} ms | {yolo_stats['p95_ms']:>8.2f} ms | {yolo_stats['fps_throughput']:>8.1f} FPS |")
    print(f"| {'Retrieval: Hybrid Search (100+)':<32} | {retrieval_stats['median_ms']:>8.2f} ms | {retrieval_stats['p95_ms']:>8.2f} ms | {retrieval_stats['qps_throughput']:>8.1f} QPS |")
    print(f"| {'AI Tutor: Response Generation':<32} | {ai_stats['median_ms']:>8.2f} ms | {ai_stats['p95_ms']:>8.2f} ms | {ai_stats['rps_throughput']:>8.1f} RPS |")
    print("=" * 78)
    print(f"Peak Memory: {mem_after_mb:.1f} MB (Delta: {mem_after_mb - mem_before_mb:+.1f} MB)")
    print("=" * 78 + "\n")

    dest_file = output_file or os.path.join(BACKEND_DIR, "benchmark_results.json")
    with open(dest_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"Benchmark results successfully recorded to {dest_file}\n")

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="NeuroLab AI Reproducible Benchmark Suite")
    parser.add_argument("--runs", type=int, default=30, help="Number of timed benchmark runs per method (default: 30)")
    parser.add_argument("--warmup", type=int, default=5, help="Number of warm-up iterations (default: 5)")
    parser.add_argument("--output", type=str, default=None, help="Output path for JSON benchmark results")
    args = parser.parse_args()

    run_full_benchmark_suite(runs=args.runs, warmup=args.warmup, output_file=args.output)

