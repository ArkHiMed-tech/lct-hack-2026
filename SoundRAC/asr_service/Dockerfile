FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

COPY asr_service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY proto/ ./proto/

RUN python -m grpc_tools.protoc \
    -I./proto \
    --python_out=./proto \
    --grpc_python_out=./proto \
    ./proto/asr.proto ./proto/rac.proto ./proto/tts.proto

COPY asr_service/ .

CMD ["python", "server.py"]