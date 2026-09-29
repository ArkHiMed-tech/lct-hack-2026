FROM python:3.11-slim

WORKDIR /app

COPY rac_service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY proto/ ./proto/

RUN python -m grpc_tools.protoc \
    -I./proto \
    --python_out=./proto \
    --grpc_python_out=./proto \
    ./proto/asr.proto ./proto/rac.proto ./proto/tts.proto

COPY rac_service/knowledge_base.index ./knowledge_base.index
COPY rac_service/knowledge_base_processed.json ./knowledge_base.json

COPY rac_service/ .

CMD ["python", "server.py"]