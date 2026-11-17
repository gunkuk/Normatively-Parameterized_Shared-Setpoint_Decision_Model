"""Numerical exponential-polynomial root isolation with a dominant-tail bound.

Rolle recursion partitions into monotone intervals; unlike a fixed epsilon
mesh this can retain tangencies and arbitrarily separated crossings. Root
locations remain floating-point approximations, not analytic certificates.
"""

import numpy as np
from scipy.optimize import brentq
from .science import welfare


def exponential_roots(rates, coefficients, lower=-1.0, xtol=1e-10):
    rates = np.asarray(rates, float)
    coefficients = np.asarray(coefficients, float)
    unique = np.unique(rates)
    c = np.array([coefficients[rates == v].sum() for v in unique])
    keep = c != 0
    b = unique[keep]
    c = c[keep]
    if len(c) < 2:
        return []
    order = np.argsort(b)
    b = b[order]
    c = c[order]
    b = b - b[-1]
    c = c / np.max(np.abs(c))

    def f(x):
        terms = b * x
        offset = max(0, float(terms.max()))
        return float(np.dot(c, np.exp(terms - offset)))

    # Beyond this bound the constant term exceeds the sum of every decaying term.
    upper = max(
        lower + 1, float(np.log(2 * np.sum(np.abs(c[:-1])) / abs(c[-1])) / (-b[-2]))
    )
    critical = exponential_roots(b[:-1], c[:-1] * b[:-1], lower, xtol)
    points = [lower] + [x for x in critical if lower < x < upper] + [upper]
    roots = []
    for x in points:
        if abs(f(x)) < 1e-12:
            roots.append(x)
    for a, z in zip(points[:-1], points[1:]):
        if f(a) * f(z) < 0:
            roots.append(brentq(f, a, z, xtol=xtol, rtol=1e-14))
    return sorted(set(round(x, 12) for x in roots))


def consistent_set(a, b, response, xtol=1e-10):
    a = np.asarray(a, float)
    b = np.asarray(b, float)
    if len(a) != len(b):
        raise ValueError("Same group required")
    if np.array_equal(np.sort(a), np.sort(b)):
        return {
            "intervals": [[0, None]],
            "method": "identical-multiset",
            "converged": True,
            "root_tolerance": xtol,
        }
    rates = np.r_[-np.log(a), -np.log(b)]
    coeff = np.r_[np.ones(len(a)), -np.ones(len(b))]
    r1 = exponential_roots(rates, coeff, xtol=xtol)
    r2 = exponential_roots(rates, coeff, xtol=xtol / 4)
    converged = len(r1) == len(r2) and all(
        abs(x - y) <= max(xtol * 20, 1e-7 * (1 + abs(x))) for x, y in zip(r1, r2)
    )
    # r=1-e changes sign at e=1; the power-sum root there is automatic,
    # and must not be mistaken for equality of the geometric means.
    candidates = [0.0] + [max(0, x + 1) for x in r2] + [1.0]
    points = sorted(set(candidates))
    intervals = []
    sign = 1 if response else -1

    def diff(e):
        return sign * float(welfare(b, e) - welfare(a, e))

    for lo, hi in zip(points, points[1:] + [float("inf")]):
        mid = (lo + hi) / 2 if np.isfinite(hi) else lo + max(1, lo)
        if diff(mid) > 0:
            intervals.append([lo, None if np.isinf(hi) else hi])
    for x in points:
        if abs(diff(x)) <= 1e-10:
            intervals.append([x, x])
    # Infinity is an exact endpoint, including a singleton if minima coincide.
    if diff(float("inf")) >= 0:
        intervals.append([None, None])
    return {
        "intervals": merge(intervals),
        "method": "exponential-polynomial-Rolle-tail-bound",
        "converged": converged,
        "root_tolerance": xtol,
        "roots_epsilon": [x for x in points if abs(diff(x)) <= 1e-10],
    }


def val(x):
    return float("inf") if x is None else x


def merge(intervals):
    out = []
    for lo, hi in sorted(intervals, key=lambda x: val(x[0])):
        if out and val(lo) <= val(out[-1][1]) + 1e-9:
            out[-1][1] = (
                None if hi is None or out[-1][1] is None else max(hi, out[-1][1])
            )
        else:
            out.append([lo, hi])
    return out


def intersect(a, b):
    out = []
    for x, y in a:
        for z, w in b:
            lo = max(val(x), val(z))
            hi = min(val(y), val(w))
            if lo <= hi:
                out.append([None if np.isinf(lo) else lo, None if np.isinf(hi) else hi])
    return merge(out)


def switch_diagnostics(grid_sets, verified=True):
    keys = sorted(k for k, v in grid_sets.items() if v)
    witness = None
    if verified:
        for i, g in enumerate(keys):
            for h in keys[i + 1 :]:
                if not intersect(grid_sets[g], grid_sets[h]):
                    # Require separation in compact q space above root uncertainty.
                    def compact(x):
                        return 1.0 if x is None else x / (1 + x)

                    distance = min(
                        max(0.0, compact(a) - compact(d), compact(c) - compact(b))
                        for a, b in grid_sets[g]
                        for c, d in grid_sets[h]
                    )
                    if distance > 1e-7:
                        witness = [g, h]
                        break
            if witness:
                break
    common = [[0, None]]
    for s in grid_sets.values():
        common = intersect(common, s)
    return dict(
        trigger_B=witness is not None,
        witness=witness,
        common=common,
        within_grid_inconsistent=[k for k, v in grid_sets.items() if not v],
        disconnected=[k for k, v in grid_sets.items() if len(v) > 1],
        status=(
            "B_CONFLICT"
            if witness
            else (
                "COMMON_NOT_STRICTLY_COMPATIBLE" if not common else "COMMON_COMPATIBLE"
            )
        ),
        numerically_verified=verified,
    )
