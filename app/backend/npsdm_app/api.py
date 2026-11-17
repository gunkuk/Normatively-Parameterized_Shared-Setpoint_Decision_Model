import os
import json
import hashlib
import secrets
import threading
import io
import csv
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from functools import lru_cache
import numpy as np
from fastapi import FastAPI, Depends, HTTPException, Header, Query, Body
from fastapi.responses import Response
from sqlalchemy import select, text
from .config import SETTINGS
from . import db
from .schemas import (
    SessionIn,
    Answer,
    ZoneIn,
    Observation,
    PolicyIn,
    DecisionIn,
    ActionIn,
)
from .bank import Bank
from .science import utility, metrics
from .inference import infer, sensitivity
from .policy import fixed_regret
from .operations import decide
from .analytics import summary

app = FastAPI(title="NPSDM Operator Console", version="1.0.0")
workers = ThreadPoolExecutor(max_workers=1)
mutex = threading.RLock()


@lru_cache
def bank():
    return Bank()


def actor(authorization: str = Header(default="")):
    token = authorization.removeprefix("Bearer ")
    configured = json.loads(os.environ.get("NPSDM_USERS", "[]"))
    for user in configured:
        if secrets.compare_digest(
            hashlib.sha256(token.encode()).hexdigest(), user["token_sha256"]
        ):
            return user
    raise HTTPException(401, "Valid bearer token required")


def permit(user, *roles):
    if user["role"] not in roles:
        raise HTTPException(403, "Role is not permitted")


@app.exception_handler(KeyError)
async def missing(request, exc):
    from fastapi.responses import JSONResponse

    return JSONResponse(
        status_code=404, content={"detail": "Resource not found in this tenant"}
    )


@app.exception_handler(ValueError)
async def invalid(request, exc):
    from fastapi.responses import JSONResponse

    return JSONResponse(status_code=422, content={"detail": str(exc)})


@app.get("/api/v1/health/ready")
def ready():
    with db.engine.connect() as c:
        c.execute(text("SELECT 1"))
        c.execute(select(db.tables["roles"].c.id).limit(1))
    return {"status": "ready", "config_hash": SETTINGS.fingerprint}


@app.on_event("startup")
def startup():
    # Compose runs a single API process. Recover interrupted worker states;
    # never silently discard trials or claim an unfinished computation completed.
    with db.engine.begin() as c:
        for user in json.loads(os.environ.get("NPSDM_USERS", "[]")):
            for table, key, data in [
                (
                    "users",
                    user["id"],
                    {k: v for k, v in user.items() if k != "token_sha256"},
                ),
                ("roles", user["role"], {"name": user["role"]}),
            ]:
                identifier = user["tenant"] + ":" + key
                try:
                    db.get(c, table, user["tenant"], identifier)
                except KeyError:
                    db.insert(c, table, user["tenant"], data, id=identifier)
        for row in c.execute(select(db.tables["elicitation_sessions"])).mappings():
            data = row["data"]
            if data["status"] == "COMPUTING":
                data.update(
                    status="INTERRUPTED",
                    error="Worker interrupted by server restart; resume explicitly",
                )
                db.replace(c, "elicitation_sessions", row["tenant_id"], row["id"], data)


@app.post("/api/v1/elicitation/{sid}/resume")
def resume(sid: str, user=Depends(actor)):
    permit(user, "Admin", "Researcher", "Operator")
    with db.engine.begin() as c:
        s = checked_session(c, user, sid, True)
        if s["status"] not in ["INTERRUPTED", "STOPPED", "FAILED"]:
            raise HTTPException(409, "Session is not resumable")
        s["status"] = "IDLE"
        db.replace(c, "elicitation_sessions", user["tenant"], sid, s)
    return {"status": "IDLE"}


@app.get("/api/v1/me")
def me(user=Depends(actor)):
    return {k: v for k, v in user.items() if k != "token_sha256"}


@app.get("/api/v1/settings")
def settings(user=Depends(actor)):
    return dict(
        settings=SETTINGS.model_dump(),
        config_hash=SETTINGS.fingerprint,
        editing="Version SETTINGS.yaml, validate, rebuild and restart; existing sessions reject changed config",
    )


