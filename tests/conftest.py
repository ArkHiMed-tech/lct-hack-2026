import pytest
import asyncio
import numpy as np
from unittest.mock import AsyncMock, MagicMock


@pytest.fixture
def event_loop():
    """Создаём event loop для async тестов"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def sample_audio():
    """Генерирует тестовое аудио (1 секунда тишины с шумом)"""
    np.random.seed(42)
    # 16000 сэмплов = 1 секунда при 16kHz
    audio = np.random.randn(16000).astype(np.float32) * 0.01
    return audio


@pytest.fixture
def sample_audio_bytes(sample_audio):
    """Тестовое аудио в формате PCM Int16 bytes"""
    pcm_int16 = (sample_audio * 32767).astype(np.int16)
    return pcm_int16.tobytes()