"""Continuous-epsilon fixed regret using upper-envelope crossing partitions.

Question acquisition never uses the policy-only dominance reduction below.
For positive utilities, coordinatewise dominance of sorted utility vectors
implies generalized-mean dominance for every finite epsilon. Endpoint tie
resolution is still evaluated on the full temperature domain.
"""

import hashlib
import json
import numpy as np
from .science import utility, welfare, choose_temperature
from .constraints import exponential_roots
from .config import APP


def qvalue(e):
    return 1.0 if np.isinf(e) else e / (1 + e)


def evalue(q):
    return float("inf") if q >= 1 else q / (1 - q)


def middle(a, b):
    return evalue((qvalue(a) + qvalue(b)) / 2)


def envelope(temps, desired, settings):
    u = utility(temps, desired, settings)
    sorted_u = np.sort(u, axis=1)
    dominated = np.all(sorted_u[:, None, :] >= sorted_u[None, :, :], axis=2) & np.any(
        sorted_u[:, None, :] > sorted_u[None, :, :], axis=2
    )
    active = np.flatnonzero(~dominated.any(axis=0))
    pair_cache = {}
    cuts = {0.0, float("inf")}
    intervals = []

    def crossings(i, j):
        key = tuple(sorted((i, j)))
        if key not in pair_cache:
            a = sorted_u[i]
            b = sorted_u[j]
            if np.array_equal(a, b):
                roots = []
            else:
                roots = [
                    max(0, x + 1)
                    for x in exponential_roots(
                        np.r_[-np.log(a), -np.log(b)],
                        np.r_[np.ones(len(a)), -np.ones(len(b))],
                        xtol=settings.root_tolerance,
                    )
                ]
                roots = [
                    x for x in roots if abs(float(welfare(a, x) - welfare(b, x))) < 1e-8
                ]
            pair_cache[key] = roots
        return pair_cache[key]

    lo = 0.0
    current = choose_temperature(temps, u, 0, settings)[0]
    visited = 0
    while np.isfinite(lo):
        visited += 1
        if visited > 5000:
            raise ValueError("Envelope did not converge; no optimality claim permitted")
        roots = sorted(
            set(
                x
                for j in active
                if j != current
                for x in crossings(current, int(j))
                if x > lo + 1e-8 * (1 + lo)
            )
        )
        edges = [lo] + roots + [float("inf")]
        probe = middle(edges[0], edges[1])
        candidate = choose_temperature(temps, u, probe, settings)[0]
        if candidate != current:
            # Equality at the left endpoint can select a different representative
            # than its right-hand open interval. Repartition using that winner.
            current = candidate
            continue
        changed = False
        for left, right in zip(edges, edges[1:]):
            candidate = choose_temperature(temps, u, middle(left, right), settings)[0]
            cuts.add(left)
            if candidate != current:
                intervals.append((lo, left, current))
                lo = left
                current = candidate
                changed = True
                break
        if not changed:
            intervals.append((lo, float("inf"), current))
            break
    # Only envelope events are needed for intervals, but tangencies can affect
    # the declared tie representative at an isolated point.
    point_choices = {x: choose_temperature(temps, u, x, settings)[0] for x in cuts}
    return (
        intervals,
        point_choices,
        dict(
            pair_comparisons=len(pair_cache),
            active_temperatures=len(active),
            root_tolerance=settings.root_tolerance,
            method="Rolle-partitioned upper-envelope sweep",
        ),
    )


def cached_envelope(temps, desired, settings):
    key = hashlib.sha256(
        json.dumps([temps.tolist(), list(desired), settings.fingerprint]).encode()
    ).hexdigest()
    path = APP / "outputs" / "envelopes" / f"{key}.json"
    if path.exists():
        d = json.loads(path.read_text())
        return (
            [
                (x[0], float("inf") if x[1] is None else x[1], x[2])
                for x in d["intervals"]
            ],
            {
                float("inf") if k == "infinity" else float(k): v
                for k, v in d["points"].items()
            },
            d["diagnostics"],
        )
    result = envelope(temps, desired, settings)
    path.parent.mkdir(parents=True, exist_ok=True)
    d = dict(
        intervals=[(a, None if np.isinf(b) else b, i) for a, b, i in result[0]],
        points={
            ("infinity" if np.isinf(k) else str(k)): v for k, v in result[1].items()
        },
        diagnostics=result[2],
    )
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(d))
    temporary.replace(path)
    return result


