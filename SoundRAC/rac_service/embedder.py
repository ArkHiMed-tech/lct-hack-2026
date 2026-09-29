from sentence_transformers import SentenceTransformer
import numpy as np


class Embedder:
    """Векторизатор текста на базе MiniLM-L12"""
    def __init__(self, model_name: str = 'paraphrase-multilingual-MiniLM-L12-v2'):
        print(f"Loading embedder model: {model_name}")
        self.model = SentenceTransformer(model_name)
        self.dimension = self.model.get_sentence_embedding_dimension()
        print(f"Embedder loaded. Dimension: {self.dimension}")
    
    def encode(self, texts: list[str]) -> np.ndarray:
        """Векторизует список текстов. Возвращает numpy array shape (N, dimension)"""
        return self.model.encode(texts, convert_to_numpy=True, normalize_embeddings=True)
    
    def encode_single(self, text: str) -> np.ndarray:
        """Векторизует один текст. Возвращает numpy array shape (dimension,)"""
        return self.encode([text])[0]