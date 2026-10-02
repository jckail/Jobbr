# Audit: what Jobbr was, and what it is now

## The soul
Job hunting is a data problem: postings are messy HTML, a candidate is a messy resume. Jobbr's idea is **turn a URL into structured facts, then answer "is this worth my time, and why?"** and track what you do about it. Everything else in the old repo was scaffolding around that loop.

## Findings in the prototype
| Area | Problem |
|---|---|
| Scope | Half the API was tutorial code (`band`, `album`, `special`); `testingStuff/` held ~15 experiments |
| Hygiene | 82 committed `__pycache__` files, 4 conflicting "initial" migrations, API keys in history (rotate them) |
| Model | One 50-column `Stg_Role` table; no companies, no applications, no resume/profile, no scores. `LLM` enum pinned to GPT-3.5/GPT-4-turbo/Claude 3 Opus |
| Pipeline | Selenium + hard-coded chromedriver path, random fake User-Agents, no SSRF protection, HTML shipped to the LLM with hand-tuned length cascades |
| AI | LangChain 0.1 wrapper with custom run/event tables but no cost or latency visibility per extraction; retry loop swallowed errors |
| Product | No UI (the Chrome extension was a stub); the headline feature, resume matching, was never built |
| Ops | Supabase/Auth0 coupling, hard `create_client` at import time, no container for the app, no tests |

## v2 decisions
- **Domain model**: Company, Job, Extraction, Profile, Match, Application, ApplicationEvent (see readme).
- **Extraction ladder**: schema.org JSON-LD (free, exact) → OpenAI Agents SDK with typed structured output → heuristics. Always works offline.
- **Matching** is deterministic, weighted, and explainable; changing your profile re-scores everything instantly.
- **Security**: SSRF guard re-validated on every redirect hop, optional write token for public hosting, non-root read-only container.
- **Frontend**: React + TypeScript, no UI framework, accessible, dark mode, mobile layout, drag-and-drop pipeline, keyboard shortcut (`N`).
- **Deploy**: one image, API + UI under `/jobbr`, SQLite default / Postgres ready.

## Not done yet (suggested next)
- Delete legacy code (kept in place pending your OK) and rotate any previously committed keys.
- Alembic initial migrations and validated adoption are now implemented; live PostgreSQL verification is in progress.
- Headless-browser fetch for JS-only career pages (today: paste text fallback).
- Resume file upload (PDF) and an LLM-written cover letter / interview prep.

## Current overhaul status

See ROADMAP.md for the full requested scope and current evidence. Sign in with ChatGPT, SDK career assistance and extension capture backend boundaries are implemented; new design implementation, provider registration/live tests and production acceptance remain outstanding.
