from __future__ import annotations

import chromadb
from chromadb.config import Settings
from google import genai

from app.config import GEMINI_API_KEY, GEMINI_EMBEDDING_MODEL_NAME, VECTORSTORE_DIR


def rag_lookup(query: str, k: int = 4) -> list[str]:
    """Query the local Chroma collection for underwriting guideline chunks."""
    if not GEMINI_API_KEY:
        return []

    try:
        client = chromadb.PersistentClient(
            path=str(VECTORSTORE_DIR),
            settings=Settings(anonymized_telemetry=False),
        )
        collection = client.get_or_create_collection(name="underwriting_guidelines")

        try:
            genai_client = genai.Client(api_key=GEMINI_API_KEY)
        except (ValueError, Exception):
            return []

        embedding = genai_client.models.embed_content(
            model=GEMINI_EMBEDDING_MODEL_NAME,
            contents=[query],
            config={"task_type": "RETRIEVAL_QUERY"},
        )
        query_vector = embedding.embeddings[0].values

        results = collection.query(query_embeddings=[query_vector], n_results=k)
        docs = results.get("documents", [[]])[0]
        return [str(doc) for doc in docs]
    except Exception:
        return []
