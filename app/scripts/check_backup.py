"""Create and restore a validation backup into a new disposable database."""

import subprocess, os, json, uuid
from pathlib import Path

app = Path(__file__).resolve().parents[1]
root = app.parent
exe = os.environ.get("DOCKER_EXE", "docker")
base = [
    exe,
    "compose",
    "-f",
    str(app / "docker-compose.yml"),
    "--env-file",
    str(app / ".env"),
    "exec",
    "-T",
    "db",
]


def run(args):
    return subprocess.check_output(base + args, cwd=root, text=True).strip()


name = "npsdm_verify_" + uuid.uuid4().hex[:12]
run(
    ["pg_dump", "-U", "npsdm", "-d", "npsdm", "-Fc", "-f", "/tmp/npsdm-validation.dump"]
)
run(["createdb", "-U", "npsdm", name])
try:
    run(["pg_restore", "-U", "npsdm", "-d", name, "/tmp/npsdm-validation.dump"])
    query = "SELECT count(*) FROM decision_cycles; SELECT count(*) FROM elicitation_trials; SELECT count(*) FROM model_policies;"
    before = run(["psql", "-U", "npsdm", "-d", "npsdm", "-At", "-c", query])
    after = run(["psql", "-U", "npsdm", "-d", name, "-At", "-c", query])
    if before != after:
        raise RuntimeError("Backup row counts differ (or concurrent writes occurred)")
    (app / "validation/BACKUP_RESTORE.json").write_text(
        json.dumps(
            dict(
                status="PASS",
                tables=["decision_cycles", "elicitation_trials", "model_policies"],
                source_counts=before.splitlines(),
                restored_counts=after.splitlines(),
                scope="Fresh temporary database restored with pg_restore; no original database deletion",
            ),
            indent=2,
        )
    )
    print("PASS backup/restore row counts")
finally:
    run(["dropdb", "-U", "npsdm", name])
