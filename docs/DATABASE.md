# Jobbr v2 database migrations

The v2 backend runs `alembic upgrade head` during application startup and verifies
that the resulting tables, columns, types, nullability, primary keys, foreign keys,
unique constraints and indexes match its current models. Startup no longer calls
`SQLModel.metadata.create_all`. Alembic configuration and revisions live in
`backend/alembic.ini` and `backend/migrations/`; the legacy root migrations are
separate and are not used by v2.

## Run migrations explicitly

Run these commands from `backend` with the backend virtual environment active:

```bash
export JOBBR_DATABASE_URL='sqlite:////absolute/path/to/jobbr-v2.db'
alembic upgrade head
alembic current
alembic check
```

`JOBBR_DATABASE_URL` is the same setting used by the API. Prefer an absolute SQLite
path to avoid changing databases when the working directory changes. An empty
database receives the initial `0001_v2` migration. Repeated startup upgrades are
idempotent. Startup locates the packaged `migrations` resources directly, so installed wheels
can migrate without an external `alembic.ini`. The source checkout retains
`backend/alembic.ini` for the commands above. The container ships these resources
and the CLI configuration.

## Preserve an existing v2 SQLite database

Stop processes using the database and back up the SQLite file before upgrading;
for a live database use SQLite's backup API or `.backup` so WAL contents are
included. Configure `JOBBR_DATABASE_URL` to point to the existing v2 database.

The initial migration accepts an unversioned database only after checking its
complete schema against the frozen v2 baseline. A database previously created by
the v2 backend's `create_all` is adopted by recording `0001_v2` in
`alembic_version`; no application tables are rebuilt and no job rows are copied,
removed or rewritten. Missing or extra tables, changed columns, missing indexes,
and changed constraints cause migration failure before recording that revision.
A rejected database retains its data; SQLite may contain an empty
`alembic_version` table after the failed attempt.

A legacy v1 database is not a v2 database. Point v2 at a new database instead of
stamping a legacy or otherwise mismatched schema. Any legacy data transfer needs
an explicit mapping and separate import. Do not use `alembic stamp head` to bypass
validation. If a previously versioned database has drifted from the models,
startup also refuses it; repair it from a verified backup or an explicit migration.

## PostgreSQL

Install the backend dependencies, which include `psycopg[binary]`, and configure a
pre-created PostgreSQL database:

```bash
export JOBBR_DATABASE_URL='postgresql+psycopg://user:password@host:5432/jobbr'
alembic upgrade head
alembic check
```

Plain `postgresql://` URLs are normalized to the psycopg driver. The initial
revision creates PostgreSQL enum types once, shares them across tables and creates
foreign keys and indexes. It also supports verified adoption of an unversioned
PostgreSQL v2 schema, including validation of enum labels. PostgreSQL offline DDL
compilation and live PostgreSQL 17 integration tests cover the initial migration.
The live checks exercise fresh and repeated upgrades, schema verification, v2
adoption with preserved rows, enum drift rejection, API ingestion, rematching,
application updates, persistence through a reopened pool and deletion of child
records.

## Run the PostgreSQL integration tests

The default test suite skips live PostgreSQL tests. To run them against a disposable
PostgreSQL database named `jobbr_test`, from `backend`:

```bash
export JOBBR_TEST_POSTGRES_URL='postgresql+psycopg://postgres:test_password@127.0.0.1:5432/jobbr_test'
python -m pytest tests/test_postgres.py
```

The database must already exist and the test user must be able to create schemas.
Tests refuse any database name other than `jobbr_test`, any URL overriding
PostgreSQL connection `options`, or an initial schema other than `public`. Each
fixture creates a separate randomly named `jobbr_test_...` schema, confines the
backend's search path to it and removes only that schema afterward. Existing
`public` tables are untouched. Use a disposable local container or a dedicated CI
service for this suite.

## Future schema changes

Change the models, then create and review a revision from `backend`:

```bash
alembic revision --autogenerate -m 'describe the schema change'
alembic upgrade head
alembic check
```

Keep `migrations/baseline.py` and `0001_v2` unchanged: they describe the original
schema accepted for adoption, independent of later model edits. Review generated
DDL carefully for SQLite batch operations, data conversions and PostgreSQL enums;
Alembic does not automatically generate every constraint or enum change. Test each
new revision against both a fresh database and a populated previous revision.

The initial revision deliberately refuses downgrade because removing the original
tables would destroy job data. Rollback across the initial revision requires
restoring a backup and running a compatible backend. Take a backup before deploying
future schema revisions and document their individual rollback behavior.

## Distribution

The wheel explicitly includes the migrations package. Startup resolves its installed package resources, so it no longer requires a backend-relative alembic.ini. The source CLI still uses backend/alembic.ini. Docker includes both for administration.
