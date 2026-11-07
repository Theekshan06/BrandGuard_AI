# BrandGuard

AI brand compliance that shows its evidence. Upload your brand guidelines, submit content, and get every violation explained with the exact text, the guideline page and the rule it breaks.

```
Violation:      Unsupported financial claim
Detected text:  "90% guaranteed returns"
Evidence:       Nova_Capital_Brand_Guidelines.pdf, page 4
Relevant rule:  Financial returns must not be guaranteed
Reason:         The content makes a guarantee that is not permitted
Severity:       Critical
Suggested fix:  Returns are not guaranteed and capital is at risk
```

## Features (Phase 1)

- Knowledge Hub: upload, list and delete guideline documents (PDF, TXT, MD, images)
- Page-aware text extraction with OCR fallback for scanned pages
- RAG retrieval of the most relevant guideline excerpts
- Fact and claim verification against the uploaded guidelines
- Violation detection with severity: Critical, High, Medium, Low
- Evidence mapping: document, page number and rule text
- Violating text highlighted and colour-coded by severity
- Basic AI correction assistant: a compliant rewrite for each violation

## Tech stack

| Layer | Technology |
|---|---|
| Frontend | React (Vite) |
| Backend | Python, FastAPI |
| Database | SQLite by default, PostgreSQL supported |
| Extraction | PyMuPDF, Tesseract OCR |
| Embeddings | Sentence Transformers (`all-MiniLM-L6-v2`) |
| Vector store | ChromaDB |
| LLM | Google Gemini API |

## How it works

1. **Upload:** a guideline is extracted page by page, split into overlapping chunks, embedded locally and stored in ChromaDB. Every chunk keeps its document name and page number.
2. **Retrieve:** submitted content is split into sentences, and each is searched against the vector store. The best excerpts are numbered G1, G2, and so on.
3. **Verify:** the excerpts and the content go to Gemini, which returns JSON findings.
4. **Map evidence:** the model returns only a guideline ID. The server looks up the document and page itself, and drops any finding whose quoted text is not in the content word for word.

## Project structure

```
brandguard/
├── backend/
│   ├── requirements.txt
│   ├── .env.example          copy to .env
│   └── app/
│       ├── main.py           FastAPI routes
│       ├── config.py         settings from .env
│       ├── db.py             document records
│       ├── extraction.py     PyMuPDF + Tesseract
│       ├── rag.py            ChromaDB + embeddings
│       └── analyzer.py       verification, evidence mapping, corrections
├── frontend/
│   ├── package.json
│   ├── vite.config.js        proxies /api to the backend
│   └── src/                  App.jsx, App.css, main.jsx
└── samples/                  guideline PDF, test files, expected results
```

## Prerequisites

- Python 3.10 or newer
- Node.js 18 or newer
- Tesseract OCR
  - Windows: install from https://github.com/UB-Mannheim/tesseract/wiki and add it to PATH
  - macOS: `brew install tesseract`
  - Ubuntu: `sudo apt install tesseract-ocr`
- A Gemini API key from https://aistudio.google.com

## Setup and run

### 1. Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env          # macOS/Linux: cp .env.example .env
```

Open `.env` and set your key:

```
GEMINI_API_KEY=your-gemini-api-key-here
LLM_MODEL=gemini-2.5-flash
DATABASE_URL=sqlite:///./brandguard.db
CHROMA_DIR=./chroma_data
```

Start the server:

```bash
uvicorn app.main:app --reload --port 8000
```

The first run downloads the embedding model, so it takes a minute. API docs are at http://localhost:8000/docs.

### 2. Frontend

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173.

### Using PostgreSQL (optional)

Set `DATABASE_URL` in `.env`:

```
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/brandguard
```

## API

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/api/guidelines` | Upload a guideline file (form field `file`) |
| GET | `/api/guidelines` | List guideline documents |
| DELETE | `/api/guidelines/{id}` | Delete a guideline and its vectors |
| POST | `/api/analyze` | Check content (form field `text` or `file`) |

## Try it

1. Upload `samples/Nova_Capital_Brand_Guidelines.pdf` in the Knowledge Hub.
2. Check each sample file and compare with `samples/EXPECTED_RESULTS.md`:
   - `test1_violations.txt`: about 7 findings
   - `test2_clean.txt`: no findings
   - `test3_mixed_subtle.txt`: about 4 subtle findings

LLM output varies slightly between runs. The quoted text and the guideline page should always be correct.

## Troubleshooting

| Problem | Fix |
|---|---|
| `GEMINI_API_KEY is not set` | Add the key to `backend/.env` and restart the backend |
| Gemini "model not found" | Set `LLM_MODEL` in `.env` to a current model name from AI Studio |
| Gemini quota error | Free-tier rate limit. Wait a minute or enable billing |
| `TesseractNotFoundError` | Install Tesseract and make sure it is on PATH |
| "Knowledge Hub is empty" | Upload a guideline document before checking content |
| Frontend cannot reach API | Make sure the backend is running on port 8000 |

## Known limitations

- Phase 2 and 3 features are not built yet
- No authentication, local only, not deployed
- No Word (.docx) support
- Claims are checked only against uploaded guidelines, not external sources
- Only the first 40 sentences of content are searched, with at most 12 excerpts sent to the model
- LLM results can vary and may miss subtle violations

## Roadmap

1. **Visual Compliance Checker:** OpenCV logo and colour checks, OCR text through the claim verifier, issues marked on the image
2. **Scoring, Voice Analyzer and Dashboard:** explainable 0-100 score, tone and readability analysis, governance dashboard
3. **Production foundations:** brand profiles, JWT roles, approval workflow, audit log, cloud deployment on PostgreSQL