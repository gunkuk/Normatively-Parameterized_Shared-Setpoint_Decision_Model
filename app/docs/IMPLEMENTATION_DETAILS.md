# Implementation details

Decision record: 2026-11-17. These user-approved operational extensions supplement the supplied v1.0 specification. This document records intended behavior; implementation and validation status is reported in ../validation/TEST_REPORT.md. Historical reproduction code and data remain unchanged.

## 1. Operational multi-objective tie resolution

The manuscript framework serves an analytical purpose. The application serves operational decision support and adds a lexicographic, multi-objective tie-resolution procedure. It does not replace the primary Atkinson welfare objective with a weighted sum of presentation metrics.

For a specified epsilon and feasible temperature domain:

1. Retain the temperatures maximizing Atkinson EDE welfare, within an explicitly versioned numerical tolerance.
2. Within that set, retain the Pareto-nondominated candidates in efficiency (mean individual utility) and equity (minimum individual utility). A candidate is dominated when another is no worse in both metrics and strictly better in at least one, under documented numerical tolerances. If these metrics trade off, retain both candidates at this step.
3. Maximize equality (1 minus Gini) among the remaining candidates.
4. Minimize absolute distance from the operational reference temperature, 23 degrees Celsius.
5. If candidates still tie, use a reproducible seeded random selection. Record the candidates, seed and selected temperature. Repeated identical inputs and policy versions must yield the same result.

The 23-degree reference is the user's chosen nominal neutral-temperature anchor. Its intended rationale is to favor central settings, reduce unnecessary variation, and limit potential consequences of estimation error. These are design intentions, not established empirical benefits: a fixed anchor does not minimize change from the previous applied temperature, does not guarantee lower expected error without a specified error distribution, and is not a universal physiological neutral temperature. No temporal smoothing or hidden switching penalty is introduced by this rule.

This same selection procedure must be used for operational recommendations and both oracle and candidate decisions in fixed-policy regret evaluation. Settings, numerical tolerances and tie-rule version must be exported. This does not change the pure maximum-EIG question-selection tie rule.

## 2. Heterogeneity boundaries for new operational groups

Frozen research groups retain their exact within-N assignments: sort 300 groups by population SD and the specified repetition/group identity, then assign 60 groups to each of five quintiles. Never reassign historical groups using operational boundary logic.

New operational groups have no historical repetition/group identity. Map their population SD to versioned within-N cutpoints; equality with a cutpoint belongs to the lower-heterogeneity interval. Repeated cutpoints can make an operational interval empty and must be disclosed rather than perturbed to manufacture equal-sized bins. Operational frequencies need not be 20 percent per bin.

The exact cutpoint construction, tie counts and boundary tests must be recorded with the source version before operational use. Unsupported group sizes or SD outside the frozen support require an explicitly approved fallback; absent a fallback, refuse the recommendation with actionable diagnostics.

## 3. Validation obligations

- Test efficiency/equity dominance and incomparable candidates without changing primary welfare maximizers.
- Test equality, distance-to-23 and residual symmetric ties independently.
- Verify deterministic replay and consistent tie handling in regret calculations.
- Test exact operational cutpoints, values immediately to either side, repeated cutpoints and out-of-support values.
- Report empirical temperature stability and estimation-error robustness as unvalidated until assessed; do not infer them from the tie rule alone.

## 4. Numerical and deployment choices

The default posterior uses 64 midpoint q nodes, with 32/128-node sensitivity views. Its uniform-q prior and kappa=30/lapse=.05 are explicit uncalibrated assumptions. Endpoint decisions include zero/infinity but the continuous prior has no endpoint spikes. Settings are versioned in YAML; changes require a validated restart/new session.

Strict feasible sets use numerical exponential-polynomial root isolation; fixed-policy regret uses upper-envelope intervals and separate singleton tie values. The root tolerance is versioned and formal interval-arithmetic certification is not claimed. All-pair EIG remains exhaustive and independent of policy-only dominance reduction.

Local deployment uses one queued API worker, PostgreSQL snapshot storage, provisioned per-tenant roles and loopback-only ports. A newly added root CI workflow is the only implementation file outside app/; it runs checks without modifying existing research code. Exact computation latency, field validation and deployment limits are separately disclosed.
