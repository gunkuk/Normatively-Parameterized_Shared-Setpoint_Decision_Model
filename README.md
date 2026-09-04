# NPSDM — Normatively Parameterized Shared-Setpoint Decision Model

NPSDM is a small, reproducible implementation of a shared indoor-temperature decision framework. It compares conventional rules with an Atkinson-based family of rules that makes the priority between average group utility and protection of lower-utility occupants explicit.

## 1. Quick start

The only required software is Python 3.10 or newer.

```bash
python -m pip install -r requirements.txt
python run_npsdm.py --smoke
python run_npsdm.py --full
```

`--smoke` runs group sizes 3 and 10 with three repetitions per size. It checks the input and execution path quickly. `--full` runs the complete analysis: group sizes 3 through 10, 300 groups per size, and 2,400 synthetic groups in total.

All generated files are written under `outputs/`, which is intentionally excluded from version control. The generated `outputs/RESULTS_SCHEMA.md` describes every result column.

## 2. Canonical study design

The implementation follows the final manuscript's methods:

- The original experiment included 128 participants. The final analytic cohort contains 62 adults, 28 women and 34 men.
- The cohort provides 248 sessions and 1,240 thermal-response observations.
- Each participant has 20 repeated direct desired-setpoint observations. 117 of the 1,240 observations are missing reports and remain missing; no replacement target is constructed.
- A representative individual desired setpoint is the most frequent reported value. If several values have the same frequency, the value nearest that participant's overall reported mean is selected. An exact distance tie is resolved by the lower value.
- For each group size from 3 to 10, 300 groups are sampled uniformly without replacement within a group. Participants may appear in different synthetic groups.
- Candidate grid-based setpoints range from 12 to 33 degrees Celsius in 0.1-degree increments.

The data file contains only the final analytic cohort and the variables needed by this release. It does not contain upstream prediction artifacts or building-energy calculations.

## 3. Decision rules

Each synthetic group receives a shared setpoint from the following rules:

| Rule | Definition |
|---|---|
| `pmv` | Select the grid temperature whose group-average Predicted Mean Vote (PMV) is closest to thermal neutrality. Metabolic rate is estimated from sex, age, mass, and height. Clothing is 0.6 clo, air speed is 0.2 m/s, relative humidity is 50%, and mean radiant temperature equals air temperature. |
| `threshold_coverage` | Select the grid temperature that covers the largest number of occupants within a 3-degree absolute deviation from their representative desired setpoint. |
| `mean` | Use the arithmetic mean of the group's representative desired setpoints. |
| `median` | Use the median of the group's representative desired setpoints. |
| `atkinson` | Select the grid temperature that maximizes Atkinson social welfare for one inequality-aversion value. |

The Atkinson rule is evaluated at epsilon values 0, 0.5, 1, 2, and infinity. Epsilon 0 is the arithmetic-mean case, epsilon 1 is the geometric-mean case, and infinity is the maximin limit. Grid ties use a stable hash-derived uniform choice so the result is deterministic without adding a second preference rule.

## 4. Welfare evaluation

For a selected shared setpoint, each occupant receives a common triangular utility:

```text
utility = clip(1 - absolute(desired_setpoint - shared_setpoint) / 6, 0.001, 1)
```

The same mapping is applied to every occupant. The resulting group is evaluated on three higher-is-better dimensions:

- `efficiency`: mean individual utility.
- `equity_cvar10`: mean utility in the lowest 10% of the group utility distribution. This is the primary lower-tail protection measure.
- `fairness`: one minus the Gini coefficient of individual utility. This is reported as a supplementary distributional measure.

Efficiency and equity are the primary comparison dimensions. Fairness is supplementary. The model does not produce an energy outcome.

## 5. Input file

`data/desired_setpoint_observations.csv` has one row per participant:

| Column | Meaning |
|---|---|
| `subject` | Stable participant identifier. |
| `sex` | `0` for female and `1` for male. |
| `age` | Age in years. |
| `weight_kg` | Body mass in kilograms. |
| `height_m` | Height in metres, retained for the PMV calculation. |
| `desired_setpoints_c` | Twenty direct reports separated by semicolons; `NA` preserves a missing report. |

The loader expands the compact column into 1,240 observation rows and checks the 62-person, 20-observations-per-person, and 117-missing-report contract before running the model.

## 6. Generated outputs

For a full run, `outputs/results/` contains:

| File | Contents |
|---|---|
| `full_groups.tsv.gz` | 21,600 group-rule rows: 2,400 groups evaluated under nine decision points. |
| `full_summary.tsv` | 72 group-size by decision-point summaries. |
| `desired_setpoint_observations.tsv` | Expanded direct observations used by the loader. |
| `desired_setpoints.tsv` | One representative desired setpoint per participant. |
| `dsf_resolution.tsv` | Frequency, tie candidates, and selected value for each participant. |
| `full_PROVENANCE.json` | Input checksum, configuration, row counts, and code checksums. |
| `../RESULTS_SCHEMA.md` | Generated column definitions and run size. |

The smoke run uses the same rules and settings on a smaller, deterministic subset. Running it twice produces the same tables.

## 7. Repository layout

```text
.
├── run_npsdm.py                 # single execution entry point
├── data/
│   └── desired_setpoint_observations.csv
├── model/npsdm/
│   ├── adapter.py                # input expansion and contract checks
│   ├── desired_setpoint.py       # representative setpoint function
│   ├── rules.py                  # PMV and shared-setpoint rules
│   ├── utility.py                # individual utility
│   ├── social.py                 # Gini, lower-tail utility, Atkinson welfare
│   ├── sampling.py               # deterministic synthetic groups
│   ├── interpreter.py             # simulation and output writing
│   └── settings.py               # single configuration source
└── outputs/                      # generated files, not committed
```

The package is deliberately small. To change a canonical analysis value, edit `model/npsdm/settings.py`, rerun the full command, and inspect the new provenance record.

## 8. License and attribution

Code and documentation are provided under the [MIT License](LICENSE), copyright 2026 `gunkuk`.

The included study data are provided, to the extent of the licensors' rights, under [CC BY 4.0](LICENSE-DATA). Retain the attribution and license link when sharing or adapting the data, and state whether changes were made.
