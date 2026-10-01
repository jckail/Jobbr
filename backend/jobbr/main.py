import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from . import __version__
from .api import router
from .config import get_settings
from .db import get_engine, init_db

log = logging.getLogger("jobbr")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    if get_settings().seed_demo:
        from sqlmodel import Session, select

        from .models import Job
        from .seed import seed

        with Session(get_engine()) as s:
            if not s.exec(select(Job)).first():
                seed(s)
                log.info("seeded demo data")
    yield


def create_app() -> FastAPI:
    st = get_settings()
    base = st.base
    app = FastAPI(title="Jobbr", version=__version__, lifespan=lifespan,
                  docs_url=f"{base}/api/docs", openapi_url=f"{base}/api/openapi.json", redoc_url=None)

    @app.get("/healthz", include_in_schema=False)
    def healthz():
        return {"ok": True}

    # API lives under the mount path so an ingress can route /jobbr/* without rewriting.
    app.include_router(router, prefix=base)

    static = Path(st.static_dir)
    if static.is_dir():
        assets = static / "assets"
        if assets.is_dir():
            app.mount(f"{base}/assets", StaticFiles(directory=assets), name="assets")

        @app.get(base + "/{path:path}", include_in_schema=False)
        def spa(path: str):
            if path.startswith("api/"):
                raise HTTPException(404)
            f = (static / path).resolve()
            if path and f.is_file() and static.resolve() in f.parents:
                return FileResponse(f)
            return FileResponse(static / "index.html", headers={"Cache-Control": "no-cache"})

    if base:
        @app.get("/", include_in_schema=False)
        def root():
            return RedirectResponse(base + "/")

    @app.exception_handler(Exception)
    async def unhandled(_, exc: Exception):
        log.exception("unhandled", exc_info=exc)
        return JSONResponse({"detail": "Internal error"}, status_code=500)

    return app


app = create_app()
