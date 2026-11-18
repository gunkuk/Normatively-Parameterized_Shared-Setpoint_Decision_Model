import os, json, hashlib
from datetime import datetime, timezone
import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient
from npsdm_app import db, api


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(api.acquisition, "prefetch", lambda *args: None)
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    monkeypatch.setattr(db, "engine", engine)
    db.metadata.create_all(engine)
    users = [
        dict(
            id=r, tenant=t, role=r, token_sha256=hashlib.sha256(k.encode()).hexdigest()
        )
        for r, t, k in [
            ("Admin", "a", "admin"),
            ("Viewer", "a", "viewer"),
            ("Operator", "b", "other"),
        ]
    ]
    monkeypatch.setenv("NPSDM_USERS", json.dumps(users))
    with TestClient(api.app) as c:
        c.headers["Authorization"] = "Bearer admin"
        yield c
    engine.dispose()


def zone(c):
    r = c.post("/api/v1/sites/zones", json={"site_name": "test", "name": "test-zone"})
    assert r.status_code == 200, r.text
    return r.json()["id"]


def policy(c, z):
    r = c.post(
        "/api/v1/policies/draft",
        json=dict(
            zone_id=z,
            kind="COMMON_FIXED",
            epsilon=1,
            rationale="test explicit assumption",
            fallback_epsilon=1,
        ),
    )
    assert r.status_code == 200, r.text
    p = r.json()["id"]
    assert c.post(f"/api/v1/policies/{p}/approve").status_code == 200
    return p


def test_auth_and_tenant_isolation(client):
    z = zone(client)
    client.headers["Authorization"] = "Bearer viewer"
    assert (
        client.post(
            "/api/v1/sites/zones", json={"site_name": "x", "name": "x"}
        ).status_code
        == 403
    )
    client.headers["Authorization"] = "Bearer other"
    assert client.get("/api/v1/sites/zones").json() == []
    assert (
        client.post(
            "/api/v1/policies/draft",
            json=dict(zone_id=z, kind="COMMON_FIXED", rationale="x"),
        ).status_code
        == 404
    )
    client.headers["Authorization"] = "Bearer bad"
    assert client.get("/api/v1/settings").status_code == 401


@pytest.mark.parametrize("mode", ["DEMO", "REPLAY", "SHADOW", "ASSISTED_LIVE"])
def test_operational_modes_and_actions(client, mode):
    z = zone(client)
    p = policy(client, z)
    origin = "SIMULATED" if mode == "DEMO" else "ACTUAL"
    now = datetime.now(timezone.utc).isoformat()
    for domain in ["occupancy", "preferences"]:
        records = []
        for i, d in enumerate([22, 23, 24]):
            record = dict(
                zone_id=z,
                observed_at=now,
                data_origin=origin,
                source="actual_report" if origin == "ACTUAL" else "simulation",
                occupant_id=f"p{i}",
            )
            record.update(
                {"present": True}
                if domain == "occupancy"
                else {"desired_setpoint_c": d}
            )
            records.append(record)
        assert client.post(f"/api/v1/ingest/{domain}", json=records).status_code == 200
    r = client.post(
        "/api/v1/operations/decide",
        json=dict(zone_id=z, policy_id=p, operation_mode=mode, at=now),
    )
    assert r.status_code == 200, r.text
    decision = r.json()
    assert decision["data_origin"] == origin and 18 <= decision["recommended_c"] <= 28
    did = decision["id"]
    url = f"/api/v1/operations/{did}/actions"
    assert (
        client.post(
            url,
            json=dict(kind="APPROVED", note="human approval", request_id="approve-1"),
        ).status_code
        == 200
    )
    body = dict(
        kind="MANUALLY_APPLIED",
        setpoint_c=23,
        note="record only",
        request_id="applied-1",
    )
    applied = client.post(url, json=body)
    assert applied.status_code == (422 if mode in ["SHADOW", "REPLAY"] else 200)
    if applied.status_code == 200:
        assert client.post(url, json=body).json()["id"] == applied.json()["id"]
    a = client.get(
        "/api/v1/analytics/summary", params=dict(zone_id=z, mode=mode)
    ).json()
    assert a["decision_count"] == 1 and sum(
        b["person_seconds"] for b in a["buckets"]
    ) == pytest.approx(2700)
    opposite = "REPLAY" if mode == "DEMO" else "DEMO"
    assert (
        client.get(
            "/api/v1/analytics/summary", params=dict(zone_id=z, mode=opposite)
        ).json()["decision_count"]
        == 0
    )


