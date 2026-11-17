# NPSDM App — Scientific & Product Specification v1.0 (Codex handoff)

**Status:** User decisions locked on 2026-11-17. This file is the implementation contract. The user-facing application is not yet implemented.  
**Repository:** `gunkuk/Normatively-Parameterized_Shared-Setpoint_Decision_Model`  
**Working boundary:** create `app/` at repository root; do not silently change `model/npsdm/`, `data/submission/`, or historical reproduction behavior.  
**Non-negotiables:** mathematical integrity, all candidate temperature pairs eligible, no ad hoc scenario filtering, transparent uncertainty, actual + synthetic operational data, reproducible provenance.

## 0. Decision register — locked requests versus technical choices

| ID | Decision | Status | Why / constraint |
|---|---|---|---|
| D01 | Start **common (overall) ε** inference; move to grid-specific ε only when **different grid evidence conflicts** (case B) | USER LOCKED | Avoid needless high-dimensional estimation; a disjoint interval **within** a single grid (case A) is **not** a switching trigger. |
| D02 | Group size N=3…10; heterogeneity quintile H1…H5; source = frozen 2,400 synthetic groups | USER LOCKED | Fig. 9 grouping, source provenance. |
| D03 | Temperature search defaults to **12.0–33.0°C, inclusive, 0.1°C**; editable through versioned `SETTINGS` | USER LOCKED | Paper Methods; do not overwrite historical 15–31°C reproduction. |
| D04 | **Every unordered pair of different candidate temperatures** for every frozen group is an eligible question; **no filtering** by utility gain/loss, Pareto status, root count, grid or pair difficulty | USER LOCKED | Pure information-gain acquisition. Multiple intersections and dominated choices allowed; UI describes pairs accurately. |
| D05 | Select next question by greatest **expected information gain (EIG)**; update after every response | USER LOCKED | Adaptive experimental design. |
| D06 | Probabilistic Bayesian inference **primary**; deterministic consistency sets **parallel diagnostic** | USER LOCKED | Handles noise but retains exact constraint interpretation. |
| D07 | Once contextual mode is activated, show **grid-specific ε together with optimal fixed ε**; operator may choose fixed or contextual mode **in Operation** | USER LOCKED | One-policy compromise via expected welfare regret minimization. |
| D08 | Modern browser-based **operator console**, not a phone-only mockup; DEMO, REPLAY, SHADOW, ASSISTED-LIVE | CONFIRMED FEATURE SCOPE | Sustainable operating workflow and audited decision records. |
| D09 | Fixed epsilon from q-mean of grid epsilons | REJECTED | A nonlinear coordinate average lacks social-welfare decision justification. |
| D10 | Switching because a single feasible set has multiple disconnected components (case A) | REJECTED AS TRIGGER | EIG does **not** mathematically rule out case A; record/display it rather than assuming impossible. |
| D11 | Claims of validated Bayesian hyperparameters, EIG runtime, or real-world operator accuracy | NOT ALLOWED | These require calibration/benchmark, not intuition. |

## 1. Definitions, exact calculations, scope

Let the fixed synthetic group be `s` with `N_s` participants and individual representative desired setpoints `d_{s,i}`. The decision temperature set is `T ∈ {12.0, 12.1, ..., 33.0}°C` by default (211 values). Setpoint constraints in actual operations can be narrower and are separately versioned.

Individual thermal utility:

\[
u_{s,i}(T)=\max\left(10^{-3},\min\left(1,\,1-\frac{|T-d_{s,i}|}{6}\right)\right).
\]

Atkinson equally distributed equivalent welfare:

\[
W_e(\mathbf u)=\begin{cases}
\left(\frac1N\sum_i u_i^{1-e}\right)^{1/(1-e)},&e\ge0,~e\ne1,\quad e<\infty,\\
\exp\left(\frac1N\sum_i\log u_i\right),&e=1,\\
\min_i u_i,&e=\infty.
\end{cases}
\]

At `e=0`, `W_e` is the arithmetic mean. `e=∞` is maximin. Compute via `logsumexp`/stable log-domain evaluation near 1 and at high e. Use **entire utility vector**, never derive ε from mean and minimum alone. Presentation metrics: `efficiency = mean(u)`, `equity = min(u)`, `equality = 1 - Gini(u)`, while `total utility = Σ u_i` is shown for leaky-bucket intuition. These are *model-generated utility* indicators, not direct survey comfort or energy data.

