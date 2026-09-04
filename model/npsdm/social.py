"""Social welfare and distribution measures."""

from __future__ import annotations

import numpy as np


def gini(values: np.ndarray) -> float:
    """Return the Gini coefficient for a non-negative utility vector."""
    x = np.sort(np.asarray(values, dtype=float))
    if len(x) == 0 or float(x.sum()) <= 0:
        return 0.0
    n = len(x)
    return float((2 * np.dot(np.arange(1, n + 1), x) / (n * x.sum())) - (n + 1) / n)


def cvar(values: np.ndarray, fraction: float = 0.10) -> float:
    """Return the mean utility in the lower fraction of the group."""
    x = np.sort(np.asarray(values, dtype=float))
    if len(x) == 0:
        return float("nan")
    count = max(1, int(np.ceil(len(x) * fraction)))
    return float(x[:count].mean())


def atkinson(values: np.ndarray, epsilon: float) -> float:
    """Return Atkinson equally distributed equivalent utility."""
    x = np.asarray(values, dtype=float)
    if len(x) == 0 or np.any(x <= 0):
        raise ValueError("Atkinson utility must be strictly positive")
    if np.isinf(epsilon):
        return float(x.min())
    if abs(epsilon - 1.0) < 1e-12:
        return float(np.exp(np.mean(np.log(x))))
    return float(np.mean(x ** (1.0 - epsilon)) ** (1.0 / (1.0 - epsilon)))
