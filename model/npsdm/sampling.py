"""Deterministic random sampling of synthetic occupant groups."""

from __future__ import annotations

import hashlib

import numpy as np


def cell_seed(group_size: int, base_seed: int) -> int:
    """Derive a stable seed for one group-size cell."""
    digest = hashlib.sha256(f"{base_seed}:group_size:{group_size}".encode("ascii")).digest()
    return int.from_bytes(digest[:8], "little")


def sample_groups(
    subjects: np.ndarray, group_size: int, repetitions: int, base_seed: int
) -> list[np.ndarray]:
    """Sample distinct occupants within each group and allow reuse across groups."""
    subjects = np.asarray(sorted(subjects), dtype=int)
    if group_size > len(subjects):
        raise ValueError(f"Group size {group_size} exceeds the cohort size {len(subjects)}")
    rng = np.random.default_rng(cell_seed(group_size, base_seed))
    return [rng.choice(subjects, size=group_size, replace=False) for _ in range(repetitions)]
