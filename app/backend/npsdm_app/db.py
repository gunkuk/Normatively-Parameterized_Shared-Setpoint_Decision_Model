import os
import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    create_engine,
    MetaData,
    Table,
    Column,
    String,
    DateTime,
    JSON,
    Index,
    UniqueConstraint,
    select,
)

URL = os.environ.get("DATABASE_URL", "sqlite:///./app-local.db")
engine = create_engine(
    URL,
    pool_pre_ping=True,
    connect_args={"check_same_thread": False} if URL.startswith("sqlite") else {},
)
metadata = MetaData()
NAMES = [
    "sites",
    "zones",
    "users",
    "roles",
    "occupants",
    "presence_events",
    "preference_observations",
    "environment_readings",
    "thermal_feedback",
    "meter_readings",
    "elicitation_sessions",
    "elicitation_trials",
    "posterior_checkpoints",
    "scenario_bank_versions",
    "model_policies",
    "decision_cycles",
    "operator_actions",
    "audit_events",
    "dataset_ingests",
]
tables = {}
for name in NAMES:
    tables[name] = Table(
        name,
        metadata,
        Column("id", String, primary_key=True),
        Column("tenant_id", String, nullable=False),
        Column("zone_id", String, nullable=True),
        Column("timestamp", DateTime(timezone=True), nullable=False),
        Column("data", JSON, nullable=False),
        Column("idempotency_key", String, nullable=True),
        UniqueConstraint("tenant_id", "idempotency_key", name=f"uq_{name}_idempotency"),
    )
    Index(
        f"ix_{name}_scope_time",
        tables[name].c.tenant_id,
        tables[name].c.zone_id,
        tables[name].c.timestamp,
    )


def now():
    return datetime.now(timezone.utc).isoformat()


def insert(conn, name, tenant, data, zone=None, id=None, key=None):
    identifier = id or str(uuid.uuid4())
    conn.execute(
        tables[name]
        .insert()
        .values(
            id=identifier,
            tenant_id=tenant,
            zone_id=zone,
            timestamp=datetime.now(timezone.utc),
            data=data,
            idempotency_key=key,
        )
    )
    return identifier


def get(conn, name, tenant, identifier, lock=False):
    q = select(tables[name]).where(
        tables[name].c.id == identifier, tables[name].c.tenant_id == tenant
    )
    if lock:
        q = q.with_for_update()
    row = conn.execute(q).mappings().first()
    if not row:
        raise KeyError(identifier)
    return dict(row)


def rows(conn, name, tenant, zone=None):
    q = select(tables[name]).where(tables[name].c.tenant_id == tenant)
    if zone:
        q = q.where(tables[name].c.zone_id == zone)
    return [
        dict(r)
        for r in conn.execute(
            q.order_by(tables[name].c.timestamp, tables[name].c.id)
        ).mappings()
    ]


def replace(conn, name, tenant, identifier, data):
    conn.execute(
        tables[name]
        .update()
        .where(tables[name].c.id == identifier, tables[name].c.tenant_id == tenant)
        .values(data=data)
    )


def audit(conn, actor, event, resource, details=None):
    insert(
        conn,
        "audit_events",
        actor["tenant"],
        dict(
            actor=actor["id"],
            event=event,
            resource=resource,
            details=details or {},
            at=now(),
        ),
    )
