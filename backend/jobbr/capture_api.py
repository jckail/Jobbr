"""Thin routes for owner-approved extension capture, separate from website authority."""

import re
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Path, Request
from fastapi.responses import Response
from sqlmodel import Session

from . import canonical_repo, services
from . import capture_services as captures
from .auth import SESSION_COOKIE, AuthService, require_csrf, require_session
from .capture_schemas import ApproveIn, CaptureIn, ExchangeIn
from .db import get_session

router = APIRouter(prefix="/api/extension", tags=["extension"])
SessionDep = Annotated[Session, Depends(get_session)]
ExtensionPath = Annotated[str, Path(min_length=32, max_length=32, pattern=r"^[a-p]{32}$")]
OpaquePath = Annotated[str, Path(min_length=43, max_length=43, pattern=r"^[A-Za-z0-9_-]{43}$")]
ExtensionHeader = Annotated[
    str, Header(alias="X-Jobbr-Extension-ID", min_length=32, max_length=32, pattern=r"^[a-p]{32}$")
]


def _auth(request: Request) -> AuthService:
    return request.app.state.auth  # type: ignore[no-any-return]


def _token(authorization: str) -> str:
    match = re.fullmatch(r"Bearer ([A-Za-z0-9_-]{43})", authorization)
    if match is None:
        raise HTTPException(401, "Use a capture-only extension authorization.")
    return match.group(1)


def _error(exc: captures.CaptureError) -> HTTPException:
    return HTTPException(exc.status, exc.detail)


@router.get("/pairings/{extension_id}/{challenge}", dependencies=[Depends(require_session)])
def pairing_detail(
    extension_id: ExtensionPath, challenge: OpaquePath, request: Request, s: SessionDep
) -> dict[str, Any]:
    try:
        return captures.pairing_detail(s, _auth(request), extension_id, challenge)
    except captures.CaptureError as exc:
        raise _error(exc) from exc


@router.post("/pairings", dependencies=[Depends(require_csrf)])
def approve_pairing(body: ApproveIn, request: Request, s: SessionDep) -> dict[str, Any]:
    try:
        return captures.approve(s, _auth(request), request.cookies.get(SESSION_COOKIE, ""), body)
    except captures.CaptureError as exc:
        raise _error(exc) from exc


@router.post("/exchange")
def exchange(body: ExchangeIn, request: Request, s: SessionDep) -> dict[str, Any]:
    try:
        return captures.exchange(s, _auth(request), body, request.headers.get("Origin", ""))
    except captures.CaptureError as exc:
        raise _error(exc) from exc


@router.post("/captures")
def capture(
    body: CaptureIn,
    request: Request,
    s: SessionDep,
    x_jobbr_extension_id: ExtensionHeader,
    authorization: Annotated[str, Header(max_length=60)],
    idempotency_key: Annotated[
        str, Header(min_length=43, max_length=43, pattern=r"^[A-Za-z0-9_-]{43}$")
    ],
    x_jobbr_ai_provider: Annotated[str | None, Header(max_length=20)] = None,
    x_jobbr_ai_model: Annotated[str | None, Header(max_length=200)] = None,
    x_jobbr_ai_enabled: Annotated[str | None, Header(max_length=5)] = None,
) -> dict[str, int]:
    try:
        return captures.capture(
            s,
            _auth(request),
            _token(authorization),
            x_jobbr_extension_id,
            request.headers.get("Origin", ""),
            idempotency_key,
            body,
            (x_jobbr_ai_provider, x_jobbr_ai_model, x_jobbr_ai_enabled),
        )
    except captures.CaptureError as exc:
        raise _error(exc) from exc
    except canonical_repo.CanonicalConflict as exc:
        headers = (
            {"Retry-After": str(max(1, min(300, exc.retry_after)))}
            if exc.retry_after is not None
            else None
        )
        raise HTTPException(409, str(exc), headers=headers) from exc
    except services.UserError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/disconnect", status_code=204)
def disconnect(
    request: Request,
    s: SessionDep,
    x_jobbr_extension_id: ExtensionHeader,
    authorization: Annotated[str, Header(max_length=60)],
) -> Response:
    try:
        captures.disconnect(
            s,
            _auth(request),
            _token(authorization),
            x_jobbr_extension_id,
            request.headers.get("Origin", ""),
        )
    except captures.CaptureError as exc:
        raise _error(exc) from exc
    return Response(status_code=204)


@router.get("/grants", dependencies=[Depends(require_session)])
def list_grants(request: Request, s: SessionDep) -> list[dict[str, Any]]:
    try:
        return captures.grants(s, _auth(request))
    except captures.CaptureError as exc:
        raise _error(exc) from exc


@router.post("/grants/{grant_id}/revoke", status_code=204, dependencies=[Depends(require_csrf)])
def revoke(grant_id: OpaquePath, request: Request, s: SessionDep) -> Response:
    try:
        captures.revoke(s, _auth(request), grant_id)
    except captures.CaptureError as exc:
        raise _error(exc) from exc
    return Response(status_code=204)


@router.options("/{path:path}")
def preflight(path: str, request: Request) -> Response:
    origin = request.headers.get("Origin", "")
    match = re.fullmatch(r"chrome-extension://([a-p]{32})", origin)
    if path not in {"exchange", "captures", "disconnect"} or match is None:
        raise HTTPException(403, "Unsupported extension preflight.")
    try:
        captures.extension_origin(origin, match.group(1))
    except captures.CaptureError as exc:
        raise _error(exc) from exc
    return Response(
        status_code=204,
        headers={
            "Access-Control-Allow-Origin": origin,
            "Vary": "Origin",
            "Cache-Control": "no-store",
            "Access-Control-Allow-Methods": "POST",
            "Access-Control-Allow-Headers": (
                "Content-Type,Authorization,X-Jobbr-Extension-ID,Idempotency-Key,"
                "X-Jobbr-AI-Provider,X-Jobbr-AI-Model,X-Jobbr-AI-Enabled"
            ),
        },
    )
