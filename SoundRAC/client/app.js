let ws = null;
let audioContext = null;
let mediaStream = null;
let processor = null;
let sessionId = null;
let nextPlayTime = 0;

async function startCall() {
    // Генерируем уникальный session_id
    sessionId = 'session_' + Date.now();
    
    // Запрашиваем доступ к микрофону
    mediaStream = await navigator.mediaDevices.getUserMedia({ 
        audio: { 
            sampleRate: 16000, 
            channelCount: 1,
            echoCancellation: true,
            noiseSuppression: true
        } 
    });
    
    // Создаём AudioContext для захвата микрофона
    audioContext = new AudioContext({ sampleRate: 16000 });
    const source = audioContext.createMediaStreamSource(mediaStream);
    
    // ScriptProcessorNode для получения PCM-чанков
    processor = audioContext.createScriptProcessor(4096, 1, 1);
    processor.onaudioprocess = (e) => {
        const inputData = e.inputBuffer.getChannelData(0);
        // Конвертируем Float32 → Int16
        const pcm16 = new Int16Array(inputData.length);
        for (let i = 0; i < inputData.length; i++) {
            pcm16[i] = Math.max(-32768, Math.min(32767, inputData[i] * 32767));
        }
        // Отправляем по WebSocket
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(pcm16.buffer);
        }
    };
    source.connect(processor);
    processor.connect(audioContext.destination);
    
    // Подключаемся к серверу
    ws = new WebSocket(`ws://${location.host}/ws/call/${sessionId}`);
    ws.binaryType = 'arraybuffer';
    
    ws.onopen = () => {
        document.getElementById('status').textContent = '🎤 Слушаю...';
        document.getElementById('status').className = 'listening';
        document.getElementById('startBtn').style.display = 'none';
        document.getElementById('stopBtn').style.display = 'inline-block';
    };
    
    ws.onmessage = (event) => {
        // Получили аудио от бота → проигрываем
        playAudio(event.data);
        document.getElementById('status').textContent = '🔊 Бот говорит...';
        document.getElementById('status').className = 'speaking';
    };
    
    ws.onclose = () => {
        document.getElementById('status').textContent = 'Звонок завершён';
        document.getElementById('status').className = 'idle';
        document.getElementById('startBtn').style.display = 'inline-block';
        document.getElementById('stopBtn').style.display = 'none';
    };
}

function playAudio(arrayBuffer) {
    // Конвертируем Int16 → Float32
    const int16Array = new Int16Array(arrayBuffer);
    const float32Array = new Float32Array(int16Array.length);
    for (let i = 0; i < int16Array.length; i++) {
        float32Array[i] = int16Array[i] / 32768.0;
    }
    
    // Создаём AudioBuffer
    const audioBuffer = audioContext.createBuffer(1, float32Array.length, 16000);
    audioBuffer.getChannelData(0).set(float32Array);
    
    // Проигрываем с учётом тайминга (избегаем наложений)
    const source = audioContext.createBufferSource();
    source.buffer = audioBuffer;
    source.connect(audioContext.destination);
    
    const currentTime = audioContext.currentTime;
    const startTime = Math.max(currentTime, nextPlayTime);
    source.start(startTime);
    nextPlayTime = startTime + audioBuffer.duration;
    
    // Возвращаем статус "Слушаю" после проигрывания
    setTimeout(() => {
        if (ws && ws.readyState === WebSocket.OPEN) {
            document.getElementById('status').textContent = '🎤 Слушаю...';
            document.getElementById('status').className = 'listening';
        }
    }, nextPlayTime * 1000 - Date.now());
}

function stopCall() {
    if (processor) processor.disconnect();
    if (mediaStream) mediaStream.getTracks().forEach(t => t.stop());
    if (audioContext) audioContext.close();
    if (ws) ws.close();
    
    document.getElementById('status').textContent = 'Звонок завершён';
    document.getElementById('status').className = 'idle';
    document.getElementById('startBtn').style.display = 'inline-block';
    document.getElementById('stopBtn').style.display = 'none';
}