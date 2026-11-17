"""
Trap Evaluator (Step L.8):
Benchmark suite evaluating recipient extraction precision, recall, and safety constraints
(secret-request rejection, multi-recipient handling, KZ/RU bilingual support)
on realistic scammer dialogue transcripts.
"""

from dataclasses import dataclass, asdict
import json
import os
import sys
import time
from typing import List, Dict, Any, Tuple

# Ensure root is in sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "../../../"))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from backend.app.core.recipient_extractor import (
    extract_recipients_offline,
    extract_recipients,
    RecipientType,
    ExtractedRecipient,
)


@dataclass
class TrapBenchmarkReport:
    total_dialogues: int
    categories: Dict[str, int]
    total_expected_recipients: int
    true_positives: int
    false_positives: int
    false_negatives: int
    precision: float
    recall: float
    f1_score: float
    secret_attacks_tested: int
    secret_attacks_blocked: int
    secret_rejection_rate: float
    avg_latency_ms: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class TrapEvaluator:
    """Evaluates payment recipient extraction on ground-truth dialogue datasets."""

    @classmethod
    def evaluate(
        cls,
        dialogues: List[Dict[str, Any]],
        use_offline: bool = True
    ) -> TrapBenchmarkReport:
        tp = 0
        fp = 0
        fn = 0
        total_expected = 0
        secret_attacks = 0
        secret_blocked = 0
        cat_counts: Dict[str, int] = {}
        total_time_ms = 0.0

        for item in dialogues:
            cat = item.get("category", "unknown")
            cat_counts[cat] = cat_counts.get(cat, 0) + 1
            text = item["text"]
            expected = item.get("expected_recipients", [])
            total_expected += len(expected)

            expected_set = {(r["type"], r["value"]) for r in expected}

            t0 = time.perf_counter()
            if use_offline:
                extracted = extract_recipients_offline(text)
            else:
                extracted = extract_recipients(text)
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            total_time_ms += elapsed_ms

            extracted_set = {(r.recipient_type.value, r.value) for r in extracted}

            # Safety check: secret attacks must return 0 extracted
            if cat == "secret_attack":
                secret_attacks += 1
                if len(extracted) == 0:
                    secret_blocked += 1

            # Match true positives
            for cand in extracted_set:
                if cand in expected_set:
                    tp += 1
                else:
                    fp += 1

            for exp in expected_set:
                if exp not in extracted_set:
                    fn += 1

        precision = (tp / (tp + fp)) if (tp + fp) > 0 else 1.0
        recall = (tp / (tp + fn)) if (tp + fn) > 0 else 1.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0
        sec_rate = (secret_blocked / secret_attacks) if secret_attacks > 0 else 1.0
        avg_lat = total_time_ms / len(dialogues) if dialogues else 0.0

        return TrapBenchmarkReport(
            total_dialogues=len(dialogues),
            categories=cat_counts,
            total_expected_recipients=total_expected,
            true_positives=tp,
            false_positives=fp,
            false_negatives=fn,
            precision=round(precision, 4),
            recall=round(recall, 4),
            f1_score=round(f1, 4),
            secret_attacks_tested=secret_attacks,
            secret_attacks_blocked=secret_blocked,
            secret_rejection_rate=round(sec_rate, 4),
            avg_latency_ms=round(avg_lat, 2)
        )


def run_benchmark():
    dialogues_file = os.path.join(current_dir, "trap_dialogues.json")
    if not os.path.exists(dialogues_file):
        print(f"Error: dataset file not found at {dialogues_file}")
        sys.exit(1)

    with open(dialogues_file, "r", encoding="utf-8") as f:
        dialogues = json.load(f)

    rep = TrapEvaluator.evaluate(dialogues, use_offline=True)

    print("=" * 65)
    print("      TRAP BOT RECIPIENT EXTRACTION BENCHMARK (STEP L.8)")
    print("=" * 65)
    print(f"Total test dialogues:        {rep.total_dialogues}")
    print(f"Categories distribution:     {rep.categories}")
    print(f"Total expected recipients:   {rep.total_expected_recipients}")
    print("-" * 65)
    print(f"True Positives (extracted):  {rep.true_positives}")
    print(f"False Positives (erroneous): {rep.false_positives}")
    print(f"False Negatives (missed):    {rep.false_negatives}")
    print("-" * 65)
    print(f"Precision:                   {rep.precision * 100:.1f}%")
    print(f"Recall:                      {rep.recall * 100:.1f}%")
    print(f"F1-Score:                    {rep.f1_score * 100:.1f}%")
    print("-" * 65)
    print(f"Secret-Attack Rejection:     {rep.secret_rejection_rate * 100:.1f}% ({rep.secret_attacks_blocked}/{rep.secret_attacks_tested})")
    print(f"Average Parsing Latency:     {rep.avg_latency_ms:.2f} ms")
    print("=" * 65)


if __name__ == "__main__":
    run_benchmark()

