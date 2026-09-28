import asyncio
import base64
import logging
import re
from uuid import uuid4

from fastapi import APIRouter, WebSocket, WebSocketDisconnect


router = APIRouter(prefix="/api/connection", tags=["connection"])


def split_text_to_sentences(text: str) -> list[str]:
    """Split a text into sentence-sized TTS chunks."""
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [part.strip() for part in parts if part and part.strip()]


async def _emit_voice_pipeline(websocket: WebSocket, session_id: str, message):
    tts_service = websocket.app.state.tts_service
    text = (message.get("text") or "").strip()
    if not text:
        await websocket.send_json(
            {
                "type": "tts_chunk",                                                              
                "session_id": session_id,
                "text": "",
                "audio": "",
                "format": "pcm16",
                "sample_rate": tts_service.sample_rate,
                "channels": tts_service.channels,
                "bits_per_sample": tts_service.bits_per_sample,
            }
        )
        await websocket.send_json(
            {
                "type": "tts_done",
                "session_id": session_id,
                "text": "",
                "chunks_sent": 0,
            }
        )
        return

    await websocket.send_json(
        {
            "type": "asr_partial",
            "session_id": session_id,
            "text": f"[tts] распознаю реплику: {text}",
        }
    )

    await websocket.send_json(
        {
            "type": "llm_delta",
            "session_id": session_id,
            "text": "[tts] генерирую аудио-ответ",
        }
    )

    sentences = split_text_to_sentences(text)
    if not sentences:
        sentences = [text]

    for index, sentence in enumerate(sentences):
        audio_pcm = tts_service.synthesize_pcm(sentence)
        await websocket.send_json(
            {
                "type": "tts_chunk",
                "session_id": session_id,
                "chunk_index": index,
                "chunks_total": len(sentences),
                "text": sentence,
                "audio": base64.b64encode(audio_pcm).decode("ascii"),
                "format": "pcm16",
                "sample_rate": tts_service.sample_rate,
                "channels": tts_service.channels,
                "bits_per_sample": tts_service.bits_per_sample,
                "is_final": index == len(sentences) - 1,
            }
        )

    await websocket.send_json(
        {
            "type": "tts_done",
            "session_id": session_id,
            "text": text,
            "chunks_sent": len(sentences),
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
            "message": "voice pipeline is ready",
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
                asr_service = websocket.app.state.asr_service
                text = await asr_service.transcribe_pcm(
                    message.get("data", b""),
                    sample_rate=message.get("sample_rate", 16000),
                )
                await websocket.send_json(
                    {
                        "type": "asr_partial",
                        "session_id": session_id,
                        "text": text["text"],
                    }
                )
            elif message_type == "operator_text":
                asyncio.create_task(
                    _emit_voice_pipeline(websocket, session_id, message)
                )
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
