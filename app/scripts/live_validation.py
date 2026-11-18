import time, json
from pathlib import Path
from datetime import datetime, timezone
import httpx

app = Path(__file__).resolve().parents[1]
token = (app / "outputs/local-access-token.txt").read_text().strip()
c = httpx.Client(
    base_url="http://127.0.0.1:8000/api/v1",
    headers={"Authorization": "Bearer " + token},
    timeout=90,
)


def call(method, path, body=None):
    r = c.request(method, path, json=body)
    if r.status_code >= 400:
        raise RuntimeError(f"{method} {path}: {r.status_code} {r.text}")
    return r.json()


report = {"health": call("GET", "/health/ready"), "checks": []}
z = call(
    "POST",
    "/sites/zones",
    dict(site_name="Validation building", name="Live API validation"),
)["id"]
p = call(
    "POST",
    "/policies/draft",
    dict(
        zone_id=z,
        kind="COMMON_FIXED",
        epsilon=1,
        fallback_epsilon=1,
        rationale="Explicit test policy; no claim of elicited accuracy",
    ),
)["id"]
call("POST", f"/policies/{p}/approve")
now = datetime.now(timezone.utc).isoformat()
for domain in ["occupancy", "preferences"]:
    items = []
    for i, d in enumerate([22, 23, 24]):
        r = dict(
            zone_id=z,
            observed_at=now,
            data_origin="ACTUAL",
            source="validation_fixture",
            occupant_id=f"fixture-{i}",
        )
        r.update(
            {"present": True} if domain == "occupancy" else {"desired_setpoint_c": d}
        )
        items.append(r)
    call("POST", f"/ingest/{domain}", items)
call(
    "POST",
    "/ingest/environment",
    [
        dict(
            zone_id=z,
            observed_at=now,
            data_origin="ACTUAL",
            source="validation_fixture",
            sensor_id="fixture-room",
            indoor_temperature_c=23,
            relative_humidity=50,
        )
    ],
)
for mode in ["REPLAY", "SHADOW", "ASSISTED_LIVE"]:
    d = call(
        "POST",
        "/operations/decide",
        dict(zone_id=z, policy_id=p, operation_mode=mode, at=now),
    )
    report["checks"].append(
        dict(mode=mode, decision_id=d["id"], recommended_c=d["recommended_c"])
    )
    call(
        "POST",
        f'/operations/{d["id"]}/actions',
        dict(
            kind="APPROVED",
            note="Validation fixture approval",
            request_id="approval-validation",
        ),
    )
    if mode == "ASSISTED_LIVE":
        call(
            "POST",
            f'/operations/{d["id"]}/actions',
            dict(
                kind="MANUALLY_APPLIED",
                setpoint_c=d["recommended_c"],
                note="Simulated manual report in validation fixture; no actual equipment",
                request_id="manual-validation",
            ),
        )
s = call("POST", "/elicitation/sessions", dict(time_budget_seconds=0, seed=31))
sid = s["id"]
start = time.perf_counter()
call("GET", f"/elicitation/{sid}/next-or-response")
(app / "outputs/live-validation-session.txt").write_text(sid)
while True:
    state = call("GET", f"/elicitation/{sid}/next-or-response")
    print(state["status"], round(state.get("progress", 0) * 100), flush=True)
    if state["status"] != "COMPUTING":
        break
    time.sleep(15)
if state["status"] != "READY":
    raise RuntimeError(str(state))
q = state["question"]
call(
    "POST",
    f"/elicitation/{sid}/next-or-response",
    dict(question_id=q["id"], response=1, request_id="validation-answer-001"),
)
r = call("GET", f"/elicitation/{sid}/results")
report.update(
    session_id=sid,
    first_question=q,
    elapsed_seconds=time.perf_counter() - start,
    posterior_status=r["common"]["status"],
    stage=r["stage"],
    zone_id=z,
    fixture_notice="ACTUAL input pathway tested using labeled validation fixtures; these are not real human observations.",
)
(app / "validation/LIVE_INTEGRATION.json").write_text(json.dumps(report, indent=2))
print("PASS live PostgreSQL API + full-bank response transaction", flush=True)
