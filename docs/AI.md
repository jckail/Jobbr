# Optional OpenAI and Claude workflows

Jobbr works without a key: JSON-LD and heuristic extraction, deterministic fit scores,
profile editing and application tracking run locally. Extraction tries schema.org
JobPosting JSON-LD first, optional structured extraction using the selected provider next, then heuristics.
JSON-LD avoids a paid request. AI errors are recorded with the heuristic fallback.

## Setup and limits

Both OpenAI and Claude are supported. Select the server provider explicitly with
`JOBBR_AI_PROVIDER=openai` (default) or `JOBBR_AI_PROVIDER=anthropic`. OpenAI uses
`JOBBR_OPENAI_API_KEY` or `OPENAI_API_KEY`; Claude uses `JOBBR_ANTHROPIC_API_KEY` or
`ANTHROPIC_API_KEY`. Jobbr-prefixed keys take precedence. Only the selected
provider's key enables AI: another configured provider is never an automatic fallback.
Keep keys on the backend; never put them in frontend configuration or browser storage.
Setting keys enables potentially paid extraction on ingestion/re-extraction. Career
drafting requires an explicit authenticated request and informed candidate consent.
Provider choice does not authorize configuring real credentials or making paid calls.

The public configuration reports selected provider/model and readiness booleans, never
keys. Selection is deployment configuration, not a browser key entry or per-request
automatic provider switch. Restart/reconfigure the server to change it.

| Backend setting | Default | Limit |
| --- | --- | --- |
| `JOBBR_AI_PROVIDER` | `openai` | `openai` or `anthropic`; no cross-provider fallback |
| `JOBBR_ANTHROPIC_MODEL` | `claude-sonnet-4-6` | Claude model supporting Messages structured outputs and account access |
| `JOBBR_MODEL` | `gpt-4.1-mini` | Requires compatible structured output and account access |
| `JOBBR_AI_TIMEOUT_S` | `45` | Whole-run cap, maximum 120 seconds |
| `JOBBR_AI_MAX_TURNS` | `2` | Maximum 5 |
| `JOBBR_AI_MAX_OUTPUT_TOKENS` | `3000` | Maximum 8000 |
| `JOBBR_MAX_INPUT_CHARS` | `60000` | Resume and posting text are truncated to budget |

The OpenAI path retains the tool-free Agents SDK with Pydantic `output_type`,
`Runner.run`, `max_turns` and a cancellable async timeout. The Claude path uses the
existing HTTP client against the fixed official Messages endpoint and
`output_config.format` JSON-schema output. It makes one bounded request; unsupported
schema constraints are described to the model, and the original Pydantic schema
validates the response. Refusals, truncated output and malformed output fail closed. Provider retries are disabled. No browsing, applications,
messages, filesystem access, or autonomous handoffs occur. Extraction invokes the
async SDK in the API's synchronous worker; career drafting is async.

## Career drafts

`generate_career(job, company, profile, kind)` supports `cover_letter` and
`interview_prep`. The typed result includes the draft, strengths, gaps, employer
questions, exact supporting profile quotes, review notes, provider, model and token counts.
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

Optional AI sends selected profile/resume and posting facts only to the selected provider, OpenAI or Claude. Application
notes, database IDs and other saved jobs are excluded. OpenAI runs disable tracing and
sensitive trace data and set `store=False`. The Claude path adds no SDK tracing.
Neither setting promises zero provider retention. No server-side conversations or agent sessions are created.

Token counts are recorded. The existing database `cost_usd=0` means **cost not
estimated**, not a free request; consult account billing for actual charges. Model
prices are not hard-coded.

Tests fake the OpenAI SDK Runner and Claude HTTP transport and cover success, typed output, privacy and bounds,
invented evidence, provider failure, malformed output, timeout, no-key behavior,
JSON-LD before paid extraction and heuristic fallback. No paid calls are made.

Official references: [Agents and typed output](https://openai.github.io/openai-agents-python/agents/),
[Runner and bounds](https://openai.github.io/openai-agents-python/running_agents/),
[client/tracing configuration](https://openai.github.io/openai-agents-python/config/).


Provider metadata is retained when explicitly saving career drafts; reopening an old
draft does not relabel it with the currently selected provider or invoke AI. Legacy
career drafts without a provider field came from the original OpenAI-only path.
Extraction history retains its recorded model; historical rows are not attributed
to the currently selected provider. Provider/account/model access and real generation
remain unverified until separately authorized live checks.

Claude references: [Messages API](https://platform.claude.com/docs/en/api/messages/create),
[structured output and schema limits](https://platform.claude.com/docs/en/build-with-claude/structured-outputs),
[stop reasons](https://platform.claude.com/docs/en/build-with-claude/handling-stop-reasons).


Browser ingestion, re-extraction and drafting requests pin the provider, model and
enabled state shown in their disclosure. A server configuration change rejects
those requests with409 before any extraction or generation; refresh the settings
and give new consent rather than automatically retrying. Existing programmatic
clients without selection headers continue to use explicit server configuration.
A partially supplied selection is rejected with422.