`H_s` = population SD (`ddof=0`) of desired setpoints; for each N separately sort its 300 frozen groups by `(H_s, repetition/group_id)` deterministically and assign five groups of 60 to Q1…Q5. Store exact membership, all percentile boundaries (including tie policy), source hashes, dataset variant, grid settings, code commit, and utility settings. 2,400 group records come from repeated sampling of **62 study participants**, not 2,400 independent population observations. Never label group-level inference as an independent external validation.

Source inputs: `data/submission/observations.csv`, `data/submission/groups.csv`, `data/submission/reference.json`; use `model/npsdm/submission.py` for historical identity/tie contract. The **app** has its own versioned `app.config.SETTINGS` setpoint domain (12–33°C), not an undocumented change to the frozen historical model (15–31°C).

## 2. Question bank: exhaustive **all-pair** contract

For each group `s`, create all unordered pairs `(T_a, T_b)` satisfying `T_a<T_b`. At default settings the precise cardinalities are:

- 211 allowed temperature values;
- `C(211,2)=22,155` pairs **per group**;
- `2,400×22,155=53,172,000` candidate question IDs overall.

No scientific/heuristic prefilters: no Pareto dominance test, minimum efficiency/equity difference, unique epsilon crossing, trade-off-direction condition, high-information percentile, grid quota, approximate shortlist or per-group sample. Data engineering batching, exact mathematical equivalence caching, and lazy enumeration **are allowed if they preserve all candidates and identical EIG rankings within documented numerical tolerance**. Store identifiers/indices and derived tensors rather than 53 million large JSON records. Every pair considered must be traceable as eligible and its score computable. Do not claim exact global maximum EIG if an approximation or shortlist was used; surface performance limits.

For each candidate, obtain `u(T_a)` and `u(T_b)` and score the full utilities under epsilon. The *operator display* must present: two temperatures, anonymized individual utility distributions (expandable), mean, minimum, total utility, difference and direction. Some all-pair candidates are **not** leaky-bucket trade-offs (one option can dominate): **do not deceptively label those as an equity–efficiency exchange**. Instead use a neutral 'Which shared setpoint do you prefer?' and display the true changes; call the general method *leaky-bucket-inspired choice elicitation*. Randomize left/right display without changing underlying A/B bookkeeping, log random seed and mapping. No random or demographic respondent labels.

Each question is identified by `(source_version, group_id, min_temperature_index, max_temperature_index)`; prevent exact same pair re-asking in a session (without removing it from the original candidate universe); re-asking is optional separate diagnostic experiment and must be explicitly labeled, not part of default pure max-EIG selector. Unlimited mode can stop when no new question remains or information has saturated.

## 3. Inference: common ε first

Let a binary question response be `Y=1` for the internally defined option B, `Y=0` for A. Under common model M0 the same ε explains choices at every grid, though choices differ across scenarios because whole utility vectors differ.

**Probabilistic likelihood — modeling assumption (not validated fact):**

\[
P(Y=1\mid e,s)=\lambda/2+(1-\lambda)\,\sigma\{\kappa[W_e(u_B)-W_e(u_A)]\}.
\]

`κ>0` sensitivity and `0≤λ<1` lapse rate; initial implementation should expose them in versioned research settings, report numerical values, and require sensitivity checks against alternative parameter settings. **Do not treat the previous κ=30, λ=.05 as empirically calibrated.** Avoid asserting ε is fully identifiable when response scale, preference noise or utility mapping are uncertain.

For computationally auditable 1-D inference, implement a configurable **discrete quadrature** on `q=e/(1+e)`, with `q∈(0,1)` interior points, retaining `e=0` and `e=∞` as **exact decision/reference endpoints** separately. A baseline uniform q prior is an *explicit, contestable engineering convention*, not a normative theorem: report at minimum alternate q-priors and grid-resolution sensitivity; add boundary tail/one-sided unidentifiability warnings. A prior assigning actual mass at `e=∞` or `e=0` must be an intentional optional spike mixture. No false 'exact infinity mass' from an interior continuous prior. Bayesian posterior update is standard normalized likelihood multiplication in log space.

