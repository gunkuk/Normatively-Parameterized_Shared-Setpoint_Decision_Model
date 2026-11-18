"""Measure actual HTTP delivery; cached EIG is still exact over the full bank."""

from pathlib import Path
import json, time, httpx

app = Path(__file__).resolve().parents[1]
c = httpx.Client(
    base_url="http://localhost:8000/api/v1",
    headers={
        "Authorization": "Bearer "
        + (app / "outputs/local-access-token.txt").read_text().strip()
    },
    timeout=60,
)


def call(method, path, data=None):
    r = c.request(method, path, json=data)
    r.raise_for_status()
    return r.json()


report = {
    "scope": "Fixed intro and both exact response branches in the deployed Docker app",
    "branches": [],
}
start = time.perf_counter()
s = call("POST", "/elicitation/sessions", {"time_budget_seconds": 0, "seed": 99})
report["first_question_seconds"] = time.perf_counter() - start
assert s["status"] == "READY" and s["question"]["selection_method"] == "fixed_intro_v2"
sid = s["id"]
start = time.perf_counter()
while True:
    state = call("GET", f"/elicitation/{sid}/next-or-response")
    p = state.get("prefetch", {})
    print("A/B prefetch", p, flush=True)
    if len(p) == 2 and all(v["ready"] for v in p.values()):
        break
    if any(v["error"] for v in p.values()):
        raise RuntimeError(p)
    time.sleep(10)
report["remaining_prefetch_wait_seconds"] = time.perf_counter() - start
for response in [0, 1]:
    if response:
        s = call(
            "POST", "/elicitation/sessions", {"time_budget_seconds": 0, "seed": 99}
        )
        sid = s["id"]
    start = time.perf_counter()
    call(
        "POST",
        f"/elicitation/{sid}/next-or-response",
        {
            "question_id": s["question"]["id"],
            "response": response,
            "request_id": f"delivery-validation-{response}",
        },
    )
    q = call("GET", f"/elicitation/{sid}/next-or-response")
    elapsed = time.perf_counter() - start
    assert q["status"] == "READY" and q["delivery"] == "precomputed_exact_cache"
    report["branches"].append(
        {
            "response": response,
            "answer_to_next_question_seconds": elapsed,
            "question_id": q["question"]["id"],
            "evaluated_candidates": q["question"]["evaluated_candidates"],
            "joint_compute_seconds": q["question"]["elapsed_seconds"],
            "exact": q["question"]["exact_discrete_global"],
        }
    )
    call("POST", f"/elicitation/{sid}/stop")
(app / "validation/DELIVERY_V2.json").write_text(json.dumps(report, indent=2))
print(json.dumps(report, indent=2), flush=True)
