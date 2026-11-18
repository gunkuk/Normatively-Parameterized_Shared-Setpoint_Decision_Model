import numpy as np
import pytest
from npsdm_app.bank import Bank
from npsdm_app.config import Settings
from npsdm_app.science import probability, eig


def test_exhaustive_small_bank_oracle_and_exclusion():
    b = Bank(
        Settings(
            question_temperature_min_c=20,
            question_temperature_max_c=24,
            question_temperature_step_c=1,
            q_quadrature_count=16,
        )
    )
    b.groups = b.groups[:3]
    scores = []
    for g in b.groups:
        c = b.curves(g)
        for a, z in b.pairs:
            score = float(eig(probability(c[a], c[z], b.settings)[None, :], b.prior)[0])
            scores.append((score, f'{g["id"]}:{a}:{z}'))
    expected = sorted(scores, key=lambda x: (-x[0], x[1]))[0]
    r = b.select(b.prior)
    assert r["eig_bits"] == pytest.approx(expected[0], abs=1e-13)
    assert r["evaluated_candidates"] == 30
    assert b.select(b.prior, [r["id"]])["id"] != r["id"]


def test_boundary_assignment_and_provenance():
    b = Bank()
    assert b.manifest["total_candidates"] == 53172000
    assert len(b.manifest["memberships"]) == 2400
    from collections import Counter

    assert set(Counter(g["grid"] for g in b.groups).values()) == {60}
    for n, limits in b.boundaries.items():
        assert limits["cutpoints"] == sorted(limits["cutpoints"])
    with pytest.raises(ValueError):
        b.map_grid([23, 23])