Show posterior median and credible **set** or interval plus prior, uncertainty width, posterior shape, and user-chosen probability mass. If posterior is multimodal, show separated components instead of silently claiming a single narrow interval. The Bayesian posterior remains nonzero under a lapse likelihood even when strict preference inequalities are inconsistent.

### 3.1 Deterministic consistency sets

For each answered question r, define its response-consistent set:

\[
C_r=\begin{cases}
\{e\ge0:W_e(u_{r,B})\ge W_e(u_{r,A})\},&Y_r=1,\\
\{e\ge0:W_e(u_{r,A})\ge W_e(u_{r,B})\},&Y_r=0.
\end{cases}
\]

Allow equality on boundaries (display precision controlled independently). For each grid with at least one observation:

\[
C_g=\bigcap_{r:g(r)=g} C_r,\qquad C_{\mathrm{common}}=\bigcap_{r\text{ answered}} C_r.
\]

Keep **unions of disjoint components**, singleton points, and unbounded upper tail. A grid without observations is *unidentified* (`[0,∞]` mathematically), **not estimated**. Numerical root isolation must check resolution and multiple crossings; output approximate sets with search tolerances and convergence diagnostics, never misleading exact analytic endpoints.

### 3.2 Switch policy — choose the user's **case B** only

Initially `stage=COMMON`. After every response recompute the sets:

- **Trigger B**: there exist **two distinct grids, each with at least one answer and internally nonempty `C_g`**, such that `C_g∩C_h=∅` (within verified numerical tolerances). Show: *The strict single-ε consistency assumption cannot explain these grid-level choices*. Automatically switch to `stage=CONTEXTUAL` for subsequent question selection and reveal contextual results + fixed-policy approximation. Log the two contradictory grid IDs, constraints, and timestamp.
- **Case A**: a single grid `C_g` or common set has multiple disconnected components but there is **no B conflict**: remain COMMON. Report the disconnected components. **Max-EIG scheduling does not prove case A impossible.**
- **Within-grid contradiction**: `C_g=∅` inside one grid: indicate response inconsistency/noise; do **not** claim that varying epsilon by grid fixes it and do not auto-switch just for this reason.
- **Global contradiction not attributable to a pair of internally consistent grids**: flag diagnostic `COMMON_NOT_STRICTLY_COMPATIBLE`, explain why B criterion was not met; do not silently force contextual acceptance.

*Scientific guardrail:* B is a **decision rule for changing the app's estimation mode**, NOT a hypothesis test proving genuine context-specific moral preferences. Response mistakes, framing and likelihood misspecification can create the conflict. Bayesian model fit comparisons / posterior predictive checks remain available for defense. No automatic on-device policy change is authorized by the switch.

## 4. Contextual stage + optimal fixed policy together

Upon switching, estimate all 40 `e_g` **separately**, starting with a transparent same-form grid prior `p0(e_g)` for each grid; update only the grid where a question was answered. This is the minimally assumption-heavy baseline; it does not impose spurious shared shrinkage or overlap. **Unasked grids remain prior-driven and must be visibly flagged**. Explicit hierarchical pooling is NOT a default hidden assumption; include as future validated optional comparison only if scientifically justified by synthetic-operator tests. Posterior/frequentist accuracy cannot be asserted from 5–30-minute sessions.

The only switch is which preference model is used for *inference/acquisition*. It does not erase the common posterior or prior history; keep all responses for reproducibility. A question in grid g uses `p(e_g|D_g)` and its utility pair. `e_common` remains a comparison baseline only after the conflict, marked strict-incompatibility.

### 4.1 Simultaneous derived optimal fixed epsilon

**Always compute alongside contextual output** a single policy epsilon `e_fixed*` by expected normative welfare regret, conditional on available data, target distribution, and constraints.

For operational case/scenario `s` in grid g, let

\[
T_s^*(e)=\mathop{\arg\max}_{T\in\mathcal T_s}W_e(u_s(T)).
\]

For hypothetical true contextual aversion `e_g`, define

\[
R_s(e;e_g)= W_{e_g}(u_s(T_s^*(e_g))) - W_{e_g}(u_s(T_s^*(e))).
\]

Then choose

