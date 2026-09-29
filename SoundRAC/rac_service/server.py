import grpc
from concurrent import futures
import asyncio
import numpy as np
import faiss
import json
from sentence_transformers import SentenceTransformer
import rac_pb2
import rac_pb2_grpc

class RACServicer(rac_pb2_grpc.RACServiceServicer):
    def __init__(self):
        # Загружаем модель (один раз при старте)
        print("Loading MiniLM-L12 model...")
        self.embedder = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
        
        # Загружаем FAISS индекс
        print("Loading FAISS index...")
        self.index = faiss.read_index("knowledge_base.index")
        
        # Загружаем базу знаний
        with open("knowledge_base.json", "r", encoding="utf-8") as f:
            self.kb = json.load(f)
        
        print(f"RAC ready. {len(self.kb)} questions loaded.")
    
    async def Process(self, request, context):
        # 1. Векторизуем запрос
        query_vector = self.embedder.encode([request.text])[0].astype('float32')
        
        # 2. Ищем в FAISS
        distances, indices = self.index.search(query_vector.reshape(1, -1), k=1)
        
        # 3. Формируем ответ
        best_idx = indices[0][0]
        best_score = float(distances[0][0])
        best_match = self.kb[best_idx]
        
        return rac_pb2.DialogResponse(
            answer=best_match["answer"],
            confidence=best_score,
            matched_question=best_match["question"]
        )

async def serve():
    server = grpc.aio.server(futures.ThreadPoolExecutor(max_workers=2))
    rac_pb2_grpc.add_RACServiceServicer_to_server(RACServicer(), server)
    server.add_insecure_port('[::]:50052')
    await server.start()
    print("RAC service started on port 50052")
    await server.wait_for_termination()

if __name__ == '__main__':
    asyncio.run(serve())