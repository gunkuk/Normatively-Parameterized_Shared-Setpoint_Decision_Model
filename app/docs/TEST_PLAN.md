# Test plan

1. Preserve historical input hashes and run original unittest tests plus full 21,600-decision reproduction into app/outputs.
2. Verify utility boundaries, grid counts, stable welfare against high-precision mpmath, epsilon endpoints, operational tie hierarchy and quadrature sensitivity.
3. Compare discrete EIG against independent mutual-information enumeration and exhaustive small-bank selection. Measure the entire 53,172,000-candidate scan without filtering.
4. Test crossing roots, tangencies, disconnected intersections, singleton/infinite endpoints, case A no-switch, within-grid contradiction no-switch, B witness and dense envelope/regret oracles.
5. Run M0/M1 synthetic operators, EIG/random/balanced at equal counts; report false switches, Brier scores and credible coverage with small-simulation limitations.
6. Test auth, cross-tenant isolation, invalid/stale inputs, transactional idempotency, all operation modes, action restrictions, analytics denominators and exports.
7. Build/typecheck frontend; Playwright runs real Docker services; live API verification exercises PostgreSQL and full-bank response transaction; reopen/restart tests verify persistence.
8. Review diff and secret exclusions before commit/PR. Report PASS/FAIL/NOT RUN per criterion; never treat a proposed algorithm or fixture as field validation.
