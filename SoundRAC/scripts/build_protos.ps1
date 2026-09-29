# scripts/build_protos.ps1
$protoDir = "proto"
$services = @("orchestrator", "asr_service", "rac_service", "tts_service")

Write-Host "Building gRPC proto files..." -ForegroundColor Cyan

foreach ($service in $services) {
    Write-Host "  Processing $service..."
    
    $outDir = Join-Path $service "proto"
    New-Item -ItemType Directory -Force -Path $outDir | Out-Null
    
    python -m grpc_tools.protoc `
        -I"$protoDir" `
        --python_out="$outDir" `
        --grpc_python_out="$outDir" `
        "$protoDir/asr.proto" "$protoDir/rac.proto" "$protoDir/tts.proto"
    
    # Создаём __init__.py для импорта
    New-Item -ItemType File -Force -Path (Join-Path $outDir "__init__.py") | Out-Null
}

Write-Host "Done!" -ForegroundColor Green