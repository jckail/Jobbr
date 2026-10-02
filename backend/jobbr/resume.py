"""Bounded, memory-only PDF previews. Worker mode never imports the web app."""
# Safe validation errors intentionally share catch scopes with untrusted parser failures.
# ruff: noqa: TRY301

import asyncio
import io
import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from fastapi import APIRouter, Request
    from python_multipart.multipart import MultipartCallbacks

MAX_FILE_BYTES = 5 * 1024 * 1024
MAX_BODY_BYTES = MAX_FILE_BYTES + 64 * 1024
MAX_PAGES = 30
MAX_TEXT_CHARS = 60_000
PARSER_TIMEOUT = 10
_slots = asyncio.Semaphore(2)


class ResumeError(ValueError):
    """A safe, fixed explanation that never contains document content."""


def safe_filename(value: str) -> str:
    name = value.replace("\\", "/").rsplit("/", 1)[-1]
    name = re.sub(r"[^A-Za-z0-9._ -]", "_", name).strip(" .")[:120]
    return name or "resume.pdf"


def extract_pdf(data: bytes) -> dict[str, Any]:
    """Run only inside the resource-limited worker (direct calls are for tests)."""
    from pypdf import PdfReader  # noqa: PLC0415 -- import after worker resource caps

    if not data.startswith(b"%PDF-"):
        raise ResumeError("Choose a valid PDF resume, or paste its plain text instead.")
    try:
        reader = PdfReader(io.BytesIO(data), strict=True)
        if reader.is_encrypted:
            raise ResumeError("Encrypted PDFs are unsupported. Upload an unencrypted copy.")
        count = len(reader.pages)
        if not 1 <= count <= MAX_PAGES:
            raise ResumeError("Upload a PDF with 1 to 30 pages, or paste its plain text instead.")
        parts: list[str] = []
        total = 0
        for page in reader.pages:
            text = page.extract_text() or ""
            total += len(text)
            if total + max(0, len(parts) * 2) > MAX_TEXT_CHARS:
                raise ResumeError("Resume text exceeds 60,000 characters. Upload a shorter PDF.")
            parts.append(text)
        text = "\n\n".join(parts).strip()
        if not text:
            raise ResumeError(
                "No readable text found. Scanned PDFs need OCR first; paste the resulting text."
            )
    except ResumeError:
        raise
    except Exception as exc:
        raise ResumeError(
            "This PDF could not be read. Export a new PDF or paste the resume text instead."
        ) from exc
    else:
        return {"text": text, "page_count": count}


def _worker() -> None:
    # No uploaded bytes or parser diagnostics ever reach logs or temporary files.
    import resource  # noqa: PLC0415 -- POSIX-only worker dependency

    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_AS, (256 * 1024 * 1024, 256 * 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_CPU, (5, 5))
    resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))
    logging.disable(logging.CRITICAL)
    try:
        data = sys.stdin.buffer.read(MAX_FILE_BYTES + 1)
        if len(data) > MAX_FILE_BYTES:
            raise ResumeError("PDF files must be 5 MiB or smaller.")
        result = extract_pdf(data)
    except ResumeError as exc:
        result = {"error": str(exc)}
    except Exception:
        result = {"error": "PDF parsing exceeded safe limits. Paste the resume text instead."}
    sys.stdout.write(json.dumps(result))


async def parse_isolated(data: bytes) -> dict[str, Any]:
    """Kill timed-out/cancelled workers; do not put resume bytes on disk or argv."""
    if os.name != "posix":
        raise ResumeError("PDF preview is unavailable on this server. Paste resume text instead.")
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-I",
        "-B",
        str(Path(__file__).resolve()),
        "--worker",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )
    try:
        output, _ = await asyncio.wait_for(process.communicate(data), timeout=PARSER_TIMEOUT)
    except (TimeoutError, asyncio.CancelledError):
        if process.returncode is None:
            process.kill()
        await process.wait()
        task = asyncio.current_task()
        if task and task.cancelling():
            raise
        raise ResumeError(
            "PDF parsing took too long. Export a simpler PDF or paste text."
        ) from None
    if process.returncode or len(output) > MAX_TEXT_CHARS * 6 + 1024:
        raise ResumeError("PDF parsing exceeded safe limits. Paste the resume text instead.")
    try:
        result: dict[str, Any] = json.loads(output)
        if "error" in result:
            raise ResumeError(result["error"])
        if not isinstance(result["text"], str) or len(result["text"]) > MAX_TEXT_CHARS:
            raise ValueError
    except ResumeError:
        raise
    except (ValueError, KeyError, TypeError) as exc:
        raise ResumeError("PDF preview failed. Paste the resume text instead.") from exc
    else:
        return result


class ResumeTooLarge(ResumeError):
    pass


