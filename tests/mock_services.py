"""
Mock-сервисы для тестирования orchestrator без реальных моделей.
Позволяют быстро тестировать всю систему.
"""
import asyncio
import numpy as np
from typing import AsyncIterator


class MockASRService:
    """Mock ASR: возвращает заранее записанные ответы"""
    def __init__(self, responses: list[str] = None):
        self.responses = responses or [
            "Где мой заказ?",
            "Какие часы работы?",
            "До свидания"
        ]
        self.response_index = 0
    
    async def StreamRecognize(self, request_iterator, context):
        """Имитирует стриминг ASR"""
        audio_buffer = b""
        
        async for chunk in request_iterator:
            audio_buffer += chunk.data
            
            # Каждые ~2 секунды аудио (32000 байт = 1 сек при 16kHz 16bit)
            if len(audio_buffer) >= 64000:
                # Возвращаем следующий ответ из списка
                if self.response_index < len(self.responses):
                    text = self.responses[self.response_index]
                    self.response_index += 1
                    
                    # Имитируем задержку распознавания
                    await asyncio.sleep(0.1)
                    
                    from proto import asr_pb2
                    yield asr_pb2.Transcript(
                        text=text,
                        is_final=True,
                        confidence=0.95
                    )
                
                audio_buffer = b""


class MockRACService:
    """Mock RAC: возвращает ответы на основе ключевых слов"""
    def __init__(self):
        self.responses = {
            "заказ": "Ваш заказ в пути, ожидайте завтра.",
            "часы": "Мы работаем с 9 до 18.",
            "до свидания": "Спасибо за звонок! Хорошего дня!",
            "привет": "Здравствуйте! Чем могу помочь?",
        }
    
    async def Process(self, request, context):
        """Имитирует обработку запроса"""
        await asyncio.sleep(0.05)  # Имитация задержки
        
        from proto import rac_pb2
        
        # Ищем ответ по ключевым словам
        text_lower = request.text.lower()
        answer = "Извините, не понял ваш вопрос."
        confidence = 0.3
        
        for keyword, response in self.responses.items():
            if keyword in text_lower:
                answer = response
                confidence = 0.95
                break
        
        return rac_pb2.DialogResponse(
            answer=answer,
            confidence=confidence,
            matched_question=request.text
        )


class MockTTSService:
    """Mock TTS: генерирует тишину вместо реального аудио"""
    async def Synthesize(self, request, context):
        """Имитирует стриминг TTS"""
        from proto import tts_pb2
        
        # Генерируем ~2 секунды тишины (48000 сэмплов при 24kHz)
        total_samples = 48000
        chunk_size = 4800  # 200 мс
        
        for i in range(0, total_samples, chunk_size):
            await asyncio.sleep(0.01)  # Имитация задержки генерации
            
            # Генерируем тишину (можно добавить тихий шум для реалистичности)
            audio = np.zeros(chunk_size, dtype=np.float32)
            audio_bytes = (audio * 32767).astype(np.int16).tobytes()
            
            yield tts_pb2.AudioChunk(
                data=audio_bytes,
                sample_rate=24000,
                is_last=(i + chunk_size >= total_samples)
            )