def test_atomic_ingestion_validation_and_stale_inputs(client):
    z = zone(client)
    p = policy(client, z)
    invalid = [
        dict(
            zone_id=z,
            observed_at="2026-01-01T00:00:00",
            data_origin="ACTUAL",
            source="x",
            occupant_id="x",
            present=True,
        )
    ]
    assert client.post("/api/v1/ingest/occupancy", json=invalid).status_code == 422
    now = datetime.now(timezone.utc).isoformat()
    r = client.post(
        "/api/v1/operations/decide",
        json=dict(zone_id=z, policy_id=p, operation_mode="SHADOW", at=now),
    )
    assert r.status_code == 422


def test_export_and_unidentified_results(client):
    r = client.post("/api/v1/elicitation/sessions", json={"time_budget_seconds": 0})
    sid = r.json()["id"]
    result = client.get(f"/api/v1/elicitation/{sid}/results").json()
    assert result["stage"] == "COMMON"
    assert all(g["status"] == "UNIDENTIFIED" for g in result["grids"].values())
    r = client.get(f"/api/v1/exports/{sid}")
    assert r.status_code == 200
    import io, zipfile

    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        assert len(z.namelist()) == 16
        assert "daily_summary.csv" in z.namelist()


def test_response_idempotency_and_checkpoint(client):
    sid = client.post(
        "/api/v1/elicitation/sessions", json={"time_budget_seconds": 0}
    ).json()["id"]
    b = api.bank()
    g = b.groups[0]
    q = dict(id=g["id"] + ":0:1", group_id=g["id"], grid=g["grid"], a=0, b=1)
    with db.engine.begin() as c:
        s = db.get(c, "elicitation_sessions", "a", sid)["data"]
        s.update(question=q, status="READY")
        db.replace(c, "elicitation_sessions", "a", sid, s)
    body = dict(question_id=q["id"], response=1, request_id="response-001")
    assert (
        client.post(
            f"/api/v1/elicitation/{sid}/next-or-response", json=body
        ).status_code
        == 200
    )
    assert (
        client.post(f"/api/v1/elicitation/{sid}/next-or-response", json=body).json()[
            "status"
        ]
        == "ALREADY_RECORDED"
    )
    body["response"] = 0
    assert (
        client.post(
            f"/api/v1/elicitation/{sid}/next-or-response", json=body
        ).status_code
        == 409
    )
    with db.engine.connect() as c:
        assert (
            len(db.rows(c, "elicitation_trials", "a")) == 1
            and len(db.rows(c, "posterior_checkpoints", "a")) == 1
        )
    assert client.get(f"/api/v1/exports/{sid}").status_code == 200