class UploadCollector:
    """Multipart callbacks with bounded in-memory file and header buffers."""

    def __init__(self) -> None:
        self.content = bytearray()
        self.header_name = bytearray()
        self.header_value = bytearray()
        self.headers: dict[bytes, bytes] = {}
        self.parts = 0
        self.header_bytes = 0
        self.filename = ""
        self.finished = False

    def part_begin(self) -> None:
        self.parts += 1
        if self.parts != 1:
            raise ResumeError("Upload exactly one PDF in the file field.")

    def _check_headers(self, length: int) -> None:
        self.header_bytes += length
        if self.header_bytes > 8192:
            raise ResumeError("PDF upload headers are too large.")

    def header_field(self, data: bytes, start: int, end: int) -> None:
        self._check_headers(end - start)
        self.header_name.extend(data[start:end])

    def header_data(self, data: bytes, start: int, end: int) -> None:
        self._check_headers(end - start)
        self.header_value.extend(data[start:end])

    def header_end(self) -> None:
        self.headers[bytes(self.header_name).lower()] = bytes(self.header_value)
        self.header_name.clear()
        self.header_value.clear()

    def headers_finished(self) -> None:
        from python_multipart.multipart import parse_options_header  # noqa: PLC0415

        kind, values = parse_options_header(self.headers.get(b"content-disposition", b""))
        if kind != b"form-data" or values.get(b"name") != b"file" or not values.get(b"filename"):
            raise ResumeError("Upload exactly one PDF in the file field.")
        self.filename = safe_filename(values[b"filename"].decode("utf-8", "replace"))

    def part_data(self, data: bytes, start: int, end: int) -> None:
        if len(self.content) + end - start > MAX_FILE_BYTES:
            raise ResumeTooLarge("PDF files must be 5 MiB or smaller.")
        self.content.extend(data[start:end])

    def finish(self) -> None:
        self.finished = True

    def callbacks(self) -> "MultipartCallbacks":
        return {
            "on_part_begin": self.part_begin,
            "on_header_field": self.header_field,
            "on_header_value": self.header_data,
            "on_header_end": self.header_end,
            "on_headers_finished": self.headers_finished,
            "on_part_data": self.part_data,
            "on_end": self.finish,
        }


async def receive_pdf(request: "Request") -> tuple[bytes, str]:
    # Lazy imports keep the worker free of application/HTTP dependencies.
    from fastapi import HTTPException  # noqa: PLC0415
    from python_multipart.multipart import MultipartParser, parse_options_header  # noqa: PLC0415

    media_type, options = parse_options_header(request.headers.get("content-type", ""))
    boundary = options.get(b"boundary")
    if media_type != b"multipart/form-data" or not boundary or len(boundary) > 200:
        raise HTTPException(415, "Upload a PDF using the file field in a multipart request.")
    try:
        if int(request.headers.get("content-length", "0")) > MAX_BODY_BYTES:
            raise HTTPException(413, "PDF files must be 5 MiB or smaller.")
    except ValueError as exc:
        raise HTTPException(400, "Invalid upload length.") from exc
    upload = UploadCollector()
    parser = MultipartParser(boundary, upload.callbacks())
    length = 0
    try:
        async for chunk in request.stream():
            length += len(chunk)
            if length > MAX_BODY_BYTES:
                raise ResumeTooLarge("PDF files must be 5 MiB or smaller.")
            parser.write(chunk)
        parser.finalize()
    except ResumeTooLarge as exc:
        raise HTTPException(413, str(exc)) from exc
    except Exception as exc:
        # Multipart parser failures may include raw headers: never return/log them.
        raise HTTPException(422, "Invalid PDF upload. Choose one PDF and try again.") from exc
    if not upload.finished or upload.parts != 1 or not upload.content:
        raise HTTPException(422, "The upload is incomplete or empty. Choose a PDF and try again.")
    return bytes(upload.content), upload.filename


def _build_router() -> "APIRouter":
    # Lazy imports prevent loading the entire app into the constrained parser worker.
    from fastapi import APIRouter, Depends, HTTPException, Request  # noqa: PLC0415

    from .api import require_access, require_token  # noqa: PLC0415

    route = APIRouter(
        prefix="/api/profile/resume",
        dependencies=[Depends(require_access), Depends(require_token)],
    )

    @route.post("")
    async def preview_resume(request: Request) -> dict[str, Any]:
        try:
            await asyncio.wait_for(_slots.acquire(), timeout=1)
        except TimeoutError as exc:
            raise HTTPException(429, "PDF preview is busy. Try again shortly.") from exc
        try:
            try:
                data, filename = await asyncio.wait_for(receive_pdf(request), timeout=15)
            except TimeoutError as exc:
                raise HTTPException(
                    408, "Upload took too long. Choose the PDF and try again."
                ) from exc
            try:
                result = await parse_isolated(data)
            except ResumeError as exc:
                raise HTTPException(422, str(exc)) from exc
            return {**result, "filename": filename}
        finally:
            _slots.release()

    return route


if __name__ == "__main__":
    _worker()
else:
    router = _build_router()