@app.get("/api/v1/question-bank/provenance")
def provenance(user=Depends(actor)):
    manifest = bank().manifest
    with db.engine.begin() as c:
        identifier = user["tenant"] + ":" + SETTINGS.fingerprint
        try:
            db.get(c, "scenario_bank_versions", user["tenant"], identifier)
        except KeyError:
            db.insert(
                c, "scenario_bank_versions", user["tenant"], manifest, id=identifier
            )
    return manifest


@app.get("/api/v1/question-bank/score")
def candidate_score(
    group_id: str, a: int, b: int, session_id: str | None = None, user=Depends(actor)
):
    from .science import probability, eig

    source = bank()
    group = source.lookup[group_id]
    if not 0 <= a < b < len(source.temperatures):
        raise ValueError("Require valid unordered pair indices a < b")
    weights = source.prior
    asked = False
    stage = "COMMON"
    if session_id:
        with db.engine.connect() as c:
            session = checked_session(c, user, session_id)
        result = infer(source, session["trials"])
        stage = result["stage"]
        weights = np.asarray(
            result["grids"][group["grid"]]["weights"]
            if stage == "CONTEXTUAL"
            else result["common"]["weights"]
        )
        asked = any(t["id"] == f"{group_id}:{a}:{b}" for t in session["trials"])
    curves = source.curves(group)
    score = float(
        eig(probability(curves[a], curves[b], source.settings)[None, :], weights)[0]
    )
    return dict(
        group_id=group_id,
        a=a,
        b=b,
        source_version=source.version,
        eig_bits=score,
        eligible_in_original_universe=True,
        available_for_session=not asked,
        stage=stage,
    )


@app.post("/api/v1/elicitation/sessions")
def create_session(body: SessionIn, user=Depends(actor)):
    permit(user, "Admin", "Researcher", "Operator")
    with db.engine.begin() as c:
        data = dict(
            **body.model_dump(),
            created_at=db.now(),
            trials=[],
            status="IDLE",
            stage="COMMON",
            config_hash=SETTINGS.fingerprint,
            question=None,
            progress=0,
        )
        sid = db.insert(c, "elicitation_sessions", user["tenant"], data)
        db.audit(c, user, "SESSION_CREATED", sid)
    return dict(id=sid, **data)


def checked_session(c, user, sid, lock=False):
    s = db.get(c, "elicitation_sessions", user["tenant"], sid, lock)["data"]
    if s["config_hash"] != SETTINGS.fingerprint:
        raise HTTPException(
            409, "Scientific configuration changed; create a new session"
        )
    return s


def selection_job(tenant, sid):
    try:
        with db.engine.begin() as c:
            s = db.get(c, "elicitation_sessions", tenant, sid)["data"]
        result = infer(bank(), s["trials"])
        weights = np.asarray(result["common"]["weights"])
        grid_weights = (
            {g: np.asarray(v["weights"]) for g, v in result["grids"].items()}
            if result["stage"] == "CONTEXTUAL"
            else None
        )

        def progress(i, n):
            if i % 20 == 0:
                with db.engine.begin() as c:
                    current = db.get(c, "elicitation_sessions", tenant, sid, True)[
                        "data"
                    ]
                    if current["status"] == "STOPPED":
                        raise InterruptedError("Session stopped by operator")
                    current["progress"] = i / n
                    db.replace(c, "elicitation_sessions", tenant, sid, current)

        q = bank().select(
            weights, [t["id"] for t in s["trials"]], grid_weights, progress
        )
        if q is not None:
            group = bank().lookup[q["group_id"]]
            q["desired"] = group["desired"]
            q["temperatures"] = bank().temperatures[[q["a"], q["b"]]].tolist()
            u = utility(q["temperatures"], group["desired"])
            q["utilities"] = u.tolist()
            q["metrics"] = {k: v.tolist() for k, v in metrics(u).items()}
            seed = s["seed"] + len(s["trials"])
            q["display_seed"] = seed
            q["display_order"] = np.random.default_rng(seed).permutation(2).tolist()
            q["label"] = "Which shared setpoint do you prefer?"
            q["utility_interpretation"] = (
                "Model-generated utility, not measured comfort"
            )
        with db.engine.begin() as c:
            current = db.get(c, "elicitation_sessions", tenant, sid, True)["data"]
            current.update(
                question=q,
                status=(
                    "STOPPED"
                    if current["status"] == "STOPPED"
                    else (
                        "TIME_BUDGET_ENDED"
                        if current["time_budget_seconds"]
                        and (
                            datetime.now(timezone.utc)
                            - datetime.fromisoformat(current["created_at"])
                        ).total_seconds()
                        >= current["time_budget_seconds"]
                        else ("READY" if q and q["eig_bits"] > 1e-14 else "SATURATED")
                    )
                ),
                progress=1,
                stage=result["stage"],
            )
            db.replace(c, "elicitation_sessions", tenant, sid, current)
    except InterruptedError:
        return
    except Exception as exc:
        with db.engine.begin() as c:
            current = db.get(c, "elicitation_sessions", tenant, sid, True)["data"]
            current.update(status="FAILED", error=str(exc))
            db.replace(c, "elicitation_sessions", tenant, sid, current)


