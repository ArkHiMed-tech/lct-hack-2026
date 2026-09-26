import io
import re
import wave
import logging
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse
import piper

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Streaming TTS Agent")

tts_voice = None

def split_text_to_sentences(text: str) -> list[str]:
    """Разбивает текст на предложения для потокового синтеза."""
    sentences = re.split(r'(?<=[.!?])\s+', text)
    return [s.strip() for s in sentences if s.strip()]

@app.on_event("startup")
async def load_model():
    global tts_voice
    logger.info("Загрузка TTS модели...")
    model_path = "ru_RU-ruslan-medium.onnx"
    config_path = "ru_RU-ruslan-medium.onnx.json"
    tts_voice = piper.PiperVoice.load(model_path, config_path)
    logger.info("✅ Модель успешно загружена!")

@app.post("/synthesize")
async def synthesize_speech(text: str = Query(..., description="Текст для озвучивания")):
    """Обычный синтез всего текста целиком (для тестов)."""
    if not text or len(text.strip()) == 0:
        raise HTTPException(status_code=400, detail="Text cannot be empty")
    
    if len(text) > 1000:
        raise HTTPException(status_code=400, detail="Text is too long (max 1000 chars)")

    audio_stream = io.BytesIO()
    
    # ИСПРАВЛЕНО: используем synthesize вместо synthesize_wav
    with wave.open(audio_stream, 'wb') as wav_file:
        tts_voice.synthesize(text, wav_file)
        
    audio_stream.seek(0)
    
    return StreamingResponse(audio_stream, media_type="audio/wav", headers={
        "Content-Disposition": "attachment; filename=speech.wav"
    })

@app.post("/synthesize_stream")
async def synthesize_stream(text: str = Query(..., description="Текст для озвучивания")):
    """Потоковый синтез по предложениям для минимальной задержки."""
    if not text or len(text.strip()) == 0:
        raise HTTPException(status_code=400, detail="Text cannot be empty")
    
    if len(text) > 2000:
        raise HTTPException(status_code=400, detail="Text is too long (max 2000 chars)")

    sentences = split_text_to_sentences(text)
    if not sentences:
        raise HTTPException(status_code=400, detail="No sentences found")

    async def generate_audio_chunks():
        for i, sentence in enumerate(sentences):
            logger.info(f"Синтез предложения {i+1}/{len(sentences)}: '{sentence[:30]}...'")
            
            audio_stream = io.BytesIO()
            # ИСПРАВЛЕНО: используем synthesize
            with wave.open(audio_stream, 'wb') as wav_file:
                tts_voice.synthesize(sentence, wav_file)
            
            audio_stream.seek(0)
            yield audio_stream.read()

    return StreamingResponse(
        generate_audio_chunks(), 
        media_type="audio/wav",
        headers={
            "X-Content-Duration": "stream",
            "Cache-Control": "no-cache"
        }
    )

@app.get("/health")
async def health_check():
    return {"status": "ok", "model_loaded": tts_voice is not None}