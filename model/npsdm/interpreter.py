"""Run the NPSDM simulation and write small, inspectable result tables."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import adapter, desired_setpoint, rules, sampling, settings, social
from .utility import thermal_utility

ROOT = Path(__file__).resolve().parents[2]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _code_fingerprint() -> dict[str, str]:
    return {
        path.relative_to(ROOT).as_posix(): _sha256(path)
        for path in sorted((ROOT / "model" / "npsdm").glob("*.py"))
    }


def run(group_sizes: tuple[int, ...], repetitions: int) -> dict:
    """Run every requested group-size cell and return data plus provenance."""
    input_path = ROOT / settings.INPUT_RELATIVE_PATH
    dataset = adapter.load(input_path)
    representatives, resolutions = desired_setpoint.build(dataset.observations)
    people = dataset.people.merge(representatives, on="subject", validate="one_to_one")
    people = people.sort_values("subject").reset_index(drop=True)
    subjects = people["subject"].to_numpy(dtype=int)
    desired_by_subject = dict(zip(people["subject"], people["desired_setpoint_c"]))
    met_by_subject = dict(zip(people["subject"], rules.metabolic_rate(people)))

    group_rows = []
    for group_size in group_sizes:
        groups = sampling.sample_groups(subjects, group_size, repetitions, settings.RANDOM_SEED)
        for repetition, members in enumerate(groups):
            members = np.asarray(members, dtype=int)
            desired = np.asarray([desired_by_subject[int(s)] for s in members], dtype=float)
            met = np.asarray([met_by_subject[int(s)] for s in members], dtype=float)
            heterogeneity = float(np.std(desired, ddof=0))
            decisions = [(rule, None) for rule in ("pmv", "threshold_coverage", "mean", "median")]
            decisions += [("atkinson", epsilon) for epsilon in settings.ATKINSON_EPSILONS]
            for rule, epsilon in decisions:
                epsilon_text = "" if epsilon is None else ("inf" if np.isinf(epsilon) else f"{epsilon:g}")
                key = f"{group_size}:{repetition}:{rule}:{epsilon_text}:" + ",".join(map(str, members))
                setpoint = rules.choose(rule, desired, met, epsilon, key)
                utility = thermal_utility(setpoint, desired)
                group_rows.append(
                    {
                        "group_size": group_size,
                        "repetition": repetition,
                        "group_id": f"N{group_size}_R{repetition:03d}",
                        "rule": rule,
                        "epsilon": epsilon_text,
                        "setpoint_c": round(setpoint, 6),
                        "efficiency": float(np.clip(utility.mean(), 0.0, 1.0)),
                        "equity_cvar10": float(np.clip(social.cvar(utility), 0.0, 1.0)),
                        "fairness": float(np.clip(1.0 - social.gini(utility), 0.0, 1.0)),
                        "thermal_heterogeneity_sd_c": heterogeneity,
                        "members": ";".join(map(str, members)),
                    }
                )

    groups_frame = pd.DataFrame(group_rows)
    summary_rows = []
    for (group_size, rule, epsilon), group in groups_frame.groupby(
        ["group_size", "rule", "epsilon"], sort=True, dropna=False
    ):
        summary_rows.append(
            {
                "group_size": int(group_size),
                "rule": rule,
                "epsilon": epsilon,
                "n_groups": int(len(group)),
                "setpoint_mean_c": float(group["setpoint_c"].mean()),
                "setpoint_sd_c": float(group["setpoint_c"].std(ddof=1)),
                "efficiency_mean": float(group["efficiency"].mean()),
                "efficiency_sd": float(group["efficiency"].std(ddof=1)),
                "equity_cvar10_mean": float(group["equity_cvar10"].mean()),
                "equity_cvar10_sd": float(group["equity_cvar10"].std(ddof=1)),
                "fairness_mean": float(group["fairness"].mean()),
                "fairness_sd": float(group["fairness"].std(ddof=1)),
                "thermal_heterogeneity_sd_c_mean": float(group["thermal_heterogeneity_sd_c"].mean()),
            }
        )
    summary = pd.DataFrame(summary_rows)
    return {
        "groups": groups_frame,
        "summary": summary,
        "observations": dataset.observations,
        "representatives": representatives,
        "resolutions": resolutions,
        "contract": dataset.contract,
        "input_path": input_path,
    }


def _write_schema(tag: str, result: dict, output_dir: Path) -> None:
    """Write a short schema document next to the generated result folder."""
    groups = result["groups"]
    summary = result["summary"]
    schema = f"""# NPSDM result schema

