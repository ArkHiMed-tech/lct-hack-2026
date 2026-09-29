import torch
import numpy as np
from typing import Iterator


class SileroTTS:
    """Text-to-Speech от Silero"""
    def __init__(self):
        self.device = torch.device('cpu')
        self.model, _ = torch.hub.load(
            repo_or_dir='snakers4/silero-models',
            model='silero_tts',
            language='ru',
            speaker='ru_v3'
        )
        self.model.eval()
    
    def synthesize(self, text: str, speaker: str = 'xenia', sample_rate: int = 24000) -> np.ndarray:
        """
        Синтезирует речь из текста.
        Возвращает numpy array float32, shape (N,)
        """
        with torch.no_grad():
            audio = self.model.apply_tts(
                text=text,
                speaker=speaker,
                sample_rate=sample_rate
            )
        return audio.numpy()
    
    def synthesize_stream(self, text: str, speaker: str = 'xenia', 
                         sample_rate: int = 24000, chunk_size: int = 4800) -> Iterator[np.ndarray]:
        """
        Синтезирует речь и возвращает чанками (для стриминга).
        chunk_size: количество сэмплов в чанке (4800 = 200 мс при 24kHz)
        """
        full_audio = self.synthesize(text, speaker, sample_rate)
        
        # Разбиваем на чанки
        for i in range(0, len(full_audio), chunk_size):
            chunk = full_audio[i:i + chunk_size]
            yield chunk