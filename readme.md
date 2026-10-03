# Jobbr

**Paste a job link. Get structured data, a transparent fit score against your resume, and a pipeline to track it.**

Deployment target: **https://jckail.com/jobbr** (production not yet verified) · API docs at `/jobbr/api/docs`

> The original prototype (FastAPI + Selenium + LangChain + Supabase experiments) is preserved untouched under the repo root's legacy files and git history; this is the v2 rewrite. See [docs/AUDIT.md](docs/AUDIT.md) for what changed and why.

## How it works

```mermaid
flowchart LR
  U[URL or pasted text] --> F[safefetch<br/>SSRF-guarded]
  F --> E{extract}
  E -->|schema.org JobPosting| J[JSON-LD, free]
  E -->|API key set| L[Selected provider<br/>OpenAI Agents or Claude]
  E -->|fallback| H[heuristics + skill taxonomy]
  J & L & H --> DB[(SQLModel DB)]
  DB --> M[matching<br/>skills 55 · level 15 · location 15 · pay 15]
  P[Profile / resume] --> M
  M --> UI[React UI<br/>overview · jobs · pipeline · profile]
```

Extraction degrades gracefully, so the app is fully usable with no API key. Every extraction is logged (method, model, tokens and latency). OpenAI cost is not yet estimated; the legacy numeric cost field is not evidence of free usage. Scores are deterministic and explained, never an opaque LLM number.

## Data model

```mermaid
erDiagram
  Company ||--o{ Job : posts
  Job ||--o{ Extraction : "produced by"
  Job ||--o| Application : tracked_as
  Application ||--o{ ApplicationEvent : history
  Job ||--o{ Match : scored
  Profile ||--o{ Match : for
```

## Run locally

```bash
# API  (SQLite by default; JOBBR_SEED_DEMO=1 loads demo data)
cd backend && uv sync --locked --extra dev && JOBBR_SEED_DEMO=1 .venv/bin/uvicorn jobbr.main:app --reload
# UI   (proxies /jobbr/api to :8000)
cd web && npm install && npm run dev        # http://localhost:5173/jobbr/
# source checks (full local release gates: docs/LOCAL_CI.md)
(cd backend && .venv/bin/ruff check . && .venv/bin/ruff format --check . && .venv/bin/mypy jobbr && .venv/bin/pytest)
(cd web && npm run check)
```

## Local iteration and deployment

Use [docs/LOCAL.md](docs/LOCAL.md) for the verified development workflow and explicit v2 Compose command. [docs/ROADMAP.md](docs/ROADMAP.md) tracks the full overhaul. [docs/DESIGN.md](docs/DESIGN.md) links the Superdesign prototype awaiting review.

Production at `https://jckail.com/jobbr` remains pending local acceptance, registered OpenAI sign-in configuration and infrastructure verification. `deploy/k8s.yaml` intentionally requires an externally managed Secret and a verified commit image tag. Never apply it with placeholders. The image serves API and UI under `/jobbr` without ingress rewriting. [Local release gates](docs/LOCAL_CI.md) cover backend, web, extension, audits and disposable-image smoke. Automatic hosted CI and main image publication are disabled; new publication requires a separately reviewed local release path.

## Configuration (env, prefix `JOBBR_`)

| Var | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./jobbr.db` | SQLite or Postgres (`postgresql://…`) |
| `BASE_PATH` | `/jobbr` | Mount path |
| `API_TOKEN` | unset | If set, writes require `X-Jobbr-Token` (public read-only demo) |
| `AI_PROVIDER` | `openai` | Select `openai` or `anthropic`; no provider fallback |
| `OPENAI_API_KEY` | unset | Enables the selected OpenAI Agents SDK path |
| `ANTHROPIC_API_KEY` | unset | Enables the selected Claude Messages path |
| `ANTHROPIC_MODEL` | `claude-sonnet-4-6` | Claude structured-output model |
| `MODEL` | `gpt-4.1-mini` | OpenAI extraction/drafting model |
| `SEED_DEMO` | `false` | Load demo data into an empty DB |

Private production access uses `JOBBR_PRIVATE_INSTANCE=true` with an API token or configured OpenAI sign-in. See [authentication](docs/AUTH.md), [AI behavior](docs/AI.md), and [database migrations](docs/DATABASE.md). The database is currently single-owner; sign-in does not yet imply multi-user isolation.

## MCP access for assistants

An optional [authenticated MCP interface](docs/MCP.md) exposes company/role search,
skills and team context, source provenance, distinct posting/discovery dates,
stored refresh status, and the Saved shortlist through the existing database.
It validates resource-bound OAuth access tokens and admits only the configured
database owner. Shortlist-note writes are separately scoped and disabled by
default. Run it with `uvicorn jobbr.mcp_server:create_app --factory` after the
documented configuration. It is not deployed or connected to ChatGPT; external
OAuth setup and live acceptance remain required. Website Sign in with ChatGPT
remains the separate, registration-gated identity flow described in AUTH.md.
