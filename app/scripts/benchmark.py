import os

os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"
import sys, time, json, threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
import psutil
from npsdm_app.bank import Bank
from npsdm_app.config import APP

peak = [0]
stop = threading.Event()


def sample():
    while not stop.wait(0.1):
        peak[0] = max(peak[0], psutil.Process().memory_info().rss)


threading.Thread(target=sample, daemon=True).start()
b = Bank()
start = time.perf_counter()


def progress(i, n):
    if i % 200 == 0:
        print(f"{i}/{n} groups; {time.perf_counter()-start:.1f}s", flush=True)


r = b.select(b.prior, progress=progress)
stop.set()
r.update(
    peak_rss_bytes=peak[0],
    quadrature_count=len(b.nodes),
    precision="float64",
    config_hash=b.settings.fingerprint,
    platform=sys.platform,
)
(APP / "validation/FULL_BANK_BENCHMARK.json").write_text(json.dumps(r, indent=2))
(APP / "validation/SCENARIO_BANK_MANIFEST.json").write_text(
    json.dumps(b.manifest, indent=2)
)
print(json.dumps(r), flush=True)
