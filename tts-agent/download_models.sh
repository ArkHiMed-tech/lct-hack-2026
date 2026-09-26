#!/bin/bash
# Останавливаем скрипт при первой же ошибке
set -e 

echo "🚀 Начинаем скачивание модели Piper TTS (ruslan)..."

# Используем curl -L для обработки редиректов и -o для точного имени файла
# Путь исправлен на v1.0.0/ru/ru_RU/ruslan/medium/
curl -L -o ru_RU-ruslan-medium.onnx https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/ru/ru_RU/ruslan/medium/ru_RU-ruslan-medium.onnx
curl -L -o ru_RU-ruslan-medium.onnx.json https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/ru/ru_RU/ruslan/medium/ru_RU-ruslan-medium.onnx.json

echo "✅ Модель успешно скачана!"