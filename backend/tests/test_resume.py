import asyncio
import io
import secrets
import time

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from jobbr import config
from jobbr.auth import ISSUER, SESSION_COOKIE, SessionRecord
from jobbr.auth_store import DatabaseAuthStore
from jobbr.main import create_app
from jobbr.resume import MAX_FILE_BYTES, ResumeError, parse_isolated, router, safe_filename

PATH = "/jobbr/api/profile/resume"


def pdf_bytes(text: str | None = "Python SQL resume", pages: int = 1, encrypted: bool = False):
    writer = PdfWriter()
    for _ in range(pages):
        page = writer.add_blank_page(width=600, height=800)
        if text is not None:
            font = DictionaryObject(
                {
                    NameObject("/Type"): NameObject("/Font"),
                    NameObject("/Subtype"): NameObject("/Type1"),
                    NameObject("/BaseFont"): NameObject("/Helvetica"),
                }
            )
            page[NameObject("/Resources")] = DictionaryObject(
                {
                    NameObject("/Font"): DictionaryObject(
                        {NameObject("/F1"): writer._add_object(font)}
                    )
                }
            )
            stream = DecodedStreamObject()
            stream.set_data(f"BT /F1 12 Tf 50 700 Td ({text}) Tj ET".encode())
            page[NameObject("/Contents")] = writer._add_object(stream)
    if encrypted:
        writer.encrypt("secret")
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


@pytest.fixture
def resume_client(env):
    app = create_app()
    # This also verifies the module router in isolation before parent mounts it in main.
    if not any(getattr(route, "path", "") == PATH for route in app.routes):
        app.include_router(router, prefix=config.get_settings().base)
    with TestClient(app) as client:
        yield client


def test_preview_extracts_text_but_does_not_save_profile(resume_client):
    before = resume_client.get("/jobbr/api/profile").json()
    response = resume_client.post(PATH, files={"file": ("../../resume.pdf", pdf_bytes())})
    assert response.status_code == 200, response.text
    assert response.json() == {
        "text": "Python SQL resume",
        "page_count": 1,
        "filename": "resume.pdf",
    }
    assert resume_client.get("/jobbr/api/profile").json() == before


@pytest.mark.parametrize(
    ("data", "message"),
    [
        (b"not a PDF", "valid PDF"),
        (b"%PDF-1.7\ncorrupt document", "could not be read"),
        (pdf_bytes(encrypted=True), "Encrypted"),
        (pdf_bytes(text=None), "OCR"),
        (pdf_bytes(pages=31), "1 to 30"),
        (pdf_bytes(text="x" * 60001), "60,000"),
    ],
)
def test_bad_pdf_returns_actionable_error(resume_client, data, message):
    response = resume_client.post(PATH, files={"file": ("resume.pdf", data)})
    assert response.status_code == 422
    assert message in response.json()["detail"]
    assert "corrupt document" not in response.text


def test_oversize_file_rejected(resume_client):
    response = resume_client.post(
        PATH, files={"file": ("large.pdf", b"%PDF-" + b"x" * MAX_FILE_BYTES)}
    )
    assert response.status_code == 413


