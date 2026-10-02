# Reviewed public ATS discovery

Jobbr can read live published postings from a company board on Greenhouse or Lever.
This is board discovery, not a web-wide job search. Review the employer's official
careers page to identify its provider and board token, then enter that token only.
No API key or paid AI request is used. Discovery does not save jobs or apply for them.

`GET /jobbr/api/discovery/boards/{provider}/{board}?q=python&remote=remote`
uses the configured app mount path. Providers are `greenhouse` and `lever`. Board
tokens are 1–80 ASCII letters/digits with optional underscores/hyphens, starting with
a letter or digit. Arbitrary URLs, escaped paths, query strings and hostnames cannot
be supplied as an endpoint. This route uses the existing private-read access guard.
An authenticated session or private-instance access token is required when those
features are enabled.

The fixed public endpoints are:

- `https://boards-api.greenhouse.io/v1/boards/{board}/jobs?content=true`
- `https://api.lever.co/v0/postings/{board}?mode=json&limit=100`

Both use the hardened fetcher's pinned DNS transport, verified TLS, disabled
proxy environment, 3 MB raw response cap, configured socket deadline and rejection
of compressed responses. Discovery rejects all redirects so an upstream response
cannot cause a request to an arbitrary endpoint. The system-DNS timeout limitation
in [FETCH_SECURITY.md](FETCH_SECURITY.md) also applies.

A snapshot returns `provider`, `board`, `source_url`, UTC `fetched_at`, `postings`,
`truncated` and `skipped_unsafe_links`. Each posting has `source_id`, `title`, nullable
`company` and `location`, a validated vendor-hosted `url`, bounded plain `raw_text`
and `remote_policy`. Employer names are not inferred from board slugs; these APIs
usually omit the company name. Greenhouse location labels do not prove workplace
policy, so its policy stays `unknown`. Lever's explicit `workplaceType` maps remote,
hybrid and on-site; otherwise policy is unknown.

The adapter examines at most the first 100 postings and returns at most 100; each
plain-text description is capped at 20,000 characters. `truncated=true` indicates
there may be more postings beyond this bounded snapshot. Query and workplace
filters apply locally to this snapshot, so no matches does not prove the whole
company has no suitable jobs. There is no background polling or pagination.

Only HTTPS links on `boards.greenhouse.io`, `job-boards.greenhouse.io` or
`jobs.lever.co` are accepted, with the matching board/posting path, no userinfo and
no nonstandard port. Greenhouse can supply valid custom employer-hosted links;
these are deliberately omitted and counted in `skipped_unsafe_links`. Missing or
unsafe links are never replaced with fabricated URLs. Source descriptions are
converted to text, never rendered as executable HTML.

Network/provider failures and malformed schemas return explicit 502 errors;
invalid tokens return 422. An empty successful snapshot means the valid API payload
had no matches in the examined window. Upstream exception details, secrets and
arbitrary response bodies are excluded from errors. Posting availability can change
between discovery and review: verify the live posting before applying.

Official API references: [Greenhouse Job Board API](https://docs.greenhouse.io/job-board.html)
and [Lever Postings API](https://github.com/lever/postings-api).
