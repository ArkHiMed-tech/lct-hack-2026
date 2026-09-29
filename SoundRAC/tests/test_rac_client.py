"""
Тестовый клиент для проверки работы RAC-сервиса.
Запускайте в отдельном терминале, пока server.py работает.
"""
import grpc
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'rac_service', 'proto'))

import rac_pb2
import rac_pb2_grpc


def test_rac(text: str):
    """Отправляет запрос в RAC-сервис и печатает ответ"""
    channel = grpc.insecure_channel('localhost:50052')
    stub = rac_pb2_grpc.RACServiceStub(channel)
    
    request = rac_pb2.DialogRequest(text=text, session_id="test")
    response = stub.Process(request)
    
    print(f"\n{'='*60}")
    print(f"📥 Запрос:  {text}")
    print(f"📤 Ответ:   {response.answer}")
    print(f"🎯 Вопрос:  {response.matched_question}")
    print(f"📊 Точность: {response.confidence:.4f}")
    print(f"{'='*60}\n")


if __name__ == '__main__':
    # Тестовые запросы (попробуйте разные формулировки!)
    test_queries = [
        "Я нахожусь по адресу улица Ленина 10",
        "Меня зовут Иван Петров",
        "Здесь произошло ДТП",
        "Горит здание школы",
        "Нужна скорая помощь",
        "Пострадавших нет",
        "Я чувствую запах дыма в квартире",
    ]
    
    for query in test_queries:
        test_rac(query)