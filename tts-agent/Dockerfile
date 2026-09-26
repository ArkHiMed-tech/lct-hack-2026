# Базовый образ на Linux (Ubuntu)
FROM python:3.10-slim

# Устанавливаем системные зависимости, которые нужны для TTS
RUN apt-get update && apt-get install -y \
    curl \
    espeak-ng \
    libespeak-ng-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Копируем зависимости и устанавливаем их
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем скрипт скачивания и скачиваем модели ВНУТРЬ образа
COPY download_models.sh .
RUN chmod +x download_models.sh && ./download_models.sh

# Копируем код приложения
COPY app.py .

# Открываем порт
EXPOSE 8000

# Команда запуска
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]