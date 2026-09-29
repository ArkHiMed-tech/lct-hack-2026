#!/usr/bin/env python3
"""
Подготовка FAISS индекса из базы знаний.
Использует mock-данные для тестирования.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'rac_service'))

import json
import numpy as np
from embedder import Embedder
from faiss_store import FAISSStore


def load_mock_knowledge_base() -> list[dict]:
    """Загружает mock базу знаний для тестирования"""
    mock_path = os.path.join(os.path.dirname(__file__), '..', 'rac_service', 'knowledge_base.json')
    
    if os.path.exists(mock_path):
        with open(mock_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    # Если файла нет — создаём тестовые данные
    mock_data = [
        {
            "question": "Здравствуйте",
            "answer": "Здравствуйте! Чем могу помочь?"
        },
        {
            "question": "Где мой заказ?",
            "answer": "Чтобы узнать статус заказа, назовите, пожалуйста, номер заказа."
        },
        {
            "question": "Как отследить посылку?",
            "answer": "Введите номер заказа на сайте в разделе 'Статус заказа'."
        },
        {
            "question": "Какие у вас часы работы?",
            "answer": "Мы работаем с 9 утра до 6 вечера, без выходных."
        },
        {
            "question": "Как вернуть товар?",
            "answer": "Вы можете вернуть товар в течение 14 дней. Обратитесь в службу поддержки по номеру 8-800-555-35-35."
        },
        {
            "question": "Сколько стоит доставка?",
            "answer": "Доставка бесплатная при заказе от 3000 рублей. В остальных случаях — 300 рублей."
        },
        {
            "question": "Хочу поговорить с оператором",
            "answer": "Соединяю вас с оператором. Пожалуйста, оставайтесь на линии."
        },
        {
            "question": "Какие способы оплаты вы принимаете?",
            "answer": "Мы принимаем банковские карты, электронные кошельки и наличные при получении."
        },
        {
            "question": "У вас есть скидки?",
            "answer": "Да! При первом заказе — скидка 10%. Для постоянных клиентов действует накопительная система."
        },
        {
            "question": "До свидания",
            "answer": "Спасибо за звонок! Хорошего дня!"
        }
    ]
    
    # Сохраняем для повторного использования
    with open(mock_path, 'w', encoding='utf-8') as f:
        json.dump(mock_data, f, ensure_ascii=False, indent=2)
    
    return mock_data


def main():
    print("=" * 60)
    print("Подготовка базы знаний для RAC-сервиса")
    print("=" * 60)
    
    # 1. Загружаем базу знаний
    print("\n[1/3] Загрузка базы знаний...")
    kb = load_mock_knowledge_base()
    print(f"  Загружено {len(kb)} записей")
    
    # 2. Векторизуем вопросы
    print("\n[2/3] Векторизация вопросов (это займёт время при первом запуске)...")
    embedder = Embedder()
    questions = [entry['question'] for entry in kb]
    vectors = embedder.encode(questions)
    print(f"  Векторы созданы: shape {vectors.shape}")
    
    # 3. Создаём FAISS индекс
    print("\n[3/3] Создание FAISS индекса...")
    store = FAISSStore(dimension=embedder.dimension)
    store.add(vectors, kb)
    
    # Сохраняем
    index_path = os.path.join(os.path.dirname(__file__), '..', 'rac_service', 'knowledge_base.index')
    kb_path = os.path.join(os.path.dirname(__file__), '..', 'rac_service', 'knowledge_base.json')
    store.save(index_path, kb_path)
    
    print(f"\n✅ Готово!")
    print(f"  Индекс: {index_path}")
    print(f"  База знаний: {kb_path}")
    print(f"  Векторов: {store.index.ntotal}")


if __name__ == '__main__':
    main()