import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlmodel import Session, select

from . import __version__
from .api import router
from .config import get_settings
from .db import get_engine, init_db
from .models import Job
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

    @app.get("/healthz", include_in_schema=False)
    def healthz() -> dict[str, bool]:
        return {"ok": True}

    # API lives under the mount path so an ingress can route /jobbr/* without rewriting.
    app.include_router(router, prefix=base)

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