@app.get("/api/v1/elicitation/{sid}/next-or-response")
def next_question(sid: str, user=Depends(actor)):
    permit(user, "Admin", "Researcher", "Operator")
    with mutex, db.engine.begin() as c:
        s = checked_session(c, user, sid, True)
        if s["status"] == "IDLE":
            elapsed = (
                datetime.now(timezone.utc) - datetime.fromisoformat(s["created_at"])
            ).total_seconds()
            if s["time_budget_seconds"] and elapsed >= s["time_budget_seconds"]:
                s["status"] = "TIME_BUDGET_ENDED"
                db.replace(c, "elicitation_sessions", user["tenant"], sid, s)
                return s
            s["status"] = "COMPUTING"
            s["progress"] = 0
            db.replace(c, "elicitation_sessions", user["tenant"], sid, s)
            # Submission occurs after commit to avoid racing the worker's first read.
            schedule = True
        else:
            schedule = False
    if schedule:
        workers.submit(selection_job, user["tenant"], sid)
    return s


@app.post("/api/v1/elicitation/{sid}/next-or-response")
def answer(sid: str, body: Answer, user=Depends(actor)):
    permit(user, "Admin", "Researcher", "Operator")
    with mutex, db.engine.begin() as c:
        s = checked_session(c, user, sid, True)
        previous = [r for r in s["trials"] if r["request_id"] == body.request_id]
        if previous:
            if (
                previous[0]["id"] != body.question_id
                or previous[0]["response"] != body.response
            ):
                raise HTTPException(
                    409, "Idempotency key reused for different response"
                )
            return {"status": "ALREADY_RECORDED", "trial": previous[0]}
        q = s.get("question")
        if s["status"] != "READY" or not q or q["id"] != body.question_id:
            raise HTTPException(409, "Question is stale or not ready")
        trial = dict(
            **q,
            response=body.response,
            request_id=body.request_id,
            answered_at=db.now(),
        )
        s["trials"].append(trial)
        result = infer(bank(), s["trials"])
        s.update(status="IDLE", question=None, stage=result["stage"])
        db.insert(
            c,
            "elicitation_trials",
            user["tenant"],
            dict(session_id=sid, **trial),
            key=sid + ":" + body.request_id,
        )
        db.insert(
            c,
            "posterior_checkpoints",
            user["tenant"],
            dict(session_id=sid, trial_count=len(s["trials"]), result=result),
        )
        db.replace(c, "elicitation_sessions", user["tenant"], sid, s)
        db.audit(c, user, "RESPONSE_RECORDED", sid, {"request_id": body.request_id})
    if result["stage"] == "CONTEXTUAL":
        workers.submit(fixed_job, user["tenant"], sid, None, None)
    return result


@app.post("/api/v1/elicitation/{sid}/stop")
def stop(sid: str, user=Depends(actor)):
    permit(user, "Admin", "Researcher", "Operator")
    with db.engine.begin() as c:
        s = checked_session(c, user, sid, True)
        s["status"] = "STOPPED"
        db.replace(c, "elicitation_sessions", user["tenant"], sid, s)
    return {"status": "STOPPED"}


