class StreamingTTSPlayer {
    constructor() {
        this.audioContext = null;
        this.nextStartTime = 0;
        this.isPlaying = false;
    }

    async play(text) {
        // Инициализируем AudioContext (нужен пользовательский жест)
        if (!this.audioContext) {
            this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
        }

        // Возобновляем контекст, если он был приостановлен
        if (this.audioContext.state === 'suspended') {
            await this.audioContext.resume();
        }

        const response = await fetch(`/synthesize_stream?text=${encodeURIComponent(text)}`);
        
        if (!response.ok) {
            throw new Error(`Ошибка TTS: ${response.status}`);
        }

        // Читаем метаданные из заголовков
        const sampleRate = parseInt(response.headers.get('X-Audio-Sample-Rate') || '22050');
        const channels = parseInt(response.headers.get('X-Audio-Channels') || '1');
        const bitsPerSample = parseInt(response.headers.get('X-Audio-Bits') || '16');

        this.isPlaying = true;
        this.nextStartTime = this.audioContext.currentTime + 0.1; // Небольшой буфер для первого чанка

        const reader = response.body.getReader();
        
        try {
            while (this.isPlaying) {
                const { done, value } = await reader.read();
                
                if (done) break;
                
                // Декодируем и проигрываем чанк немедленно
                await this.playPCMChunk(value, sampleRate, channels, bitsPerSample);
            }
        } catch (error) {
            console.error('Ошибка стриминга:', error);
            throw error;
        }
    }

    async playPCMChunk(pcmData, sampleRate, channels, bitsPerSample) {
        // Конвертируем PCM в AudioBuffer
        const audioBuffer = this.audioContext.createBuffer(
            channels,
            pcmData.length / (channels * (bitsPerSample / 8)),
            sampleRate
        );

        // Заполняем каналы данными
        for (let channel = 0; channel < channels; channel++) {
            const channelData = audioBuffer.getChannelData(channel);
            
            for (let i = 0; i < channelData.length; i++) {
                // Читаем 16-bit PCM (little-endian)
                const offset = (i * channels + channel) * 2;
                const sample = pcmData[offset] | (pcmData[offset + 1] << 8);
                // Нормализуем в диапазон [-1, 1]
                channelData[i] = sample / 32768;
            }
        }

        // Создаем источник звука
        const source = this.audioContext.createBufferSource();
        source.buffer = audioBuffer;
        source.connect(this.audioContext.destination);

        // Планируем воспроизведение сразу после предыдущего чанка
        source.start(this.nextStartTime);
        
        // Обновляем время начала следующего чанка
        this.nextStartTime += audioBuffer.duration;
    }

    stop() {
        this.isPlaying = false;
        if (this.audioContext) {
            this.audioContext.close();
            this.audioContext = null;
        }
    }
}

// Использование:
const ttsPlayer = new StreamingTTSPlayer();

// Запуск по клику на кнопку (нужен пользовательский жест для AudioContext)
document.getElementById('playBtn').addEventListener('click', async () => {
    const text = document.getElementById('textInput').value;
    try {
        await ttsPlayer.play(text);
    } catch (error) {
        console.error('Ошибка:', error);
    }
});

// Остановка
document.getElementById('stopBtn').addEventListener('click', () => {
    ttsPlayer.stop();
});