"""Holdout set: fresh scenarios that were never used to tune any rule."""
import json
import os

from backend.app.benchmark.holdout_dataset import build_holdout

BENCH = os.path.join(os.path.dirname(__file__), "../app/benchmark")


def _load(name):
    with open(os.path.join(BENCH, name), encoding="utf-8") as f:
        return json.load(f)


def test_holdout_is_balanced_and_bilingual():
    data = build_holdout()
    assert len(data) == 60
    assert sum(s["is_scam"] for s in data) == 30
    assert {s["language"] for s in data} == {"ru", "kz"}
    assert {s["split"] for s in data} == {"holdout"}
    assert [s["id"] for s in data] == list(range(1001, 1061))


def test_holdout_has_no_text_overlap_with_train_or_test():
    seen = {s["answer_text"] for s in _load("scenarios_500.json")}
    assert not ({s["answer_text"] for s in build_holdout()} & seen)


def test_committed_holdout_file_matches_builder():
    assert _load("scenarios_holdout.json") == build_holdout()


def test_holdout_contains_masked_scams_and_hard_legit():
    data = build_holdout()
    assert any(s["attack_vector"] == "coached_masked" for s in data)  # honest about the limit
    assert any(not s["is_scam"] and s["amount"] >= 500000 for s in data)  # big legit
    assert any(not s["is_scam"] and (s["transfer_hour"] >= 23 or s["transfer_hour"] <= 6) for s in data)


def test_evaluator_supports_holdout_split():
    from backend.app.benchmark.evaluator import BenchmarkEvaluator

    report = BenchmarkEvaluator.run_evaluation(build_holdout(), split="holdout")
    assert report.split == "holdout"
    assert report.total_scenarios == 60
    assert report.scam_count == 30 and report.legit_count == 30