@app.get("/api/v1/elicitation/{sid}/results")
def results(sid: str, user=Depends(actor)):
    with db.engine.connect() as c:
        s = checked_session(c, user, sid)
    result = infer(bank(), s["trials"])
    result["sensitivity"] = sensitivity(bank(), s["trials"])
    result["fixed_policy"] = (
        s.get(
            "fixed_policy",
            {
                "status": "NOT_COMPUTED",
                "endpoint": "POST /elicitation/{id}/fixed-regret",
            },
        )
        if result["stage"] == "CONTEXTUAL"
        else None
    )
    return result


def fixed_job(tenant, sid, weights, zone_id):
    try:
        with db.engine.begin() as c:
            s = db.get(c, "elicitation_sessions", tenant, sid, True)["data"]
            trials = s["trials"]
            count = len(trials)
            bounds = None
            if zone_id:
                zone = db.get(c, "zones", tenant, zone_id)["data"]
                bounds = [zone["min_c"], zone["max_c"]]
            s["fixed_policy"] = {
                "status": "COMPUTING",
                "trial_count": count,
                "zone_id": zone_id,
            }
            db.replace(c, "elicitation_sessions", tenant, sid, s)
        r = infer(bank(), trials)
        post = {
            g: np.asarray(v["weights"])
            for g, v in r["grids"].items()
            if v["status"] != "UNIDENTIFIED"
        }
        computed = fixed_regret(bank(), post, weights, temperature_bounds=bounds)
        from scipy.stats import beta

        q = bank().nodes / (1 + bank().nodes)
        variants = []
        for alpha, beta_shape in [(2.0, 2.0), (0.5, 0.5)]:
            alt_prior = beta.pdf(q, alpha, beta_shape)
            alt_prior = alt_prior / alt_prior.sum()
            alternative = {}
            for grid, base in post.items():
                adjusted = base * alt_prior / bank().prior
                alternative[grid] = adjusted / adjusted.sum()
            for grid in r["grids"]:
                if grid not in alternative:
                    alternative[grid] = alt_prior
            alt = fixed_regret(bank(), alternative, weights, temperature_bounds=bounds)
            variants.append(
                dict(
                    prior=f"beta({alpha},{beta_shape})",
                    epsilon=alt["epsilon"],
                    expected_regret=alt["expected_regret"],
                    minimizer_ranges=alt["minimizer_ranges"],
                )
            )
        computed.update(trial_count=count, zone_id=zone_id, prior_sensitivity=variants)
        with db.engine.begin() as c:
            s = db.get(c, "elicitation_sessions", tenant, sid, True)["data"]
            if len(s["trials"]) == count:
                s["fixed_policy"] = computed
                db.replace(c, "elicitation_sessions", tenant, sid, s)
    except Exception as exc:
        with db.engine.begin() as c:
            s = db.get(c, "elicitation_sessions", tenant, sid, True)["data"]
            s["fixed_policy"] = {"status": "FAILED", "error": str(exc)}
            db.replace(c, "elicitation_sessions", tenant, sid, s)


@app.get("/api/v1/analytics/grid-weights")
def observed_weights(
    zone_id: str,
    mode: str,
    lookback_days: int = Query(30, ge=1, le=3650),
    smoothing: float = Query(0, ge=0),
    user=Depends(actor),
):
    from datetime import timedelta

    if mode not in ["DEMO", "REPLAY", "SHADOW", "ASSISTED_LIVE"]:
        raise ValueError("Invalid mode")
    with db.engine.connect() as c:
        report = summary(c, user["tenant"], zone_id, mode)
    cutoff = (
        (datetime.now(timezone.utc) - timedelta(days=lookback_days)).date().isoformat()
    )
    values = {g: float(smoothing) for g in sorted({x["grid"] for x in bank().groups})}
    covered = 0.0
    for bucket in report["buckets"]:
        if bucket["period"] < cutoff:
            continue
        for g, seconds in bucket["grid_seconds"].items():
            if g in values:
                values[g] += seconds
                covered += seconds
    total = sum(values.values())
    if total <= 0:
        raise ValueError(
            "No covered observations; choose explicit uniform weights or smoothing"
        )
    return dict(
        weights={g: v / total for g, v in values.items()},
        lookback_days=lookback_days,
        smoothing_seconds_per_grid=smoothing,
        coverage_seconds=covered,
        mode=mode,
        as_of=db.now(),
        source="Nonoverlapping recorded decision exposure; only known grids; historical policy selection can affect coverage",
    )


