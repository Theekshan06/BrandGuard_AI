
"""Knowledge Hub vector store: ChromaDB + Gemini Embeddings."""

from google import genai
from google.genai import types

from .config import CHROMA_DIR, GEMINI_API_KEY

_client = None
_collection = None
_genai_client = None

COLLECTION_NAME = "guidelines_gemini"


def _get_collection():
    global _client, _collection

    if _collection is None:
        import chromadb

        _client = chromadb.PersistentClient(path=CHROMA_DIR)

        _collection = _client.get_or_create_collection(
            COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"}
        )

    return _collection


def _get_genai_client():
    global _genai_client

    if _genai_client is None:
        if not GEMINI_API_KEY:
            raise RuntimeError("GEMINI_API_KEY is not configured")

        _genai_client = genai.Client(api_key=GEMINI_API_KEY)

    return _genai_client


def _embed(text: str, task_type: str) -> list[float]:
    client = _get_genai_client()

    response = client.models.embed_content(
        model="gemini-embedding-001",
        contents=text,
        config=types.EmbedContentConfig(
            task_type=task_type,
            output_dimensionality=768
        )
    )

    return response.embeddings[0].values


def chunk_text(text: str, size: int = 800, overlap: int = 150) -> list[str]:
    text = " ".join(text.split())
    out, start = [], 0

    while start < len(text):
        out.append(text[start:start + size])
        start += size - overlap

    return [c for c in out if len(c) > 30]


def index_document(doc_id: int, filename: str, pages: list[dict]) -> int:
    collection = _get_collection()

    ids, texts, metas = [], [], []

    for page in pages:
        for i, chunk in enumerate(chunk_text(page["text"])):
            ids.append(f"{doc_id}-p{page['page']}-c{i}")
            texts.append(chunk)
            metas.append({
                "doc_id": doc_id,
                "filename": filename,
                "page": page["page"]
            })

    if ids:
        embeddings = [_embed(text, "RETRIEVAL_DOCUMENT") for text in texts]

        collection.add(
            ids=ids,
            documents=texts,
            metadatas=metas,
            embeddings=embeddings
        )

    return len(ids)


def delete_document(doc_id: int):
    collection = _get_collection()
    collection.delete(where={"doc_id": doc_id})


def search(query: str, k: int = 3) -> list[dict]:
    collection = _get_collection()

    count = collection.count()

    if count == 0:
        return []

    query_embedding = _embed(query, "RETRIEVAL_QUERY")

    result = collection.query(
        query_embeddings=[query_embedding],
        n_results=min(k, count)
    )

    return [
        {
            "id": item_id,
            "text": document,
            "filename": metadata["filename"],
            "page": metadata["page"],
            "distance": distance
        }
        for item_id, document, metadata, distance in zip(
            result["ids"][0],
            result["documents"][0],
            result["metadatas"][0],
            result["distances"][0]
        )
    ]
