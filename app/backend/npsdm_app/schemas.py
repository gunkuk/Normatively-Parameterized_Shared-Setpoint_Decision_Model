from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict, model_validator


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class SessionIn(Strict):
    time_budget_seconds: int = Field(600, ge=0, le=86400)
    seed: int = 0


class Answer(Strict):
    question_id: str
    response: Literal[0, 1, "skip"]
    request_id: str = Field(min_length=8, max_length=128)


class ZoneIn(Strict):
    site_name: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=100)
    timezone: str = "Asia/Seoul"
    min_c: float = Field(18, ge=5, le=40)
    max_c: float = Field(28, ge=5, le=40)
    freshness_seconds: int = Field(3600, ge=60)
    cadence_seconds: int = Field(900, ge=1)

    @model_validator(mode="after")
    def bounds(self):
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

        try:
            ZoneInfo(self.timezone)
        except ZoneInfoNotFoundError:
            raise ValueError("Unknown IANA timezone")
        if self.min_c >= self.max_c:
            raise ValueError("Invalid zone bounds")
        return self


class Observation(Strict):
    zone_id: str
    observed_at: datetime
    data_origin: Literal["ACTUAL", "SIMULATED"]
    source: str = Field(min_length=1, max_length=100)
    occupant_id: str | None = None
    present: bool | None = None
    desired_setpoint_c: float | None = Field(None, ge=5, le=40)
    model_id: str | None = None
    uncertainty_c: float | None = Field(None, ge=0)
    indoor_temperature_c: float | None = Field(None, ge=-20, le=60)
    relative_humidity: float | None = Field(None, ge=0, le=100)
    sensor_id: str | None = None
    comfort_vote: float | None = None
    consent: bool | None = None
    meter_id: str | None = None
    value: float | None = Field(None, ge=0)
    units: Literal["kW", "kWh"] | None = None
    interval_seconds: float | None = Field(None, gt=0)

    @model_validator(mode="after")
    def aware(self):
        if self.observed_at.tzinfo is None:
            raise ValueError("Timezone-aware observed_at required")
        if self.source == "PCM_prediction" and (
            self.model_id is None or self.uncertainty_c is None
        ):
            raise ValueError("Predictions require model_id and uncertainty_c")
        return self


class PolicyIn(Strict):
    zone_id: str
    kind: Literal["COMMON_FIXED", "CONTEXTUAL_BY_GRID", "REGRET_OPTIMAL_FIXED"]
    epsilon: float | Literal["infinity"] = 0
    grid_epsilons: dict[str, float | Literal["infinity"]] = {}
    fallback_epsilon: float | Literal["infinity"] | None = None
    session_id: str | None = None
    weights: dict[str, float] | None = None
    rationale: str = Field(min_length=1)

    @model_validator(mode="after")
    def eps(self):
        for x in [self.epsilon, self.fallback_epsilon, *self.grid_epsilons.values()]:
            if x is not None and x != "infinity" and x < 0:
                raise ValueError("Negative epsilon")
        return self


class DecisionIn(Strict):
    zone_id: str
    policy_id: str
    operation_mode: Literal["DEMO", "REPLAY", "SHADOW", "ASSISTED_LIVE"]
    at: datetime

    @model_validator(mode="after")
    def aware(self):
        if self.at.tzinfo is None:
            raise ValueError("Timezone-aware decision timestamp required")
        return self


class ActionIn(Strict):
    kind: Literal[
        "APPROVED",
        "REJECTED",
        "OVERRIDE",
        "MANUALLY_APPLIED",
        "INDEPENDENTLY_CONFIRMED",
    ]
    setpoint_c: float | None = None
    note: str = Field(min_length=1)
    request_id: str = Field(min_length=8)