@app.post("/api/v1/elicitation/{sid}/fixed-regret")
def regret(
    sid: str,
    weights: dict[str, float] | None = Body(default=None),
    zone_id: str | None = None,
    user=Depends(actor),
):
    permit(user, "Admin", "Researcher", "Operator")
    with db.engine.connect() as c:
        checked_session(c, user, sid)
        if zone_id:
            db.get(c, "zones", user["tenant"], zone_id)
    workers.submit(fixed_job, user["tenant"], sid, weights, zone_id)
    return {
        "status": "QUEUED",
        "message": "Results will appear alongside contextual output",
    }


@app.get("/api/v1/sites/zones")
def zones(user=Depends(actor)):
    with db.engine.connect() as c:
        return [
            dict(r["data"], record_id=r["id"], id=r["id"])
            for r in db.rows(c, "zones", user["tenant"])
        ]


@app.post("/api/v1/sites/zones")
def create_zone(body: ZoneIn, user=Depends(actor)):
    permit(user, "Admin")
    with db.engine.begin() as c:
        site = db.insert(c, "sites", user["tenant"], {"name": body.site_name})
        d = dict(**body.model_dump(), site_id=site, version=1)
        zid = db.insert(c, "zones", user["tenant"], d)
        db.audit(c, user, "ZONE_CREATED", zid)
    return dict(id=zid, **d)


DOMAINS = {
    "preferences": "preference_observations",
    "occupancy": "presence_events",
    "environment": "environment_readings",
    "feedback": "thermal_feedback",
    "metering": "meter_readings",
}


def ingest_records(domain, items, user):
    if domain not in DOMAINS:
        raise HTTPException(404, "Unknown domain")
    ids = []
    with db.engine.begin() as c:
        for item in items:
            db.get(c, "zones", user["tenant"], item.zone_id)
            required = {
                "preferences": ["occupant_id", "desired_setpoint_c"],
                "occupancy": ["occupant_id", "present"],
                "environment": ["sensor_id", "indoor_temperature_c"],
                "feedback": ["occupant_id", "comfort_vote", "consent"],
                "metering": ["meter_id", "value", "units", "interval_seconds"],
            }[domain]
            if any(getattr(item, k) is None for k in required):
                raise ValueError("Missing required fields: " + ",".join(required))
            if domain == "feedback" and not item.consent:
                raise ValueError("Feedback consent required")
            if item.occupant_id:
                oid = user["tenant"] + ":" + item.occupant_id
                try:
                    db.get(c, "occupants", user["tenant"], oid)
                except KeyError:
                    db.insert(
                        c,
                        "occupants",
                        user["tenant"],
                        {"opaque_id": item.occupant_id},
                        id=oid,
                    )
            d = item.model_dump(mode="json")
            key = hashlib.sha256(json.dumps(d, sort_keys=True).encode()).hexdigest()
            previous = c.execute(
                select(db.tables[DOMAINS[domain]].c.id).where(
                    db.tables[DOMAINS[domain]].c.tenant_id == user["tenant"],
                    db.tables[DOMAINS[domain]].c.idempotency_key == key,
                )
            ).scalar()
            ids.append(
                previous
                or db.insert(
                    c, DOMAINS[domain], user["tenant"], d, item.zone_id, key=key
                )
            )
        iid = db.insert(
            c,
            "dataset_ingests",
            user["tenant"],
            {"domain": domain, "count": len(items), "ids": ids},
        )
        db.audit(c, user, "DATA_INGESTED", iid)
    return dict(ids=ids, count=len(ids), ingest_id=iid)


@app.post("/api/v1/ingest/{domain}")
def ingest(domain: str, items: list[Observation], user=Depends(actor)):
    permit(user, "Admin", "Operator", "Researcher")
    return ingest_records(domain, items, user)


