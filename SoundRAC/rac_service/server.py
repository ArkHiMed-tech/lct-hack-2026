import grpc
from concurrent import futures
import asyncio
import numpy as np
import faiss
import json
import os
import sys

# Добавляем путь для импорта proto-файлов
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'proto'))

import rac_pb2
import rac_pb2_grpc
from embedder import Embedder
from faiss_store import FAISSStore


class RACServicer(rac_pb2_grpc.RACServiceServicer):
    def __init__(self):
        # Загружаем модель (один раз при старте)
        print("🔄 Loading MiniLM-L12 model...")
        self.embedder = Embedder()
        
        # Загружаем FAISS индекс
        print("🔄 Loading FAISS index...")
        self.store = FAISSStore(dimension=self.embedder.dimension)
        
        index_path = os.path.join(os.path.dirname(__file__), 'knowledge_base.index')
        kb_path = os.path.join(os.path.dirname(__file__), 'knowledge_base_processed.json')
        self.store.load(index_path, kb_path)
        
        print(f"✅ RAC ready. {self.store.index.ntotal} vectors loaded.")
    
    async def Process(self, request, context):
        # 1. Векторизуем запрос
        query_vector = self.embedder.encode_single(request.text)
        
        # 2. Ищем в FAISS
        results = self.store.search(query_vector, k=1)
        
        # 3. Формируем ответ
        if results:
            best = results[0]
            return rac_pb2.DialogResponse(
                answer=best.answer,
                confidence=best.score,
                matched_question=best.question
            )
        else:
            return rac_pb2.DialogResponse(
                answer="Извините, я не понял ваш вопрос.",
                confidence=0.0,
                matched_question=""
            )


async def serve():
    server = grpc.aio.server(futures.ThreadPoolExecutor(max_workers=4))
    rac_pb2_grpc.add_RACServiceServicer_to_server(RACServicer(), server)
    server.add_insecure_port('[::]:50052')
    print("🚀 RAC service starting on port 50052...")
    await server.start()
    print("✅ RAC service is running!")
    await server.wait_for_termination()


if __name__ == '__main__':
    asyncio.run(serve())