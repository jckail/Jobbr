# Backup and restore for a local Jobbr instance

`scripts/backup.py` handles SQLite snapshots for the single-owner local deployment.
Run it with the backend virtual environment's Python, or use `/app/backup.py` in
the Docker image. It accepts explicit file paths and never prints database rows,
API keys or connection URLs. Backups contain private resume text and application
notes, saved career drafts, and encrypted/authentication state; keep a copy outside the Docker data volume.

Both `backup` and `restore` use SQLite's backup API to capture committed data,
including pages in the WAL. They validate SQLite integrity, foreign keys, the
Alembic revision and the exact schema for that supported revision before publishing
a single-file database. They do not migrate the source. Unversioned, unknown-revision, corrupt or mismatched databases are rejected.
Versioned v2 snapshots at `0001_v2` and `0002_saved_drafts` remain accepted against
their frozen historical schemas. Restoring one copies it unchanged; application
startup upgrades only the restored copy to the current migration head.

The output directory must already exist. A private staging file with mode `0600`
is published atomically without replacing existing paths. Existing files,
directories and symlinks cause failure, including paths created during the backup.
Publication requires hard-link support, available on normal Linux filesystems and
Docker named volumes. Use a directory you own. There is no overwrite option;
failed validation leaves no published output.

## Source checkout

From the repository root:

```bash
mkdir -p backups
backend/.venv/bin/python scripts/backup.py backup /absolute/path/jobbr.db backups/jobbr-before-upgrade.db
backend/.venv/bin/python scripts/backup.py verify backups/jobbr-before-upgrade.db
backend/.venv/bin/python scripts/backup.py restore backups/jobbr-before-upgrade.db /absolute/path/jobbr-restored.db
```

Choose new output names each time. Restore creates a separate validated database
and leaves the current database intact. Stop the API before changing its setting
to `JOBBR_DATABASE_URL=sqlite:////absolute/path/jobbr-restored.db`. Check the restored
profile, jobs and application history before retiring the previous database.

## Docker SQLite backup

The local `compose.yaml` mounts the database at `/data/jobbr.db`. Build the current
image so it includes `/app/backup.py`. The API may remain running during backup;
SQLite provides a consistent committed snapshot. Retry during a quiet period if
continuous writes cause the 60-second snapshot timeout.

```bash
docker compose exec -T app mkdir -p /data/backups
docker compose exec -T app python /app/backup.py backup /data/jobbr.db /data/backups/jobbr-before-upgrade.db
docker compose exec -T app python /app/backup.py verify /data/backups/jobbr-before-upgrade.db
```

Export into a fresh host directory so `docker compose cp` cannot replace a
previous backup:

```bash
backup_export_dir=$(mktemp -d "$PWD/jobbr-backup.XXXXXX")
docker compose cp app:/data/backups/jobbr-before-upgrade.db "$backup_export_dir/jobbr.db"
chmod 600 "$backup_export_dir/jobbr.db"
backend/.venv/bin/python scripts/backup.py verify "$backup_export_dir/jobbr.db"
```

Save that directory on separate storage. Copy only the completed, validated
snapshot. Copying the live `jobbr.db` file alone while the API is writing can omit
committed pages that still reside in `jobbr.db-wal`.

## Docker restore to a new database

Use a backend that supports the snapshot revision. For a snapshot already
in `/data/backups`, stop the API and restore alongside the current database:

```bash
docker compose stop app
docker compose run --rm --no-deps app python /app/backup.py restore /data/backups/jobbr-before-upgrade.db /data/jobbr-restored.db
```

For a host backup, place a transfer copy in a directory readable by container UID
`10001`, then mount that directory read-only for a one-off restore:

```bash
docker compose run --rm --no-deps -v /absolute/readable-backups:/backups:ro app python /app/backup.py restore /backups/jobbr.db /data/jobbr-restored.db
```

Keep the protected archival copy separate from the readable transfer directory.
Both commands refuse an existing `/data/jobbr-restored.db` and leave
`/data/jobbr.db` and its sidecars intact.

After validation, change `app.environment.JOBBR_DATABASE_URL` in your local Compose
configuration to `sqlite:////data/jobbr-restored.db`, then recreate the app:

```bash
docker compose up -d app
docker compose logs --tail=50 app
```

Check `/healthz` and open the profile, saved jobs and application history. Retain
the previous database. To return to it, stop the app, restore the original database
URL and recreate the container. Do not delete the Docker volume during recovery.

## Optional PostgreSQL backup

The SQLite tool does not accept PostgreSQL URLs. Use `pg_dump` with a client version
compatible with the server. Keep credentials in your normal PostgreSQL credential
mechanism, such as a protected `.pgpass` file. With `PGHOST`, `PGPORT`, `PGUSER` and
`PGDATABASE` configured:

```bash
pg_dump --format=custom --file=/absolute/new-backup-dir/jobbr.dump
pg_restore --list /absolute/new-backup-dir/jobbr.dump
```

Create a separate empty recovery database and restore into that explicit target:

```bash
createdb jobbr_restore_check
pg_restore --exit-on-error --no-owner --no-acl --dbname=jobbr_restore_check /absolute/new-backup-dir/jobbr.dump
```

Avoid `--clean` against the active database. Check the restored database with the
compatible backend's migration/schema validation and exercise its profile, jobs
and application history before switching the API URL. Listing a dump checks its
format; a successful restore rehearsal checks preservation. Use a fresh private
directory for each dump so it cannot overwrite an earlier archive. Retain the
original database during the switch.

## Verification coverage

`backend/tests/test_backup.py` exercises a WAL-enabled populated SQLite database
and verifies full profile/company/job/match/extraction/application/event
preservation through backup and restore. It also covers CLI behavior, existing
files, symlinks, source-as-output, missing/corrupt input, revision mismatch, schema
drift and foreign-key violations. Tests use disposable databases.
