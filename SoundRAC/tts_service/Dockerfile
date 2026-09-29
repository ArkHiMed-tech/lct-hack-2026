FROM python:3.11-slim

WORKDIR /app

# Системные зависимости для аудио
RUN apt-get update && apt-get install -y \
    libsndfile1 \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Копируем requirements и устанавливаем зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем сгенерированные proto-файлы
COPY proto/ ./proto/

# Копируем остальной код
COPY . .

CMD ["python", "server.py"]