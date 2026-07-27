import uuid
from datetime import datetime

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction


class Memory:
    """Долговременная память Тето на основе векторного поиска (RAG)."""

    def __init__(self, db_path: str = "./data/chroma", user_id: str = "default"):
        self.user_id = user_id
        embedding_fn = SentenceTransformerEmbeddingFunction(model_name="BAAI/bge-m3")
        client = chromadb.PersistentClient(path=db_path)
        self.collection = client.get_or_create_collection(
            name="user_memory",
            embedding_function=embedding_fn,
            metadata={"hnsw:space": "cosine"},
        )

    def remember_fact(self, fact: str) -> None:
        """Сохранить один факт о собеседнике."""
        self.collection.add(
            documents=[fact],
            metadatas=[{
                "user_id": self.user_id,
                "timestamp": datetime.now().isoformat(),
                "kind": "fact",
            }],
            ids=[str(uuid.uuid4())],
        )

    def delete_fact(self, fact_id: str) -> None:
        """Удалить факт по его id (для перезаписи)."""
        self.collection.delete(ids=[fact_id])

    def all_facts(self) -> list[dict]:
        """Все факты о собеседнике: [{"id":..., "text":...}, ...].
        Нужно, чтобы модель видела, что уже известно, и не плодила дубли."""
        got = self.collection.get(where={"user_id": self.user_id})
        ids = got.get("ids", [])
        docs = got.get("documents", [])
        return [{"id": i, "text": t} for i, t in zip(ids, docs)]

    def recall(self, query: str, k: int = 4) -> list[str]:
        """Найти k самых близких по смыслу фактов под текущую реплику."""
        count = self.collection.count()
        if count == 0:
            return []
        results = self.collection.query(
            query_texts=[query],
            n_results=min(k, count),
            where={"user_id": self.user_id},
        )
        return results["documents"][0]