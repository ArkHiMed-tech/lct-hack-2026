"""
Интеграционные тесты: проверяют взаимодействие всех компонентов.
Используют mock-сервисы вместо реальных моделей.
"""
import pytest
import asyncio
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'mock_services'))

from mock_services import MockASRService, MockRACService, MockTTSService


class TestMockServices:
    @pytest.mark.asyncio
    async def test_mock_rac_service(self):
        """Проверяем, что mock RAC возвращает правильные ответы"""
        from proto import rac_pb2
        
        service = MockRACService()
        
        # Тестовый запрос
        request = rac_pb2.DialogRequest(
            text="Где мой заказ?",
            session_id="test"
        )
        
        response = await service.Process(request, None)
        
        assert response.confidence > 0.9
        assert "заказ" in response.answer.lower() or "пути" in response.answer.lower()
    
    @pytest.mark.asyncio
    async def test_mock_tts_service(self):
        """Проверяем, что mock TTS стримит аудио"""
        from proto import tts_pb2
        
        service = MockTTSService()
        
        request = tts_pb2.SynthesisRequest(
            text="Тестовая фраза",
            speaker="xenia",
            sample_rate=24000,
            session_id="test"
        )
        
        chunks = []
        async for chunk in service.Synthesize(request, None):
            chunks.append(chunk)
        
        assert len(chunks) > 0
        assert chunks[-1].is_last is True
        assert all(chunk.sample_rate == 24000 for chunk in chunks)