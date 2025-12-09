"""
Audio stream router - for direct browser playback (not Chromecast).
"""
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
import asyncio

router = APIRouter()


async def audio_stream_generator(tuner_service):
    """Generate audio stream chunks."""
    while True:
        chunk = await tuner_service.read_audio_chunk(8192)
        if chunk:
            yield chunk
        else:
            await asyncio.sleep(0.01)
            # Check if tuner is still running
            if not tuner_service.is_running:
                break


@router.get("/stream")
async def get_audio_stream(request: Request):
    """
    Get the raw audio stream.
    This endpoint can be used for direct browser playback or other clients.
    """
    tuner_service = request.app.state.tuner_service
    
    if not tuner_service.is_running:
        return {"error": "Tuner is not running. Tune to a frequency first."}
    
    return StreamingResponse(
        audio_stream_generator(tuner_service),
        media_type="audio/mpeg",
        headers={
            "Cache-Control": "no-cache, no-store",
            "Connection": "keep-alive",
        },
    )
