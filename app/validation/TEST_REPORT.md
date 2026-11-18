# NPSDM implementation verification

Status: implemented local operator application; numerical/software verification recorded below. This report does not certify field accuracy, comfort improvement, energy savings, formal interval arithmetic, or production security.

## Executed checks

| Check | Result | Evidence |
|---|---|---|
| Existing local research tests | PASS, 8 tests | historical-tests.log (includes preexisting local-study tests not added by this PR) |
| Full frozen historical reproduction | PASS, 21,600 decisions; unchanged source inputs/code | HISTORICAL_REPRODUCTION.json |
| App backend numerical/API/security tests | PASS, 39 tests | VERIFY.json; high-precision welfare, crossing/tangency, switch rules, regret oracle, tenant scoping, idempotency, retention and timezone tests |
| Frontend TypeScript and production build | PASS | VERIFY.json |
| Docker PostgreSQL/API/frontend stack | PASS | docker-build.log |
| Browser operator journey and invalid authentication | PASS, 2 Playwright tests | PLAYWRIGHT.json, browser-tests.log, OPERATION.png, ELICITATION.png |
| Actual PostgreSQL operation APIs and full-bank response transaction | PASS | LIVE_INTEGRATION.json; ACTUAL routes use explicitly labeled validation fixtures, not human data |
| Contextual conflict, full fixed-policy calculation and human approval endpoint | PASS | CONTEXTUAL_INTEGRATION.json; synthetic response fixture |
| PostgreSQL backup restored into new temporary DB | PASS | BACKUP_RESTORE.json |
| M0/M1, EIG/random/balanced synthetic comparisons | EXECUTED, limited internal simulation | SYNTHETIC_OPERATORS.json |
| Human pilot / field operational accuracy | NOT RUN | Requires real participants and site protocol |
| Formal WCAG conformance / penetration testing | NOT RUN | Keyboard/labels/responsive design and auth tests do not replace these audits |

## Full-bank and fixed-policy measurements

- Windows initial full scan: **53,172,000 candidates**, 64 midpoint q nodes, float64; **376.953 seconds**; peak sampled process RSS **399,360,000 bytes**. No candidate shortlist or heuristic filter. Source: FULL_BANK_BENCHMARK.json.
- Linux Docker full-bank request plus response/result transaction: **105.250 seconds** end to end. This is a different runtime/environment and is not a directly controlled speed comparison. Source: LIVE_INTEGRATION.json.
- Full 2,400-group uniform-prior fixed policy: **302.133 seconds**, numerical representative epsilon **2.254600941051**, model-conditional expected regret **0.010529595897**. Returned minimizer sets, rather than this representative alone, define the result. Source: FIXED_REGRET_BENCHMARK.json.
- Contextual fixture with zone constraints and two alternative q priors: **205.845 seconds** through successful policy approval. Source: CONTEXTUAL_INTEGRATION.json.

These benchmarks concern named configurations and hardware. They do not promise subsecond interaction or posterior accuracy. These baseline measurements predate the fixed-introduction amendment below. The UI displays long-job status; cancellation preserves trials and exact restart does not substitute approximate selection.

## Specification acceptance mapping

| Spec section 12 item | Status / qualification |
|---|---|
| Frozen reproduction unchanged | PASS |
| Editable 12–33°C, 0.1°C defaults and cache/config identity | PASS; edits are versioned YAML + validated restart, not an unrestricted runtime form |
| All 53,172,000 questions eligible | PASS; full measured scan and arbitrary-pair score API |
| Utility/welfare corner cases | PASS against 60-digit references and known crossover fixtures |
| Bayesian and union-valued strict consistency | PASS on tests; approximate numerical root endpoints disclosed |
| Only B triggers contextual acquisition | PASS; case A/intra-grid/global-only diagnostics separated |
| Contextual and regret-optimal fixed outputs together | PASS; background status, independent unidentified grids, zone bounds, weights and prior sensitivity |
| Pure max EIG and full-bank runtime | PASS after the user-authorized fixed first question, on discrete quadrature; continuous quadrature-resolution uncertainty remains |
| Demo/replay/shadow/assisted-live, DB, imports and exports | PASS locally; no physical equipment command integration |
| Visual semantic distinctions | PASS on implemented journeys; no independent accessibility certification |
| README, implementation details, scientific/data/operating docs | PASS |
| Frontend/backend/integration/security verification | PASS locally; remote CI result is the PR workflow check and must be read separately |

## Scientific limits exposed by validation

The reduced synthetic-operator experiment used two frozen groups, a reduced temperature grid, 12 seeds per condition and 24 responses. Pure EIG switched in 0/12 common-epsilon simulations and 3/12 contextual simulations. This is not evidence of reliable real-world detection: contextual credible-set coverage was approximately 0.417 in this small experiment. Balanced acquisition produced many false switches under common epsilon. These comparisons do not change the mandated deployed pure-EIG selector; their different queried items also limit direct Brier-score comparisons.

Root isolation uses floating-point exponential polynomials, tolerance refinement and a dominant-tail bound. The fixed search partitions continuous epsilon by upper-envelope crossings and retains point ties; it is not a machine-checked interval-arithmetic certificate. Extremely close/canceling roots remain a numerical limitation. The UI/report uses model-conditional and provisional labels.

The 23°C anchor and multi-objective tie rule are explicit operational design choices. They do not prove reduced temporal variation or lower estimation error. Actual-group boundary equality is assigned to the lower interval without changing frozen 60-group memberships.

## Scope and remaining deployment work

Existing research files and the user's uncommitted changes are not part of this PR. New files live under app/ except the app-only GitHub Actions workflow. There is no automatic merge.

No organizational SSO, distributed multi-worker job scheduler, full subject-erasure workflow, autonomous HVAC control, empirically calibrated thermal dynamics, or site deployment approval is claimed. Local roles use provisioned bearer credentials, jobs use one process, retention is an explicit dry-run-first administrative CLI, and actual operation requires authorized site data. These boundaries are documented rather than hidden as completed production capabilities.

CI regression: a run near Asia/Seoul midnight correctly split one 15-minute exposure across two daily buckets. The test now checks total person-seconds across buckets instead of assuming one calendar day. Failed early setup also skips container teardown when no environment file exists.


## November 18 delivery and question experience revision

- PASS: 43 backend tests, TypeScript check, production build; VERIFY.json.
- PASS: 3 Playwright browser journeys, including scenario, distance labels, deferred equality, participant drilldown and font declaration; PLAYWRIGHT.json. Saved OVERVIEW_V2.png and QUESTION_V2.png visually inspected.
- PASS: joint A/B selection agrees with independent exhaustive selection on a reduced bank; cache persistence, branch separation, exclusion and source demographic mapping tested.
- PASS: deployed full-bank A and B cache adoption; DELIVERY_V2.json. Initial measured first-question response 2.09 seconds; shared two-branch cold scan 59.20 seconds; answer-to-next-question 0.036/0.042 seconds after results were ready. These are local measurements, not a service-level promise. Server-start prewarming was added afterward; it changes when work begins, not the exact numerical selection.
- LIMIT: a user answering before speculative work finishes still waits. Skip histories require their own computation. Cache reuse does not provide calibrated human inference or remove exhaustive computation costs.
- User-authorized changes supersede the initial specification only for the fixed introductory question and descriptive demographic display; scientific utility and posterior definitions remain unchanged.