@app.post("/api/v1/ingest/{domain}/csv")
def ingest_csv(
    domain: str, content: str = Body(media_type="text/plain"), user=Depends(actor)
):
    permit(user, "Admin", "Operator", "Researcher")
    items = [
        Observation(**{k: v for k, v in row.items() if v != ""})
        for row in csv.DictReader(io.StringIO(content))
    ]
    return ingest_records(domain, items, user)


@app.get("/api/v1/policies")
def policies(user=Depends(actor)):
    with db.engine.connect() as c:
        return [
            dict(r["data"], record_id=r["id"], id=r["id"])
            for r in db.rows(c, "model_policies", user["tenant"])
        ]


@app.post("/api/v1/policies/draft")
def draft(body: PolicyIn, user=Depends(actor)):
    permit(user, "Admin", "Researcher", "Operator")
    with db.engine.begin() as c:
        zone = db.get(c, "zones", user["tenant"], body.zone_id)["data"]
        result = None
        if body.session_id:
            result = infer(bank(), checked_session(c, user, body.session_id)["trials"])
        if (
            body.kind == "COMMON_FIXED"
            and result
            and result["deterministic"]["status"] != "COMMON_COMPATIBLE"
        ):
            raise ValueError("Common policy requires coherent common constraints")
        if body.kind == "CONTEXTUAL_BY_GRID":
            if not result or result["stage"] != "CONTEXTUAL":
                raise ValueError("Contextual session required")
            for g in body.grid_epsilons:
                if (
                    g not in result["grids"]
                    or result["grids"][g]["status"] == "UNIDENTIFIED"
                ):
                    raise ValueError(
                        "Unidentified cell cannot be approved as estimated"
                    )
        if body.kind == "REGRET_OPTIMAL_FIXED":
            if not body.session_id or not result or result["stage"] != "CONTEXTUAL":
                raise ValueError("Contextual session required")
            session = checked_session(c, user, body.session_id)
            fixed = session.get("fixed_policy", {})
            if (
                not fixed.get("numerical_global_search")
                or fixed.get("trial_count") != len(session["trials"])
                or fixed.get("zone_id") != body.zone_id
            ):
                raise ValueError(
                    "Compute a current fixed-regret result for this zone first"
                )
            if body.epsilon != fixed["epsilon"]:
                raise ValueError(
                    "Policy epsilon must match the computed representative"
                )
            if body.weights is not None and body.weights != fixed["weights"]:
                raise ValueError("Weights differ from computed optimum")
        d = dict(
            **body.model_dump(),
            status="DRAFT",
            version=1,
            config_hash=SETTINGS.fingerprint,
            zone_version=zone["version"],
            created_at=db.now(),
            inference_snapshot=result,
            fixed_regret_snapshot=(
                fixed if body.kind == "REGRET_OPTIMAL_FIXED" else None
            ),
        )
        pid = db.insert(c, "model_policies", user["tenant"], d, body.zone_id)
        db.audit(c, user, "POLICY_DRAFTED", pid)
    return dict(id=pid, **d)


@app.post("/api/v1/policies/{pid}/approve")
def approve(pid: str, user=Depends(actor)):
    permit(user, "Admin", "Operator")
    with db.engine.begin() as c:
        p = db.get(c, "model_policies", user["tenant"], pid, True)["data"]
        if p["config_hash"] != SETTINGS.fingerprint:
            raise ValueError("Policy configuration is stale")
        if p["status"] == "APPROVED":
            return dict(id=pid, **p)
        p.update(status="APPROVED", approved_at=db.now(), approved_by=user["id"])
        db.replace(c, "model_policies", user["tenant"], pid, p)
        db.audit(c, user, "POLICY_APPROVED", pid)
    return dict(id=pid, **p)


@app.post("/api/v1/operations/decide")
def decision(body: DecisionIn, user=Depends(actor)):
    permit(user, "Admin", "Operator")
    with db.engine.begin() as c:
        d = decide(c, user["tenant"], body, bank())
        did = db.insert(c, "decision_cycles", user["tenant"], d, body.zone_id)
        db.audit(c, user, "DECISION_RECOMMENDED", did)
    return dict(id=did, **d)


