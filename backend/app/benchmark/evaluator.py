"""
Benchmark Evaluator: Calculates anti-fraud metrics and compares
the legacy banking baseline against the 'Qaqpan' multi-tiered ladder.

Metrics:
- Stop Rate (Recall on Fraud): TP / (TP + FN)
- False Positive Rate (FPR): FP / (FP + TN)
- Friction Rate on Legitimate Customers
- Financial Impact: Total KZT theft prevented
- Honest evaluation on partitioned Train and Test splits per AGENTS.md.
"""

from dataclasses import dataclass, asdict
import json
import os
import sys
import time
from typing import List, Dict, Any, Optional  # Any: Primitives mapping in metrics dictionaries

# Ensure imports resolve cleanly
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "../../../"))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

try:
    from backend.app.core.rules_engine import RulesEngine, TransactionContext, RiskLevel
    from backend.app.benchmark.adversarial_robot import AdversarialScenario
except ImportError:
    from rules_engine import RulesEngine, TransactionContext, RiskLevel
    from adversarial_robot import AdversarialScenario


# Modelled delay assumptions (synthetic prototype, not measured on real clients).
QUESTION_ANSWER_SECONDS: float = 15.0  # Client reads and answers one question
TRUSTED_WAIT_SECONDS: float = 120.0  # Trusted person reviews and decides
BASELINE_REVIEW_SECONDS: float = 600.0  # Legacy rule: bank holds the transfer for manual review


@dataclass
class ModelPerformance:
    """Performance metrics for an anti-fraud model."""
    name: str
    stop_rate: float  # Percentage of fraudulent transfers stopped (Recall)
    false_positive_rate: float  # Percentage of legitimate transfers incorrectly flagged
    stopped_scams: int  # True Positives
    missed_scams: int  # False Negatives
    false_positives: int  # False Positives
    clean_legit: int  # True Negatives
    prevented_loss_kzt: float  # Monetary value of prevented fraud in tenge
    # Friction on legitimate clients (modelled, see the *_SECONDS assumptions below).
    legit_questioned_rate: float = 0.0  # Share of legit transfers that were questioned or held
    avg_delay_seconds: float = 0.0  # Mean modelled delay per legit transfer

    def to_dict(self) -> Dict[str, Any]:  # Any: Primitives dictionary
        return asdict(self)


@dataclass
class EvaluationReport:
    """Comparative benchmark outcome."""
    split: str  # 'train', 'test', or 'full'
    total_scenarios: int
    scam_count: int
    legit_count: int
    baseline: ModelPerformance
    qaqpan: ModelPerformance
    stop_rate_delta: str  # e.g. '+52.4%'
    false_positive_reduction: str  # e.g. '-16.2%'
    latency_ms: float

    def to_dict(self) -> Dict[str, Any]:  # Any: JSON serialization mapping
        data: Dict[str, Any] = asdict(self)  # Any: Dictionary conversion
        return data


