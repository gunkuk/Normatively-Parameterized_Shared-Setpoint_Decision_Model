from datetime import datetime, timezone
import numpy as np
from .db import rows, get, insert, now
from .science import utility, choose_temperature, metrics, welfare


def epsilon(x):
    return float("inf") if x == "infinity" else float(x)


def decide(conn, tenant, request, bank):
    zone = get(conn, "zones", tenant, request.zone_id)["data"]
    policy = get(conn, "model_policies", tenant, request.policy_id)["data"]
    if policy["status"] != "APPROVED" or policy["zone_id"] != request.zone_id:
        raise ValueError("Approved policy for this zone required")
    if (
        policy["config_hash"] != bank.settings.fingerprint
        or policy["zone_version"] != zone["version"]
    ):
        raise ValueError(
            "Approved policy configuration is stale; review a new policy version"
        )
    origin = "SIMULATED" if request.operation_mode == "DEMO" else "ACTUAL"
    at = request.at.astimezone(timezone.utc)
    if (
        request.operation_mode in ["SHADOW", "ASSISTED_LIVE"]
        and abs((datetime.now(timezone.utc) - at).total_seconds())
        > zone["freshness_seconds"]
    ):
        raise ValueError("Live decision timestamp is stale or in the future")

    def recent(table):
        result = []
        for row in rows(conn, table, tenant, request.zone_id):
            d = row["data"]
            t = datetime.fromisoformat(d["observed_at"]).astimezone(timezone.utc)
            if (
                d["data_origin"] == origin
                and 0 <= (at - t).total_seconds() <= zone["freshness_seconds"]
            ):
                result.append((t, row["id"], d))
        return sorted(result, key=lambda x: (x[0], x[1]))

    presence = {d["occupant_id"]: d for _, _, d in recent("presence_events")}
    occupants = sorted(k for k, d in presence.items() if d["present"])
    preferences = {d["occupant_id"]: d for _, _, d in recent("preference_observations")}
    missing = [k for k in occupants if k not in preferences]
    if not occupants or missing:
        raise ValueError(
            f"MISSING_OR_STALE_PREFERENCES: {missing}; occupants={len(occupants)}"
        )
    desired = [preferences[k]["desired_setpoint_c"] for k in occupants]
    quality = []
    try:
        grid = bank.map_grid(desired)
    except ValueError:
        grid = None
        quality.append("OUT_OF_DOMAIN")
    e = policy["epsilon"]
    if grid is None or (
        policy["kind"] == "CONTEXTUAL_BY_GRID" and grid not in policy["grid_epsilons"]
    ):
        if policy.get("fallback_epsilon") is None:
            raise ValueError(
                "Out-of-domain/unidentified grid requires approved fallback"
            )
        e = policy["fallback_epsilon"]
        quality.append("APPROVED_FALLBACK")
    elif policy["kind"] == "CONTEXTUAL_BY_GRID":
        e = policy["grid_epsilons"][grid]
    temps = bank.temperatures[
        (bank.temperatures >= zone["min_c"]) & (bank.temperatures <= zone["max_c"])
    ]
    u = utility(temps, desired, bank.settings)
    ix, tie = choose_temperature(temps, u, epsilon(e), bank.settings)
    env = recent("environment_readings")
    measured = env[-1][2] if env else None
    if measured is None:
        quality.append("NO_FRESH_ENVIRONMENT")
    snapshot = dict(
        mode=request.operation_mode,
        data_origin=origin,
        zone_id=request.zone_id,
        policy_id=request.policy_id,
        config_hash=bank.settings.fingerprint,
        model_version="npsdm-app-v1",
        policy_version=policy["version"],
        observed_at=at.isoformat(),
        created_at=now(),
        members=occupants,
        desired=desired,
        n=len(desired),
        sd=float(np.std(desired)),
        grid=grid,
        epsilon=e,
        recommended_c=float(temps[ix]),
        modeled_metrics={k: float(v) for k, v in metrics(u[ix]).items()},
        measured_environment=measured,
        quality=quality,
        tie=tie,
        feasible_temperatures=temps.tolist(),
    )
    snapshot["counterfactuals"] = []
    for p in rows(conn, "model_policies", tenant, request.zone_id):
        d = p["data"]
        if d["status"] != "APPROVED":
            continue
        ce = (
            d["grid_epsilons"].get(grid, d.get("fallback_epsilon"))
            if d["kind"] == "CONTEXTUAL_BY_GRID"
            else d["epsilon"]
        )
        if grid is None:
            ce = d.get("fallback_epsilon")
        if ce is None:
            continue
        ci, _ = choose_temperature(temps, u, epsilon(ce), bank.settings)
        snapshot["counterfactuals"].append(
            dict(
                policy_id=p["id"],
                kind=d["kind"],
                recommended_c=float(temps[ci]),
                metrics={k: float(v) for k, v in metrics(u[ci]).items()},
                interpretation="Modeled on identical observed-group snapshot",
            )
        )
    return snapshot
