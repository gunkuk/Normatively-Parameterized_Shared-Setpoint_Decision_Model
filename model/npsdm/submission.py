"""Recompute the frozen as-submitted decisions and welfare from study inputs.

Historical implementation choices are retained explicitly; this module does
not silently correct the differences listed in the release README.
"""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from .rules import _pmv_fanger
from .social import atkinson, gini
from .utility import thermal_utility

ROOT = Path(__file__).resolve().parents[2]
GRID = np.round(15.0 + np.arange(161) * 0.1, 10)
EPSILONS = [0.0, 0.5, 1.0, 2.0, float("inf")]
OVERRIDES = {19: 24.0, 83: 22.0}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _tie(scores: np.ndarray, desired: np.ndarray) -> int:
    indices = np.flatnonzero(scores >= scores.max() - 1e-9)
    if len(indices) == 1:
        return int(indices[0])
    digest = hashlib.sha256(desired.astype(float).tobytes() + indices.astype(np.int64).tobytes()).digest()[:8]
    rng = np.random.default_rng(int.from_bytes(digest, "little"))
    return int(indices[rng.integers(len(indices))])


def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    source = ROOT / "data" / "submission"
    reference = json.loads((source / "reference.json").read_text(encoding="utf-8"))
    for name, expected in reference["input_sha256"].items():
        if _sha(source / name) != expected:
            raise ValueError(f"Submission input checksum changed: {name}")
    people = pd.read_csv(source / "observations.csv", keep_default_na=False)
    groups = pd.read_csv(source / "groups.csv", keep_default_na=False)
    if len(people) != 62 or people.subject.nunique() != 62 or len(groups) != 2400:
        raise ValueError("Expected 62 distinct people and 2400 fixed groups")
    if groups.duplicated(["group_size", "repetition"]).any():
        raise ValueError("Duplicate fixed group")
    representatives = []
    missing = 0
    for row in people.itertuples():
        values = np.asarray([float(v) for v in row.desired_setpoints_c.split(";")])
        reported = row.reported_setpoints_c.split(";")
        if len(values) != 20 or len(reported) != 20 or not np.isfinite(values).all():
            raise ValueError(f"Invalid observation contract: {row.subject}")
        for actual, raw in zip(values, reported):
            if raw == "NA":
                missing += 1
            elif abs(actual - float(raw)) > 1e-12:
                raise ValueError("Filled value differs from a nonmissing direct report")
        counts = Counter(values)
        candidates = sorted(v for v, count in counts.items() if count == max(counts.values()))
        if len(candidates) > 1:
            distance = min(abs(v-values.mean()) for v in candidates)
            candidates = [v for v in candidates if np.isclose(abs(v-values.mean()), distance)]
        if len(candidates) > 1:
            chosen = OVERRIDES.get(int(row.subject))
            if chosen not in candidates:
                raise ValueError("Unresolved historical DSF tie")
        else:
            chosen = candidates[0]
        representatives.append(float(chosen))
    if missing != 117:
        raise ValueError("Expected 117 historically filled observations")
    people["representative_c"] = representatives
    subjects = people.subject.to_numpy(int)
    for n, frame in groups.groupby("group_size", sort=True):
        if len(frame) != 300:
            raise ValueError("Expected 300 groups for every group size")
        seed = int(hashlib.sha256(f"{n}|pooled|annual|0".encode()).hexdigest()[:8], 16)
        rng = np.random.default_rng(seed)
        for row in frame.sort_values("repetition").itertuples():
            sampled = subjects[rng.choice(len(subjects), size=int(n), replace=False)]
            if ";".join(map(str,sampled)) != row.members:
                raise ValueError("Historical synthetic-group sampling did not reproduce")
    return people, groups, reference


