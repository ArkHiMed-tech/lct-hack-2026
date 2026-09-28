import pypiper as piper
import math
import logging
from pathlib import Path
import wave
import io

logger = logging.getLogger(__name__)

class TTSService:
    def __init__(self):
        self.voice = None
        self.model_loaded = False
        self.sample_rate = 22050
        self.channels = 1
        self.bits_per_sample = 16
        self._load_model()

    def _load_model(self):
        base_dir = Path(__file__).resolve().parents[1]
        candidates = [
            base_dir / "tts-agent" / "ru_RU-ruslan-medium.onnx",
            base_dir / "ru_RU-ruslan-medium.onnx",
            base_dir / "models" / "ru_RU-ruslan-medium.onnx",
        ]

        for model_path in candidates:
            config_path = model_path.with_suffix(".onnx.json")
            if not model_path.exists() or not config_path.exists():
                continue

            try:
                self.voice = piper.PiperVoice.load(str(model_path), str(config_path))
                self.model_loaded = True
                logger.info("TTS model loaded from %s", model_path)
                return
            except Exception as exc:  # pragma: no cover - runtime model format issues
                logger.warning("Failed to load TTS model %s: %s", model_path, exc)

        logger.warning(
            "No TTS model file found; websocket will emit generated PCM fallback audio."
        )

    def synthesize_pcm(self, text: str) -> bytes:
        clean_text = (text or "").strip()
        if not clean_text:
            return b""

        if self.voice is not None:
            wav_buffer = io.BytesIO()
            try:
                with wave.open(wav_buffer, "wb") as wav_file:
                    wav_file.setnchannels(self.channels)
                    wav_file.setsampwidth(self.bits_per_sample // 8)
                    wav_file.setframerate(self.sample_rate)
                    self.voice.synthesize(clean_text, wav_file)

                wav_buffer.seek(0)
                with wave.open(wav_buffer, "rb") as wav_reader:
                    return wav_reader.readframes(wav_reader.getnframes())
            except (
                Exception
            ) as exc:  # pragma: no cover - fallback if Piper crashes during synthesis
                logger.warning(
                    "Real TTS synth failed, falling back to generated PCM: %s", exc
                )

        return self._generate_fallback_pcm(clean_text)

    def _generate_fallback_pcm(self, text: str) -> bytes:
        duration_seconds = max(0.6, 0.07 * max(1, len(text.split())))
        frame_count = int(self.sample_rate * duration_seconds)
        amplitude = 2400
        pcm = bytearray()

        for i in range(frame_count):
            frequency = 180 + (i % 45) * 2
            value = int(
                math.sin(2 * math.pi * frequency * i / self.sample_rate) * amplitude
            )
            pcm.extend(value.to_bytes(2, byteorder="little", signed=True))

        return bytes(pcm)