def test_contextual_fixed_policy_binding(client, monkeypatch):
    z = zone(client)
    sid = client.post(
        "/api/v1/elicitation/sessions", json={"time_budget_seconds": 0}
    ).json()["id"]
    trials = [
        dict(
            id="N5/R041:100:110",
            group_id="N5/R041",
            a=100,
            b=110,
            response=1,
            answered_at="2026-11-17T00:00:00+00:00",
        ),
        dict(
            id="N5/R049:105:130",
            group_id="N5/R049",
            a=105,
            b=130,
            response=1,
            answered_at="2026-11-17T00:00:00+00:00",
        ),
    ]
    with db.engine.begin() as c:
        s = db.get(c, "elicitation_sessions", "a", sid)["data"]
        s["trials"] = trials
        s["fixed_policy"] = dict(
            numerical_global_search=True,
            trial_count=2,
            zone_id=z,
            epsilon=2.5,
            weights={},
        )
        db.replace(c, "elicitation_sessions", "a", sid, s)
    body = dict(
        zone_id=z,
        kind="REGRET_OPTIMAL_FIXED",
        epsilon=2.5,
        session_id=sid,
        rationale="Fixture tests snapshot binding only, not optimizer",
    )
    r = client.post("/api/v1/policies/draft", json=body)
    assert r.status_code == 200, r.text
    body["epsilon"] = 3
    assert client.post("/api/v1/policies/draft", json=body).status_code == 422
    body.update(kind="CONTEXTUAL_BY_GRID", grid_epsilons={"N3/H1": 1})
    assert client.post("/api/v1/policies/draft", json=body).status_code == 422


def test_timezone_daily_split(client):
    r = client.post(
        "/api/v1/sites/zones",
        json=dict(
            site_name="DST", name="NY", timezone="America/New_York", cadence_seconds=900
        ),
    )
    z = r.json()["id"]
    d = dict(
        mode="REPLAY",
        observed_at="2026-11-01T03:55:00+00:00",
        n=3,
        members=["a", "b", "c"],
        desired=[22, 23, 24],
        recommended_c=23,
        modeled_metrics={"efficiency": 0.8, "equity": 0.7},
        measured_environment=None,
        grid="N3/H2",
        counterfactuals=[],
    )
    with db.engine.begin() as c:
        db.insert(c, "decision_cycles", "a", d, z)
    report = client.get(
        "/api/v1/analytics/summary", params=dict(zone_id=z, mode="REPLAY")
    ).json()
    assert [b["coverage_seconds"] for b in report["buckets"]] == [300, 600]
    assert sum(b["person_seconds"] for b in report["buckets"]) == 2700


def test_retention_preview_apply_and_scope(client):
    from npsdm_app.retention import retain

    old = dict(observed_at="2020-01-01T00:00:00+00:00")
    with db.engine.begin() as c:
        db.insert(c, "environment_readings", "a", old)
        db.insert(c, "environment_readings", "b", old)
        assert retain(c, "a", 365)["counts"]["environment_readings"] == 1
        assert len(db.rows(c, "environment_readings", "a")) == 1
        retain(c, "a", 365, apply=True)
        assert len(db.rows(c, "environment_readings", "a")) == 0
        assert len(db.rows(c, "environment_readings", "b")) == 1


def test_first_question_is_immediately_ready(client):
    r = client.post("/api/v1/elicitation/sessions", json={"time_budget_seconds": 0})
    assert r.status_code == 200
    s = r.json()
    assert s["status"] == "READY"
    assert s["question"]["selection_method"] == "fixed_intro_v2"
    assert s["question"]["scenario"]["n"] == 5
    assert s["question"]["temperature_difference"]["mean_c"] == pytest.approx(
        [0.6, 0.8]
    )


def test_expired_session_rejects_answer_before_poll(client):
    session = client.post(
        "/api/v1/elicitation/sessions", json={"time_budget_seconds": 300}
    ).json()
    sid = session["id"]
    with db.engine.begin() as c:
        session["created_at"] = "2020-01-01T00:00:00+00:00"
        db.replace(c, "elicitation_sessions", "a", sid, session)
    path = f"/api/v1/elicitation/{sid}/next-or-response"
    posted = client.post(
        path,
        json={
            "question_id": session["question"]["id"],
            "response": 0,
            "request_id": "late-test-response",
        },
    )
    assert posted.status_code == 409
    state = client.get(path).json()
    assert state["status"] == "TIME_BUDGET_ENDED"
    assert state["trials"] == []
