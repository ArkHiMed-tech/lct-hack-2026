FROM python:3.11-slim

WORKDIR /app

# Копируем requirements и устанавливаем зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем сгенерированные proto-файлы
COPY proto/ ./proto/

# Копируем базу знаний и индекс
COPY knowledge_base.index ./knowledge_base.index
COPY knowledge_base_processed.json ./knowledge_base_processed.json

# Копируем остальной код
COPY . .

CMD ["python", "server.py"]