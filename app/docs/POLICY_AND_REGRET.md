# Policies and expected welfare regret

For each scenario, the oracle chooses T*(e_g) on the same feasible domain and under the same tie rule as the candidate policy. Regret is W_e_g(T*(e_g))-W_e_g(T*(e)). The fixed policy minimizes its posterior expectation averaged within each grid and weighted by rho_g.

Uniform_grid assigns 1/40 to each frozen grid. Observed-frequency weights can be obtained from nonoverlapping recorded decision exposure with explicit lookback, smoothing and coverage, then supplied as all 40 nonnegative weights summing to one. These are target-distribution choices, not normative theorems. Recorded operations can themselves be policy-selected and need not represent future occupancy.

The optimizer sweeps the upper envelope of welfare curves using isolated crossings, accumulating constant-regret intervals and point corrections for exact tie representatives. It includes epsilon=0 and infinity. Dominance reduction uses sorted utility vectors only within policy optimization: coordinatewise greater utilities imply no smaller generalized means. Full-domain endpoint/tie choices are retained. Dense independent numerical candidates test the returned regret. Minimizer regions have explicit open endpoints, with qualifying singleton points listed separately.

All results are provisional/model-conditional; numerical global search is not a formal interval-arithmetic certificate. Unidentified grids depend on their priors. Display contextual estimates and the fixed-policy calculation status together. Before approving REGRET_OPTIMAL_FIXED, calculate the result for the selected zone's feasible bounds and latest session trial count. The approval binds that numerical result and weighting snapshot; changing inputs requires a new policy.

Policies are immutable after approval through the API. Contextual unidentified/out-of-domain cases require a separately declared fallback. A manually specified common epsilon is not claimed to have been elicited.
