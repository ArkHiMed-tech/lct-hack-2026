from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import numpy as np
from session import DialogSession
from grpc_clients import ASRClient, RACClient, TTSClient

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# gRPC клиенты (один на весь сервер)
asr_client = ASRClient("asr_service:50051")
rac_client = RACClient("rac_service:50052")
tts_client = TTSClient("tts_service:50053")

# Хранилище активных сессий
sessions: dict[str, DialogSession] = {}

@app.websocket("/ws/call/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await websocket.accept()
    
    # Создаём сессию
    session = DialogSession(
        session_id=session_id,
        websocket=websocket,
        asr_client=asr_client,
        rac_client=rac_client,
        tts_client=tts_client
    )
    sessions[session_id] = session
    
    try:
        # Запускаем параллельные задачи
        await asyncio.gather(
            session.receive_audio_loop(),      # Приём аудио от клиента
            session.process_asr_stream(),      # Обработка ASR
            session.send_audio_loop()          # Отправка аудио клиенту
        )
    except WebSocketDisconnect:
        print(f"Session {session_id} disconnected")
    finally:
        # Очищаем ресурсы
        await session.cleanup()
        sessions.pop(session_id, None)

@app.get("/health")
async def health():
    return {"status": "ok", "active_sessions": len(sessions)}