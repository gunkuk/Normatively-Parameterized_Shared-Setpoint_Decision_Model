# Data dictionary and provenance

PostgreSQL tables: sites, zones, users, roles, occupants, presence_events, preference_observations, environment_readings, thermal_feedback, meter_readings, elicitation_sessions, elicitation_trials, posterior_checkpoints, scenario_bank_versions, model_policies, decision_cycles, operator_actions, audit_events, dataset_ingests.

Each has UUID/string id, tenant_id, optional zone_id, UTC record timestamp, validated JSON payload and optional tenant-unique idempotency_key. Indices cover tenant/zone/timestamp. Typed payload contracts are in schemas.py and /openapi.json; JSON storage permits versioned scientific snapshots without rewriting historical records. SQL table existence does not mean every optional registry is populated; occupants are referenced by opaque IDs in observation records.

Observed timestamps must carry a timezone. Separate recorded-at timestamps distinguish late imports. Temperature units are Celsius, RH is percent, utility is dimensionless, exposure is seconds/person-seconds, metering is interval kWh or interval-average kW with positive interval duration. Predicted preferences require model_id and uncertainty_c. Feedback requires explicit consent metadata.

Data origin ACTUAL/SIMULATED is independent of operation mode. DEMO uses SIMULATED; other modes use ACTUAL. Development integration fixtures exercising ACTUAL routes are labeled validation_fixture and must never be interpreted as collected human observations. The application stores pseudonymous occupant IDs, not names or demographics.

Exports are explicit ZIP snapshots. Inference files belong to the selected session; operational files include the authorized tenant snapshot. CSV cells that could begin spreadsheet formulas are escaped. Local secrets, DB volumes and generated outputs are not committed.
