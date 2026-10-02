# Optional OpenAI workflows

Jobbr works without a key: JSON-LD and heuristic extraction, deterministic fit scores,
profile editing and application tracking run locally. Extraction tries schema.org
JobPosting JSON-LD first, optional OpenAI structured extraction next, then heuristics.
JSON-LD avoids a paid request. AI errors are recorded with the heuristic fallback.

## Setup and limits

Install backend dependencies including `openai-agents`. Set `JOBBR_OPENAI_API_KEY`
on the backend, or `OPENAI_API_KEY`; the Jobbr-prefixed key takes precedence. Never
put a key in frontend configuration or browser storage. A key enables optional
extraction. Career drafting requires an explicit authenticated request.

| Backend setting | Default | Limit |
| --- | --- | --- |
| `JOBBR_MODEL` | `gpt-4.1-mini` | Requires compatible structured output and account access |
| `JOBBR_AI_TIMEOUT_S` | `45` | Whole-run cap, maximum 120 seconds |
| `JOBBR_AI_MAX_TURNS` | `2` | Maximum 5 |
| `JOBBR_AI_MAX_OUTPUT_TOKENS` | `3000` | Maximum 8000 |
| `JOBBR_MAX_INPUT_CHARS` | `60000` | Resume and posting text are truncated to budget |

A tool-free Agent uses Pydantic `output_type`, `Runner.run`, `max_turns` and a
cancellable async timeout. Provider retries are disabled. No browsing, applications,
messages, filesystem access, or autonomous handoffs occur. Extraction invokes the
async SDK in the API's synchronous worker; career drafting is async.

## Career drafts

`generate_career(job, company, profile, kind)` supports `cover_letter` and
`interview_prep`. The typed result includes the draft, strengths, gaps, employer
questions, exact supporting profile quotes, review notes, model and token counts.
Interview preparation has at least five job-specific questions and answer outlines.
The deterministic fit score stays unchanged.

A draft needs a saved resume, headline, or skills. Instructions require only supplied
candidate facts and prohibit invented employers, dates, credentials, projects,
metrics, and experience. Requirements in a posting are not candidate qualifications.
Embedded posting/resume instructions are treated as untrusted data. Exact evidence
quotes are validated against supplied profile facts; invented quotes, missing
evidence, wrong shapes and incomplete drafts are rejected. This does not prove
every generated sentence is factual. `requires_review` is always true: the candidate
must verify every claim before using it.

Without a key, `AIUnavailable` reports disabled AI; no substitute letter or fake
AI text is returned. Missing facts raise `CareerInputError`. Timeout, provider error,
malformed output and unverifiable evidence raise `CareerGenerationError`. Public
errors exclude provider response bodies, resume content and credentials. The
workflow returns drafts for review; it does not save, send or submit them.

## Privacy and usage

Optional AI sends selected profile/resume and posting facts to OpenAI. Application
notes, database IDs and other saved jobs are excluded. Each run disables tracing and
sensitive trace data. Responses set `store=False`; this does not promise zero
provider retention. No server-side conversations or agent sessions are created.

Token counts are recorded. The existing database `cost_usd=0` means **cost not
estimated**, not a free request; consult account billing for actual charges. Model
prices are not hard-coded.

Tests fake the SDK Runner and cover success, typed output, privacy and bounds,
invented evidence, provider failure, malformed output, timeout, no-key behavior,
JSON-LD before paid extraction and heuristic fallback. No paid calls are made.

Official references: [Agents and typed output](https://openai.github.io/openai-agents-python/agents/),
[Runner and bounds](https://openai.github.io/openai-agents-python/running_agents/),
[client/tracing configuration](https://openai.github.io/openai-agents-python/config/).
