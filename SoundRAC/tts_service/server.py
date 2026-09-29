import grpc
from concurrent import futures
import asyncio
import torch
import numpy as np
import tts_pb2
import tts_pb2_grpc
from silero_tts import SileroTTS

class TTSServicer(tts_pb2_grpc.TTSServiceServicer):
    def __init__(self):
        print("Loading Silero TTS model...")
        self.tts = SileroTTS()
        print("TTS ready.")
    
    async def Synthesize(self, request, context):
        # Silero TTS поддерживает стриминг
        sample_rate = request.sample_rate or 24000
        speaker = request.speaker or "xenia"
        
        # Генерируем аудио чанками
        audio_chunks = self.tts.synthesize_stream(
            text=request.text,
            speaker=speaker,
            sample_rate=sample_rate
        )
        
        for i, chunk in enumerate(audio_chunks):
            # Конвертируем в bytes
            audio_bytes = (chunk * 32767).astype(np.int16).tobytes()
            
            yield tts_pb2.AudioChunk(
                data=audio_bytes,
                sample_rate=sample_rate,
                is_last=(i == len(audio_chunks) - 1)
            )

async def serve():
    server = grpc.aio.server(futures.ThreadPoolExecutor(max_workers=4))
    tts_pb2_grpc.add_TTSServiceServicer_to_server(TTSServicer(), server)
    server.add_insecure_port('[::]:50053')
    await server.start()
    print("TTS service started on port 50053")
    await server.wait_for_termination()

if __name__ == '__main__':
    asyncio.run(serve())