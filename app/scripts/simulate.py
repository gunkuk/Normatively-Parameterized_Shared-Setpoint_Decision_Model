"""Reduced-bank synthetic-operator internal verification; not deployment acquisition."""

import os

os.environ["OPENBLAS_NUM_THREADS"] = "1"
import sys, json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
import numpy as np
from npsdm_app.bank import Bank
from npsdm_app.config import Settings, APP
from npsdm_app.science import (
    probability,
    welfare,
    utility,
    eig,
    update,
    posterior_summary,
)
from npsdm_app.constraints import consistent_set, intersect, switch_diagnostics

s = Settings(
    question_temperature_min_c=20,
    question_temperature_max_c=27,
    question_temperature_step_c=0.5,
    q_quadrature_count=64,
)
b = Bank(s)
groups = [b.lookup["N5/R041"], b.lookup["N5/R049"]]
candidates = []
for g in groups:
    c = b.curves(g)
    for a, z in b.pairs:
        candidates.append((g, int(a), int(z), probability(c[a], c[z], s)))
records = []
for model in ["M0", "M1"]:
    for method in ["EIG", "random", "balanced"]:
        for repeat in range(12):
            rng = np.random.default_rng(1000 + repeat)
            common = b.prior.copy()
            post = {g["grid"]: b.prior.copy() for g in groups}
            sets = {}
            asked = set()
            counts = {g["grid"]: 0 for g in groups}
            switched = False
            predictions = []
            coverage = []
            for step in range(24):
                available = [i for i in range(len(candidates)) if i not in asked]
                if method == "random":
                    index = int(rng.choice(available))
                else:
                    scores = []
                    for i in available:
                        g, a, z, p = candidates[i]
                        score = float(
                            eig(p[None, :], post[g["grid"]] if switched else common)[0]
                        )
                        if method == "balanced" and counts[g["grid"]] > min(
                            counts.values()
                        ):
                            score = -1
                        scores.append(score)
                    index = available[int(np.argmax(scores))]
                asked.add(index)
                g, a, z, p = candidates[index]
                true = 2.0 if model == "M0" else (0.2 if g["id"] == "N5/R041" else 10.0)
                u = utility(b.temperatures[[a, z]], g["desired"], s)
                truth = float(probability(welfare(u[0], true), welfare(u[1], true), s))
                pred = float(p @ (post[g["grid"]] if switched else common))
                y = int(rng.random() < truth)
                predictions.append((pred - y) ** 2)
                common = update(common, p, y)
                post[g["grid"]] = update(post[g["grid"]], p, y)
                counts[g["grid"]] += 1
                cs = consistent_set(u[0], u[1], y)
                sets[g["grid"]] = intersect(
                    sets.get(g["grid"], [[0, None]]), cs["intervals"]
                )
                switched = switched or switch_diagnostics(sets)["trigger_B"]
            for g in groups:
                true = 2.0 if model == "M0" else (0.2 if g["id"] == "N5/R041" else 10.0)
                summary = posterior_summary(
                    b.nodes,
                    post[g["grid"]] if switched else common,
                    observations=counts[g["grid"]],
                )
                coverage.append(
                    any(
                        lo <= true and (hi is None or true <= hi)
                        for lo, hi in summary["credible_set"]
                    )
                )
            records.append(
                dict(
                    model=model,
                    method=method,
                    seed=1000 + repeat,
                    responses=24,
                    switched=switched,
                    brier=float(np.mean(predictions)),
                    credible_coverage=float(np.mean(coverage)),
                )
            )
report = dict(
    scope="Internal synthetic verification on two frozen groups, reduced temperature bank, 12 seeds x 24 responses. Not external calibration or full-bank acquisition performance.",
    records=records,
    summary=[],
)
for model in ["M0", "M1"]:
    for method in ["EIG", "random", "balanced"]:
        r = [x for x in records if x["model"] == model and x["method"] == method]
        report["summary"].append(
            dict(
                model=model,
                method=method,
                switch_rate=float(np.mean([x["switched"] for x in r])),
                brier=float(np.mean([x["brier"] for x in r])),
                credible_coverage=float(np.mean([x["credible_coverage"] for x in r])),
            )
        )
(APP / "validation/SYNTHETIC_OPERATORS.json").write_text(json.dumps(report, indent=2))
print(json.dumps(report["summary"], indent=2))
