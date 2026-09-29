import numpy as np
import math
from typing import Optional

def resample_audio(audio: np.ndarray, src_sr: int, dst_sr: int) -> np.ndarray:
    """
    Простой ресемплинг аудио через линейную интерполяцию.
    Для production лучше использовать librosa или soxr, но это добавит зависимости.
    """
    if src_sr == dst_sr:
        return audio
    
    ratio = dst_sr / src_sr
    n_samples = int(len(audio) * ratio)
    
    # Линейная интерполяция
    indices = np.linspace(0, len(audio) - 1, n_samples)
    resampled = np.interp(indices, np.arange(len(audio)), audio)
    return resampled.astype(audio.dtype)


def pcm_int16_to_float32(pcm_bytes: bytes) -> np.ndarray:
    """Конвертирует PCM Int16 bytes → Float32 numpy array [-1.0, 1.0]"""
    pcm_int16 = np.frombuffer(pcm_bytes, dtype=np.int16)
    return pcm_int16.astype(np.float32) / 32768.0


def float32_to_pcm_int16(audio: np.ndarray) -> bytes:
    """Конвертирует Float32 [-1.0, 1.0] → PCM Int16 bytes"""
    clipped = np.clip(audio, -1.0, 1.0)
    pcm_int16 = (clipped * 32767).astype(np.int16)
    return pcm_int16.tobytes()


class SimpleVAD:
    """
    Простейший VAD на основе энергии сигнала.
    Используется как fallback, если Silero VAD недоступен.
    """
    def __init__(self, threshold: float = 0.01, frame_size: int = 512):
        self.threshold = threshold
        self.frame_size = frame_size
    
    def is_speech(self, audio: np.ndarray) -> bool:
        """Проверяет, есть ли речь в аудио-чанке"""
        if len(audio) == 0:
            return False
        energy = np.sqrt(np.mean(audio ** 2))
        return energy > self.threshold


def split_into_sentences(text: str) -> list[str]:
    """Разбивает текст на предложения для TTS"""
    import re
    # Разделяем по точкам, восклицательным и вопросительным знакам
    sentences = re.split(r'(?<=[.!?])\s+', text)
    return [s.strip() for s in sentences if s.strip()]