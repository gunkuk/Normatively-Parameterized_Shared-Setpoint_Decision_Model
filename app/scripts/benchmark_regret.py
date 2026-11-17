import os

os.environ["OPENBLAS_NUM_THREADS"] = "1"
import sys, time, json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from npsdm_app.bank import Bank
from npsdm_app.policy import fixed_regret
from npsdm_app.config import APP

b = Bank()
start = time.perf_counter()


def progress(i, n):
    if i % 100 == 0:
        print(i, n, round(time.perf_counter() - start, 1), flush=True)


r = fixed_regret(b, {}, progress=progress)
r["elapsed_seconds"] = time.perf_counter() - start
(APP / "validation/FIXED_REGRET_BENCHMARK.json").write_text(json.dumps(r, indent=2))
print("Finished", r["elapsed_seconds"], r["expected_regret"], r["epsilon"], flush=True)