@app.post("/api/v1/operations/{did}/actions")
def action(did: str, body: ActionIn, user=Depends(actor)):
    permit(user, "Admin", "Operator")
    with db.engine.begin() as c:
        decision = db.get(c, "decision_cycles", user["tenant"], did, True)["data"]
        if decision["mode"] in ["REPLAY", "SHADOW"] and body.kind in [
            "MANUALLY_APPLIED",
            "INDEPENDENTLY_CONFIRMED",
        ]:
            raise ValueError("Replay/shadow cannot record physical application")
        zone = db.get(c, "zones", user["tenant"], decision["zone_id"])["data"]
        if (
            body.kind in ["OVERRIDE", "MANUALLY_APPLIED", "INDEPENDENTLY_CONFIRMED"]
            and body.setpoint_c is None
        ):
            raise ValueError("Explicit setpoint required")
        if (
            body.setpoint_c is not None
            and not zone["min_c"] <= body.setpoint_c <= zone["max_c"]
        ):
            raise ValueError("Action outside zone bounds")
        previous = [
            r
            for r in db.rows(c, "operator_actions", user["tenant"], decision["zone_id"])
            if r["data"]["decision_id"] == did
        ]
        for r in previous:
            if r["data"]["request_id"] == body.request_id:
                if any(r["data"][k] != v for k, v in body.model_dump().items()):
                    raise HTTPException(409, "Idempotency conflict")
                return dict(r["data"], record_id=r["id"], id=r["id"])
        if body.kind == "MANUALLY_APPLIED" and not any(
            r["data"]["kind"] in ["APPROVED", "OVERRIDE"] for r in previous
        ):
            raise ValueError("Approval/override required before manual application")
        if body.kind == "INDEPENDENTLY_CONFIRMED" and not any(
            r["data"]["kind"] == "MANUALLY_APPLIED" for r in previous
        ):
            raise ValueError("Manual application must precede confirmation")
        d = dict(
            **body.model_dump(),
            decision_id=did,
            recorded_at=db.now(),
            actor=user["id"],
            mode=decision["mode"],
            data_origin=decision["data_origin"],
        )
        aid = db.insert(
            c,
            "operator_actions",
            user["tenant"],
            d,
            decision["zone_id"],
            key=did + ":" + body.request_id,
        )
        db.audit(c, user, "ACTION_RECORDED", aid)
    return dict(id=aid, **d)


@app.get("/api/v1/operations/history")
def history(zone_id: str | None = None, user=Depends(actor)):
    with db.engine.connect() as c:
        return [
            dict(r["data"], record_id=r["id"], id=r["id"])
            for r in db.rows(c, "decision_cycles", user["tenant"], zone_id)
        ]


@app.get("/api/v1/analytics/summary")
def analytics(
    zone_id: str,
    mode: str = Query(pattern="^(DEMO|REPLAY|SHADOW|ASSISTED_LIVE)$"),
    period: str = Query("daily", pattern="^(daily|weekly|monthly)$"),
    user=Depends(actor),
):
    with db.engine.connect() as c:
        return summary(c, user["tenant"], zone_id, mode, period)


