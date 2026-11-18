# Analytics semantics

Daily/weekly/monthly summaries use building-local calendar boundaries and timezone-aware UTC arithmetic, including daylight-saving boundaries. Decision exposure ends at the next decision or configured cadence, whichever comes first; intervals never overlap. Denominators are covered seconds and person-seconds, not raw row counts.

Primary modeled utility is evaluated at recommended temperature. Separately labeled realized-temperature-based modeled utility uses fresh indoor temperature; neither is a measured comfort vote. Individual utility and burden are exposure-weighted. Worst-off burden integrates 1-min(u). Time outside target refers explicitly to measured temperature outside the zone's approved bounds, not a universal comfort target. Missing environment coverage is reported.

Mode filters prevent DEMO/actual aggregation. Histories retain recommendations, actions and measured temperatures separately. Counterfactuals compare versioned policies on identical desired-setpoint snapshots. Valid interval metering converts kW times hours to kWh; overlapping same-meter intervals are excluded and flagged. No causal energy savings are inferred.

Coverage is only the recorded decision intervals; it does not claim continuous monitoring between uncovered periods. A temporal plot, detailed action records and source JSON complement summary tables.
