from pathlib import Path
from typing import Optional
import asyncio

try:
    import numpy as np
except ImportError:  # опциональная зависимость
    np = None

try:
    from faster_whisper import WhisperModel
except ImportError:  # опциональная зависимость: без неё работает stub
    WhisperModel = None


class StubASRService:
    """Заглушка, когда faster-whisper не установлен: старт не падает."""

    language = "ru"

    async def transcribe_pcm(self, *args, **kwargs) -> dict:
        return {"text": "", "segments": [], "language": "ru",
                "language_probability": 0.0, "stub": True}

class ASRService:
    """
    Сервис для распознавания речи с использованием faster-whisper.
    Оптимизирован для работы на CPU.
    """
    
    def __init__(
        self,
        model_size: str = "medium",
        device: str = "cpu",
        compute_type: str = "int8",  # int8 для CPU (быстрее), float16 для GPU
        language: str = "ru"
    ):
        if WhisperModel is None:
            raise RuntimeError(
                "faster-whisper не установлен — поставьте requirements-stt.txt "
                "или используйте StubASRService"
            )
        if np is None:
            raise RuntimeError("numpy не установлен — нужен для ASR")
        print(f"Загрузка модели {model_size} на {device}...")
        self.model = WhisperModel(
            model_size, 
            device=device, 
            compute_type=compute_type
        )
        self.language = language
        print("Модель загружена!")
    
    def transcribe_pcm(
        self, 
        pcm_data: bytes,
        sample_rate: int = 16000,
        channels: int = 1,
        sample_width: int = 2  # 16-bit = 2 bytes
    ) -> dict:
        """
        Распознает речь из сырых PCM-данных.
        
        Args:
            pcm_data: Сырые PCM-данные (bytes)
            sample_rate: Частота дискретизации (обычно 16000 для Whisper)
            channels: Количество каналов (1 = mono, 2 = stereo)
            sample_width: Размер сэмпла в байтах (2 = 16-bit)
            
        Returns:
            dict с результатами:
            {
                "text": "полный текст",
                "segments": [список сегментов с таймкодами],
                "language": "ru",
                "language_probability": 0.99
            }
        """
        # Конвертируем PCM bytes в numpy array
        # Определяем тип данных в зависимости от sample_width
        if sample_width == 2:
            dtype = np.int16
        elif sample_width == 4:
            dtype = np.int32
        else:
            raise ValueError(f"Неподдерживаемый sample_width: {sample_width}")
        
        # Преобразуем bytes в numpy array
        audio_array = np.frombuffer(pcm_data, dtype=dtype)
        
        # Если стерео, конвертируем в моно (берем среднее)
        if channels == 2:
            audio_array = audio_array.reshape(-1, 2).mean(axis=1)
        
        # Нормализуем в float32 (Whisper ожидает float32 в диапазоне [-1, 1])
        audio_array = audio_array.astype(np.float32) / 32768.0  # для 16-bit
        
        # Распознаем речь
        segments, info = self.model.transcribe(
            audio_array,
            language=self.language,
            beam_size=5,  # Больше = точнее, но медленнее
            vad_filter=True,  # Фильтр тишины (ускоряет обработку)
            vad_parameters=dict(
                min_silence_duration_ms=500  # Минимальная пауза между словами
            )
        )
        
        # Собираем результаты
        result_segments = []
        full_text_parts = []
        
        for segment in segments:
            result_segments.append({
                "start": segment.start,
                "end": segment.end,
                "text": segment.text.strip()
            })
            full_text_parts.append(segment.text.strip())
        
        return {
            "text": " ".join(full_text_parts),
            "segments": result_segments,
            "language": info.language,
            "language_probability": info.language_probability
        }


# Singleton для переиспользования модели (загружается один раз)
_asr_instance: Optional[ASRService] = None

async def get_asr_service():
    """Получить экземпляр ASR сервиса (singleton).

    Тяжёлую модель НЕ грузим на старте без необходимости: если faster-whisper
    недоступен — возвращается stub, сервер продолжает работать (STT просто
    отдаёт пустой текст). Через env ``ASR_DISABLED=1`` — всегда stub.
    """
    import os

    global _asr_instance
    if _asr_instance is None:
        if os.getenv("ASR_DISABLED", "").strip().lower() in ("1", "true", "yes"):
            _asr_instance = StubASRService()
        elif WhisperModel is None:
            print("faster-whisper не установлен — ASR работает в stub-режиме.")
            _asr_instance = StubASRService()
        else:
            try:
                loop = asyncio.get_running_loop()
                _asr_instance = await loop.run_in_executor(None, ASRService)
            except Exception as exc:
                print(f"Не удалось загрузить ASR-модель ({exc}) — stub-режим.")
                _asr_instance = StubASRService()
    return _asr_instance

async def transcribe_audio(pcm_data: bytes, **kwargs) -> dict:
    """
    Удобная функция для распознавания речи.
    
    Args:
        pcm_data: Сырые PCM-данные (bytes)
        **kwargs: Дополнительные параметры (sample_rate, channels, sample_width)
        
    Returns:
        dict с результатами распознавания
    """
    service = await get_asr_service() # ОБРАТИТЬ ВНИМАНИЕ !!!
    return service.transcribe_pcm(pcm_data, **kwargs)

async def main():
    # Тестовый пример с файлом
    with open(Path(__file__).resolve().parent / "test_audio.pcm", "rb") as f:
        pcm_data = f.read()
    
    result = await transcribe_audio(pcm_data, sample_rate=16000)
    print(f"Распознанный текст: {result['text']}")
    print(f"Язык: {result['language']} (уверенность: {result['language_probability']:.2%})")


# Пример использования (если запускаешь напрямую)
if __name__ == "__main__":
    asyncio.run(main())