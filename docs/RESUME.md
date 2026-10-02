# PDF resume preview

On **Your profile**, choose a PDF and click **Preview PDF text**. This sends the selected file to your Jobbr server for text extraction. Review or edit the preview, then click **Use this text** to replace the resume in the form. Your saved profile changes only after **Save & re-score**. Discarding a preview leaves the form unchanged.

Paste plain text in the existing resume field when a PDF is scanned, encrypted, incomplete, or unsupported. This feature does not perform OCR and does not invent missing resume content. PDF reading order can differ from the visible layout, especially with columns; check names, dates, and section ordering before accepting.

## API

`POST /jobbr/api/profile/resume` accepts `multipart/form-data` with exactly one `file` part. It returns `{text, page_count, filename}` without saving a profile or sending text to an LLM. The filename is sanitized for display; it never becomes a filesystem path.

The endpoint enforces the same private-access, write-token, authenticated session, Origin, and CSRF checks as other profile writes. The browser’s API helper supplies these headers and lets the browser generate the multipart boundary.

Limits:

- PDF file: 5 MiB; multipart envelope: an additional 64 KiB; headers: 8 KiB; one file only.
- Document: 1–30 pages; extracted text: at most 60,000 characters, rejected rather than silently truncated.
- Upload: 15 seconds. Two concurrent preview requests per server process; additional requests receive 429 after a one-second wait.
- Parser subprocess: 256 MiB address space, five CPU seconds, ten wall-clock seconds. Timed-out or cancelled workers are killed and reaped. Malformed, encrypted, and image-only PDFs return actionable 422 errors.

The parser uses `pypdf` inside a fresh POSIX subprocess with resource limits, off the application event loop. PDF uploads are streamed into a bounded memory buffer using `python-multipart` callbacks; FastAPI’s disk-spooling `UploadFile` is deliberately avoided. The application does not write uploaded PDFs or extracted previews to disk, include document bytes in subprocess arguments, emit parser diagnostics, or save preview text to the database. Normal proxy buffering, operating-system swap, or independently configured request-body tracing are outside this application’s control; disable body logging/tracing for sensitive upload routes. The intended production server is Linux. Non-POSIX servers report that PDF preview is unavailable and offer the plain-text route.

Acceptance only updates browser form state. The existing explicit profile save persists accepted text and derives skills. Subsequent explicitly requested career-assistance features can use saved profile text with the configured LLM; PDF preview itself makes no LLM call.

## Verification

```sh
cd backend
.venv/bin/pytest -q tests/test_resume.py
.venv/bin/ruff check jobbr/resume.py tests/test_resume.py
.venv/bin/mypy jobbr/resume.py
cd ../web
npm run check
```

Tests cover real subprocess extraction, preview without profile persistence, malformed/encrypted/scanned PDFs, page/text/file limits, missing-length uploads, malformed multipart bodies, filename sanitization, authentication and timeout cleanup. Browser interaction should also be checked with a real resume before release, including preview editing, replacing existing form text, discarding, and explicit save.

## Profile history

Explicit profile saves retain immutable snapshots of all scoring inputs. Review a historical snapshot before restoring it; restoration activates that profile and re-scores jobs while preserving application notes and existing career drafts. PDF preview and form edits remain transient until Save. Identical saves reuse the active revision.

History requires sign-in or a valid instance token even on an otherwise open demo. New snapshots are bounded to1MiB of UTF8 JSON and at most50 revisions per profile; no snapshot is silently evicted. Only an inactive revision can be explicitly deleted. Existing profiles are backfilled verbatim, with the date history was first recorded rather than an invented original resume save date. Earlier backups remain verifiable/restorable.

The web interface sends a monotonic version token on saves/restores/deletes. A stale edit receives409 and keeps form/PDF content; review the active snapshot before deliberately keeping your edits for a new Save. Legacy programmatic profile PUT clients may omit this check for compatibility.

Resume tailoring and generation provenance tied to a selected immutable revision remain a separate pending increment. Current career drafts retain their existing save-time fingerprints; history alone does not prove which revision generated an old draft.
