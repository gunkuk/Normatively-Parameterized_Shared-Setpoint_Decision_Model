"""Create local secrets once; never overwrite an existing environment file."""

from pathlib import Path
import secrets, hashlib, json

app = Path(__file__).resolve().parents[1]
target = app / ".env"
if target.exists():
    raise SystemExit("Existing .env preserved")
token = secrets.token_urlsafe(32)
users = [
    dict(
        id="local-admin",
        tenant="local",
        role="Admin",
        token_sha256=hashlib.sha256(token.encode()).hexdigest(),
    )
]
with target.open("x") as f:
    f.write(
        "POSTGRES_PASSWORD="
        + secrets.token_hex(24)
        + "\nNPSDM_USERS="
        + json.dumps(users, separators=(",", ":"))
        + "\n"
    )
(app / "outputs").mkdir(exist_ok=True)
(app / "outputs/local-access-token.txt").write_text(token)
print(
    "Created app/.env and app/outputs/local-access-token.txt; these files are gitignored. Never publish the token."
)
