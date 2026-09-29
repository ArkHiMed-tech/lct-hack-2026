import asyncio
import numpy as np
from fastapi import WebSocket
from grpc_clients import ASRClient, RACClient, TTSClient
from audio_utils import resample_audio

class DialogSession:
    def __init__(
        self,
        session_id: str,
        websocket: WebSocket,
        asr_client: ASRClient,
        rac_client: RACClient,
        tts_client: TTSClient
    ):
        self.session_id = session_id
        self.ws = websocket
        self.asr_client = asr_client
        self.rac_client = rac_client
        self.tts_client = tts_client
        
        # Очереди для асинхронной передачи данных
        self.audio_in_queue = asyncio.Queue(maxsize=100)   # Аудио от клиента
        self.audio_out_queue = asyncio.Queue(maxsize=100)  # Аудио клиенту
        self.asr_stream = None
        self.is_speaking = False
        self.current_tts_task = None
    
    async def receive_audio_loop(self):
        """Получаем аудио от клиента и кладём в очередь"""
        try:
            while True:
                data = await self.ws.receive_bytes()
                await self.audio_in_queue.put(data)
        except Exception as e:
            print(f"Receive error: {e}")
    
    async def process_asr_stream(self):
        """Стримим аудио в ASR, получаем текст, отправляем в RAC, запускаем TTS"""
        async with self.asr_client.stream_recognize(self.session_id) as asr_stream:
            self.asr_stream = asr_stream
            
            while True:
                # Ждём аудио от клиента
                audio_chunk = await self.audio_in_queue.get()
                
                # Отправляем в ASR
                await asr_stream.write(audio_chunk)
                
                # Читаем ответы от ASR (неблокирующе)
                try:
                    async for transcript in asr_stream.read():
                        if transcript.is_final and transcript.text.strip():
                            # Запускаем обработку ответа в отдельной задаче
                            asyncio.create_task(
                                self.handle_final_transcript(transcript.text)
                            )
                except asyncio.CancelledError:
                    break
    
    async def handle_final_transcript(self, text: str):
        """Обработка финального текста от ASR"""
        print(f"[{self.session_id}] User said: {text}")
        
        # 1. Отправляем в RAC
        response = await self.rac_client.process(text, self.session_id)
        print(f"[{self.session_id}] RAC answer: {response.answer}")
        
        # 2. Запускаем TTS (прерываем предыдущий, если был)
        if self.current_tts_task and not self.current_tts_task.done():
            self.current_tts_task.cancel()
        
        self.current_tts_task = asyncio.create_task(
            self.synthesize_and_stream(response.answer)
        )
    
    async def synthesize_and_stream(self, text: str):
        """Стримим TTS → клиент"""
        self.is_speaking = True
        try:
            async for audio_chunk in self.tts_client.synthesize(text, self.session_id):
                # Ресемплинг 24kHz → 16kHz (для клиента)
                audio_np = np.frombuffer(audio_chunk.data, dtype=np.int16)
                audio_resampled = resample_audio(audio_np, 24000, 16000)
                
                # Отправляем клиенту
                await self.audio_out_queue.put(audio_resampled.tobytes())
                
                if audio_chunk.is_last:
                    break
        except asyncio.CancelledError:
            print(f"[{self.session_id}] TTS interrupted (barge-in)")
        finally:
            self.is_speaking = False
    
    async def send_audio_loop(self):
        """Отправляем аудио клиенту из очереди"""
        while True:
            audio_data = await self.audio_out_queue.get()
            await self.ws.send_bytes(audio_data)
    
    async def cleanup(self):
        """Очистка ресурсов при отключении"""
        if self.current_tts_task and not self.current_tts_task.done():
            self.current_tts_task.cancel()
        if self.asr_stream:
            await self.asr_stream.close()