import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'orchestrator'))


class TestDialogSession:
    @pytest.fixture
    def mock_clients(self):
        """Создаёт mock gRPC клиенты"""
        asr_client = AsyncMock()
        rac_client = AsyncMock()
        tts_client = AsyncMock()
        
        # Mock RAC response
        rac_response = MagicMock()
        rac_response.answer = "Тестовый ответ"
        rac_response.confidence = 0.95
        rac_client.process.return_value = rac_response
        
        # Mock TTS stream
        async def mock_tts_stream(*args, **kwargs):
            chunk = MagicMock()
            chunk.data = b'\x00' * 1000
            chunk.is_last = True
            yield chunk
        
        tts_client.synthesize = mock_tts_stream
        
        return asr_client, rac_client, tts_client
    
    @pytest.mark.asyncio
    async def test_handle_final_transcript(self, mock_clients):
        """Проверяем обработку финального текста от ASR"""
        from session import DialogSession
        
        asr_client, rac_client, tts_client = mock_clients
        
        # Создаём mock WebSocket
        ws = AsyncMock()
        
        session = DialogSession(
            session_id="test_session",
            websocket=ws,
            asr_client=asr_client,
            rac_client=rac_client,
            tts_client=tts_client
        )
        
        # Обрабатываем текст
        await session.handle_final_transcript("Где мой заказ?")
        
        # Проверяем, что RAC был вызван
        rac_client.process.assert_called_once_with("Где мой заказ?", "test_session")
        
        # Проверяем, что TTS был запущен
        await asyncio.sleep(0.1)  # Даём время на выполнение задачи
        assert session.current_tts_task is not None