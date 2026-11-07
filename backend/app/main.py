
import os
from pathlib import Path
from dotenv import load_dotenv

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware

env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(env_path)

if not os.getenv("GEMINI_API_KEY"):
    raise RuntimeError("GEMINI_API_KEY is missing from environment variables")

app = FastAPI(title="BrandGuard API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173","https://brand-guard-2tefr9orl-theekshanmaari-5329.vercel.app","https://brand-guard-ai-zeta.vercel.app","https://brand-guard-d62oql1hp-theekshanmaari-5329.vercel.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)


@app.post("/api/guidelines")
async def upload_guideline(file: UploadFile = File(...)):
    from . import rag
    from .db import SessionLocal, Document
    from .extraction import extract_pages

    pages = extract_pages(await file.read(), file.filename)

    with SessionLocal() as db:
        doc = Document(filename=file.filename, pages=len(pages))
        db.add(doc)
        db.commit()
        db.refresh(doc)

        doc.chunks = rag.index_document(doc.id, file.filename, pages)
        db.commit()

        return {
            "id": doc.id,
            "filename": doc.filename,
            "pages": doc.pages,
            "chunks": doc.chunks
        }


@app.get("/api/guidelines")
def list_guidelines():
    from .db import SessionLocal, Document

    with SessionLocal() as db:
        return [
            {
                "id": d.id,
                "filename": d.filename,
                "pages": d.pages,
                "chunks": d.chunks
            }
            for d in db.query(Document).order_by(Document.id.desc())
        ]


@app.delete("/api/guidelines/{doc_id}")
def delete_guideline(doc_id: int):
    from . import rag
    from .db import SessionLocal, Document

    with SessionLocal() as db:
        doc = db.get(Document, doc_id)

        if not doc:
            raise HTTPException(404, "Not found")

        rag.delete_document(doc_id)
        db.delete(doc)
        db.commit()

    return {"ok": True}


@app.post("/api/analyze")
async def analyze_content(
    text: str = Form(""),
    file: UploadFile | None = File(None)
):
    from .analyzer import analyze
    from .extraction import extract_pages

    if file:
        pages = extract_pages(await file.read(), file.filename)
    elif text.strip():
        pages = [{"page": 1, "text": text}]
    else:
        raise HTTPException(400, "Provide text or a file")

    try:
        return analyze(pages)
    except RuntimeError as e:
        raise HTTPException(400, str(e))