\[
\boxed{e_{\mathrm{fixed}}^*\in\arg\min_{e\ge0}\sum_{g=1}^{40}\rho_g\,\frac{1}{|S_g|}\sum_{s\in S_g}\mathbb E_{e_g\mid D_g}[R_s(e;e_g)]}. 
\]

- `S_g` = 60 frozen groups per g for reproducible study/demo calculations; in actual building operational analysis optionally use **versioned observed future-relevant scenarios** (no leakage of outcomes).
- `ρ_g≥0`, `Σρ_g=1` is the **policy target distribution**, *not* a mathematically mandated weight. Research-demo default `1/40` may be chosen only with explicit `uniform_grid` label; building mode can instead use observed grid occurrence frequencies, with look-back window/smoothing/coverage reported. User explicitly may choose weighting mode **at Operation**.
- `T_s` feasible domain must reflect the policy and building temperature constraints (versioned separately from offline 12–33 question bank).
- If optimum is a **set/plateau**, return the set/range; allow operator final confirmation of a representative with a declared tie rule; do not pretend unique ε exists.
- Underidentified grids can dominate the optimum through their priors. Show a sensitivity panel and strong *provisional* flag; do not call it statistically optimal for the real world.
- This is a **best fixed approximation to contextual normative targets**, not an estimator of a 'true overall ε' and not an energy-optimal thermostat setting.

**Operation policy choices:** (1) `COMMON_FIXED` (when common is coherent), (2) `CONTEXTUAL_BY_GRID` (approved per-grid epsilon policy with fallback for unidentified/out-of-domain grids), (3) `REGRET_OPTIMAL_FIXED` (approved fixed epsilon from above). Show `CONTEXTUAL_BY_GRID` and `REGRET_OPTIMAL_FIXED` together in policy review; always require human approval, record chosen version and prior/weights.

## 5. Adaptive selection — pure EIG, no arbitrary weights, no scientific filtering

At stage COMMON, the latent estimand is `e_common`. Score **every eligible unasked pair** by mutual information:

\[
\operatorname{EIG}_0(s)=I(Y_s;e_{common}\mid D)=H(Y_s\mid D)-\mathbb E_{e\mid D}[H(Y_s\mid e)].
\]

At stage CONTEXTUAL, the latent parameter vector is `\boldsymbol e=(e_g)_{g=1}^{40}`. Under independent per-grid priors/posteriors and because a question in grid g depends only on e_g:

\[
\operatorname{EIG}_1(s)=I(Y_s;\boldsymbol e\mid D)=I(Y_s;e_g\mid D_g).
\]

This **joint-information interpretation** avoids arbitrary `[overall, grid, model]` weights and is fully consistent with sequential switching. **Do not** divide EIG by estimated response time in the default scorer or enforce cell quotas: user chose the largest information gain. An optional clearly labeled `research_comparison` method may evaluate regret-aware selection, but cannot replace pure EIG without separately granted scope.

For Bernoulli response with posterior scenario-specific probability `p_s(e)`, use exact discrete-posterior formula

\[
\mathrm{EIG}(s)=h\big(\mathbb E[p_s(e)]\big)-\mathbb E[h(p_s(e))],\quad
h(p)=-p\log_2p-(1-p)\log_2(1-p).
\]

Question tie rule: maximum EIG within documented machine precision; deterministic stable scenario ID chosen (reproducibility), while left/right screen orientation can be randomized and fully logged. **Do not infer context effects merely from different question crossover values**: same ε can yield different scenario choices.

**Computational caveat (hard constraint):** 53,172,000 candidates × many ε nodes × every response is a substantial computation. Build a fast proof-of-concept/full-bank benchmark BEFORE promising low-latency interactive EIG. You may use exact streaming blocks, compiled kernels, GPU optional, precalculated per-group per-temperature welfare curves, equivalent-form algebraic caching; **must evaluate every eligible candidate for the declared global maximum**. If not feasible, UI should show a long-running progress state or explicitly mark approximate mode and seek authorization before relaxing the all-pairs/no-filter criterion. The Codex agent should publish memory consumption, full-bank elapsed benchmark, numeric precision and exact-vs-reference sample checks. Do not quietly switch to a top-K shortlist.

