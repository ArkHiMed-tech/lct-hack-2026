import asyncio
from uuid import uuid4

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from asr.asr_service import transcribe_audio

router = APIRouter(prefix="/api/connection", tags=["connection"])


async def _emit_voice_pipeline_stub(websocket: WebSocket, session_id: str, message):
    await websocket.send_json(
        {
            "type": "asr_partial",
            "session_id": session_id,
            "text": f"[stub] слышу вас, разбираю речь. Слышу: {message.get('text', 'ничего не слышу')}",
        }
    )
    await asyncio.sleep(0.25)

    await websocket.send_json(
        {
            "type": "llm_delta",
            "session_id": session_id,
            "text": "[stub] обработал запрос, генерирую ответ",
        }
    )
    await asyncio.sleep(0.25)

    await websocket.send_json(
        {
            "type": "tts_chunk",
            "session_id": session_id,
            "audio": "stub-audio-chunk",
            "format": "pcm16",
        }
    )


@router.websocket("/call")
async def voip_call(websocket: WebSocket):
    session_id = str(uuid4())
    await websocket.accept()
    await websocket.send_json(
        {
            "type": "ready",
            "status": "connected",
            "session_id": session_id,
            "message": "voice pipeline stub is ready",
        }
    )

    try:
        while True:
            message = await websocket.receive_json()
            print(f"Received message: {message['type']}")
            message_type = message.get("type")
            session_id = message.get("session_id") or session_id

            if message_type == "start":
                await websocket.send_json(
                    {
                        "type": "ack",
                        "status": "started",
                        "session_id": session_id,
                    }
                )
            elif message_type == "audio":
                text = await transcribe_audio(message.get('data', b''), sample_rate=message.get('sample_rate', 16000))
                await websocket.send_json({'type': 'asr_partial', 'session_id': session_id, 'text': text['text']})
            elif message_type == "operator_text":
                asyncio.create_task(_emit_voice_pipeline_stub(websocket, session_id, message))
            elif message_type in ["end", "stop"]:
                await websocket.send_json(
                    {
                        "type": "ack",
                        "status": "stopped",
                        "session_id": session_id,
                    }
                )
                break
            else:
                await websocket.send_json(
                    {
                        "type": "ack",
                        "status": "received",
                        "event_type": message_type,
                        "session_id": session_id,
                    }
                )
    except WebSocketDisconnect:
        return
