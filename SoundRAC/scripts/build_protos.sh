#!/bin/bash
set -e

PROTO_DIR="proto"
SERVICES=("orchestrator" "asr_service" "rac_service" "tts_service")

echo "Building gRPC proto files..."

for service in "${SERVICES[@]}"; do
    echo "  Processing $service..."
    mkdir -p "$service/proto"
    
    python -m grpc_tools.protoc \
        -I"$PROTO_DIR" \
        --python_out="$service/proto" \
        --grpc_python_out="$service/proto" \
        "$PROTO_DIR"/*.proto
    
    # Добавляем __init__.py для импорта
    touch "$service/proto/__init__.py"
done

echo "Done!"