**Time budgets:** user-selectable estimated survey length 5/10/30 min/unlimited. Timing is a UX constraint, **not** guaranteed ε accuracy. Trigger either user stop, elapsed budget, or no informative unused questions; save interrupted sessions, unanswered/skipped trials separately, report `UNIDENTIFIED` if applicable. Skips are not modeled as A/B answers. Time budget does not modify pure-max EIG ranking.

## 6. Scientific evaluation / defense before product claim

1. Full source checksum and frozen historical submission reproduction; app's adjusted temperature range is version-disclosed, never silently compared to 15–31°C reference outputs.
2. Validate all temperature counts, all-pair count, no hidden filters, utility baseline and Atkinson endpoint behavior.
3. Analytic vs quadrature reference EIG on hand-constructed small banks; symmetry/tie and repeated-answer stability.
4. **M0 synthetic operators** with identical epsilon across grid: compare predicted vs observed choices; measure false contextual switching due to lapse/noise separately from *true* preference variation.
5. **M1 synthetic operators** with substantially different grid-specific epsilon: evaluate switching sensitivity, per-grid recovery, probability calibration, confidence/credible-region accuracy, unasked-cell `UNIDENTIFIED` reporting.
6. Stress: multiple roots, disconnected components, within-grid impossible constraints, identical utilities, dominated pair, posterior boundary saturation, `epsilon=1/∞`, high SD and temperature extremes.
7. Prior and κ/λ sensitivity, choice fatigue/response noise, no false claim of fully calibrated parameters.
8. EIG vs random vs balanced selection at equal response counts, with clear chosen user requirement `pure EIG` regardless of any baseline result.
9. Fixed-regret validation: regret ≥0 up to tolerance, fixed optimum no worse than any benchmark tested, correct grid weighting and tie plateau; compare contextual and fixed on identical inputs.
10. Full 53m-pair performance benchmark; memory and latency observability, no silent approximation.
11. Historical tests, backend tests, frontend E2E, API schema, audit/security, demo/replay/shadow operations and deterministic exports.

A scientific statement of empirical effectiveness requires human/pilot validation; simulator-based recovery under the same assumed likelihood is **internal verification**, not external validation.

## 7. Product architecture and standard operator UX

**Architecture:** `app/frontend/` Next.js App Router + TypeScript + Tailwind + shadcn/ui, `app/backend/` FastAPI + NumPy/SciPy + SQLAlchemy + Alembic, PostgreSQL persistent operational database, optional separate worker for expensive EIG. Compose for local demo. Version lock dependencies; version-control configs. CI with `pytest`, JS static checks, Playwright for core flows.

**UI:** desktop-first responsive operations console; clear DEMO/REPLAY/SHADOW/ASSISTED-LIVE badge; keyboard usable; WCAG 2.2 AA target; selection mode progress, A/B neutral wording, distributions + total/mean/min values; contextual conflict diagnostic, not a claim of true moral instability; policy approval step and no unapproved automatic actuation. Use Nielsen usability principles (visibility, control, error prevention, consistent terminology). Choose compact dashboard in operations and one-question-at-a-time for survey.

**Screens:** Overview; Elicitation setup/questions/results (common then contextual); Policy comparison & approval (common/contextual/regret-optimal fixed); Buildings/Zones; Operation console; Data ingest/validation; Historical Analytics; Research/Quality diagnostics; Settings and roles. Show posterior diagnostics and all data provenance in an Advanced panel; show understandable total efficiency and worst-off improvements to operators.

## 8. Real operation + synthetic operation (must be implemented)

Modes: `DEMO` (generated; isolated namespace), `REPLAY` (timestamped imported data), `SHADOW` (live data, recommendations only), `ASSISTED_LIVE` (recommendation → human accept/reject/override → record manually applied setpoint and observed confirmation). **No automatic BMS/HVAC control in v1** and no false claim that operator approval proves physical actuation. Every decision stores `mode`, `data_origin`, `model_version`, `policy_version`, `config_hash`, `quality` and UTC event timestamp (with building local timezone for display).

**Data at minimum:**

