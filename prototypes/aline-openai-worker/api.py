"""Authenticated, offline-only FastAPI adapter for the Aline L1 pilot.

This service deliberately makes zero model calls and performs no external writes.
"""
import hmac
import os
from typing import Literal

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel

from worker import Analysis, Snapshot, WORKER_ID, assert_pilot_fixture, offline_demo

app = FastAPI(
    title="Aline L1 offline pilot",
    version="0.1.0",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)


class OfflineAnalysisResponse(BaseModel):
    worker_id: str
    runtime_status: Literal["advisory_only_not_authoritative"]
    execution_mode: Literal["offline_deterministic_demo"]
    api_requests_made: Literal[0]
    writes_performed: Literal[0]
    snapshot_id: str
    synthetic_input: Literal[True]
    report: Analysis


def require_pilot_token(
    x_pilot_token: str | None = Header(default=None, alias="X-Pilot-Token"),
) -> None:
    """Fail closed until a long, separate staging secret is provided."""
    expected = os.environ.get("ALINE_PILOT_TOKEN", "")
    if len(expected) < 32:
        raise HTTPException(status_code=503, detail="pilot authentication not configured")
    if x_pilot_token is None or not hmac.compare_digest(expected, x_pilot_token):
        raise HTTPException(status_code=401, detail="unauthorized")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "aline-l1-offline-api"}


@app.get("/ready")
def ready() -> dict[str, str]:
    # Readiness is NOT a signal that the model, IAM or real sources are authorized.
    if len(os.environ.get("ALINE_PILOT_TOKEN", "")) < 32:
        raise HTTPException(status_code=503, detail="pilot authentication not configured")
    return {"status": "ready", "mode": "synthetic_offline_only"}


@app.post("/v1/offline-analysis", response_model=OfflineAnalysisResponse)
def offline_analysis(
    snapshot: Snapshot,
    _auth: None = Depends(require_pilot_token),
) -> OfflineAnalysisResponse:
    try:
        assert_pilot_fixture(snapshot)
    except RuntimeError:
        raise HTTPException(
            status_code=422,
            detail="only the bundled synthetic fixture is permitted",
        ) from None
    report = offline_demo(snapshot)
    return OfflineAnalysisResponse(
        worker_id=WORKER_ID,
        runtime_status="advisory_only_not_authoritative",
        execution_mode="offline_deterministic_demo",
        api_requests_made=0,
        writes_performed=0,
        snapshot_id=snapshot.snapshot_id,
        synthetic_input=True,
        report=report,
    )
