# Codex implementation brief — NPSDM App v1.0

## Repository and authority

Target `gunkuk/Normatively-Parameterized_Shared-Setpoint_Decision_Model`, root-level `app/` **only**, except one minimal link in root README if appropriate. Use a new feature branch `feat/npsdm-operator-app`; create PR into `main`; do not merge automatically. Read `NPSDM_FINAL_SCIENTIFIC_AND_APP_SPEC_v1.0.md` fully; copy it to `app/SPEC.md` in the repo. User decisions in Section 0 override prior draft v0.1–v0.3 and any convenient implementation shortcuts.

## Non-negotiable product / scientific behavior

1. Initially infer **common ε** across all grids using Bayesian primary posterior and deterministic consistency sets in parallel. **Switch to grid-specific mode only if two distinct internally consistent grid constraint sets have empty intersection (case B)**. A disconnected interval within one grid (case A) is NOT the trigger; neither is an inconsistent set within a single grid.
2. Use frozen 62-person / 2,400 synthetic group data from `data/submission`. Each N=3…10, 300 groups, 5 within-N SD quintiles. Preserve source hashes and participant/group ids pseudonymous.
3. Configurable app-local scientific `SETTINGS`: default full domain 12–33°C inclusive step 0.1, **all 211 choose 2 = 22,155 unordered temperature pairs for every group**, **53,172,000 total**, **no prefilters or hidden shortlist**. Do not overwrite historical 15–31°C reproduction and reference fixtures.
4. Next question **maximizes pure expected information gain**, without time division, quota, trade-off screen, Pareto pruning or ad hoc thresholds. Score all eligible unasked candidates (or mathematically equivalent exact computation). If exact interactive scoring cannot meet measured runtime, **report failure and quantitative benchmark** instead of pretending approximate score is global best.
5. Contextual stage: expose 40 independent, uncertainty-tagged grid ε posteriors; also compute/display expected-welfare-regret-minimizing fixed ε policy, with uniform-grid or actual observed-frequency weights selectable and transparent. Underidentified cells remain underidentified; no hidden hierarchical shrinkage or q-averaged overall epsilon.
6. Operation screen offers human-approved COMMON_FIXED / CONTEXTUAL_BY_GRID / REGRET_OPTIMAL_FIXED. Real data input and separate seeded DEMO are essential. Replay, Shadow and Assisted Live must preserve actual-vs-simulated, recommended-vs-approved-vs-applied-vs-measured distinctions. No HVAC direct actuation.
7. Professional desktop-first operator web console with Next.js, TypeScript, shadcn/ui, FastAPI, PostgreSQL; install/run via Docker Compose; implemented audits, access controls, API docs, import/validation/export, analytics and Playwright.

## Milestones / hard gates

**M1 — repo + scientific smoke**: create app folder docs, dependencies, config and source-data adapter. Run historical CLI/tests, verify 211/22,155/53,172,000 and known synthetic groups. Record full exact regression result.

**M2 — source question bank & mathematical oracle**: generate derived utility/welfare curves; lazy/block enumeration of **every pair**; exact all-bank score baseline reference tests on reduced grids; document numerical accuracy. Expose bank provenance via API and CLI.

**M3 — inference + switch**: posterior update with explicit uncalibrated likelihood and prior settings; deterministic feasible-set union and numerical root diagnostics; confirm B switch and A no-switch / intra-grid no-switch with synthetic cases. Persist full trial records.

**M4 — contextual + fixed regret**: per-grid posterior/status, policy regret objective and weights, tie ranges and prior sensitivity; human policy confirmation and version audit.

**M5 — operation backend + DB**: real and demo ingestion; versioned zone and policy; decision cycles; replay/shadow/assisted states; integrity validation, auth and audit logs; rollups and exports.

**M6 — frontend**: accessible neutral A/B experiment, switching explanation, posterior chart, grid heatmap, policy selection, live operation dashboard and analytics. Keyboard/contrast/labels.

**M7 — verification**: pytest + reference tests + Playwright E2E; dual-mode synthetic-operator tests, choices' data-quality cases, alternative prior/likelihood sensitivity, EIG exactness and full-bank performance benchmark. Document failures and risks honestly in `app/validation/TEST_REPORT.md`.

**M8 — deliver**: root app README, app README complete, SPEC and docs, local run commands tested, documented API, reproducible demo, PR URL and test results. If something is blocked, state precise uncompleted step; never quietly loosen requirements.

## Required repository files

`app/README.md`, `app/SPEC.md`, `app/SETTINGS.yaml`, `app/.env.example`, `app/docker-compose.yml`, `app/docs/{SCIENTIFIC_CONTRACT,DECISION_RATIONALE,QUESTION_BANK,INFERENCE,POLICY_AND_REGRET,DATA_DICTIONARY,API,UX_UI,OPERATIONS,ANALYTICS,TEST_PLAN,DEPLOYMENT}.md`, `app/backend/`, `app/frontend/`, `app/demo/`, `app/scripts/`, `app/validation/`, `.gitignore` for generated `app/outputs/`.

## Scientific assertions Codex must NOT make

- 'EIG makes disconnected deterministic ε sets impossible' — false without a proof; document only user's B switching rule.
- 'B switch proves the operator's moral preference varies with context' — no; noisy choices can imitate B.
- 'Bayesian credible interval is same as deterministic compatibility region' — no.
- 'The frozen dataset supplies actual time-series building operation data' — no.
- 'All-pair EIG evaluated' if a top-K candidate shortlist was substituted — no.
- 'Optimal fixed epsilon estimates the overall true epsilon' — no; it minimizes model-conditional expected policy regret.
- 'Applied/approved setpoint is a measured physical action' — no; separate confirmation fields.
- 'Model utility proves measured comfort/energy savings' — no.

## Codex acceptance / review

Provide PR with a complete check list tied to spec Section 12. Include terminal logs/test commands, version/hash manifests, full-bank EIG runtime and memory for the default 53.172M candidates, any remaining unvalidated scientific assumptions, and screenshot evidence if possible. Block automatic merge.
