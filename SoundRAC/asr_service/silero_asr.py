import torch
import numpy as np
from typing import Optional


class SileroVAD:
    """Voice Activity Detection от Silero"""
    def __init__(self):
        self.model, self.utils = torch.hub.load(
            repo_or_dir='snakers4/silero-vad',
            model='silero_vad',
            force_reload=False
        )
        self.model.eval()
        self.reset_states()
    
    def reset_states(self):
        self._h = torch.zeros(2, 1, 64)
        self._c = torch.zeros(2, 1, 64)
    
    def __call__(self, audio: np.ndarray, sample_rate: int = 16000) -> bool:
        """
        Проверяет, есть ли речь в аудио.
        audio: numpy array float32, shape (N,)
        """
        if sample_rate != 16000:
            raise ValueError("Silero VAD requires 16kHz audio")
        
        # Silero VAD требует чанки по 512 сэмплов (32 мс)
        if len(audio) < 512:
            audio = np.pad(audio, (0, 512 - len(audio)))
        
        tensor = torch.from_numpy(audio).float()
        if tensor.dim() == 1:
            tensor = tensor.unsqueeze(0)
        
        with torch.no_grad():
            speech_prob, self._h, self._c = self.model(tensor, self._h, self._c)
        
        return speech_prob.item() > 0.5


class SileroASR:
    """Speech-to-Text от Silero"""
    def __init__(self, language: str = 'ru'):
        self.device = torch.device('cpu')
        self.model = torch.hub.load(
            repo_or_dir='snakers4/silero-models',
            model='silero_stt',
            language=language,
            device=self.device
        )
        self.model.eval()
    
    def __call__(self, audio: np.ndarray, sample_rate: int = 16000) -> str:
        """
        Распознаёт речь из аудио.
        audio: numpy array float32, shape (N,)
        """
        if sample_rate != 16000:
            raise ValueError("Silero ASR requires 16kHz audio")
        
        tensor = torch.from_numpy(audio).float()
        
        with torch.no_grad():
            text = self.model.apply_asr(tensor)
        
        return text if isinstance(text, str) else text[0] if text else ""