| Domain | Required / optional examples | Grain | Input route |
|---|---|---|---|
| Site/zone/config | site_id, zone_id, operating setpoint limits, timezone, action cadence | versioned zone | UI + API |
| Occupant presence | opaque occupant_id, zone_id, observed_at, present, source | occupant×time | UI/CSV/API |
| Preferred temperature | occupant_id, desired_setpoint_c, time, actual_report/PCM_prediction/proxy source, model_id and uncertainty if predicted | occupant×time | UI/CSV/API |
| Environment | zone_id, sensor timestamp, indoor air temperature, RH, sensor_id, quality | zone×time | optional UI/CSV/API |
| Feedback | thermal sensation, preference, comfort vote, respondent id, timestamp, consent/source | occupant×time | optional UI/CSV/API |
| Metering | meter_id, kWh or kW with interval & units, zone mapping, timestamp | meter×time | optional CSV/API |
| Decision | group members/version, N, SD, H, epsilon policy and value, recommended T, predicted welfare, constraints, missingness, timestamps | zone×decision | computed |
| Action | recommended / approved / rejected / override / manually applied / independently confirmed | event | UI/API |

**Behavior:** determine current occupants from explicit presence and freshness rules, retrieve recent preferences, reject invalid/missing data with actionable diagnostics (do not silently fill), map N=3…10 and H to frozen quintile boundary version, select policy epsilon, maximize welfare over zone's feasible temperature domain, show predicted outcomes, log recommendation and operation action separately. Out-of-domain N or SD, sensor staleness, unpublished/unauthorized contextual cell -> warn and use only explicitly configured and operator-approved fallback; never silently extrapolate.

**DEMO:** freeze 2,400-study-group identity as initial population only. Original dataset has **no real hourly operational series**. Generate arrivals/departures, preference changes, room-temperature responses, sensor noise, energy (if shown) with **separate documented synthetic assumptions** and seed. Mark all as simulated; no leakage into actual observations and no claim of realistic HVAC physics absent validation.

**Data integrity/privacy:** use pseudonymous occupant IDs, no names or sensitive demographic fields unless strictly necessary; scope by site/zone, roles (Viewer/Operator/Admin/Researcher), immutable policy versions, audit trails and configurable retention. Database secrets not committed. Consent/legal obligations for any actual occupant feedback must be addressed before real deployment.

## 9. Analytics semantics

Always distinguish **recommendation**, **operator approval**, **applied setpoint**, **measured temperature** and **modeled individual utility**. Optional measured survey comfort is a different outcome. Dashboard:

- Current metrics: measured indoor T, recommended T, last applied T, active policy/epsilon, N/H, data quality and decision age;
- Curves: recommended/applied/measured T; modeled mean/min/1-Gini welfare (with legend for prediction versus realized-temperature-based *modeled* welfare); group size and SD; approvals, overrides and state transitions;
- Analysis: daily/weekly/monthly selectable, individual exposure-time-weighted modeled utility and worst-off burden, time outside target, missingness/staleness, conditional grid occupancy, versioned policy comparisons;
- Counterfactual comparison on **identical** observed-group input snapshots: common fixed vs contextual vs regret-optimal fixed, clearly modeled-not-observed differences;
- Energy only when input metered and valid; not causal savings without baseline/M&V design;
- Aggregation by nonoverlapping time intervals and valid coverage, with sample/exposure denominators, missingness, timezone/DST handling, and distinct DEMO vs real filters.

Export machine-readable: `run_manifest.json`, `scenario_bank_manifest.json`, `elicitation_trials.csv`, `common_epsilon_M0.json`, `grid_specific_epsilon.csv`, `conflict_diagnostics.json`, `fixed_epsilon_regret.json`, `question_eig_diagnostics.csv`, `policy.json`, `decision_cycles.csv`, `observations.csv`, `actions.csv`, `daily_summary.csv`, `policy_counterfactual.csv`, `data_quality.csv`, `validation_report.json`. Raw application state lives in DB; file export is intentional and reproducible.

## 10. Repository contract

