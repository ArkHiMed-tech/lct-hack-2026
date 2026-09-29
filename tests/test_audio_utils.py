import pytest
import numpy as np
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'orchestrator'))

from audio_utils import (
    resample_audio,
    pcm_int16_to_float32,
    float32_to_pcm_int16,
    SimpleVAD,
    split_into_sentences
)


class TestAudioConversion:
    def test_pcm_int16_to_float32(self):
        # Создаём тестовые данные
        pcm_bytes = np.array([0, 16384, -16384, 32767, -32768], dtype=np.int16).tobytes()
        result = pcm_int16_to_float32(pcm_bytes)
        
        assert result.dtype == np.float32
        assert len(result) == 5
        assert abs(result[0]) < 0.01  # 0 → ~0.0
        assert abs(result[1] - 0.5) < 0.01  # 16384 → ~0.5
        assert abs(result[3] - 1.0) < 0.01  # 32767 → ~1.0
    
    def test_float32_to_pcm_int16(self):
        audio = np.array([0.0, 0.5, -0.5, 1.0, -1.0], dtype=np.float32)
        result_bytes = float32_to_pcm_int16(audio)
        result = np.frombuffer(result_bytes, dtype=np.int16)
        
        assert len(result) == 5
        assert result[0] == 0
        assert abs(result[1] - 16383) < 10
        assert abs(result[3] - 32767) < 10
    
    def test_roundtrip_conversion(self):
        """Проверяем, что конвертация туда-обратно не теряет данные"""
        original = np.array([0.0, 0.25, -0.25, 0.75, -0.75], dtype=np.float32)
        pcm_bytes = float32_to_pcm_int16(original)
        restored = pcm_int16_to_float32(pcm_bytes)
        
        np.testing.assert_allclose(original, restored, atol=0.001)


class TestResample:
    def test_resample_same_rate(self):
        audio = np.array([1, 2, 3, 4, 5], dtype=np.float32)
        result = resample_audio(audio, 16000, 16000)
        np.testing.assert_array_equal(audio, result)
    
    def test_resample_upsample(self):
        audio = np.array([0, 1, 0, -1], dtype=np.float32)
        result = resample_audio(audio, 16000, 32000)
        assert len(result) == 8  # В 2 раза больше
    
    def test_resample_downsample(self):
        audio = np.arange(100, dtype=np.float32)
        result = resample_audio(audio, 32000, 16000)
        assert len(result) == 50  # В 2 раза меньше


class TestVAD:
    def test_silence_not_speech(self):
        vad = SimpleVAD(threshold=0.01)
        silence = np.zeros(512, dtype=np.float32)
        assert vad.is_speech(silence) is False
    
    def test_loud_sound_is_speech(self):
        vad = SimpleVAD(threshold=0.01)
        loud = np.random.randn(512).astype(np.float32) * 0.5
        assert vad.is_speech(loud) is True


class TestSplitSentences:
    def test_single_sentence(self):
        text = "Привет, как дела?"
        result = split_into_sentences(text)
        assert result == ["Привет, как дела?"]
    
    def test_multiple_sentences(self):
        text = "Привет. Как дела? Хорошо!"
        result = split_into_sentences(text)
        assert len(result) == 3
        assert "Привет." in result
        assert "Как дела?" in result
        assert "Хорошо!" in result
    
    def test_empty_string(self):
        assert split_into_sentences("") == []
        assert split_into_sentences("   ") == []