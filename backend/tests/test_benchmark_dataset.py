"""The benchmark test split must contain hard legitimate cases, without touching train."""
import json
import os
import random

from backend.app.benchmark.adversarial_robot import AdversarialRobot

DATA = os.path.join(os.path.dirname(__file__), "../app/benchmark/scenarios_500.json")


def _suite():
    random.seed(1337)
    return [s.to_dict() for s in AdversarialRobot.generate_benchmark_suite(500, 0.7)]


def test_suite_is_500_and_matches_committed_file():
    suite = _suite()
    assert len(suite) == 500
    with open(DATA, encoding="utf-8") as f:
        assert json.load(f) == suite


def test_test_split_has_hard_legit_with_real_friction_potential():
    test_legit = [s for s in _suite() if s["split"] == "test" and not s["is_scam"]]
    hard = [s for s in test_legit if s["attack_vector"] == "benign_hard"]
    assert len(hard) >= 25
    assert any(s["amount"] >= 500000 for s in hard)            # big legit transfers
    assert any(s["transfer_hour"] >= 23 or s["transfer_hour"] <= 6 for s in hard)  # night
    assert any(s["frequency_last_hour"] >= 2 for s in hard)    # repeated payments
    assert {s["language"] for s in hard} == {"ru", "kz"}


def test_no_verbatim_overlap_between_train_and_test():
    suite = _suite()
    train = {s["answer_text"] for s in suite if s["split"] == "train"}
    test = {s["answer_text"] for s in suite if s["split"] == "test"}
    assert not (train & test)


def test_train_split_is_unchanged_by_hard_cases():
    suite = _suite()
    train_ids = [s["id"] for s in suite if s["split"] == "train"]
    assert train_ids == list(range(1, 351))


def test_train_split_also_has_hard_legit_with_distinct_texts():
    suite = _suite()
    train_hard = [s for s in suite if s["split"] == "train" and s["attack_vector"] == "benign_hard"]
    test_hard = [s for s in suite if s["split"] == "test" and s["attack_vector"] == "benign_hard"]
    assert len(train_hard) >= 10
    assert {s["language"] for s in train_hard} == {"ru", "kz"}
    assert not ({s["answer_text"] for s in train_hard} & {s["answer_text"] for s in test_hard})
    # Total size and ids stay fixed.
    assert [s["id"] for s in suite] == list(range(1, 501))


def test_train_has_advance_fee_scams_with_distinct_texts():
    suite = _suite()
    fee = [s for s in suite if s["split"] == "train" and s["attack_vector"] == "advance_fee"]
    assert len(fee) >= 10
    assert all(s["is_scam"] for s in fee)
    assert {s["language"] for s in fee} == {"ru", "kz"}
    assert [s["id"] for s in suite] == list(range(1, 501))
    holdout_texts = set()
    from backend.app.benchmark.holdout_dataset import build_holdout

    holdout_texts = {s["answer_text"] for s in build_holdout()}
    assert not ({s["answer_text"] for s in fee} & holdout_texts)
