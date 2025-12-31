"""
RTL-SDR tuner API router.
"""
from typing import Optional

from fastapi import APIRouter, HTTPException, Header, Request

from app.models import TuneRequest, TunerStatus
from app.services.tuner_lock import TunerMode

router = APIRouter()


@router.get("/status", response_model=TunerStatus)
async def get_tuner_status(request: Request):
    """Get current tuner status."""
    service = request.app.state.tuner_service
    return service.get_status()


@router.post("/tune")
async def tune(
    tune_req: TuneRequest,
    request: Request,
    x_client_id: Optional[str] = Header(default="frontend", alias="X-Client-ID"),
    x_force_takeover: Optional[bool] = Header(default=False, alias="X-Force-Takeover"),
):
    """
    Tune to a specific frequency.

    Headers:
        X-Client-ID: Identifier for this client (default: "frontend")
        X-Force-Takeover: If true, forcibly take over from another client
    """
    tuner_lock = request.app.state.tuner_lock
    service = request.app.state.tuner_service

    # Acquire tuner lock
    success, result = await tuner_lock.acquire(
        client_id=x_client_id,
        mode=TunerMode.FM,
        force=x_force_takeover,
    )

    if not success:
        raise HTTPException(
            status_code=409,
            detail=f"Tuner conflict: {result}",
        )

    session_id = result

    tune_success = await service.tune(
        frequency=tune_req.frequency,
        modulation=tune_req.modulation,
        gain=tune_req.gain,
        squelch=tune_req.squelch,
    )

    if not tune_success:
        # Release lock on failure
        await tuner_lock.release(x_client_id, session_id)
        raise HTTPException(
            status_code=500,
            detail="Failed to tune. Check that RTL-SDR device is connected.",
        )

    return {
        "message": f"Tuned to {tune_req.frequency} MHz",
        "frequency": tune_req.frequency,
        "modulation": tune_req.modulation.value,
        "session_id": session_id,
    }


@router.post("/stop")
async def stop_tuner(
    request: Request,
    x_client_id: Optional[str] = Header(default="frontend", alias="X-Client-ID"),
):
    """Stop the tuner and release the lock."""
    tuner_lock = request.app.state.tuner_lock
    service = request.app.state.tuner_service

    await service.stop()
    await tuner_lock.release(x_client_id)

    return {"message": "Tuner stopped"}
