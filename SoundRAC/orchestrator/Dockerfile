FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

COPY orchestrator/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY proto/ ./proto/

RUN python -m grpc_tools.protoc \
    -I./proto \
    --python_out=./proto \
    --grpc_python_out=./proto \
    ./proto/asr.proto ./proto/rac.proto ./proto/tts.proto

COPY orchestrator/ .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]