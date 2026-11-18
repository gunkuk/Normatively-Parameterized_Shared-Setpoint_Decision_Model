"""CI/local verification runner. Execute inside the app virtual environment."""

import subprocess, sys, os, json
from pathlib import Path

root = Path(__file__).resolve().parents[2]
app = root / "app"
commands = [
    [sys.executable, "-m", "pytest", "app/backend/tests", "-q"],
    [
        "npm.cmd" if os.name == "nt" else "npm",
        "run",
        "typecheck",
        "--prefix",
        "app/frontend",
    ],
    [
        "npm.cmd" if os.name == "nt" else "npm",
        "run",
        "build",
        "--prefix",
        "app/frontend",
    ],
]
results = []
for command in commands:
    r = subprocess.run(
        command,
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    results.append(
        {
            "command": command,
            "status": "PASS" if r.returncode == 0 else "FAIL",
            "returncode": r.returncode,
            "output": r.stdout + r.stderr,
        }
    )
(app / "validation/VERIFY.json").write_text(json.dumps(results, indent=2))
print([(r["command"][2:4], r["status"]) for r in results])
sys.exit(any(r["returncode"] for r in results))
