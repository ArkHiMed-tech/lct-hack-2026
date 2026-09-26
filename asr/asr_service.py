from faster_whisper import WhisperModel
import numpy as np
from typing import Optional

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
        """
        Инициализация модели.
        
        Args:
            model_size: Размер модели (tiny, base, small, medium, large-v2)
            device: Устройство (cpu или cuda)
            compute_type: Тип вычислений (int8 для CPU, float16 для GPU)
            language: Язык распознавания (ru, en, и т.д.)
        """
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

def get_asr_service() -> ASRService:
    """Получить экземпляр ASR сервиса (singleton)."""
    global _asr_instance
    if _asr_instance is None:
        _asr_instance = ASRService()
    return _asr_instance

def transcribe_audio(pcm_data: bytes, **kwargs) -> dict:
    """
    Удобная функция для распознавания речи.
    
    Args:
        pcm_data: Сырые PCM-данные (bytes)
        **kwargs: Дополнительные параметры (sample_rate, channels, sample_width)
        
    Returns:
        dict с результатами распознавания
    """
    service = get_asr_service()
    return service.transcribe_pcm(pcm_data, **kwargs)


# Пример использования (если запускаешь напрямую)
if __name__ == "__main__":
    # Тестовый пример с файлом
    with open("test_audio.pcm", "rb") as f:
        pcm_data = f.read()
    
    result = transcribe_audio(pcm_data, sample_rate=16000)
    print(f"Распознанный текст: {result['text']}")
    print(f"Язык: {result['language']} (уверенность: {result['language_probability']:.2%})")