"""Knowledge Hub vector store: ChromaDB + Sentence Transformers, with page metadata."""
import chromadb
from sentence_transformers import SentenceTransformer
from .config import CHROMA_DIR

_model = None
_client = chromadb.PersistentClient(path=CHROMA_DIR)
_col = _client.get_or_create_collection("guidelines", metadata={"hnsw:space": "cosine"})


def _embedder():
    global _model
    if _model is None:
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


def chunk_text(text: str, size: int = 800, overlap: int = 150) -> list[str]:
    text = " ".join(text.split())
    out, start = [], 0
    while start < len(text):
        out.append(text[start:start + size])
        start += size - overlap
    return [c for c in out if len(c) > 30]


def index_document(doc_id: int, filename: str, pages: list[dict]) -> int:
    ids, texts, metas = [], [], []
    for p in pages:
        for i, c in enumerate(chunk_text(p["text"])):
            ids.append(f"{doc_id}-p{p['page']}-c{i}")
            texts.append(c)
            metas.append({"doc_id": doc_id, "filename": filename, "page": p["page"]})
    if ids:
        _col.add(ids=ids, documents=texts, metadatas=metas,
                 embeddings=_embedder().encode(texts).tolist())
    return len(ids)


def delete_document(doc_id: int):
    _col.delete(where={"doc_id": doc_id})


def search(query: str, k: int = 3) -> list[dict]:
    n = _col.count()
    if n == 0:
        return []
    res = _col.query(query_embeddings=_embedder().encode([query]).tolist(), n_results=min(k, n))
    return [{"id": i, "text": d, "filename": m["filename"], "page": m["page"], "distance": dist}
            for i, d, m, dist in zip(res["ids"][0], res["documents"][0], res["metadatas"][0], res["distances"][0])]