@app.post("/api/v1/demo/seed")
def seed_demo(zone_id: str, seed: int = 7, user=Depends(actor)):
    permit(user, "Admin", "Researcher", "Operator")
    from datetime import timedelta

    rng = np.random.default_rng(seed)
    g = next(g for g in bank().groups if g["n"] == 8)
    at = datetime.now(timezone.utc)
    records = {domain: [] for domain in ["occupancy", "preferences", "environment"]}
    indoor = 23.0
    for step in range(12):
        stamp = (at - timedelta(minutes=(11 - step) * 15)).isoformat()
        desired = np.array(g["desired"]) + 0.15 * np.sin(step / 3 + np.arange(8))
        present = [step == 11 or (i + step) % 7 != 0 for i in range(8)]
        target = float(desired[np.array(present)].mean())
        indoor = indoor + 0.2 * (target - indoor) + float(rng.normal(0, 0.08))
        records["environment"].append(
            Observation(
                zone_id=zone_id,
                observed_at=stamp,
                data_origin="SIMULATED",
                source=f"demo-seed-{seed}",
                sensor_id="demo-room",
                indoor_temperature_c=indoor + float(rng.normal(0, 0.05)),
                relative_humidity=50,
            )
        )
        for i, d in enumerate(desired):
            common = dict(
                zone_id=zone_id,
                observed_at=stamp,
                data_origin="SIMULATED",
                source=f"demo-seed-{seed}",
                occupant_id=f"demo-{i}",
            )
            records["occupancy"].append(Observation(**common, present=present[i]))
            records["preferences"].append(
                Observation(**common, desired_setpoint_c=float(d))
            )
    count = sum(
        ingest_records(domain, items, user)["count"]
        for domain, items in records.items()
    )
    return dict(
        count=count,
        seed=seed,
        base_group=g["id"],
        assumptions="Synthetic arrivals/departures; sinusoidal desired-setpoint drift +/-0.15 C; first-order room response coefficient 0.2; Gaussian process/sensor noise 0.08/0.05 C; no validated HVAC physics or energy model",
        at=at.isoformat(),
    )


@app.get("/api/v1/exports/{sid}")
def export(sid: str, user=Depends(actor)):
    with db.engine.connect() as c:
        s = checked_session(c, user, sid)
        state = {
            n: [
                dict(r["data"], record_id=r["id"], id=r["id"])
                for r in db.rows(c, n, user["tenant"])
            ]
            for n in db.NAMES
            if n not in ["users", "roles"]
        }
    r = infer(bank(), s["trials"])
    files = {
        "run_manifest.json": dict(
            config_hash=SETTINGS.fingerprint,
            exported_at=db.now(),
            session_id=sid,
            scope="session inference plus tenant operational snapshot",
        ),
        "scenario_bank_manifest.json": bank().manifest,
        "common_epsilon_M0.json": r["common"],
        "conflict_diagnostics.json": r["deterministic"],
        "fixed_epsilon_regret.json": s.get("fixed_policy", {"status": "NOT_COMPUTED"}),
        "policy.json": state["model_policies"],
        "validation_report.json": {
            "runtime_export": True,
            "validation": "See versioned app/validation reports; runtime export is not a certification",
        },
    }

    def csvtext(records):
        f = io.StringIO()
        keys = sorted({k for r in records for k in r})
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        for row in records:
            writer.writerow(
                {
                    k: (
                        json.dumps(v)
                        if isinstance(v, (list, dict))
                        else (
                            "'" + v
                            if isinstance(v, str) and v.startswith(("=", "+", "-", "@"))
                            else v
                        )
                    )
                    for k, v in row.items()
                }
            )
        return f.getvalue()

    csvs = {
        "elicitation_trials.csv": s["trials"],
        "grid_specific_epsilon.csv": [dict(grid=g, **v) for g, v in r["grids"].items()],
        "question_eig_diagnostics.csv": s["trials"],
        "decision_cycles.csv": state["decision_cycles"],
        "observations.csv": sum([state[n] for n in DOMAINS.values()], []),
        "actions.csv": state["operator_actions"],
        "daily_summary.csv": [],
        "policy_counterfactual.csv": [
            dict(decision_id=d["id"], **x)
            for d in state["decision_cycles"]
            for x in d["counterfactuals"]
        ],
        "data_quality.csv": [
            dict(decision_id=d["id"], quality=d["quality"])
            for d in state["decision_cycles"]
        ],
    }
    with db.engine.connect() as c:
        for z in state["zones"]:
            for mode in ["DEMO", "REPLAY", "SHADOW", "ASSISTED_LIVE"]:
                csvs["daily_summary.csv"] += [
                    dict(zone_id=z["id"], mode=mode, **b)
                    for b in summary(c, user["tenant"], z["id"], mode)["buckets"]
                ]
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in files.items():
            z.writestr(name, json.dumps(data, indent=2))
        for name, data in csvs.items():
            z.writestr(name, csvtext(data))
    return Response(
        output.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="npsdm-{sid}.zip"'},
    )
