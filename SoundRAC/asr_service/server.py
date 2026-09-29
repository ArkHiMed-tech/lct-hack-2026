import grpc
from concurrent import futures
import asyncio
import numpy as np
import os
import sys

# Добавляем путь для импорта proto-файлов
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'proto'))

import asr_pb2
import asr_pb2_grpc
from silero_asr import SileroASR, SileroVAD


class ASRServicer(asr_pb2_grpc.ASRServiceServicer):
    def __init__(self):
        print("🔄 Initializing ASR service...")
        self.vad = SileroVAD()
        self.asr = SileroASR(language='ru')
        print("✅ ASR service ready.")
    
    async def StreamRecognize(self, request_iterator, context):
        """Стриминг аудио → стриминг текста"""
        audio_buffer = []
        speech_started = False
        silence_counter = 0
        
        async for chunk in request_iterator:
            # Конвертируем bytes → numpy array
            audio_np = np.frombuffer(chunk.data, dtype=np.int16).astype(np.float32) / 32768.0
            
            # VAD проверка
            is_speech = self.vad(audio_np)
            
            if is_speech:
                speech_started = True
                silence_counter = 0
                audio_buffer.append(audio_np)
            elif speech_started:
                # Пауза после речи
                silence_counter += 1
                
                # Если тишина длится достаточно долго (примерно 0.5 сек = 25 чанков по 20мс)
                if silence_counter > 25 and len(audio_buffer) > 0:
                    # Финализируем фразу
                    full_audio = np.concatenate(audio_buffer)
                    
                    # Распознаём речь
                    text = self.asr(full_audio)
                    
                    if text.strip():
                        yield asr_pb2.Transcript(
                            text=text,
                            is_final=True,
                            confidence=0.95
                        )
                    
                    # Сбрасываем буфер
                    audio_buffer = []
                    speech_started = False
                    silence_counter = 0


async def serve():
    server = grpc.aio.server(futures.ThreadPoolExecutor(max_workers=4))
    asr_pb2_grpc.add_ASRServiceServicer_to_server(ASRServicer(), server)
    server.add_insecure_port('[::]:50051')
    print("🚀 ASR service starting on port 50051...")
    await server.start()
    print("✅ ASR service is running!")
    await server.wait_for_termination()


if __name__ == '__main__':
    asyncio.run(serve())