import hashlib
import json
import sys
import time
import subprocess
from pathlib import Path
import numpy as np
from .config import ROOT, SETTINGS
from .science import utility, welfare, quadrature, probability, eig


class Bank:
    def __init__(self, settings=SETTINGS):
        self.settings = settings
        sys.path.insert(0, str(ROOT / "model"))
        from npsdm.submission import load_inputs

        people, groups, ref = load_inputs()
        desired = dict(zip(people.subject, people.representative_c))
        self.groups = []
        self.boundaries = {}
        for n, frame in groups.groupby("group_size", sort=True):
            rows = []
            for row in frame.itertuples():
                d = [desired[int(x)] for x in row.members.split(";")]
                rows.append(
                    dict(
                        id=f"N{n}/R{int(row.repetition):03d}",
                        n=int(n),
                        repetition=int(row.repetition),
                        desired=d,
                        sd=float(np.std(d, ddof=0)),
                        members=row.members.split(";"),
                    )
                )
            rows.sort(key=lambda x: (x["sd"], x["repetition"]))
            cuts = [rows[k - 1]["sd"] for k in [60, 120, 180, 240]]
            self.boundaries[str(n)] = dict(
                cutpoints=cuts,
                min=rows[0]["sd"],
                max=rows[-1]["sd"],
                ties=[sum(abs(r["sd"] - v) < 1e-12 for r in rows) for v in cuts],
                rule="upper-observed-order-statistic; equality-lower",
            )
            for rank, row in enumerate(rows):
                row["grid"] = f"N{n}/H{rank//60+1}"
                self.groups.append(row)
        self.groups.sort(key=lambda x: x["id"])
        self.lookup = {g["id"]: g for g in self.groups}
        self.temperatures = settings.temperatures
        self.nodes, self.prior = quadrature(settings)
        self.pairs = np.stack(np.triu_indices(len(self.temperatures), 1), axis=1)
        self._curves = {}
        try:
            commit = subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
            ).strip()
        except Exception:
            commit = "unknown"
        self.manifest = dict(
            source_sha256={
                p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted((ROOT / "data/submission").glob("*"))
                if p.is_file()
            },
            config_hash=settings.fingerprint,
            settings=settings.model_dump(),
            code_commit=commit,
            groups=2400,
            participants=62,
            temperatures=len(self.temperatures),
            pairs_per_group=len(self.pairs),
            total_candidates=len(self.pairs) * len(self.groups),
            boundaries=self.boundaries,
            memberships=self.groups,
            variant="frozen-submission",
            warning="Resampled groups; not independent external observations",
        )
        self.manifest["code_sha256"] = {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(Path(__file__).parent.glob("*.py"))
        }
        self.version = hashlib.sha256(
            json.dumps(
                {
                    "source": self.manifest["source_sha256"],
                    "config": settings.fingerprint,
                },
                sort_keys=True,
            ).encode()
        ).hexdigest()
        self.manifest["source_version"] = self.version

    def curves(self, group):
        key = tuple(group["desired"])
        if key not in self._curves:
            u = utility(self.temperatures, group["desired"], self.settings)
            self._curves[key] = np.stack([welfare(u, e) for e in self.nodes], axis=1)
        return self._curves[key]

    def map_grid(self, desired):
        n = len(desired)
        sd = float(np.std(desired, ddof=0))
        b = self.boundaries.get(str(n))
        if b is None or sd < b["min"] - 1e-12 or sd > b["max"] + 1e-12:
            raise ValueError("OUT_OF_DOMAIN: approved fallback required")
        return f'N{n}/H{int(np.searchsorted(b["cutpoints"],sd,side="left"))+1}'

    def select(self, posterior, asked=(), grid_posteriors=None, progress=None):
        started = time.perf_counter()
        asked = set(asked)
        best = None
        evaluated = 0
        # Each candidate remains eligible; identical desired vectors share only
        # precomputed welfare curves, never a heuristic candidate shortlist.
        for gi, g in enumerate(self.groups):
            curves = self.curves(g)
            weights = (
                grid_posteriors.get(g["grid"], self.prior)
                if grid_posteriors is not None
                else posterior
            )
            for offset in range(0, len(self.pairs), self.settings.pair_block_size):
                pairs = self.pairs[offset : offset + self.settings.pair_block_size]
                scores = eig(
                    probability(
                        curves[pairs[:, 0]], curves[pairs[:, 1]], self.settings
                    ),
                    weights,
                )
                if asked:
                    for qid in asked:
                        gid, sa, sb = qid.split(":")
                        if gid == g["id"]:
                            scores[
                                (pairs[:, 0] == int(sa)) & (pairs[:, 1] == int(sb))
                            ] = -np.inf
                evaluated += len(scores)
                j = int(np.argmax(scores))
                score = float(scores[j])
                a, b = map(int, pairs[j])
                if np.isfinite(score) and (best is None or score > best["eig_bits"]):
                    best = dict(
                        group_id=g["id"],
                        grid=g["grid"],
                        a=a,
                        b=b,
                        id=f'{g["id"]}:{a}:{b}',
                        source_version=self.version,
                        eig_bits=score,
                    )
            if progress:
                progress(gi + 1, len(self.groups))
        if best is not None:
            best.update(
                evaluated_candidates=evaluated,
                elapsed_seconds=time.perf_counter() - started,
                exact_discrete_global=True,
            )
        return best