```text
repo/
├── README.md                        # preserve historical project docs; link new app only
├── data/ model/ tests/ validation/  # do not silently rewrite
└── app/
    ├── README.md                   # installation/run/architecture/data/tests/outputs/limits
    ├── SPEC.md                     # this signed-off scientific & product contract
    ├── SETTINGS.yaml               # configurable scientific defaults; versioned/fingerprinted
    ├── .env.example
    ├── docker-compose.yml
    ├── docs/
    │   ├── SCIENTIFIC_CONTRACT.md  # model formulas, comparison with frozen study
    │   ├── DECISION_RATIONALE.md   # evidence/alternative/failure/validation register
    │   ├── QUESTION_BANK.md        # 2,400 group × all distinct temperature pairs
    │   ├── INFERENCE.md            # common-first, grid conflict, Bayesian + deterministic
    │   ├── POLICY_AND_REGRET.md    # contextual + fixed policy, target weights
    │   ├── DATA_DICTIONARY.md      # schemas, provenance, privacy
    │   ├── API.md                  # endpoints and error contracts
    │   ├── UX_UI.md                # flows, accessibility, operator states
    │   ├── OPERATIONS.md           # real/synthetic workflows, approvals
    │   ├── ANALYTICS.md            # metrics and aggregations
    │   ├── TEST_PLAN.md            # automated + simulation + speed benchmarks
    │   └── DEPLOYMENT.md           # local/demo/server/known security boundaries
    ├── frontend/                   # Next.js + TS + shadcn/ui, Playwright
    ├── backend/                    # FastAPI + NPSDM adapter + EIG + database + tests
    ├── demo/                       # deterministic synthetic operating series, seeds
    ├── scripts/                    # setup/verification/benchmark/build bank
    ├── validation/                 # versioned checks/reports (not source dataset)
    └── outputs/                    # gitignored generated exports
```

**Editable SETTINGS must contain at minimum:** `question_temperature_min_c=12`, `max=33`, `step=0.1`, `utility_width_c=6`, `utility_floor=0.001`, `group_sizes=[3..10]`, `heterogeneity_quantiles=5`, `q_quadrature_count` (documented accuracy), `prior_family/parameters`, `choice_kappa`, `choice_lapse`, `experiment_time_budget`, `posterior_mass`, `mode_switch_rule=B`, numerical comparison tolerances, algorithm cache/block/precision settings; operation zone feasible bounds and cadence must be zone/policy-level settings. On change of scientific settings, invalidate scenario-bank cache and annotate all outputs with full config hash. Reject invalid min/max/step and configurations outside historical-derived data capability; settings edit is an administrator/researcher function, not a free-form runtime user change to published results.

**Potential performance issue:** changing temperature range can explode `C(M,2)` (quadratic growth). Validate config and display cost estimate; changing settings must not silently change frozen reproducibility tests.

## 11. API/DB minimum contracts

HTTP API routes (versioned `/api/v1/`): `GET settings`, `GET question-bank/provenance`, `POST elicitation/sessions`, `GET/POST elicitation/{id}/next-or-response` (idempotent and concurrency safe), `GET elicitation/{id}/results`, `POST policies/draft`, `POST policies/{id}/approve`, `POST sites/zones`, `POST ingest/{preferences,occupancy,environment,feedback,metering}`, `POST operations/decide`, `POST operations/{id}/actions`, `GET operations/history`, `GET analytics/summary`, `GET exports/{run_id}`, `GET health/ready`. Specify Pydantic schema, units, timezones, validation errors and auth for each. Server-side authorization, immutable approved policy versions, no cross-tenant access, transactional response append and posterior checkpoint.

DB tables: `sites`, `zones`, `users`, `roles`, `occupants`, `presence_events`, `preference_observations`, `environment_readings`, `thermal_feedback`, `meter_readings`, `elicitation_sessions`, `elicitation_trials`, `posterior_checkpoints`, `scenario_bank_versions`, `model_policies`, `decision_cycles`, `operator_actions`, `audit_events`, `dataset_ingests`. Multi-site scoping and indices by `(site/zone,timestamp)`; migrations and backup documented. Separate `data_origin` and `operation_mode` — they are not interchangeable.

## 12. Acceptance criteria — Codex must report PASS/FAIL, not conceal exceptions

