import numpy as np
import pytest
from npsdm_app.bank import Bank
from npsdm_app.config import Settings
from npsdm_app.presentation import fixed_question, present
from npsdm_app.acquisition import Acquisition


def small_bank():
    b = Bank(
        Settings(
            question_temperature_min_c=20,
            question_temperature_max_c=24,
            question_temperature_step_c=1,
            q_quadrature_count=16,
        )
    )
    b.groups = b.groups[:3]
    return b


def test_joint_scans_match_independent_exact_scans():
    b = small_bank()
    post = b.prior.copy()
    post[0] *= 3
    post /= post.sum()
    asked = {b.groups[0]["id"]: [(0, 1)]}
    states = [dict(common=p, grids=None, excluded=asked) for p in [b.prior, post]]
    results = b.select_many(states)
    for p, r in zip([b.prior, post], results):
        oracle = b.select(p, [b.groups[0]["id"] + ":0:1"])
        assert r["eig_bits"] == pytest.approx(oracle["eig_bits"], abs=1e-13)
        assert r["id"] == oracle["id"] and r["evaluated_candidates"] == 30


def test_question_temperature_differences_and_real_demographics():
    b = Bank()
    q = present(b, fixed_question(b), 17, 0)
    assert q["scenario"]["n"] == 5
    assert q["temperature_difference"]["mean_c"] == pytest.approx([0.6, 0.8])
    assert q["temperature_difference"]["worst_c"] == [2, 1]
    assert q["exact_discrete_global"] is False
    assert len(q["participants"]) == 5
    for p, subject in zip(q["participants"], b.lookup[q["group_id"]]["members"]):
        assert p["age"] == b.people[subject]["age"]
        assert p["sex"] in ["여성", "남성"]
        assert "subject" not in p


def test_cache_is_answer_sensitive_and_survives_new_coordinator(tmp_path):
    b = small_bank()
    engine = Acquisition()
    engine.directory = tmp_path
    q = fixed_question(b)
    a = [dict(q, response=0)]
    z = [dict(q, response=1)]
    assert engine.key(b, a) != engine.key(b, z)
    engine._compute(b, [(engine.key(b, a), a), (engine.key(b, z), z)])
    assert not engine.errors
    hit, value = engine.get(b, a)
    assert hit and value["id"] != q["id"]
    restored = Acquisition()
    restored.directory = tmp_path
    assert restored.get(b, a) == (hit, value)
    assert restored.get(b, [dict(q, response="skip")])[0] is False
    engine.pool.shutdown()
    restored.pool.shutdown()
