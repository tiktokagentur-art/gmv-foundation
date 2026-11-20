"""Aline's single FastAPI runtime: existing offline fixture and gated live dialogue."""
import hmac
import json
import logging
import os
from datetime import UTC, datetime
from typing import Literal

import live_runtime
from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field
from worker import WORKER_ID, Analysis, Snapshot, assert_pilot_fixture, offline_demo


class _JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        data = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "event": record.getMessage(),
            "worker_id": WORKER_ID,
        }
        run_id = getattr(record, "run_id", None)
        if isinstance(run_id, str):
            data["run_id"] = run_id
        error_type = getattr(record, "error_type", None)
        if isinstance(error_type, str):
            data["error_type"] = error_type
        return json.dumps(data, ensure_ascii=False)


_handler = logging.StreamHandler()
_handler.setFormatter(_JsonLogFormatter())
logger = logging.getLogger("aline.api")
logger.handlers[:] = [_handler]
logger.propagate = False
logger.setLevel(logging.INFO)
GREETING = (
    "Hallo Aline, wie geht es dir heute? Bitte stelle dich kurz vor und "
    "bestätige deinen aktuellen Betriebsstatus."
)

app = FastAPI(
    title="Aline L1 pilot",
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


def require_ceo_token(
    x_ceo_token: str | None = Header(default=None, alias="X-CEO-Token"),
) -> None:
    """Keep the dialogue credential distinct from the old offline demo token."""
    expected = os.environ.get("ALINE_CEO_TOKEN", "")
    if len(expected) < 32:
        raise HTTPException(status_code=503, detail="dialogue authentication not configured")
    if x_ceo_token is None or not hmac.compare_digest(expected, x_ceo_token):
        raise HTTPException(status_code=401, detail="unauthorized")


class DialogRequest(BaseModel):
    message: str = Field(min_length=1, max_length=500)
    synthetic: Literal[True]


def _ceo_scope_ready() -> bool:
    return len(os.environ.get("ALINE_CEO_TOKEN", "")) >= 32


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "aline-openai-worker-l1"}


@app.get("/ready")
def ready() -> dict[str, str]:
    # Deployment readiness is a local gate; provider access is proved only by a live call.
    if not _ceo_scope_ready():
        raise HTTPException(status_code=503, detail="dialogue authentication not configured")
    okay, reason = live_runtime.readiness()
    if not okay:
        raise HTTPException(status_code=503, detail=reason)
    return {"status": "ready", "mode": "l1_live_pilot"}


@app.get("/v1/status")
def status(_auth: None = Depends(require_ceo_token)) -> dict:
    return live_runtime.get_status()


@app.post("/v1/dialog")
async def dialog(request: DialogRequest, _auth: None = Depends(require_ceo_token)) -> dict:
    if request.message != GREETING and os.environ.get("ALINE_CEO_DIALOG_APPROVED") != "true":
        raise HTTPException(status_code=403, detail="message outside approved synthetic corridor")
    try:
        result = await live_runtime.dialog(request.message)
    except live_runtime.RuntimeBusy:
        logger.warning("dialogue rejected", extra={"error_type": "RuntimeBusy"})
        raise HTTPException(status_code=409, detail="another run is active") from None
    except live_runtime.RuntimeUncertain:
        logger.error("dialogue outcome uncertain", extra={"error_type": "RuntimeUncertain"})
        raise HTTPException(
            status_code=502, detail="model outcome uncertain; pilot paused"
        ) from None
    except live_runtime.RuntimeBlocked as exc:
        logger.warning("dialogue blocked", extra={"error_type": "RuntimeBlocked"})
        raise HTTPException(status_code=503, detail=str(exc)) from None
    logger.info("dialogue succeeded", extra={"run_id": result.get("run_id")})
    return result


@app.post("/v1/stop")
def stop(_auth: None = Depends(require_ceo_token)) -> dict[str, str]:
    try:
        live_runtime.stop()
    except live_runtime.RuntimeBlocked as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from None
    logger.warning("pilot stopped by CEO")
    return {"status": "stopped", "worker_id": WORKER_ID}


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
