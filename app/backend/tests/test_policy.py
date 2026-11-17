import numpy as np
import pytest
from npsdm_app.policy import envelope, fixed_regret
from npsdm_app.science import utility, choose_temperature, welfare, quadrature
from npsdm_app.config import Settings
from types import SimpleNamespace


@pytest.mark.parametrize(
    "d",
    [
        [24, 22, 22, 22, 23],
        [25, 23, 25, 20, 25],
        [22, 22, 25.1, 25.1],
        [19, 21, 24, 28],
    ],
)
def test_envelope_dense_oracle(d):
    s = Settings()
    t = s.temperatures
    segments, points, diag = envelope(t, d, s)
    u = utility(t, d, s)
    for e in np.r_[np.linspace(0, 10, 101), 100, 10000]:
        j = next(i for a, b, i in segments if a <= e < b)
        best = welfare(u, e).max()
        assert welfare(u[j], e) == pytest.approx(best, abs=2e-8)
    assert points[0] == choose_temperature(t, u, 0, s)[0]


def test_fixed_regret_beats_dense_candidates():
    s = Settings(
        question_temperature_min_c=20,
        question_temperature_max_c=27,
        question_temperature_step_c=0.5,
        q_quadrature_count=16,
    )
    nodes, prior = quadrature(s)
    b = SimpleNamespace(
        settings=s,
        temperatures=s.temperatures,
        nodes=nodes,
        prior=prior,
        groups=[
            dict(grid="a", desired=[22, 22, 26]),
            dict(grid="b", desired=[20, 24, 24]),
        ],
    )
    post = {"a": np.eye(16)[1], "b": np.eye(16)[13]}
    result = fixed_regret(b, post)
    for e in np.r_[np.linspace(0, 30, 100), np.inf]:
        cost = 0
        for g in b.groups:
            u = utility(b.temperatures, g["desired"], s)
            j, _ = choose_temperature(b.temperatures, u, e, s)
            w = np.stack([welfare(u, x) for x in nodes])
            cost += float(post[g["grid"]] @ (w.max(axis=1) - w[:, j])) / 2
        assert result["expected_regret"] <= cost + 1e-8
    assert result["expected_regret"] >= 0
