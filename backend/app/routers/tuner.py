"""
RTL-SDR tuner API router.
"""
from fastapi import APIRouter, HTTPException, Request

from app.models import TuneRequest, TunerStatus

router = APIRouter()


@router.get("/status", response_model=TunerStatus)
async def get_tuner_status(request: Request):
    """Get current tuner status."""
    service = request.app.state.tuner_service
    return service.get_status()


@router.post("/tune")
async def tune(tune_req: TuneRequest, request: Request):
    """Tune to a specific frequency."""
    service = request.app.state.tuner_service
    
    success = await service.tune(
        frequency=tune_req.frequency,
        modulation=tune_req.modulation,
        gain=tune_req.gain,
        squelch=tune_req.squelch,
    )
    
    if not success:
        raise HTTPException(
            status_code=500,
            detail="Failed to tune. Check that RTL-SDR device is connected.",
        )
    
    return {
        "message": f"Tuned to {tune_req.frequency} MHz",
        "frequency": tune_req.frequency,
        "modulation": tune_req.modulation.value,
    }


@router.post("/stop")
async def stop_tuner(request: Request):
    """Stop the tuner."""
    service = request.app.state.tuner_service
    await service.stop()
    return {"message": "Tuner stopped"}
