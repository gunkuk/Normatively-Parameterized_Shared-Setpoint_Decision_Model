"""Persistent exact-result cache and one-level A/B speculation; no guessed answers."""

import hashlib, json, threading, os
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import numpy as np
from .config import APP
from .inference import infer


class Acquisition:
    def __init__(self):
        self.pool = ThreadPoolExecutor(max_workers=1)
        self.lock = threading.RLock()
        self.pending = {}
        self.progress = {}
        self.errors = {}
        self.directory = APP / "outputs" / "acquisition-v2"

    def key(self, bank, trials):
        payload = dict(
            version=bank.version,
            algorithm="shared-exact-v2",
            code=bank.manifest["code_sha256"],
            answers=[
                (t["group_id"], t["a"], t["b"], t.get("response")) for t in trials
            ],
        )
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()

    def get(self, bank, trials):
        key = self.key(bank, trials)
        path = self.directory / (key + ".json")
        if path.exists():
            data = json.loads(path.read_text())
            return True, data["question"]
        return False, None

    def state(self, bank, trials):
        key = self.key(bank, trials)
        with self.lock:
            return dict(progress=self.progress.get(key, 0), error=self.errors.get(key))

    def ensure(self, bank, histories):
        with self.lock:
            todo = []
            for trials in histories:
                key = self.key(bank, trials)
                if (
                    self.get(bank, trials)[0]
                    or key in self.pending
                    or key in self.errors
                ):
                    continue
                self.pending[key] = True
                self.progress[key] = 0
                self.errors.pop(key, None)
                todo.append((key, trials))
            if todo:
                self.pool.submit(self._compute, bank, todo)

    def retry(self, bank, trials):
        with self.lock:
            self.errors.pop(self.key(bank, trials), None)

    def prefetch(self, bank, trials, question):
        # Only observed history plus the currently displayed A/B branch. No answer is recorded.
        self.ensure(
            bank, [trials + [dict(question, response=response)] for response in [0, 1]]
        )

    def _compute(self, bank, todo):
        try:
            states = []
            for key, trials in todo:
                r = infer(bank, trials)
                excluded = {}
                for t in trials:
                    excluded.setdefault(t["group_id"], []).append((t["a"], t["b"]))
                states.append(
                    dict(
                        common=np.asarray(r["common"]["weights"]),
                        grids=(
                            {g: np.asarray(v["weights"]) for g, v in r["grids"].items()}
                            if r["stage"] == "CONTEXTUAL"
                            else None
                        ),
                        excluded=excluded,
                    )
                )

            def progress(i, n):
                with self.lock:
                    for key, _ in todo:
                        self.progress[key] = i / n

            results = bank.select_many(states, progress)
            self.directory.mkdir(parents=True, exist_ok=True)
            for (key, _), question in zip(todo, results):
                path = self.directory / (key + ".json")
                temp = path.with_suffix(".tmp")
                temp.write_text(json.dumps(dict(question=question)))
                os.replace(temp, path)
        except Exception as exc:
            with self.lock:
                for key, _ in todo:
                    self.errors[key] = str(exc)
        finally:
            with self.lock:
                for key, _ in todo:
                    self.pending.pop(key, None)
