from pathlib import Path
import hashlib
import json
import numpy as np
import yaml
from pydantic import BaseModel, Field, model_validator, ConfigDict

APP = Path(__file__).resolve().parents[2]
ROOT = APP.parent


class Settings(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False, extra="forbid")
    version: int = 1
    question_temperature_min_c: float = 12
    question_temperature_max_c: float = 33
    question_temperature_step_c: float = 0.1
    utility_width_c: float = 6
    utility_floor: float = 0.001
    group_sizes: list[int] = list(range(3, 11))
    heterogeneity_quantiles: int = 5
    q_quadrature_count: int = Field(64, ge=8, le=2048)
    prior_family: str = "uniform"
    prior_alpha: float = Field(1, gt=0)
    prior_beta: float = Field(1, gt=0)
    choice_kappa: float = Field(30, gt=0)
    choice_lapse: float = Field(0.05, ge=0, lt=1)
    experiment_time_budget: int = Field(600, ge=0)
    posterior_mass: float = Field(0.95, gt=0, lt=1)
    mode_switch_rule: str = "B"
    comparison_tolerance: float = Field(1e-10, gt=0)
    root_tolerance: float = Field(1e-9, gt=0)
    pair_block_size: int = Field(4096, ge=1)
    precision: str = "float64"
    reference_temperature_c: float = 23

    @model_validator(mode="after")
    def validate_science(self):
        a, b, h = (
            self.question_temperature_min_c,
            self.question_temperature_max_c,
            self.question_temperature_step_c,
        )
        if (
            not np.isfinite([a, b, h, self.utility_width_c, self.utility_floor]).all()
            or h <= 0
            or b <= a
        ):
            raise ValueError(
                "Finite increasing temperature bounds and positive step required"
            )
        if abs((b - a) / h - round((b - a) / h)) > 1e-8 or (b - a) / h > 5000:
            raise ValueError(
                "Grid must include both endpoints and contain at most 5001 temperatures"
            )
        if self.utility_width_c <= 0 or not 0 < self.utility_floor < 1:
            raise ValueError("Invalid utility settings")
        if self.group_sizes != list(range(3, 11)) or self.heterogeneity_quantiles != 5:
            raise ValueError("Frozen source supports N=3..10 and five quintiles only")
        if (
            self.mode_switch_rule != "B"
            or self.precision != "float64"
            or self.prior_family not in ["uniform", "beta"]
        ):
            raise ValueError("Unsupported scientific configuration")
        return self

    @property
    def temperatures(self):
        return np.round(
            np.linspace(
                self.question_temperature_min_c,
                self.question_temperature_max_c,
                round(
                    (self.question_temperature_max_c - self.question_temperature_min_c)
                    / self.question_temperature_step_c
                )
                + 1,
            ),
            10,
        )

    @property
    def fingerprint(self):
        return hashlib.sha256(
            json.dumps(self.model_dump(), sort_keys=True).encode()
        ).hexdigest()


SETTINGS = Settings(**yaml.safe_load((APP / "SETTINGS.yaml").read_text()))
