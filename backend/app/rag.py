
"""Knowledge Hub vector store: ChromaDB + Gemini Embeddings."""

from google import genai
from google.genai import types

from .config import CHROMA_DIR, GEMINI_API_KEY

_client = None
_collection = None
_genai_client = None

COLLECTION_NAME = "guidelines_gemini"
EMBEDDING_MODEL = "gemini-embedding-001"
EMBEDDING_DIMENSIONS = 768


def _get_collection():
    """Initialize and return the persistent ChromaDB collection."""
    global _client, _collection

    if _collection is None:
        import chromadb

        print(f"[RAG] Initializing ChromaDB at: {CHROMA_DIR}")

        _client = chromadb.PersistentClient(path=CHROMA_DIR)

        _collection = _client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"}
        )

        print(f"[RAG] Collection: {COLLECTION_NAME}")
        print(f"[RAG] Existing chunks: {_collection.count()}")

    return _collection


def _get_genai_client():
    """Initialize Gemini client only when embeddings are needed."""
    global _genai_client

    if _genai_client is None:
        if not GEMINI_API_KEY:
            raise RuntimeError("GEMINI_API_KEY is not configured")

        _genai_client = genai.Client(api_key=GEMINI_API_KEY)

    return _genai_client


def _embed(text: str, task_type: str) -> list[float]:
    """Generate Gemini embeddings."""
    if not text or not text.strip():
        raise ValueError("Cannot generate embeddings for empty text")

    client = _get_genai_client()

    try:
        response = client.models.embed_content(
            model=EMBEDDING_MODEL,
            contents=text,
            config=types.EmbedContentConfig(
                task_type=task_type,
                output_dimensionality=EMBEDDING_DIMENSIONS
            )
        )

        if not response.embeddings:
            raise RuntimeError("Gemini returned an empty embedding")

        values = response.embeddings[0].values

        if len(values) != EMBEDDING_DIMENSIONS:
            raise RuntimeError(
                f"Expected {EMBEDDING_DIMENSIONS} dimensions, "
                f"received {len(values)}"
            )

        return values

    except Exception as e:
        print(f"[RAG] Embedding error: {e}")
        raise RuntimeError(f"Gemini embedding failed: {e}") from e


def chunk_text(
    text: str,
    size: int = 800,
    overlap: int = 150
) -> list[str]:
    """Split extracted document text into overlapping chunks."""

    if not text:
        return []

    if size <= 0 or overlap < 0 or overlap >= size:
        raise ValueError("Invalid chunk size or overlap")

    text = " ".join(text.split())

    out = []
    start = 0

    while start < len(text):
        chunk = text[start:start + size]

        if len(chunk.strip()) > 30:
            out.append(chunk)

        start += size - overlap

    return out


def index_document(
    doc_id: int,
    filename: str,
    pages: list[dict]
) -> int:
    """Extract chunks, generate embeddings and store them in ChromaDB."""

    collection = _get_collection()

    print("\n[RAG] Starting document indexing")
    print(f"[RAG] Document ID: {doc_id}")
    print(f"[RAG] Filename: {filename}")
    print(f"[RAG] Pages received: {len(pages)}")
    print(f"[RAG] Database path: {CHROMA_DIR}")

    ids = []
    texts = []
    metas = []

    for page in pages:
        page_number = page.get("page", 1)
        page_text = page.get("text", "")

        print(
            f"[RAG] Page {page_number}: "
            f"{len(page_text)} characters extracted"
        )

        chunks = chunk_text(page_text)

        for i, chunk in enumerate(chunks):
            ids.append(f"{doc_id}-p{page_number}-c{i}")
            texts.append(chunk)

            metas.append({
                "doc_id": doc_id,
                "filename": filename,
                "page": page_number
            })

    print(f"[RAG] Total chunks created: {len(texts)}")

    if not ids:
        raise RuntimeError(
            "No text chunks could be extracted from this PDF. "
            "Check whether the PDF contains selectable text or requires OCR."
        )

    # Remove old vectors for this document before re-indexing.
    collection.delete(where={"doc_id": doc_id})

    embeddings = []

    for i, chunk in enumerate(texts):
        print(f"[RAG] Generating embedding {i + 1}/{len(texts)}")

        embeddings.append(
            _embed(chunk, "RETRIEVAL_DOCUMENT")
        )

    collection.add(
        ids=ids,
        documents=texts,
        metadatas=metas,
        embeddings=embeddings
    )

    final_count = collection.count()

    print(f"[RAG] Successfully indexed: {len(ids)} chunks")
    print(f"[RAG] Total ChromaDB chunks: {final_count}")
    print("[RAG] Document indexing completed\n")

    return len(ids)


def delete_document(doc_id: int):
    """Delete all vectors belonging to a document."""

    collection = _get_collection()

    collection.delete(
        where={"doc_id": doc_id}
    )

    print(f"[RAG] Deleted vectors for document ID: {doc_id}")
    print(f"[RAG] Remaining chunks: {collection.count()}")


def search(query: str, k: int = 3) -> list[dict]:
    """Retrieve the most relevant guideline chunks."""

    collection = _get_collection()

    count = collection.count()

    print(f"[RAG] ChromaDB count during search: {count}")
    print(f"[RAG] Database path during search: {CHROMA_DIR}")

    if count == 0:
        print("[RAG] WARNING: Knowledge Hub contains zero chunks")
        return []

    if not query or not query.strip():
        return []

    query_embedding = _embed(
        query,
        "RETRIEVAL_QUERY"
    )

    result = collection.query(
        query_embeddings=[query_embedding],
        n_results=min(k, count),
        include=["documents", "metadatas", "distances"]
    )

    matches = []

    for item_id, document, metadata, distance in zip(
        result["ids"][0],
        result["documents"][0],
        result["metadatas"][0],
        result["distances"][0]
    ):
        matches.append({
            "id": item_id,
            "text": document,
            "filename": metadata["filename"],
            "page": metadata["page"],
            "distance": distance
        })

    print(f"[RAG] Retrieved {len(matches)} guideline chunks")

    return matches
