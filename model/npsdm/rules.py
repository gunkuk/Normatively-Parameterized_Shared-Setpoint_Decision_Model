"""Conventional and Atkinson shared-setpoint decision rules."""

from __future__ import annotations

import hashlib
import math

import numpy as np

from . import settings
from .social import atkinson
from .utility import thermal_utility


GRID = np.round(
    settings.SETPOINT_MIN_C
    + np.arange(
        int(round((settings.SETPOINT_MAX_C - settings.SETPOINT_MIN_C) / settings.SETPOINT_STEP_C))
        + 1
    )
    * settings.SETPOINT_STEP_C,
    10,
)


def _pmv_fanger(ta: float, tr: float, vel: float, rh: float, met: float, clo: float) -> float:
    """Calculate PMV using the ISO 7730 heat-balance iteration."""
    pa = rh * 10.0 * math.exp(16.6536 - 4030.183 / (ta + 235.0))
    icl = 0.155 * clo
    m = met * 58.15
    mw = m
    fcl = 1.05 + 0.645 * icl if icl > 0.078 else 1.0 + 1.29 * icl
    hcf = 12.1 * math.sqrt(vel)
    taa = ta + 273.0
    tra = tr + 273.0
    tcla = taa + (35.5 - ta) / (3.5 * icl + 0.1)
    p1 = icl * fcl
    p2 = p1 * 3.96
    p3 = p1 * 100.0
    p4 = p1 * taa
    p5 = 308.7 - 0.028 * mw + p2 * (tra / 100.0) ** 4
    xn = tcla / 100.0
    hc = hcf
    for _ in range(150):
        previous = xn
        hcn = 2.38 * abs(100.0 * previous - taa) ** 0.25
        hc = max(hcf, hcn)
        xn = (p5 + p4 * hc - p2 * previous**4) / (100.0 + p3 * hc)
        if abs(xn - previous) <= 1e-5:
            break
    tcl = 100.0 * xn - 273.0
    hl1 = 3.05e-3 * (5733.0 - 6.99 * mw - pa)
    hl2 = 0.42 * (mw - 58.15) if mw > 58.15 else 0.0
    hl3 = 1.7e-5 * m * (5867.0 - pa)
    hl4 = 0.0014 * m * (34.0 - ta)
    hl5 = 3.96 * fcl * (xn**4 - (tra / 100.0) ** 4)
    hl6 = fcl * hc * (tcl - ta)
    thermal_load = mw - hl1 - hl2 - hl3 - hl4 - hl5 - hl6
    return (0.303 * math.exp(-0.036 * m) + 0.028) * thermal_load


def metabolic_rate(people) -> np.ndarray:
    """Estimate met from sex, age, mass, and height."""
    values = []
    for row in people.itertuples(index=False):
        height_cm = float(row.height_m) * 100.0
        bmr = 10.0 * row.weight_kg + 6.25 * height_cm - 5.0 * row.age
        bmr += 5.0 if int(row.sex) == 1 else -161.0
        bmr_w = bmr * 4184.0 / 86400.0
        body_surface_area = 0.007184 * row.weight_kg**0.425 * height_cm**0.725
        values.append((bmr_w / body_surface_area) / 58.15)
    values = np.asarray(values, dtype=float)
    return np.clip(values * (settings.PMV_REFERENCE_MET / values.mean()), 0.8, 2.0)


def _tie_index(scores: np.ndarray, key: str) -> int:
    """Resolve a grid tie with a stable hash-derived uniform choice."""
    best = float(np.max(scores))
    indices = np.flatnonzero(scores >= best - 1e-12)
    if len(indices) == 1:
        return int(indices[0])
    digest = hashlib.sha256(key.encode("utf-8")).digest()
    rng = np.random.default_rng(int.from_bytes(digest[:8], "little"))
    return int(indices[rng.integers(len(indices))])


def choose(
    rule: str,
    desired: np.ndarray,
    met: np.ndarray,
    epsilon: float | None,
    key: str,
) -> float:
    """Choose one shared setpoint for a group."""
    if rule == "mean":
        return float(np.mean(desired))
    if rule == "median":
        return float(np.median(desired))
    if rule == "pmv":
        scores = np.asarray(
            [
                -abs(
                    np.mean(
                        [
                            _pmv_fanger(
                                t,
                                t,
                                settings.PMV_AIR_SPEED_M_S,
                                settings.PMV_RELATIVE_HUMIDITY,
                                m,
                                settings.PMV_CLO,
                            )
                            for m in met
                        ]
                    )
                )
                for t in GRID
            ]
        )
    elif rule == "threshold_coverage":
        scores = (
            np.abs(GRID[:, None] - desired[None, :]) <= settings.COVERAGE_BAND_C + 1e-12
        ).sum(axis=1)
    elif rule == "atkinson":
        if epsilon is None:
            raise ValueError("Atkinson requires epsilon")
        scores = np.asarray([atkinson(thermal_utility(t, desired), epsilon) for t in GRID])
    else:
        raise ValueError(f"Unknown rule: {rule}")
    return float(GRID[_tie_index(scores, key)])