Generated by `python run_npsdm.py`. The current run is `{tag}`.

## Files

| File | Description |
|---|---|
| `{tag}_groups.tsv.gz` | One row per synthetic group and decision rule. |
| `{tag}_summary.tsv` | Mean and sample standard deviation for each group-size and rule cell. |
| `desired_setpoints.tsv` | One DSF-derived representative setpoint per person. |
| `dsf_resolution.tsv` | Mode frequency and tie-resolution record for each person. |
| `{tag}_PROVENANCE.json` | Input, configuration, and code hashes. |

The current run has {len(groups):,} group-rule rows and {len(summary):,} summary rows.

## Decision and outcome columns

`rule` is one of `pmv`, `threshold_coverage`, `mean`, `median`, or `atkinson`.
`epsilon` is populated only for Atkinson rows and takes `0`, `0.5`, `1`, `2`, or `inf`.
`setpoint_c` is the selected shared setpoint in degrees Celsius.
`efficiency` is mean individual utility; `equity_cvar10` is mean utility in the lower 10% tail;
`fairness` is one minus the Gini coefficient of individual utility.
All three metrics are on a higher-is-better scale from 0 to 1.

`thermal_heterogeneity_sd_c` is the population standard deviation of the group members' representative
desired setpoints. `members` lists the sampled subject identifiers in the group.
"""
    (output_dir.parent / "RESULTS_SCHEMA.md").write_text(schema, encoding="utf-8")


def write_outputs(result: dict, tag: str) -> None:
    """Write result tables, DSF evidence, and a machine-readable provenance record."""
    output_dir = ROOT / settings.OUTPUT_RELATIVE_PATH
    output_dir.mkdir(parents=True, exist_ok=True)
    result["groups"].to_csv(
        output_dir / f"{tag}_groups.tsv.gz",
        sep="\t",
        index=False,
        compression={"method": "gzip", "mtime": 0},
    )
    result["summary"].to_csv(output_dir / f"{tag}_summary.tsv", sep="\t", index=False)
    result["observations"].to_csv(
        output_dir / "desired_setpoint_observations.tsv", sep="\t", index=False
    )
    result["representatives"].to_csv(
        output_dir / "desired_setpoints.tsv", sep="\t", index=False
    )
    result["resolutions"].to_csv(output_dir / "dsf_resolution.tsv", sep="\t", index=False)

    provenance = {
        "project": "NPSDM",
        "tag": tag,
        "input": {
            "path": settings.INPUT_RELATIVE_PATH,
            "sha256": _sha256(result["input_path"]),
        },
        "contract": result["contract"],
        "configuration": {
            "group_sizes": sorted(result["summary"]["group_size"].unique().tolist()),
            "repetitions_per_group_size": int(result["groups"]["repetition"].nunique()),
            "candidate_setpoint_min_c": settings.SETPOINT_MIN_C,
            "candidate_setpoint_max_c": settings.SETPOINT_MAX_C,
            "candidate_setpoint_step_c": settings.SETPOINT_STEP_C,
            "utility_width_c": settings.UTILITY_WIDTH_C,
            "utility_floor": settings.UTILITY_FLOOR,
            "coverage_band_c": settings.COVERAGE_BAND_C,
            "atkinson_epsilons": ["inf" if np.isinf(e) else e for e in settings.ATKINSON_EPSILONS],
            "random_seed": settings.RANDOM_SEED,
        },
        "rows": {
            "group_rule_rows": int(len(result["groups"])),
            "summary_rows": int(len(result["summary"])),
        },
        "code_sha256": _code_fingerprint(),
    }
    (output_dir / f"{tag}_PROVENANCE.json").write_text(
        json.dumps(provenance, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    _write_schema(tag, result, output_dir)
