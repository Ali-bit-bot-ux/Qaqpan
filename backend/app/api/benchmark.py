from fastapi import APIRouter
from ..models.schemas import BenchmarkSimulationRequest, BenchmarkResult, BenchmarkMetrics

router = APIRouter(prefix="/benchmark", tags=["Benchmark & Fraudster Robot"])


@router.post("/simulate", response_model=BenchmarkResult)
async def run_benchmark_simulation(payload: BenchmarkSimulationRequest):
    """
    Mock endpoint for adversarial stress testing.
    Backend 2 will replace this logic with actual synthetic attack generation.
    """
    return BenchmarkResult(
        total_scenarios=payload.scenarios_count,
        baseline_metrics=BenchmarkMetrics(
            stop_rate_pct=42.1,
            false_positive_pct=31.5,
            friction_rate_pct=0.0,
            avg_delay_seconds=1080.0
        ),
        qaqpan_before_metrics=BenchmarkMetrics(
            stop_rate_pct=88.4,
            false_positive_pct=4.8,
            friction_rate_pct=8.2,
            avg_delay_seconds=1.2
        ),
        qaqpan_after_metrics=BenchmarkMetrics(
            stop_rate_pct=96.8,
            false_positive_pct=2.9,
            friction_rate_pct=6.1,
            avg_delay_seconds=0.8
        ),
        bypasses_found=18,
        bypasses_fixed=16,
        status="completed"
    )

