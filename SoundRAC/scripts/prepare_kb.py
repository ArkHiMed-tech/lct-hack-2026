#!/usr/bin/env python3
"""
Подготовка FAISS индекса из базы знаний (адаптировано под формат шаблонов 112).
"""
import sys
import os

# Добавляем путь к rac_service для импорта
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'rac_service'))

import json
import numpy as np
from embedder import Embedder
from faiss_store import FAISSStore


def load_and_transform_knowledge_base() -> list[dict]:
    """Загружает JSON с шаблонами и преобразует его в формат для FAISS"""
    kb_path = os.path.join(os.path.dirname(__file__), '..', 'rac_service', 'knowledge_base.json')
    
    if not os.path.exists(kb_path):
        raise FileNotFoundError(f"Файл не найден: {kb_path}")
    
    with open(kb_path, 'r', encoding='utf-8') as f:
        raw_kb = json.load(f)
    
    if not isinstance(raw_kb, dict):
        raise ValueError("Ожидался JSON-объект (словарь) с категориями интентов.")
    
    transformed_kb = []
    
    for intent, templates in raw_kb.items():
        # Убираем лишние пробелы в названиях категорий (например, "caller_name " -> "caller_name")
        clean_intent = intent.strip()
        
        if not isinstance(templates, list):
            continue
            
        for template in templates:
            # Для качественной векторизации заменяем {text} на нейтральное слово, 
            # чтобы предложение было семантически полным для эмбеддера.
            question_for_embedding = template.replace("{text}", "[данные]").strip()
            
            # Формируем ответ. Пока сделаем универсальное подтверждение категории.
            # В будущем здесь можно настроить логику: "Принято, ваше имя: [данные]. Что случилось?"
            answer = f"Принято, категория: {clean_intent}. Продолжайте."
            
            transformed_kb.append({
                "intent": clean_intent,
                "question": question_for_embedding,
                "answer": answer,
                "original_template": template.strip()
            })
            
    print(f"  Преобразовано {len(transformed_kb)} шаблонов из {len(raw_kb)} категорий.")
    return transformed_kb


def main():
    print("=" * 60)
    print("Подготовка базы знаний для RAC-сервиса (Формат 112)")
    print("=" * 60)
    
    # 1. Загружаем и преобразуем базу знаний
    print("\n[1/3] Загрузка и преобразование базы знаний...")
    kb = load_and_transform_knowledge_base()
    
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
    
    # ВАЖНО: Мы перезаписываем JSON преобразованным видом, чтобы RAC-сервис мог его читать
    kb_output_path = os.path.join(os.path.dirname(__file__), '..', 'rac_service', 'knowledge_base_processed.json')
    store.save(index_path, kb_output_path)
    
    print(f"\n✅ Готово!")
    print(f"  Индекс сохранен в: {index_path}")
    print(f"  Обработанная база сохранена в: {kb_output_path}")
    print(f"  Всего векторов: {store.index.ntotal}")


if __name__ == '__main__':
    main()