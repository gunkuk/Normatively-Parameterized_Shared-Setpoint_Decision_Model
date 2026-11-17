# Deployment, backup and security boundary

The verified target is local Docker Desktop with Linux containers. Compose creates PostgreSQL, a single FastAPI worker process and Next.js. Loopback bindings prevent accidental LAN exposure. Running containers is not publishing a public website.

setup_env.py creates a random database password and local Admin bearer token once. Additional users are provisioned in NPSDM_USERS as {id,tenant,role,token_sha256}. Restart the API after authorized credential changes. No token is stored in browser localStorage. Use a TLS reverse proxy and reviewed identity system before remote deployment; bearer tokens are not suitable for transmission over untrusted plaintext networks.

Alembic revision 001 creates the schema before API startup. Approved policies are immutable via application routes. Database administrators retain technical write capability; this is not a tamper-proof regulatory archive.

Back up with PostgreSQL pg_dump in custom format and store the archive outside the container; restore with pg_restore into a separate test database and verify row counts and source/config versions before recovery. Example from repository root:

```powershell
docker compose -f app/docker-compose.yml --env-file app/.env exec -T db pg_dump -U npsdm -d npsdm -Fc -f /tmp/npsdm-backup.dump
docker compose -f app/docker-compose.yml --env-file app/.env cp db:/tmp/npsdm-backup.dump app/outputs/npsdm-backup.dump
```

Retention is a site governance decision. No unattended deletion job runs by default. The retention CLI accepts an explicit tenant and day threshold: `python -m npsdm_app.retention --tenant local --days 365` previews counts; adding `--apply` deletes those source observations transactionally and records an audit event. Decision snapshots remain; this is not full subject erasure. Scheduling retention, SSO and production penetration testing are not implemented.

Version-controlled Python direct dependencies and npm lockfile are provided. Docker base tags are pinned to a version but not content digests. A new .github/workflows/npsdm-app.yml runs backend/historical tests, frontend checks and Docker/Playwright integration on app pull requests. This is the sole new file outside app/; existing research code and root documentation are unchanged. Single-host validation is not an availability guarantee.
