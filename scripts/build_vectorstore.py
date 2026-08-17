from __future__ import annotations

import os
import sys
from pathlib import Path

import chromadb
from chromadb.config import Settings
from google import genai

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import GEMINI_API_KEY, GEMINI_EMBEDDING_MODEL_NAME, GUIDELINES_PDF, VECTORSTORE_DIR


def chunk_text(text: str, size: int = 420) -> list[str]:
    words = text.split()
    chunks = []
    current = []
    for word in words:
        current.append(word)
        if len(" ".join(current)) >= size:
            chunks.append(" ".join(current))
            current = []
    if current:
        chunks.append(" ".join(current))
    return chunks


def extract_pdf_text(pdf_path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError("pypdf is required to read the underwriting PDF. Install it via pip or generate the PDF with a package that includes it.") from exc

    reader = PdfReader(str(pdf_path))
    pages = []
    for page in reader.pages:
        text = page.extract_text() or ""
        pages.append(text)
    return "\n".join(pages)


def build_vectorstore() -> None:
    if not GUIDELINES_PDF.exists():
        raise FileNotFoundError(f"Guidelines PDF not found at {GUIDELINES_PDF}")

    text = extract_pdf_text(GUIDELINES_PDF)
    chunks = chunk_text(text)

    client = chromadb.PersistentClient(
        path=str(VECTORSTORE_DIR),
        settings=Settings(anonymized_telemetry=False),
    )
    
    # Delete existing collection if it exists, then create fresh
    try:
        client.delete_collection(name="underwriting_guidelines")
    except Exception:
        pass  # Collection doesn't exist yet
    
    collection = client.get_or_create_collection(name="underwriting_guidelines")

    embeddings_client = genai.Client(api_key=GEMINI_API_KEY)
    embed_results = []
    for chunk in chunks:
        result = embeddings_client.models.embed_content(
            model=GEMINI_EMBEDDING_MODEL_NAME,
            contents=[chunk],
            config={"task_type": "RETRIEVAL_DOCUMENT"},
        )
        try:
            values = result.embeddings[0].values
        except Exception:
            values = result["embedding"] if isinstance(result, dict) and "embedding" in result else None
        if values is None:
            raise ValueError("Unable to generate embeddings from Gemini for guideline chunks.")
        embed_results.append((chunk, values))

    documents = [chunk for chunk, _ in embed_results]
    vectors = [vector for _, vector in embed_results]
    collection.add(documents=documents, embeddings=vectors, ids=[f"chunk-{i}" for i in range(len(documents))])
    print(f"Indexed {len(chunks)} guideline chunks into Chroma.")


if __name__ == "__main__":
    build_vectorstore()
