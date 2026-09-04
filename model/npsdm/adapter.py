"""Load and validate the compact direct-observation input."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from . import settings


@dataclass(frozen=True)
class Dataset:
    observations: pd.DataFrame
    people: pd.DataFrame
    contract: dict


def load(path: Path) -> Dataset:
    """Expand the one-row-per-person file and enforce the data contract."""
    raw = pd.read_csv(path, keep_default_na=False)
    required = {
        "subject",
        "sex",
        "age",
        "weight_kg",
        "height_m",
        "desired_setpoints_c",
    }
    missing = required.difference(raw.columns)
    if missing:
        raise ValueError(f"Missing input columns: {sorted(missing)}")
    forbidden = [
        column
        for column in raw.columns
        if any(token in column.lower() for token in ("energy", "energyplus"))
    ]
    if forbidden:
        raise ValueError(f"Forbidden input columns: {forbidden}")
    if len(raw) != settings.EXPECTED_SUBJECTS:
        raise ValueError(f"Expected {settings.EXPECTED_SUBJECTS} people, found {len(raw)}")
    if raw["subject"].duplicated().any():
        raise ValueError("Each subject must occur exactly once in the compact input")

    people = raw[["subject", "sex", "age", "weight_kg", "height_m"]].copy()
    for column in ("subject", "sex", "age", "weight_kg", "height_m"):
        people[column] = pd.to_numeric(people[column], errors="raise")
    if not set(people["sex"].astype(int)).issubset({0, 1}):
        raise ValueError("sex must use 0=female and 1=male")
    if (people[["weight_kg", "height_m"]] <= 0).any().any():
        raise ValueError("weight_kg and height_m must be positive")
    people["subject"] = people["subject"].astype(int)
    people["sex"] = people["sex"].astype(int)
    people["age"] = people["age"].astype(int)
    people["bmi"] = people["weight_kg"] / people["height_m"] ** 2

    rows = []
    for record in raw.itertuples(index=False):
        values = str(record.desired_setpoints_c).split(";")
        if len(values) != settings.OBSERVATIONS_PER_SUBJECT:
            raise ValueError(
                f"Subject {record.subject} must have exactly "
                f"{settings.OBSERVATIONS_PER_SUBJECT} observations"
            )
        for observation, value in enumerate(values):
            desired = np.nan if value.strip().upper() in {"", "NA", "N/A"} else float(value)
            rows.append(
                {
                    "subject": int(record.subject),
                    "observation": observation,
                    "desired_setpoint_c": desired,
                }
            )

    observations = pd.DataFrame(rows).merge(
        people, on="subject", how="left", validate="many_to_one"
    )
    if len(observations) != settings.EXPECTED_OBSERVATIONS:
        raise ValueError(
            f"Expected {settings.EXPECTED_OBSERVATIONS} observations, found {len(observations)}"
        )
    if observations["desired_setpoint_c"].notna().sum() == 0:
        raise ValueError("At least one direct desired-setpoint observation is required")
    observed_values = observations["desired_setpoint_c"].dropna()
    if not observed_values.between(10, 40).all():
        raise ValueError("Desired setpoints must be plausible Celsius temperatures")
    missing_desired = int(observations["desired_setpoint_c"].isna().sum())
    if missing_desired != settings.EXPECTED_MISSING_DESIRED:
        raise ValueError(
            f"Expected {settings.EXPECTED_MISSING_DESIRED} missing observations, found {missing_desired}"
        )

    contract = {
        "subjects": int(observations["subject"].nunique()),
        "observations": int(len(observations)),
        "observations_per_subject": settings.OBSERVATIONS_PER_SUBJECT,
        "missing_desired_setpoints": missing_desired,
        "sex_encoding": {"0": "female", "1": "male"},
    }
    return Dataset(observations=observations, people=people, contract=contract)
