import numpy as np
import pytest
import mpmath as mp
from scipy.optimize import brentq
from npsdm_app.science import *
from npsdm_app.config import Settings
from npsdm_app.constraints import *


@pytest.mark.parametrize("e", [0, 0.5, 1 - 1e-9, 1, 1 + 1e-9, 2, 100, 10000, np.inf])
def test_welfare_independent_high_precision(e):
    mp.mp.dps = 60
    u = np.array([0.001, 0.12, 0.6, 1.0])
    a = [mp.mpf(str(v)) for v in u]
    ref = (
        min(a)
        if np.isinf(e)
        else (
            mp.exp(sum(mp.log(v) for v in a) / 4)
            if e == 1
            else (sum(v ** (1 - mp.mpf(str(e))) for v in a) / 4)
            ** (1 / (1 - mp.mpf(str(e))))
        )
    )
    assert welfare(u, e) == pytest.approx(float(ref), rel=1e-10, abs=1e-12)


def test_utility_grid_and_invalid_settings():
    s = Settings()
    assert len(s.temperatures) == 211
    assert 211 * 210 // 2 == 22155 and 2400 * 22155 == 53172000
    assert utility(22, [22, 28, 40]).tolist() == [1, 0.001, 0.001]
    with pytest.raises(ValueError):
        Settings(question_temperature_step_c=0.13)
    with pytest.raises(ValueError):
        Settings(choice_kappa=float("inf"))
    assert Settings(question_temperature_max_c=32).fingerprint != s.fingerprint


def test_ties_and_metrics():
    s = Settings()
    t = np.array([23.5, 23.6])
    u = utility(t, [22, 22, 25.1, 25.1])
    j, _ = choose_temperature(t, u, np.inf)
    assert j == 0
    t = np.array([22.9, 23.1])
    u = np.array([[0.5, 0.7], [0.7, 0.5]])
    j, a = choose_temperature(t, u, 1)
    k, b = choose_temperature(t, u, 1)
    assert j == k and a == b and len(a["ties"]) == 2
    assert metrics(np.ones(4))["equality"] == 1


def test_eig_oracle_and_update():
    p = np.array([[0.1, 0.8, 0.4], [0.5, 0.5, 0.5]])
    prior = np.array([0.2, 0.3, 0.5])
    ref = 0.0
    for i in range(3):
        for y in [0, 1]:
            py = p[0, i] if y else 1 - p[0, i]
            marg = float(p[0] @ prior) if y else float((1 - p[0]) @ prior)
            ref += prior[i] * py * np.log2(py / marg)
    assert eig(p, prior) == pytest.approx([ref, 0], abs=1e-13)
    assert eig(1 - p, prior) == pytest.approx(eig(p, prior))
    for _ in range(1000):
        prior = update(prior, p[0], 1)
    assert np.isfinite(prior).all() and prior.sum() == pytest.approx(1)


@pytest.mark.parametrize(
    "desired,a,b,root",
    [
        ([24, 22, 22, 22, 23], 22, 23, 3.402858816),
        ([25, 23, 25, 20, 25], 25, 22.5, 1.040219717),
    ],
)
def test_reference_roots(desired, a, b, root):
    u = utility(np.array([a, b]), desired)
    r = brentq(lambda e: welfare(u[0], e) - welfare(u[1], e), 0.01, 10)
    assert r == pytest.approx(root, abs=1e-8)
    cs = consistent_set(u[0], u[1], 1)
    assert cs["converged"]
    assert any(abs(x - root) < 1e-6 for x in cs["roots_epsilon"])


def test_switch_rules_and_singletons():
    assert switch_diagnostics({"a": [[0, 1], [3, None]]})["trigger_B"] is False
    assert switch_diagnostics({"a": [], "b": [[2, 3]]})["trigger_B"] is False
    assert switch_diagnostics({"a": [[0, 1]], "b": [[2, 3]]})["trigger_B"]
    assert not switch_diagnostics({"a": [[0, 1]], "b": [[1, 3]]})["trigger_B"]
    assert intersect([[0, 1]], [[1, None]]) == [[1, 1]]
    assert intersect([[None, None]], [[0, None]]) == [[None, None]]


def test_exponential_multiple_and_tangent_roots():
    # (exp(x)-2)(exp(x)-3) and (exp(x)-2)^2.
    assert exponential_roots([0, 1, 2], [6, -5, 1]) == pytest.approx(
        [np.log(2), np.log(3)], abs=1e-8
    )
    assert exponential_roots([0, 1, 2], [4, -4, 1]) == pytest.approx(
        [np.log(2)], abs=1e-7
    )


def test_dominated_and_identical_sets():
    assert consistent_set([0.5, 0.5], [0.6, 0.6], 1)["intervals"] == [[0, None]]
    assert consistent_set([0.5, 0.5], [0.6, 0.6], 0)["intervals"] == []
    assert consistent_set([0.2, 0.8], [0.8, 0.2], 0)["intervals"] == [[0, None]]


def test_posterior_credible_components_and_prior():
    n, p = quadrature()
    assert not np.isinf(n).any() and (n > 0).all()
    p = np.zeros(64)
    p[10] = 0.5
    p[50] = 0.5
    s = posterior_summary(n, p, observations=2)
    assert len(s["credible_set"]) == 2 and s["endpoint_mass"]["infinity"] == 0


def test_near_touching_conflict_is_not_certified_in_either_order():
    assert not switch_diagnostics({"a": [[1 + 1e-10, 2]], "b": [[0, 1]]})["trigger_B"]
    assert not switch_diagnostics({"b": [[1 + 1e-10, 2]], "a": [[0, 1]]})["trigger_B"]