def test_chunked_oversize_rejected_without_content_length(resume_client):
    boundary = "resume-test-boundary"
    prefix = (
        f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="resume.pdf"'
        "\r\nContent-Type: application/pdf\r\n\r\n"
    ).encode()

    def chunks():
        yield prefix
        for _ in range(81):
            yield b"x" * 65536
        yield f"\r\n--{boundary}--\r\n".encode()

    response = resume_client.post(
        PATH,
        content=chunks(),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    assert response.status_code == 413


def test_invalid_multipart_empty_and_extra_files_rejected(resume_client):
    assert resume_client.post(PATH, json={"file": "fake"}).status_code == 415
    assert resume_client.post(PATH, files={"file": ("empty.pdf", b"")}).status_code == 422
    assert resume_client.post(PATH, files={"other": ("resume.pdf", pdf_bytes())}).status_code == 422
    response = resume_client.post(
        PATH, files=[("file", ("first.pdf", pdf_bytes())), ("file", ("second.pdf", pdf_bytes()))]
    )
    assert response.status_code == 422
    incomplete = (
        b'--b\r\nContent-Disposition: form-data; name="file"; filename="x.pdf"\r\n\r\n%PDF-'
    )
    assert (
        resume_client.post(
            PATH, content=incomplete, headers={"Content-Type": "multipart/form-data; boundary=b"}
        ).status_code
        == 422
    )


def test_filename_is_display_only_and_sanitized():
    assert safe_filename(r"C:\Users\me\resume.pdf") == "resume.pdf"
    assert safe_filename("../../<img src=x>.pdf") == "_img src_x_.pdf"
    assert safe_filename(".../") == "resume.pdf"
    assert len(safe_filename("x" * 1000)) == 120


def test_preview_requires_write_token(env):
    env.setenv("JOBBR_API_TOKEN", "resume-secret")
    config.get_settings.cache_clear()
    app = create_app()
    if not any(getattr(route, "path", "") == PATH for route in app.routes):
        app.include_router(router, prefix=config.get_settings().base)
    with TestClient(app) as client:
        assert client.post(PATH, files={"file": ("r.pdf", pdf_bytes())}).status_code == 401
        assert (
            client.post(
                PATH, files={"file": ("r.pdf", pdf_bytes())}, headers={"X-Jobbr-Token": "wrong"}
            ).status_code
            == 401
        )
        assert (
            client.post(
                PATH,
                files={"file": ("r.pdf", pdf_bytes())},
                headers={"X-Jobbr-Token": "resume-secret"},
            ).status_code
            == 200
        )


def test_oidc_preview_requires_session_origin_and_csrf(env):
    env.setenv("JOBBR_OPENAI_AUTH_ENABLED", "true")
    env.setenv("JOBBR_OPENAI_CLIENT_ID", "oaiapp_resume_test")
    env.setenv("JOBBR_OPENAI_ALLOWED_SUBJECT", "owner")
    env.setenv("JOBBR_OPENAI_REDIRECT_URI", "https://jobbr.example/jobbr/auth/openai/callback")
    env.setenv("JOBBR_OPENAI_STORE_KEY", Fernet.generate_key().decode())
    env.setenv("JOBBR_OPENAI_TOKEN_AUTH_METHOD", "none")
    env.delenv("JOBBR_OPENAI_CLIENT_SECRET", raising=False)
    app = create_app()
    service = app.state.auth
    with TestClient(app, base_url="https://jobbr.example") as client:
        # Lifespan runs the real migrations before the shared store is populated.
        assert isinstance(service.store, DatabaseAuthStore)
        assert service.problem() is None
        assert client.post(PATH, files={"file": ("r.pdf", pdf_bytes())}).status_code == 401
        session_id = secrets.token_urlsafe(32)
        csrf_token = service.store.csrf(session_id)
        service.store.rotate_session(
            "",
            session_id,
            SessionRecord(
                issuer=ISSUER,
                client_id="oaiapp_resume_test",
                subject="owner",
                name=None,
                email=None,
                csrf_token=csrf_token,
                expires_at=time.time() + 300,
            ),
            service.scope,
        )
        client.cookies.set(SESSION_COOKIE, session_id, domain="jobbr.example", path="/")
        before = client.get("/jobbr/api/profile")
        assert before.status_code == 200
        assert client.post(PATH, files={"file": ("r.pdf", pdf_bytes())}).status_code == 403
        headers = {"Origin": "https://jobbr.example", "X-CSRF-Token": csrf_token}
        assert (
            client.post(
                PATH,
                files={"file": ("r.pdf", pdf_bytes())},
                headers={**headers, "Origin": "https://attacker.example"},
            ).status_code
            == 403
        )
        assert (
            client.post(PATH, files={"file": ("r.pdf", pdf_bytes())}, headers=headers).status_code
            == 200
        )

        assert client.get("/jobbr/api/profile").json() == before.json()


def test_isolated_parser_timeout_kills_worker(monkeypatch):
    class SlowProcess:
        returncode = None
        killed = False

        async def communicate(self, _data):
            await asyncio.sleep(1)
            return b"{}", b""

        def kill(self):
            self.killed = True

        async def wait(self):
            self.returncode = -9

    process = SlowProcess()

    async def create_process(*_args, **_kwargs):
        return process

    monkeypatch.setattr("jobbr.resume.asyncio.create_subprocess_exec", create_process)
    monkeypatch.setattr("jobbr.resume.PARSER_TIMEOUT", 0.01)
    with pytest.raises(ResumeError, match="too long"):
        asyncio.run(parse_isolated(b"%PDF-"))
    assert process.killed
