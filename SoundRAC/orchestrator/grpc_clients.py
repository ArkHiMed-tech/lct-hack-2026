import grpc
import asyncio
from typing import AsyncIterator, Optional
import sys
import os

# Добавляем путь к сгенерированным proto-файлам
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'proto'))

import asr_pb2
import asr_pb2_grpc
import rac_pb2
import rac_pb2_grpc
import tts_pb2
import tts_pb2_grpc


class ASRClient:
    def __init__(self, host: str):
        self.host = host
        self.channel = None
        self.stub = None
    
    async def connect(self):
        self.channel = grpc.aio.insecure_channel(self.host)
        self.stub = asr_pb2_grpc.ASRServiceStub(self.channel)
    
    async def close(self):
        if self.channel:
            await self.channel.close()
    
    def stream_recognize(self, session_id: str) -> 'ASRStream':
        return ASRStream(self.stub, session_id)


class ASRStream:
    """Обёртка над gRPC-стримом ASR"""
    def __init__(self, stub, session_id: str):
        self.stub = stub
        self.session_id = session_id
        self.request_queue: asyncio.Queue = asyncio.Queue()
        self.response_stream = None
        self._closed = False
    
    async def __aenter__(self):
        self.response_stream = self.stub.StreamRecognize(self._request_generator())
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
    
    async def _request_generator(self) -> AsyncIterator[asr_pb2.AudioChunk]:
        while not self._closed:
            try:
                data = await asyncio.wait_for(self.request_queue.get(), timeout=1.0)
                yield asr_pb2.AudioChunk(
                    data=data,
                    sample_rate=16000,
                    session_id=self.session_id
                )
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
    
    async def write(self, audio_data: bytes):
        await self.request_queue.put(audio_data)
    
    async def read(self) -> AsyncIterator[asr_pb2.Transcript]:
        async for response in self.response_stream:
            yield response
    
    async def close(self):
        self._closed = True


class RACClient:
    def __init__(self, host: str):
        self.host = host
        self.channel = None
        self.stub = None
    
    async def connect(self):
        self.channel = grpc.aio.insecure_channel(self.host)
        self.stub = rac_pb2_grpc.RACServiceStub(self.channel)
    
    async def close(self):
        if self.channel:
            await self.channel.close()
    
    async def process(self, text: str, session_id: str) -> rac_pb2.DialogResponse:
        request = rac_pb2.DialogRequest(text=text, session_id=session_id)
        return await self.stub.Process(request)


class TTSClient:
    def __init__(self, host: str):
        self.host = host
        self.channel = None
        self.stub = None
    
    async def connect(self):
        self.channel = grpc.aio.insecure_channel(self.host)
        self.stub = tts_pb2_grpc.TTSServiceStub(self.channel)
    
    async def close(self):
        if self.channel:
            await self.channel.close()
    
    async def synthesize(self, text: str, session_id: str, speaker: str = "xenia") -> AsyncIterator[tts_pb2.AudioChunk]:
        request = tts_pb2.SynthesisRequest(
            text=text,
            speaker=speaker,
            sample_rate=24000,
            session_id=session_id
        )
        async for chunk in self.stub.Synthesize(request):
            yield chunk