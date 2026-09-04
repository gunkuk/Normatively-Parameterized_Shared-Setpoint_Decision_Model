"""Common individual thermal utility mapping."""

from __future__ import annotations

import numpy as np

from . import settings


def thermal_utility(setpoint_c: float, desired_c: np.ndarray) -> np.ndarray:
    """Map absolute temperature deviation to a bounded triangular utility."""
    desired = np.asarray(desired_c, dtype=float)
    return np.clip(
        1.0 - np.abs(desired - float(setpoint_c)) / settings.UTILITY_WIDTH_C,
        settings.UTILITY_FLOOR,
        1.0,
    )
