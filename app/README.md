# NPSDM Operator Console

A local, browser-based operator console for normatively parameterized shared-temperature decisions. The scientific contract is [SPEC.md](SPEC.md); user-approved operational amendments are in [Implementation details](docs/IMPLEMENTATION_DETAILS.md).

The app preserves the historical research implementation. It uses the frozen 62-person / 2,400-resampled-group source but its own 12–33°C decision domain. These groups are not independent external observations. Real building operation and physical actuation are not validated by the research dataset.

## Run locally

Prerequisites: Docker Desktop running with Linux containers and Docker Compose; Python is needed only for the one-time local secret generator. From the repository root:

```powershell
python app/scripts/setup_env.py
docker compose -f app/docker-compose.yml --env-file app/.env up -d --build
```

Open http://localhost:3000. Read `app/outputs/local-access-token.txt` locally and enter its token into the console. Do not publish that file or `.env`. The secret generator refuses to overwrite an existing environment. API readiness is http://localhost:8000/api/v1/health/ready and the interactive API schema is http://localhost:8000/docs. Ports bind to loopback only.

The Compose stack uses Next.js/TypeScript, FastAPI/NumPy/SciPy, SQLAlchemy/Alembic and PostgreSQL. PostgreSQL records live in a named volume. Normal `docker compose down` keeps them; do not use `down -v` unless you explicitly intend data deletion.

## First operator journey

1. Buildings / Zones: register a zone. UI defaults are 18–28°C, Asia/Seoul, 60-minute observation freshness and 15-minute decision coverage; the typed API supports explicit alternatives.
2. Elicitation: create an unlimited session for initial testing. Exact all-bank acquisition is slow: measured first scan 376.95 seconds and peak sampled RSS 399,360,000 bytes on the validation host (64 q nodes, float64). Five-minute sessions may end before any question is answered. Progress is shown; skips are not preferences.
3. Review the common posterior, strict consistency components and sensitivity variants. Only a witnessed pair of internally nonempty, incompatible grid sets triggers contextual inference. Unasked grids remain unidentified.
4. Policies: create and explicitly approve a policy. Operator-specified epsilon without an elicitation session is a declared manual policy, not an inferred preference. Contextual policies require an eligible session and identified grid entries; fallback values are separate operator choices.
5. Operation: choose a zone, approved policy and mode. DEMO generates isolated simulated observations. REPLAY/SHADOW/ASSISTED_LIVE require ACTUAL input records. API/CSV validation rejects missing or stale preferences.
6. Approval, rejection, override, manual application and independent confirmation are distinct audit events. The app sends no equipment commands.
7. Analytics: inspect mode-specific time coverage and modeled utility; session exports include inference and the tenant's operational snapshot.

## Inference and policy

Atkinson welfare is evaluated from the entire positive individual utility vector in the log domain. Bayesian inference uses midpoint quadrature on q=epsilon/(1+epsilon); epsilon=0/infinity remain exact decision endpoints, without invented posterior endpoint mass. The lapse likelihood and priors are uncalibrated assumptions. Alternative beta priors, sensitivity/lapse values and node counts are reported.

Strict consistency uses exponential-polynomial root isolation, recursive monotone partitions and a dominant-tail bound. Endpoints and intersections remain numerical approximations, with tolerance diagnostics. This is not a formal interval-arithmetic proof. Fixed-policy regret partitions the continuous epsilon axis by upper-envelope temperature crossings, reports open minimizer regions and isolated minimizers, and evaluates exact decision endpoints. It is a model-conditional numerical global search, not an empirically optimal building controller.

Operational tie rule: maximum Atkinson welfare → Pareto-nondominated efficiency/equity → maximum equality → nearest 23°C → seeded residual random tie. This rule also applies inside regret evaluation. Question selection retains its own stable-ID maximum-EIG rule.

## Development and tests

```powershell
python -m venv app/.venv
app/.venv/Scripts/python.exe -m pip install -r app/backend/requirements.txt
app/.venv/Scripts/python.exe -m pytest app/backend/tests -q
npm.cmd ci --prefix app/frontend
npm.cmd run typecheck --prefix app/frontend
npm.cmd run build --prefix app/frontend
npm.cmd exec --prefix app/frontend -- playwright install chromium
npm.cmd run test:e2e --prefix app/frontend
app/.venv/Scripts/python.exe app/scripts/benchmark.py
app/.venv/Scripts/python.exe app/scripts/benchmark_regret.py
app/.venv/Scripts/python.exe app/scripts/simulate.py
```

E2E tests require the running Compose stack and local access token. They write clearly labeled test zones/observations into the local database. Run them against a dedicated validation stack for deployment testing. Backend tests use isolated SQLite fixtures; live integration additionally exercises PostgreSQL. See [TEST_REPORT](validation/TEST_REPORT.md) for actual results, limitations and evidence; commands alone are not claims of passed validation.

## Documentation

[Scientific contract](docs/SCIENTIFIC_CONTRACT.md) · [Question bank](docs/QUESTION_BANK.md) · [Inference](docs/INFERENCE.md) · [Policy and regret](docs/POLICY_AND_REGRET.md) · [Operations](docs/OPERATIONS.md) · [Analytics](docs/ANALYTICS.md) · [Data dictionary](docs/DATA_DICTIONARY.md) · [API](docs/API.md) · [Deployment](docs/DEPLOYMENT.md) · [UX](docs/UX_UI.md) · [Rationale](docs/DECISION_RATIONALE.md) · [Test plan](docs/TEST_PLAN.md).

## Deployment boundary

This is a local/research operator application with environment-provisioned role-bearing bearer credentials. It does not provide organizational SSO, automated consent administration, autonomous HVAC control, or a production security certification. Field accuracy, comfort/energy effects and universal neutrality of 23°C remain unvalidated. Long exact acquisition is an explicit performance limitation, not grounds for replacing the candidate universe with a hidden shortlist.
