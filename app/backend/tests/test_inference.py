import numpy as np
from npsdm_app.bank import Bank
from npsdm_app.inference import infer, sensitivity
from npsdm_app.constraints import consistent_set
from npsdm_app.science import utility, welfare


def test_real_frozen_scenarios_trigger_only_cross_grid_conflict():
    b = Bank()

    def trial(g, a, z):
        return dict(
            group_id=g,
            a=int(round((a - 12) * 10)),
            b=int(round((z - 12) * 10)),
            response=1,
            answered_at="2026-11-17T00:00:00+00:00",
        )

    trials = [trial("N5/R041", 22, 23), trial("N5/R049", 22.5, 25)]
    r = infer(b, trials)
    assert r["stage"] == "CONTEXTUAL"
    assert r["deterministic"]["trigger_B"]
    assert len(r["deterministic"]["switch_witness"]["witness"]) == 2
    assert sum(v["status"] == "UNIDENTIFIED" for v in r["grids"].values()) == 38
    assert len(sensitivity(b, trials)) == 7
    for v in r["grids"].values():
        assert abs(sum(v["weights"]) - 1) < 1e-12


def test_root_regions_against_independent_dense_signs():
    rng = np.random.default_rng(19)
    for _ in range(30):
        desired = rng.uniform(18, 29, 5)
        u = utility(rng.uniform(18, 29, 2), desired)
        for answer in [0, 1]:
            s = consistent_set(u[0], u[1], answer)
            assert s["converged"]
            for e in np.r_[0, 1, np.geomspace(0.001, 10000, 120)]:
                diff = float(welfare(u[1], e) - welfare(u[0], e)) * (
                    1 if answer else -1
                )
                if abs(diff) < 1e-8:
                    continue
                inside = any(
                    (lo is not None and lo <= e) and (hi is None or e <= hi)
                    for lo, hi in s["intervals"]
                )
                assert inside == (diff > 0)
