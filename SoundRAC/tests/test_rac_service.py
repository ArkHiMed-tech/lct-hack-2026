import pytest
import numpy as np
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'rac_service'))

from faiss_store import FAISSStore, SearchResult


class TestFAISSStore:
    @pytest.fixture
    def store(self):
        """Создаёт тестовый FAISS store"""
        store = FAISSStore(dimension=384)
        
        # Добавляем тестовые данные
        vectors = np.random.randn(10, 384).astype('float32')
        # Нормализуем для cosine similarity
        vectors = vectors / np.linalg.norm(vectors, axis=1, keepdims=True)
        
        entries = [
            {"question": f"Вопрос {i}", "answer": f"Ответ {i}"}
            for i in range(10)
        ]
        
        store.add(vectors, entries)
        return store
    
    def test_add_and_search(self, store):
        """Проверяем, что поиск работает"""
        # Берём первый вектор как запрос
        query = store.index.reconstruct(0).reshape(1, -1)
        
        results = store.search(query, k=1)
        
        assert len(results) == 1
        assert results[0].question == "Вопрос 0"
        assert results[0].answer == "Ответ 0"
        assert results[0].score > 0.99  # Должен быть почти идентичен
    
    def test_search_top_k(self, store):
        """Проверяем поиск top-k"""
        query = np.random.randn(384).astype('float32')
        query = query / np.linalg.norm(query)
        
        results = store.search(query, k=5)
        
        assert len(results) == 5
        # Результаты должны быть отсортированы по убыванию score
        for i in range(len(results) - 1):
            assert results[i].score >= results[i + 1].score
    
    def test_empty_store(self):
        """Проверяем поведение пустого store"""
        store = FAISSStore(dimension=384)
        query = np.random.randn(384).astype('float32')
        
        results = store.search(query, k=1)
        assert len(results) == 0