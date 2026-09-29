import faiss
import numpy as np
import json
import os
import io
from typing import Optional
from dataclasses import dataclass


@dataclass
class SearchResult:
    question: str
    answer: str
    score: float
    index: int


class FAISSStore:
    """Хранилище векторов на базе FAISS"""
    def __init__(self, dimension: int):
        self.dimension = dimension
        self.index = faiss.IndexFlatIP(dimension)  # Inner Product = Cosine Similarity
        self.kb: list[dict] = []
    
    def load(self, index_path: str, kb_path: str):
        """Загружает индекс и базу знаний с диска"""
        index_path = os.path.abspath(index_path)
        kb_path = os.path.abspath(kb_path)
        
        # Читаем файл в буфер через Python (поддерживает Unicode), 
        # а затем передаём буфер в FAISS
        with open(index_path, 'rb') as f:
            buffer = io.BytesIO(f.read())
        
        self.index = faiss.read_index(faiss.PyCallbackIOReader(buffer.read))
        
        with open(kb_path, 'r', encoding='utf-8') as f:
            self.kb = json.load(f)
        print(f"Loaded FAISS index: {self.index.ntotal} vectors, {len(self.kb)} KB entries")
    
    def save(self, index_path: str, kb_path: str):
        """Сохраняет индекс и базу знаний на диск"""
        index_path = os.path.abspath(index_path)
        kb_path = os.path.abspath(kb_path)
        
        # Убеждаемся, что папки существуют
        os.makedirs(os.path.dirname(index_path), exist_ok=True)
        os.makedirs(os.path.dirname(kb_path), exist_ok=True)
        
        # FAISS на Windows не умеет писать в пути с кириллицей через C API.
        # Поэтому пишем в буфер в памяти, а буфер сохраняем через Python.
        buffer = io.BytesIO()
        faiss.write_index(self.index, faiss.PyCallbackIOWriter(buffer.write))
        
        with open(index_path, 'wb') as f:
            f.write(buffer.getvalue())
        
        with open(kb_path, 'w', encoding='utf-8') as f:
            json.dump(self.kb, f, ensure_ascii=False, indent=2)
    
    def add(self, vectors: np.ndarray, entries: list[dict]):
        """Добавляет векторы и соответствующие записи в базу знаний"""
        assert vectors.shape[1] == self.dimension
        assert len(vectors) == len(entries)
        
        vectors = vectors.astype('float32')
        self.index.add(vectors)
        self.kb.extend(entries)
    
    def search(self, query_vector: np.ndarray, k: int = 1) -> list[SearchResult]:
        """Ищет k ближайших векторов"""
        query_vector = query_vector.reshape(1, -1).astype('float32')
        
        # Нормализуем для cosine similarity
        faiss.normalize_L2(query_vector)
        
        scores, indices = self.index.search(query_vector, k)
        
        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0 or idx >= len(self.kb):
                continue
            entry = self.kb[idx]
            results.append(SearchResult(
                question=entry['question'],
                answer=entry['answer'],
                score=float(score),
                index=int(idx)
            ))
        
        return results