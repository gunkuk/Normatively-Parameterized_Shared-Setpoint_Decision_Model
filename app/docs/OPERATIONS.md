# Operations

DEMO: seeded synthetic presence, desired-temperature drift and noisy first-order room response; no validated physical HVAC model. REPLAY: decisions at explicit historical timestamps using only observations at or before that time. SHADOW: current actual data and recommendations only. ASSISTED_LIVE: current actual data plus human approve/reject/override, manual application and separately recorded confirmation.

Current occupants require explicit fresh presence. Each present occupant requires a fresh preference. Missing values are rejected with diagnostics, never silently filled. Fresh environment data are optional and missingness is flagged. Future/stale timestamps cannot support a live decision. Group N/SD map to frozen versioned support; unsupported/unknown contextual cells require an approved fallback.

All recommendations preserve group membership, desired values, policy/config versions, feasible temperatures and predicted outcomes. Counterfactual policies run on that identical snapshot. Action records are append-only through the API and do not retroactively change recommendations. Replay/shadow reject physical-application records.

Actual deployment needs site authorization, consent/retention policy, identity provisioning and sensor reliability review. No physical control integration is included.
