from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from .db import rows, get


def summary(conn, tenant, zone_id, mode, period="daily"):
    zone = get(conn, "zones", tenant, zone_id)["data"]
    tz = ZoneInfo(zone["timezone"])
    decisions = [
        r
        for r in rows(conn, "decision_cycles", tenant, zone_id)
        if r["data"]["mode"] == mode
    ]
    decisions.sort(key=lambda r: r["data"]["observed_at"])
    buckets = {}
    individual = {}
    for i, row in enumerate(decisions):
        d = row["data"]
        start = datetime.fromisoformat(d["observed_at"])
        end = start + timedelta(seconds=zone["cadence_seconds"])
        if i + 1 < len(decisions):
            end = min(
                end, datetime.fromisoformat(decisions[i + 1]["data"]["observed_at"])
            )
        cursor = start
        while cursor < end:
            local = cursor.astimezone(tz)
            next_midnight = datetime.combine(
                local.date() + timedelta(days=1), datetime.min.time(), tzinfo=tz
            ).astimezone(timezone.utc)
            stop = min(end, next_midnight)
            seconds = max(0, (stop - cursor).total_seconds())
            key = (
                local.strftime("%Y-%m")
                if period == "monthly"
                else (
                    (local.date() - timedelta(days=local.weekday())).isoformat()
                    if period == "weekly"
                    else local.date().isoformat()
                )
            )
            b = buckets.setdefault(
                key,
                dict(
                    period=key,
                    coverage_seconds=0,
                    person_seconds=0,
                    utility_person_seconds=0,
                    worst_off_burden_seconds=0,
                    segments=0,
                    missing_environment_seconds=0,
                    measured_seconds_outside_zone_bounds=0,
                    measured_utility_person_seconds=0,
                    measured_person_seconds=0,
                    grid_seconds={},
                ),
            )
            b["coverage_seconds"] += seconds
            b["person_seconds"] += seconds * d["n"]
            b["utility_person_seconds"] += (
                seconds * d["n"] * d["modeled_metrics"]["efficiency"]
            )
            b["worst_off_burden_seconds"] += seconds * (
                1 - d["modeled_metrics"]["equity"]
            )
            b["segments"] += 1
            b["missing_environment_seconds"] += seconds * int(
                d["measured_environment"] is None
            )
            from .science import utility

            if d["measured_environment"] is not None:
                measured = d["measured_environment"]["indoor_temperature_c"]
                b["measured_seconds_outside_zone_bounds"] += seconds * int(
                    measured < zone["min_c"] or measured > zone["max_c"]
                )
                b["measured_utility_person_seconds"] += seconds * float(
                    utility(measured, d["desired"]).sum()
                )
                b["measured_person_seconds"] += seconds * d["n"]
            g = d["grid"] or "OUT_OF_DOMAIN"
            b["grid_seconds"][g] = b["grid_seconds"].get(g, 0) + seconds
            from .science import utility

            for occupant, u in zip(
                d["members"], utility(d["recommended_c"], d["desired"])
            ):
                item = individual.setdefault(
                    occupant,
                    dict(person_seconds=0, utility_seconds=0, burden_seconds=0),
                )
                item["person_seconds"] += seconds
                item["utility_seconds"] += seconds * float(u)
                item["burden_seconds"] += seconds * (1 - float(u))
            cursor = stop
    for b in buckets.values():
        b["exposure_weighted_modeled_utility"] = (
            b["utility_person_seconds"] / b["person_seconds"]
            if b["person_seconds"]
            else None
        )
        b["measured_temperature_based_modeled_utility"] = (
            b["measured_utility_person_seconds"] / b["measured_person_seconds"]
            if b["measured_person_seconds"]
            else None
        )
    origin = "SIMULATED" if mode == "DEMO" else "ACTUAL"
    energy = []
    meter_ends = {}
    for row in sorted(
        rows(conn, "meter_readings", tenant, zone_id),
        key=lambda r: r["data"]["observed_at"],
    ):
        m = row["data"]
        if m["data_origin"] != origin:
            continue
        start = datetime.fromisoformat(m["observed_at"])
        stop = start + timedelta(seconds=m["interval_seconds"])
        if start < meter_ends.get(
            m["meter_id"], datetime.min.replace(tzinfo=timezone.utc)
        ):
            energy.append({"id": row["id"], "status": "OVERLAP_EXCLUDED"})
            continue
        meter_ends[m["meter_id"]] = stop
        energy.append(
            {
                "id": row["id"],
                "meter_id": m["meter_id"],
                "observed_at": m["observed_at"],
                "interval_seconds": m["interval_seconds"],
                "kwh": (
                    m["value"]
                    if m["units"] == "kWh"
                    else m["value"] * m["interval_seconds"] / 3600
                ),
                "status": "VALID",
                "data_origin": origin,
            }
        )
    for v in individual.values():
        v["exposure_weighted_modeled_utility"] = (
            v["utility_seconds"] / v["person_seconds"] if v["person_seconds"] else None
        )
    return dict(
        mode=mode,
        timezone=zone["timezone"],
        period=period,
        aggregation="Nonoverlapping decision exposure intervals capped at configured cadence; recommendation-based modeled utility, not measured comfort",
        buckets=list(buckets.values()),
        individual=individual,
        decision_count=len(decisions),
        series=[dict(id=r["id"], **r["data"]) for r in decisions],
        actions=[
            dict(id=r["id"], **r["data"])
            for r in rows(conn, "operator_actions", tenant, zone_id)
            if r["data"]["decision_id"] in {d["id"] for d in decisions}
        ],
        metering=energy,
        energy_claim="Valid interval metering only; overlapping intervals excluded; no causal energy savings inferred",
    )
