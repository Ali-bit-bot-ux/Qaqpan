"""
Benchmark API Router: Endpoint providing automated adversarial simulation
and metrics for the Bank Analyst dashboard (AnalystView.jsx).
"""

import json
import logging
import os
import sys
from typing import Dict, Any, Optional, List  # Any: JSON response dictionary mapping

# Ensure relative imports resolve cleanly
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "../../../"))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

try:
    from fastapi import APIRouter, Query, HTTPException
    from pydantic import BaseModel, Field
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False
    # Lightweight dummy router and Query for standalone execution if fastapi is not yet installed
    def Query(default: Any = ..., **kwargs: Any) -> Any:  # Any: Passthrough query parameter helper
        return default

    class APIRouter:  # type: ignore
        def __init__(self, *args: Any, **kwargs: Any) -> None:  # Any: Passthrough initialization
            self.routes: List[Dict[str, Any]] = []  # Any: Route metadata dictionary
        def get(self, path: str, **kwargs: Any) -> Any:  # Any: Decorator passthrough
            def decorator(func: Any) -> Any:  # Any: Wrapped endpoint function
                return func
            return decorator
        def post(self, path: str, **kwargs: Any) -> Any:  # Any: Decorator passthrough
            def decorator(func: Any) -> Any:  # Any: Wrapped endpoint function
                return func
            return decorator

from backend.app.benchmark.evaluator import BenchmarkEvaluator, EvaluationReport
from backend.app.benchmark.adversarial_robot import AdversarialRobot, generate_and_save_benchmark

logger = logging.getLogger("qaqpan.api.benchmark")
router = APIRouter(prefix="/benchmark", tags=["Benchmark"])


def get_or_create_dataset(filepath: Optional[str] = None) -> List[Dict[str, Any]]:  # Any: Scenario data items
    """Loads 500 scenarios from file or synthesizes them on-the-fly."""
    if filepath is None:
        benchmark_dir = os.path.abspath(os.path.join(current_dir, "../benchmark"))
        filepath = os.path.join(benchmark_dir, "scenarios_500.json")

    if not os.path.exists(filepath):
        logger.info("Dataset file not found at %s. Generating fresh 500 scenarios...", filepath)
        generate_and_save_benchmark(filepath)

    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


@router.post("/simulate")
@router.get("/simulate")
def run_simulation(
    split: str = Query("test", description="Dataset split to evaluate: 'test', 'train', 'holdout' (fresh, never tuned on) or 'full'"),
    count: int = Query(500, description="Number of scenarios in simulation pool")
) -> Dict[str, Any]:  # Any: Serialized benchmark report payload
    """
    Executes adversarial simulation comparing the Baseline against Qaqpan.
    Returns metrics: Stop Rate, False Positive Rate, prevented loss, and latency.
    """
    try:
        data = get_or_create_dataset()
        if split == "holdout":
            data = get_or_create_dataset(os.path.join(os.path.dirname(os.path.abspath(__file__)), "../benchmark/scenarios_holdout.json"))
        # Filter by split first to ensure target split elements exist
        if split in ("train", "test", "holdout"):
            subset = [s for s in data if s.get("split") == split]
        else:
            subset = data

        if count < len(subset):
            subset = subset[:count]

        report = BenchmarkEvaluator.run_evaluation(subset, split=split)
        return {
            "status": "success",
            "benchmark": report.to_dict()
        }
    except Exception as exc:
        logger.error("Benchmark simulation error: %s", exc)
        return {
            "status": "error",
            "message": str(exc)
        }


@router.get("/scenarios/sample")
def get_sample_scenarios(
    limit: int = Query(10, description="Number of sample scenarios to return")
) -> Dict[str, Any]:  # Any: Sample list response mapping
    """Returns sample scenarios for visual inspection in Analyst dashboard."""
    try:
        data = get_or_create_dataset()
        samples = data[:limit]
        return {
            "status": "success",
            "count": len(samples),
            "samples": samples
        }
    except Exception as exc:
        return {
            "status": "error",
            "message": str(exc)
        }


if __name__ == "__main__":
    print("=== TESTING BENCHMARK API ROUTE LOCALLY ===")
    res = run_simulation(split="test", count=150)
    print("Simulation status:", res.get("status"))
    bench = res.get("benchmark", {})
    print("Evaluated split:", bench.get("split"))
    print("Total scenarios:", bench.get("total_scenarios"))
    print("Stop Rate boost:", bench.get("stop_rate_delta"))
    print("FPR reduction:", bench.get("false_positive_reduction"))
