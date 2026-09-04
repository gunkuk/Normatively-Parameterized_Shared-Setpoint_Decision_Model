"""Derive one representative desired setpoint per person."""

from __future__ import annotations

import pandas as pd


def build(observations: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Use the most frequent direct report and resolve ties by mean proximity."""
    representatives = []
    resolutions = []
    for subject, group in observations.groupby("subject", sort=True):
        values = group["desired_setpoint_c"].dropna().to_numpy(dtype=float)
        if len(values) == 0:
            raise ValueError(f"Subject {subject} has no reported desired setpoint")
        counts = pd.Series(values).value_counts()
        highest = int(counts.max())
        candidates = sorted(float(value) for value in counts[counts == highest].index)
        overall_mean = float(values.mean())
        if len(candidates) == 1:
            chosen = candidates[0]
            resolution = "unique_mode"
        else:
            chosen = min(candidates, key=lambda value: (abs(value - overall_mean), value))
            resolution = "nearest_overall_mean"
        representatives.append(
            {
                "subject": int(subject),
                "desired_setpoint_c": chosen,
                "reported_observations": int(len(values)),
                "missing_observations": int(group["desired_setpoint_c"].isna().sum()),
            }
        )
        resolutions.append(
            {
                "subject": int(subject),
                "resolution": resolution,
                "mode_frequency": highest,
                "mode_candidates_c": ";".join(f"{value:g}" for value in candidates),
                "overall_mean_c": overall_mean,
                "selected_setpoint_c": chosen,
            }
        )
    return pd.DataFrame(representatives), pd.DataFrame(resolutions)
