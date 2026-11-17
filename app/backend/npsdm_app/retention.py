"""Explicit, dry-run-first retention of source observations; snapshots stay auditable."""

import argparse
from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from . import db

TABLES = [
    "presence_events",
    "preference_observations",
    "environment_readings",
    "thermal_feedback",
    "meter_readings",
]


def retain(conn, tenant, days, apply=False, at=None):
    if days < 1:
        raise ValueError("Retention must be at least one day")
    cutoff = (at or datetime.now(timezone.utc)) - timedelta(days=days)
    candidates = {}
    for name in TABLES:
        candidates[name] = [
            r["id"]
            for r in db.rows(conn, name, tenant)
            if datetime.fromisoformat(r["data"]["observed_at"]).astimezone(timezone.utc)
            < cutoff
        ]
    if apply:
        for name, ids in candidates.items():
            if ids:
                conn.execute(
                    db.tables[name]
                    .delete()
                    .where(
                        db.tables[name].c.tenant_id == tenant,
                        db.tables[name].c.id.in_(ids),
                    )
                )
        db.insert(
            conn,
            "audit_events",
            tenant,
            dict(
                event="RETENTION_APPLIED",
                days=days,
                counts={k: len(v) for k, v in candidates.items()},
                at=db.now(),
                scope="source observations only; decision snapshots and opaque IDs retained",
            ),
        )
    return dict(
        applied=apply,
        cutoff=cutoff.isoformat(),
        counts={k: len(v) for k, v in candidates.items()},
        scope="source observations only; not a full subject-erasure workflow",
    )


if __name__ == "__main__":
    import json

    p = argparse.ArgumentParser()
    p.add_argument("--tenant", required=True)
    p.add_argument("--days", type=int, required=True)
    p.add_argument("--apply", action="store_true")
    args = p.parse_args()
    with db.engine.begin() as conn:
        print(json.dumps(retain(conn, args.tenant, args.days, args.apply), indent=2))