class BenchmarkEvaluator:
    """Executes high-speed evaluation of anti-fraud strategies."""

    BASELINE_AMOUNT_THRESHOLD: float = 500000.0  # Traditional static bank rule

    @classmethod
    def evaluate_scenario_baseline(cls, amount: float) -> bool:
        """
        Legacy rule: Flag if amount > 500,000 KZT, otherwise pass.
        Returns True if flagged/stopped, False if allowed.
        """
        return amount >= cls.BASELINE_AMOUNT_THRESHOLD

    @classmethod
    def run_evaluation(
        cls,
        scenarios: List[Dict[str, Any]],  # Any: Scenario data objects
        split: str = "test"
    ) -> EvaluationReport:
        """
        Runs comparative benchmark on selected split ('train', 'test', or 'full').
        """
        start_time = time.time()

        # Filter by split if requested
        if split in ("train", "test", "holdout", "holdout2"):
            dataset = [s for s in scenarios if s.get("split", "test") == split]
        else:
            dataset = scenarios
            split = "full"

        total = len(dataset)
        if total == 0:
            raise ValueError(f"No scenarios found for split '{split}'")

        scam_scenarios = [s for s in dataset if s["is_scam"]]
        legit_scenarios = [s for s in dataset if not s["is_scam"]]
        scam_c = len(scam_scenarios)
        legit_c = len(legit_scenarios)

        # -------------------------------------------------------------
        # 1. Evaluate Baseline (Amount > 500k KZT)
        # -------------------------------------------------------------
        base_tp = 0  # Scams stopped
        base_fn = 0  # Scams missed
        base_fp = 0  # Legit flagged
        base_tn = 0  # Legit passed
        base_prevented_kzt = 0.0

        for sc in scam_scenarios:
            stopped = cls.evaluate_scenario_baseline(sc["amount"])
            if stopped:
                base_tp += 1
                base_prevented_kzt += sc["amount"]
            else:
                base_fn += 1

        for sc in legit_scenarios:
            stopped = cls.evaluate_scenario_baseline(sc["amount"])
            if stopped:
                base_fp += 1
            else:
                base_tn += 1

        base_questioned = (base_fp / legit_c) if legit_c > 0 else 0.0
        base_avg_delay = base_questioned * BASELINE_REVIEW_SECONDS

        base_stop_rate = (base_tp / scam_c) if scam_c > 0 else 0.0
        base_fpr = (base_fp / legit_c) if legit_c > 0 else 0.0

        baseline_perf = ModelPerformance(
            name="Традиционный лимит банка (> 500k ₸)",
            stop_rate=round(base_stop_rate, 4),
            false_positive_rate=round(base_fpr, 4),
            stopped_scams=base_tp,
            missed_scams=base_fn,
            false_positives=base_fp,
            clean_legit=base_tn,
            prevented_loss_kzt=round(base_prevented_kzt, 2),
            legit_questioned_rate=round(base_questioned, 4),
            avg_delay_seconds=round(base_avg_delay, 2),
        )

        # -------------------------------------------------------------
        # 2. Evaluate 'Qaqpan' Multi-tiered Ladder
        # -------------------------------------------------------------
        qaqpan_tp = 0
        qaqpan_fn = 0
        qaqpan_fp = 0
        qaqpan_tn = 0
        qaqpan_prevented_kzt = 0.0
        legit_questioned = 0
        legit_total_delay = 0.0

        for sc in scam_scenarios:
            ctx = TransactionContext(
                amount=sc["amount"],
                is_new_recipient=sc["is_new_recipient"],
                transfer_hour=sc.get("transfer_hour", 14),
                frequency_last_hour=sc.get("frequency_last_hour", 1)
            )
            res = RulesEngine.evaluate_with_answer(ctx, sc["answer_text"])
            # In Qaqpan, HIGH triggers trusted contact intervention (stopped)
            stopped = (res.risk_level == RiskLevel.HIGH)
            if stopped:
                qaqpan_tp += 1
                qaqpan_prevented_kzt += sc["amount"]
            else:
                qaqpan_fn += 1

        for sc in legit_scenarios:
            ctx = TransactionContext(
                amount=sc["amount"],
                is_new_recipient=sc["is_new_recipient"],
                transfer_hour=sc.get("transfer_hour", 14),
                frequency_last_hour=sc.get("frequency_last_hour", 1)
            )
            res = RulesEngine.evaluate_with_answer(ctx, sc["answer_text"])
            # Friction: any initial non-ALLOW means the client was questioned or held.
            if RulesEngine.evaluate_initial_transaction(ctx).risk_level != RiskLevel.LOW:
                legit_questioned += 1
                legit_total_delay += QUESTION_ANSWER_SECONDS
            # False positive if customer was blocked or sent to trusted contact unnecessarily
            stopped = (res.risk_level == RiskLevel.HIGH)
            if stopped:
                legit_total_delay += TRUSTED_WAIT_SECONDS
            if stopped:
                qaqpan_fp += 1
            else:
                qaqpan_tn += 1

        qaqpan_stop_rate = (qaqpan_tp / scam_c) if scam_c > 0 else 0.0
        qaqpan_fpr = (qaqpan_fp / legit_c) if legit_c > 0 else 0.0

        qaqpan_perf = ModelPerformance(
            name="Лестница защиты 'Қақпан'",
            stop_rate=round(qaqpan_stop_rate, 4),
            false_positive_rate=round(qaqpan_fpr, 4),
            stopped_scams=qaqpan_tp,
            missed_scams=qaqpan_fn,
            false_positives=qaqpan_fp,
            clean_legit=qaqpan_tn,
            prevented_loss_kzt=round(qaqpan_prevented_kzt, 2),
            legit_questioned_rate=round(legit_questioned / legit_c, 4) if legit_c else 0.0,
            avg_delay_seconds=round(legit_total_delay / legit_c, 2) if legit_c else 0.0,
        )

        elapsed_ms = (time.time() - start_time) * 1000.0
        delta_stop = (qaqpan_stop_rate - base_stop_rate) * 100.0
        delta_fp = (base_fpr - qaqpan_fpr) * 100.0

        return EvaluationReport(
            split=split,
            total_scenarios=total,
            scam_count=scam_c,
            legit_count=legit_c,
            baseline=baseline_perf,
            qaqpan=qaqpan_perf,
            stop_rate_delta=f"{delta_stop:+.1f}%",
            false_positive_reduction=f"{delta_fp:+.1f}%",
            latency_ms=round(elapsed_ms, 2)
        )


if __name__ == "__main__":
    current_dir = os.path.dirname(os.path.abspath(__file__))
    dataset_file = os.path.join(current_dir, "scenarios_500.json")

    with open(dataset_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    print("=== EXECUTING ADVERSARIAL BENCHMARK (TEST SPLIT) ===")
    test_report = BenchmarkEvaluator.run_evaluation(data, split="test")
    print(f"\n[Test Split - {test_report.total_scenarios} scenarios ({test_report.scam_count} scam / {test_report.legit_count} legit)]")
    print(f"Elapsed Time: {test_report.latency_ms} ms")
    print("\n1. BASELINE (Legacy limit > 500k ₸):")
    print(f"   Stop Rate: {test_report.baseline.stop_rate*100:.1f}% ({test_report.baseline.stopped_scams}/{test_report.scam_count})")
    print(f"   False Positive Rate: {test_report.baseline.false_positive_rate*100:.1f}% ({test_report.baseline.false_positives}/{test_report.legit_count})")
    print(f"   Prevented Loss: {test_report.baseline.prevented_loss_kzt:,.0f} ₸")
    
    print("\n2. QAQPAN (Adaptive Risk Ladder):")
    print(f"   Stop Rate: {test_report.qaqpan.stop_rate*100:.1f}% ({test_report.qaqpan.stopped_scams}/{test_report.scam_count})")
    print(f"   False Positive Rate: {test_report.qaqpan.false_positive_rate*100:.1f}% ({test_report.qaqpan.false_positives}/{test_report.legit_count})")
    print(f"   Prevented Loss: {test_report.qaqpan.prevented_loss_kzt:,.0f} ₸")

    print("\n3. COMPARATIVE ADVANTAGE:")
    print(f"   Stop Rate Boost: {test_report.stop_rate_delta}")
    print(f"   FPR Reduction: {test_report.false_positive_reduction}")
