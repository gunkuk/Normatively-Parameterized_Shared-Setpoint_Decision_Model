import hashlib
import numpy as np
from scipy.special import logsumexp, expit, xlogy
from scipy.stats import beta
from .config import SETTINGS


def utility(temperatures, desired, settings=SETTINGS):
    d = np.asarray(desired, dtype=float)
    if d.ndim != 1 or not len(d) or not np.isfinite(d).all():
        raise ValueError("Desired setpoints must be a nonempty finite vector")
    return np.clip(
        1 - np.abs(np.asarray(temperatures)[..., None] - d) / settings.utility_width_c,
        settings.utility_floor,
        1,
    )


def welfare(u, epsilon):
    u = np.asarray(u, dtype=float)
    if not np.isfinite(u).all() or np.any(u <= 0) or u.shape[-1] == 0:
        raise ValueError("Positive finite utilities required")
    if epsilon < 0 or np.isnan(epsilon):
        raise ValueError("epsilon must be nonnegative")
    if np.isinf(epsilon):
        return np.min(u, axis=-1)
    logs = np.log(u)
    r = 1 - float(epsilon)
    center = logs.mean(axis=-1)
    if abs(r) < 1e-7:
        delta = logs - center[..., None]
        return np.exp(
            center
            + r * np.mean(delta**2, axis=-1) / 2
            + r * r * np.mean(delta**3, axis=-1) / 6
        )
    return np.exp((logsumexp(r * logs, axis=-1) - np.log(u.shape[-1])) / r)


def metrics(u):
    u = np.asarray(u, dtype=float)
    mean = u.mean(axis=-1)
    gini = np.abs(u[..., :, None] - u[..., None, :]).mean(axis=(-2, -1)) / (2 * mean)
    return {
        "efficiency": mean,
        "equity": u.min(axis=-1),
        "equality": 1 - gini,
        "total": u.sum(axis=-1),
    }


def choose_temperature(temperatures, u, epsilon, settings=SETTINGS):
    t = np.asarray(temperatures)
    w = welfare(u, epsilon)
    tol = settings.comparison_tolerance
    ids = np.flatnonzero(w >= w.max() - tol)
    m = metrics(u)
    keep = []
    for i in ids:
        dominates = (
            (m["efficiency"][ids] >= m["efficiency"][i] - tol)
            & (m["equity"][ids] >= m["equity"][i] - tol)
            & (
                (m["efficiency"][ids] > m["efficiency"][i] + tol)
                | (m["equity"][ids] > m["equity"][i] + tol)
            )
        )
        if not dominates.any():
            keep.append(i)
    ids = np.array(keep, dtype=int)
    ids = ids[m["equality"][ids] >= m["equality"][ids].max() - tol]
    distances = np.abs(t[ids] - settings.reference_temperature_c)
    ids = ids[distances <= distances.min() + tol]
    seed = int.from_bytes(
        hashlib.sha256(
            np.asarray(u, dtype="<f8").tobytes()
            + t.astype("<f8").tobytes()
            + settings.fingerprint.encode()
        ).digest()[:8],
        "little",
    )
    chosen = int(ids[np.random.default_rng(seed).integers(len(ids))])
    return chosen, {
        "ties": ids.tolist(),
        "seed": str(seed),
        "rule": "welfare-pareto-equality-distance23-seeded-v1",
    }


def quadrature(settings=SETTINGS):
    q = (np.arange(settings.q_quadrature_count) + 0.5) / settings.q_quadrature_count
    weights = (
        np.ones(len(q))
        if settings.prior_family == "uniform"
        else beta.pdf(q, settings.prior_alpha, settings.prior_beta)
    )
    return q / (1 - q), weights / weights.sum()


def probability(wa, wb, settings=SETTINGS):
    return settings.choice_lapse / 2 + (1 - settings.choice_lapse) * expit(
        settings.choice_kappa * (wb - wa)
    )


def entropy(p):
    return -(xlogy(p, p) + xlogy(1 - p, 1 - p)) / np.log(2)


def eig(probabilities, posterior):
    p = np.asarray(probabilities)
    return np.maximum(0, entropy(p @ posterior) - entropy(p) @ posterior)


def update(posterior, probabilities, response):
    likelihood = probabilities if response else 1 - probabilities
    logp = np.log(np.maximum(posterior, np.finfo(float).tiny)) + np.log(
        np.maximum(likelihood, np.finfo(float).tiny)
    )
    return np.exp(logp - logsumexp(logp))


def posterior_summary(nodes, weights, mass=0.95, observations=0):
    q = nodes / (1 + nodes)
    order = np.argsort(-weights, kind="stable")
    selected = np.zeros(len(weights), bool)
    selected[order[: np.searchsorted(np.cumsum(weights[order]), mass) + 1]] = True
    edges = np.linspace(0, 1, len(q) + 1)
    components = []
    for ix in np.split(
        np.flatnonzero(selected), np.where(np.diff(np.flatnonzero(selected)) > 1)[0] + 1
    ):
        if len(ix):
            lo, hi = edges[ix[0]], edges[ix[-1] + 1]
            components.append(
                [float(lo / (1 - lo)), None if hi == 1 else float(hi / (1 - hi))]
            )
    warnings = []
    if selected[0] or selected[-1]:
        warnings.append("BOUNDARY_TAIL_UNIDENTIFIED")
    if len(components) > 1:
        warnings.append("MULTIMODAL_CREDIBLE_SET")
    return dict(
        status="ESTIMATED_UNCALIBRATED" if observations else "UNIDENTIFIED",
        median=float(nodes[np.searchsorted(np.cumsum(weights), 0.5)]),
        credible_set=components,
        requested_mass=mass,
        attained_mass=float(weights[selected].sum()),
        nodes=nodes.tolist(),
        weights=weights.tolist(),
        warnings=warnings,
        endpoint_mass={"zero": 0, "infinity": 0},
    )
