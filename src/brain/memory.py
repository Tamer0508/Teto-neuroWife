import uuid
from datetime import datetime

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction


class Memory:
    """Долговременная память Тето на основе векторного поиска (RAG)."""

    def __init__(self, db_path: str = "./data/chroma", user_id: str = "default"):
        self.user_id = user_id

        # Локальная мультиязычная модель эмбеддингов (хорошо знает русский).
        # Первый запуск скачает ~2 ГБ в кэш, дальше грузит из него.
        embedding_fn = SentenceTransformerEmbeddingFunction(model_name="BAAI/bge-m3")

        # PersistentClient пишет базу на диск -> память переживает перезапуск.
        client = chromadb.PersistentClient(path=db_path)

        # Коллекция = "таблица" воспоминаний. cosine — метрика близости векторов.
        self.collection = client.get_or_create_collection(
            name="user_memory",
            embedding_function=embedding_fn,
            metadata={"hnsw:space": "cosine"},
        )

    def remember(self, user_message: str, teto_message: str) -> None:
        """Сохранить один обмен репликами в память."""
        document = f"Пользователь: {user_message}\nТето: {teto_message}"
        self.collection.add(
            documents=[document],
            metadatas=[{
                "user_id": self.user_id,
                "timestamp": datetime.now().isoformat(),
            }],
            ids=[str(uuid.uuid4())],
        )

    def recall(self, query: str, k: int = 4) -> list[str]:
        """Найти k самых близких по смыслу воспоминаний под текущую реплику."""
        count = self.collection.count()
        if count == 0:
            return []

        results = self.collection.query(
            query_texts=[query],
            n_results=min(k, count),
            where={"user_id": self.user_id},
        )
        # query отвечает списком списков (по одному на каждый запрос) -> берём [0]
        return results["documents"][0]