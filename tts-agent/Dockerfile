# Базовый образ на Linux (Ubuntu/Debian)
FROM python:3.10-slim

# Устанавливаем curl (для скачивания) и espeak-ng (системная зависимость для TTS)
RUN apt-get update && apt-get install -y \
    curl \
    espeak-ng \
    libespeak-ng-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Копируем зависимости и устанавливаем их
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Скачиваем модели ПРЯМО ВНУТРИ Dockerfile (проблема CRLF больше не страшна)
RUN curl -L -o ru_RU-ruslan-medium.onnx https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/ru/ru_RU/ruslan/medium/ru_RU-ruslan-medium.onnx && \
    curl -L -o ru_RU-ruslan-medium.onnx.json https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/ru/ru_RU/ruslan/medium/ru_RU-ruslan-medium.onnx.json

# Копируем код приложения
COPY app.py .

# Открываем порт
EXPOSE 8000

# Команда запуска
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]