def _historical_met(people: pd.DataFrame) -> np.ndarray:
    # The old numeric-sex branch treated the minimum code (0) as male.
    # Retain it for result reproduction and disclose it, rather than silently
    # presenting this as the corrected physiological convention.
    height_cm = np.sqrt(people.weight_kg.to_numpy() / people.bmi.to_numpy()) * 100
    mass = people.weight_kg.to_numpy()
    bmr = 10*mass + 6.25*height_cm - 5*people.age.to_numpy()
    bmr += np.where(people.sex.to_numpy()==people.sex.min(), 5, -161)
    bsa = .007184 * mass**.425 * height_cm**.725
    raw = bmr * 4184 / 86400 / bsa / 58.15
    return np.clip(raw*(1.1/raw.mean()), .8, 2.0)


def run(smoke: bool = False, output: Path | None = None) -> dict:
    people, groups, reference = load_inputs()
    if smoke:
        groups = groups[groups.group_size.isin([3,10])].groupby("group_size", group_keys=False).head(3)
    desired = dict(zip(people.subject, people.representative_c))
    met = _historical_met(people)
    pmv_curves = {
        int(row.subject): np.asarray([_pmv_fanger(t,t,.2,50.,m,.6) for t in GRID])
        for row,m in zip(people.itertuples(), met)
    }
    records = []
    max_temperature_error = 0.0
    for _, group in groups.iterrows():
        ids = list(map(int,group.members.split(";")))
        d = np.asarray([desired[s] for s in ids],dtype=float)
        utilities = np.asarray([thermal_utility(t,d) for t in GRID])
        decisions = {"mean":float(d.mean()),"median":float(np.median(d))}
        pmv = np.mean(np.stack([pmv_curves[s] for s in ids]),axis=0)
        decisions["pmv"] = float(GRID[np.argmin(np.abs(pmv))])
        covered = (np.abs(GRID[:,None]-d[None,:])<=3.).sum(axis=1).astype(float)
        decisions["threshold_cov"] = float(GRID[_tie(covered,d)])
        for epsilon in EPSILONS:
            scores = np.asarray([atkinson(u,epsilon) for u in utilities])
            decisions["atkinson_"+str(epsilon)] = float(GRID[_tie(scores,d)])
        for rule,temperature in decisions.items():
            # Reference temperatures are validation fixtures, never selection inputs.
            expected = float(group["reference_"+rule])
            error = abs(temperature-expected)
            tolerance = .00050001 if rule=="mean" else 1e-8
            if error>tolerance:
                raise ValueError(f"Decision mismatch: N={group.group_size},rep={group.repetition},{rule},{temperature},{expected}")
            max_temperature_error = max(max_temperature_error,error)
            u = thermal_utility(temperature,d)
            records.append(dict(group_size=int(group.group_size),repetition=int(group.repetition),rule=rule,
                setpoint_c=temperature,efficiency=float(u.mean()),equity=float(u.min()),equality=float(1-gini(u))))
    frame = pd.DataFrame(records)
    overall = frame.groupby("rule",sort=True)[["efficiency","equity","equality"]].mean().reset_index()
    if not smoke:
        for row in overall.itertuples(index=False):
            for metric in ["efficiency","equity","equality"]:
                if abs(getattr(row,metric)-reference["welfare"][row.rule][metric])>1.1e-6:
                    raise ValueError(f"Welfare did not reproduce: {row.rule}/{metric}")
    folder = output or ROOT/"outputs"/("submission_smoke" if smoke else "submission_full")
    folder.mkdir(parents=True,exist_ok=True)
    frame.to_csv(folder/"groups.tsv",sep="\t",index=False)
    overall.to_csv(folder/"overall.tsv",sep="\t",index=False)
    result = dict(status="PASS",mode="smoke" if smoke else "full",subjects=62,observations=1240,
        historically_filled=117,groups=len(groups),decision_rows=len(frame),
        sampling="regenerated from historical cell seeds; membership fixtures matched",
        decision_recalculation="all nine decisions independently recomputed from person inputs",
        maximum_temperature_serialization_error_c=max_temperature_error,
        scope="numerical results; manual figure appearance and DOCX layout are outside this mode",
        known_differences=reference["known_differences"],input_sha256=reference["input_sha256"],
        code_sha256={p.name:_sha(p) for p in sorted(Path(__file__).parent.glob("*.py"))})
    (folder/"verification.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
    return result
