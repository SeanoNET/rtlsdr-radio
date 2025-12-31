"""
Audio stream router - for direct browser playback (not Chromecast).
"""
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
import asyncio

router = APIRouter()


async def fm_audio_stream_generator(tuner_service):
    """Generate FM audio stream chunks."""
    while True:
        chunk = await tuner_service.read_audio_chunk(8192)
        if chunk:
            yield chunk
        else:
            await asyncio.sleep(0.01)
            # Check if tuner is still running
            if not tuner_service.is_running:
                break


async def dab_audio_stream_generator(dab_service):
    """Generate DAB+ audio stream chunks."""
    while True:
        chunk = await dab_service.read_audio_chunk(8192)
        if chunk:
            yield chunk
        else:
            await asyncio.sleep(0.01)
            # Check if DAB is still running
            if not dab_service.is_running:
                break


@router.get("/stream")
async def get_audio_stream(request: Request):
    """
    Get the raw audio stream.
    This endpoint can be used for direct browser playback or other clients.
    Automatically selects FM or DAB+ based on which is currently running.
    """
    tuner_service = request.app.state.tuner_service
    dab_service = request.app.state.dab_service

    # Check which service is running and stream from it
    if dab_service.is_running:
        return StreamingResponse(
            dab_audio_stream_generator(dab_service),
            media_type="audio/mpeg",
            headers={
                "Cache-Control": "no-cache, no-store",
                "Connection": "keep-alive",
            },
        )
    elif tuner_service.is_running:
        return StreamingResponse(
            fm_audio_stream_generator(tuner_service),
            media_type="audio/mpeg",
            headers={
                "Cache-Control": "no-cache, no-store",
                "Connection": "keep-alive",
            },
        )
    else:
        return {"error": "No tuner is running. Tune to a station first."}
