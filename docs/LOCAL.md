# Local test instance

Current development is in `/home/jkail/jobbr-v2` on `claude/beautiful-sagan-mtnuvk`. The original `/mnt/c/Users/jkail/Documents/projects/jobbr` main worktree was dirty before this task and is preserved.

## Docker

```sh
cd /home/jkail/jobbr-v2
docker compose -f compose.yaml up --build -d
```

Open http://localhost:8000/jobbr/ and http://localhost:8000/jobbr/api/docs. The API and built UI share an origin, mount path and image. No API key is required for demo ingestion/matching/pipeline. Demo data is explicit in local Compose; production manifest disables it and requires private access.

Compose defaults to `JOBBR_AI_PROVIDER=openai`, `JOBBR_MODEL=gpt-4.1-mini`, and `JOBBR_ANTHROPIC_MODEL=claude-sonnet-4-6`, matching the server defaults. To intentionally enable paid extraction/drafting, configure the selected provider's server-side key: `JOBBR_OPENAI_API_KEY` for OpenAI, or `JOBBR_AI_PROVIDER=anthropic` with `JOBBR_ANTHROPIC_API_KEY` for Claude. Compose also accepts the generic `OPENAI_API_KEY` and `ANTHROPIC_API_KEY` aliases when the corresponding Jobbr-specific key is empty or unset. Only the selected provider's key enables AI; it never falls back to the other provider. Model overrides use `JOBBR_MODEL` and `JOBBR_ANTHROPIC_MODEL`. Keys remain server-side; leave both keys unset for the no-key demo.

The named volume holds your database across restarts. Do not run `down --volumes` against a database you want to keep. Existing legacy docker-compose.yml is preserved; always pass `-f compose.yaml` for v2.

## Source development and checks

Requires Python 3.11+ (tested 3.12), uv, and Node 22.12+.

```sh
uv sync --project backend --locked --extra dev
(cd backend && JOBBR_SEED_DEMO=true .venv/bin/uvicorn jobbr.main:app --host 127.0.0.1 --port 8000)
(cd web && npm ci && npm run dev -- --host 127.0.0.1)
(cd backend && .venv/bin/ruff check . && .venv/bin/ruff format --check . && .venv/bin/mypy jobbr && .venv/bin/pytest)
(cd web && npm run check && npm audit --audit-level=high)
node --test extension/*.test.mjs
```

The smoke script creates and deletes a test job; run it only against a disposable database/container, never your real tracker. CI uses a fresh anonymous data volume. Live provider and Chrome tests remain separate from offline checks.

See AUTH.md for registered HTTPS callback requirements, AI.md for SDK behavior, EXTENSION.md to load unpacked, and ROADMAP.md for remaining delivery work.
