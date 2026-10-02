import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlmodel import Session, select
from starlette.middleware.base import RequestResponseEndpoint
from starlette.responses import Response

from . import __version__
from .api import router
from .auth import AuthService, AuthSettings, build_auth_router
from .config import get_settings
from .db import get_engine, init_db
from .discovery import router as discovery_router
from .models import Job
from .resume import router as resume_router
from .seed import seed

log = logging.getLogger("jobbr")


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    init_db()
    if get_settings().seed_demo:
        with Session(get_engine()) as s:
            if not s.exec(select(Job)).first():
                seed(s)
                log.info("seeded demo data")
    yield


def _mount_spa(app: FastAPI, static: Path, base: str) -> None:
    """Serve the built UI (with history fallback to index.html) under the mount path."""
    if not static.is_dir():
        return
    root = static.resolve()
    if (static / "assets").is_dir():
        app.mount(f"{base}/assets", StaticFiles(directory=static / "assets"), name="assets")

    @app.get(base + "/{path:path}", include_in_schema=False)
    def spa(path: str) -> FileResponse:
        if path.startswith("api/"):
            raise HTTPException(404)
        f = (static / path).resolve()
        if path and f.is_file() and root in f.parents:
            return FileResponse(f)
        return FileResponse(static / "index.html", headers={"Cache-Control": "no-cache"})


def create_app() -> FastAPI:
    st = get_settings()
    base = st.base
    app = FastAPI(
        title="Jobbr",
        version=__version__,
        lifespan=lifespan,
        docs_url=f"{base}/api/docs",
        openapi_url=f"{base}/api/openapi.json",
        redoc_url=None,
    )
    auth = AuthService(AuthSettings(), base=base)
    app.state.auth = auth
    if st.private_instance and not (st.api_token or auth.settings.auth_enabled):
        raise RuntimeError("Private instances require an API token or configured OpenAI sign-in.")

    @app.middleware("http")
    async def security_headers(request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        if request.url.path.startswith(base + "/api"):
            response.headers["Cache-Control"] = "no-store"
        else:
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; script-src 'self'; "
                "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
                "font-src 'self' https://fonts.gstatic.com; "
                "img-src 'self' data:; connect-src 'self'; object-src 'none'; "
                "base-uri 'self'; frame-ancestors 'none'; form-action 'self'"
            )
        return response

    @app.get("/healthz", include_in_schema=False)
    def healthz() -> dict[str, bool]:
        return {"ok": True}

    # API lives under the mount path so an ingress can route /jobbr/* without rewriting.
    app.include_router(router, prefix=base)
    app.include_router(build_auth_router(auth), prefix=base)
    app.include_router(discovery_router, prefix=base)
    app.include_router(resume_router, prefix=base)

    _mount_spa(app, Path(st.static_dir), base)

    if base:

        @app.get("/", include_in_schema=False)
        def root() -> RedirectResponse:
            return RedirectResponse(base + "/")

    @app.exception_handler(Exception)
    async def unhandled(_request: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled", exc_info=exc)
        return JSONResponse({"detail": "Internal error"}, status_code=500)

    return app


app = create_app()
