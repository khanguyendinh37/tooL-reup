"""License status/activation API and the gate for new processing jobs."""

from __future__ import annotations

import asyncio
import logging
import re

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.core.licensing import LicenseError, LicenseRejected, ProviderUnavailable, get_manager

logger = logging.getLogger(__name__)
router = APIRouter()

# Requests that start new work (download, dubbing, retry). Status, history and
# downloads of finished results stay available without a valid license, and
# jobs already accepted are allowed to finish.
GATED_ROUTES = re.compile(r"^/api/dubbing/(preview|start|[^/]+/retry)/?$")
REVALIDATE_INTERVAL_SECONDS = 30 * 60


class ActivateRequest(BaseModel):
    key: str = Field(..., min_length=1, max_length=256)


@router.get("/status")
async def license_status():
    return await asyncio.to_thread(get_manager().status)


@router.post("/activate")
async def activate_license(req: ActivateRequest):
    try:
        return await asyncio.to_thread(get_manager().activate, req.key)
    except ProviderUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except LicenseRejected as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except LicenseError as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/refresh")
async def refresh_license():
    return await asyncio.to_thread(get_manager().refresh)


async def license_gate_middleware(request: Request, call_next):
    if request.method == "POST" and GATED_ROUTES.match(request.url.path):
        manager = get_manager()
        if manager.enforced:
            status = await asyncio.to_thread(manager.refresh_if_due)
            if not status["allowed"]:
                return JSONResponse(
                    status_code=403,
                    content={"detail": manager.denial_message(status), "code": "license_required"},
                )
    return await call_next(request)


async def periodic_revalidation() -> None:
    """Re-validate online while the app is open (no-op when not enforced)."""
    manager = get_manager()
    if not manager.enforced:
        return
    while True:
        try:
            await asyncio.to_thread(manager.refresh_if_due)
        except Exception:
            logger.exception("Periodic license check failed")
        await asyncio.sleep(REVALIDATE_INTERVAL_SECONDS)