def fixed_regret(
    bank,
    grid_posteriors,
    weights=None,
    resolution=None,
    temperature_bounds=None,
    progress=None,
):
    grids = sorted({g["grid"] for g in bank.groups})
    rho = {g: 1 / len(grids) for g in grids} if weights is None else weights
    if (
        set(rho) != set(grids)
        or any(v < 0 or not np.isfinite(v) for v in rho.values())
        or abs(sum(rho.values()) - 1) > 1e-9
    ):
        raise ValueError("Weights must cover all grids and sum to one")
    temps = bank.temperatures
    if temperature_bounds:
        temps = temps[
            (temps >= temperature_bounds[0]) & (temps <= temperature_bounds[1])
        ]
    if not len(temps):
        raise ValueError("Empty feasible domain")
    counts = {g: sum(x["grid"] == g for x in bank.groups) for g in grids}
    events = {0.0: 0.0}
    corrections = {0.0: 0.0, float("inf"): 0.0}
    infinity_cost = 0.0
    diagnostics = []
    provisional = []
    for count, g in enumerate(bank.groups):
        posterior = np.asarray(grid_posteriors.get(g["grid"], bank.prior))
        factor = rho[g["grid"]] / counts[g["grid"]]
        if g["grid"] not in grid_posteriors:
            provisional.append(g["grid"])
        u = utility(temps, g["desired"], bank.settings)
        true_w = np.stack([welfare(u, e) for e in bank.nodes])
        oracle = float(posterior @ true_w.max(axis=1))
        costs = np.maximum(0, oracle - posterior @ true_w) * factor
        segments, points, diag = cached_envelope(temps, g["desired"], bank.settings)
        diagnostics.append(diag)
        prev = 0.0
        for a, b, i in segments:
            events[a] = events.get(a, 0) + float(costs[i]) - prev
            prev = float(costs[i])
        for x, i in points.items():
            if np.isinf(x):
                infinity_cost += float(costs[i])
                continue
            right_index = next(j for a, b, j in segments if a <= x < b)
            corrections[x] = corrections.get(x, 0) + float(
                costs[i] - costs[right_index]
            )
        if progress:
            progress(count + 1, len(bank.groups))
    edges = sorted(set(events) | set(corrections) - {float("inf")})
    current = 0.0
    regions = []
    point_values = []
    for k, x in enumerate(edges):
        current += events.get(x, 0)
        current = max(0, current)
        point_values.append((x, current + corrections.get(x, 0)))
        hi = edges[k + 1] if k + 1 < len(edges) else float("inf")
        regions.append((x, hi, current))
    point_values.append((float("inf"), infinity_cost))
    best = min([v for a, b, v in regions] + [v for x, v in point_values])
    tol = 1e-9
    ranges = [
        dict(
            epsilon_lower=a,
            epsilon_upper=None if np.isinf(b) else b,
            lower_closed=False,
            upper_closed=False,
            regret=v,
        )
        for a, b, v in regions
        if v <= best + tol
    ]
    points = [None if np.isinf(x) else x for x, v in point_values if v <= best + tol]
    representative = (
        points[0]
        if points
        else middle(
            ranges[0]["epsilon_lower"],
            (
                float("inf")
                if ranges[0]["epsilon_upper"] is None
                else ranges[0]["epsilon_upper"]
            ),
        )
    )
    return dict(
        status="PROVISIONAL_MODEL_CONDITIONAL",
        epsilon="infinity" if representative is None else representative,
        expected_regret=float(best),
        minimizer_ranges=ranges,
        minimizer_points=points,
        weights=rho,
        weight_mode="uniform_grid" if weights is None else "observed_frequency",
        continuous_global_optimum_certified=False,
        numerical_global_search=True,
        method="Complete upper-envelope crossing partition; floating-point roots, not formal interval-arithmetic certificate",
        root_tolerance=bank.settings.root_tolerance,
        objective_tolerance=tol,
        unidentified_grids=sorted(set(provisional)),
        pair_comparisons=sum(d["pair_comparisons"] for d in diagnostics),
        temperature_bounds=[float(temps[0]), float(temps[-1])],
        config_hash=bank.settings.fingerprint,
        warning="Model-conditional numerical optimum; uncalibrated likelihood/prior and approximate root locations. Not real-world statistical optimality.",
    )
