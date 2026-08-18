from __future__ import annotations

import chromadb
from chromadb.config import Settings
from google import genai

from app.config import GEMINI_API_KEY, GEMINI_EMBEDDING_MODEL_NAME, VECTORSTORE_DIR

_K_MIN, _K_MAX = 1, 10


def rag_lookup(query: str, k: int = 4) -> list[str]:
    """Query the local Chroma collection for underwriting guideline chunks.

    Returns retrieved chunks on success, [] when no relevant evidence is found,
    or [] with a logged failure reason when retrieval is unavailable.
    """
    k = max(_K_MIN, min(_K_MAX, k))

    if not GEMINI_API_KEY:
        print("[rag_lookup] status=unavailable reason=missing_api_key")
        return []

    try:
        client = chromadb.PersistentClient(
            path=str(VECTORSTORE_DIR),
            settings=Settings(anonymized_telemetry=False),
        )
        collection = client.get_or_create_collection(name="underwriting_guidelines")
        doc_count = collection.count()
        if doc_count == 0:
            print("[rag_lookup] status=unavailable reason=empty_collection")
            return []
    except Exception as e:
        print(f"[rag_lookup] status=unavailable reason=vectorstore_error error={type(e).__name__}")
        return []

    try:
        genai_client = genai.Client(api_key=GEMINI_API_KEY)
    except Exception as e:
        print(f"[rag_lookup] status=unavailable reason=client_init_failed error={type(e).__name__}")
        return []

    try:
        embedding = genai_client.models.embed_content(
            model=GEMINI_EMBEDDING_MODEL_NAME,
            contents=[query],
            config={"task_type": "RETRIEVAL_QUERY"},
        )
        query_vector = embedding.embeddings[0].values
        results = collection.query(query_embeddings=[query_vector], n_results=k)
        docs = results.get("documents", [[]])[0]
        chunks = [str(doc) for doc in docs]
        if not chunks:
            print("[rag_lookup] status=available chunks=0 (no relevant evidence found)")
        else:
            print(f"[rag_lookup] status=available chunks={len(chunks)}")
        return chunks
    except Exception as e:
        print(f"[rag_lookup] status=unavailable reason=embedding_or_query_failed error={type(e).__name__}: {str(e)[:80]}")
        return []