- [ ] Historical exact reproduction tests still pass without edits to frozen data.
- [ ] Default SETTINGS exactly 12.0–33.0 by 0.1 inclusive; alternate range is editable and deterministically changes counts + cache hash.
- [ ] All 53,172,000 distinct questions remain eligible, with no implicit filters or approximate shortlist masquerading as exhaustive search.
- [ ] Utility and welfare corner-case numerical tests match known values, with documented tolerances.
- [ ] Common Bayesian posterior updates and strict feasible-set intersections tested, including possible disconnected sets.
- [ ] **Only inter-grid B conflict** triggers grid-specific acquisition; case A and within-grid inconsistent responses do not.
- [ ] Contextual result always includes fixed regret-optimal policy (with weighting, prior sensitivity, confidence/status and optimizer tie ranges).
- [ ] Pure maximum EIG verified against brute-force small-case oracle; performance for default 53m bank disclosed before claim of interactive latency.
- [ ] Full operator journeys: demo, replay, shadow, assisted-live; real input from CSV/API, repeated decisions, durable database/audit log, exports.
- [ ] Visual distinctions for simulated vs real, suggested vs applied vs measured, deterministic vs Bayesian intervals, common vs contextual vs fixed-regret.
- [ ] Documented `README`, scientific contract, implementation defense rationale, public data/consent/privacy notes, settings and all outputs.
- [ ] Frontend/build/static/E2E, backend/integration/security tests run; results captured in `app/validation/`.

## 13. Evidence sources and what each actually supports

- **Internal paper/source of truth:** `Kuk et al. (2026) Manuscript_clean.docx`, Section 3.3 and Section 4.2/5.4; repository `model/npsdm/{social.py,utility.py,submission.py}`, `data/submission/{observations.csv,groups.csv,reference.json}`. Research dataset supports group composition and *model-derived* utility, not real operating response dynamics.
- **Atkinson EDE/inequality valuation:** Atkinson A.B. (1970), *On the Measurement of Inequality*, Journal of Economic Theory, DOI `10.1016/0022-0531(70)90039-6`; original paper supports framework, **not** this app's independent choice model.
- **Expected information gain as experiment objective:** Chaloner K. & Verdinelli I. (1995), *Bayesian Experimental Design: A Review*, Statistical Science 10(3), 273–304, DOI `10.1214/ss/1177009939`. Does **not** prove interactive speed or this app's optimal empirical accuracy.
- **Web API schema:** https://fastapi.tiangolo.com/tutorial/first-steps/ (FastAPI native OpenAPI).
- **Operator UX/accessibility:** https://www.w3.org/TR/WCAG22/ (WCAG 2.2), https://ui.shadcn.com/docs (UI components), https://playwright.dev/docs/intro (E2E testing), https://nextjs.org/docs/app (React application architecture).

## 14. Known unsolved issues / mandatory discovery gates

**Gate G1: exact full-bank EIG benchmark** — 53.172M candidates is large. Do a measured scale test, then choose a mathematically equivalent acceleration. If the user-chosen exhaustive requirement cannot be achieved at usable speed, do not silently violate it; report quantitative limit and ask before changing scientific selection semantics.

**Gate G2: response-model calibration** — κ/lapse and prior are unvalidated; provide defaults only as explicitly labeled assumptions and run sensitivity checks. Real survey pilot needed to claim operational validity.

**Gate G3: conflict detection numeric rigor** — disjoint epsilon constraint regions are tolerance-sensitive with nonlinear roots. Convergence verification and recorded trigger witnesses required.

**Gate G4: operational real-world deployment** — live data permissions, privacy, reliability, and HVAC handoff are external validation tasks. V1 supports operator-assisted decisions and persistent logs, not autonomous HVAC actuation.

## Appendix A — Independently computed small numerical checks (not app validation)

These checks use actual frozen-group desired setpoints and the 6°C triangular utility, and were independently recomputed with SciPy's scalar root finder. They demonstrate that **question-specific** crossover ε depends on group composition, not that the operator's own ε must vary.

| Frozen group | Desired setpoints (°C) | Pair A→B | Mean utility A→B | Min utility A→B | Atkinson tie ε |
|---|---|---|---|---|---|
| N5/R041, low SD (0.800°C) | 24,22,22,22,23 | 22.0→23.0°C | 0.9000→0.8667 | 0.6667→0.8333 | 3.402858816 |
| N5/R049, high SD (1.960°C) | 25,23,25,20,25 | 25.0→22.5°C | 0.7667→0.6500 | 0.1667→0.5833 | 1.040219717 |

Reproduce root isolation inside `app/backend/tests/test_reference_scenarios.py`; test does not validate every pair or the response model.
