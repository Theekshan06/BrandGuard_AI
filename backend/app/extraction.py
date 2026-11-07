"""Document extraction. Every result keeps its page number (needed for evidence mapping)."""
import io
import fitz  # PyMuPDF
import pytesseract
from PIL import Image


def _ocr(img: Image.Image) -> str:
    return pytesseract.image_to_string(img).strip()


def extract_pages(data: bytes, filename: str) -> list[dict]:
    name = filename.lower()
    if name.endswith(".pdf"):
        doc = fitz.open(stream=data, filetype="pdf")
        pages = []
        for i, page in enumerate(doc):
            text = page.get_text().strip()
            if len(text) < 20:  # scanned page -> OCR fallback
                pix = page.get_pixmap(dpi=200)
                text = _ocr(Image.open(io.BytesIO(pix.tobytes("png"))))
            pages.append({"page": i + 1, "text": text})
        return pages
    if name.endswith((".png", ".jpg", ".jpeg")):
        return [{"page": 1, "text": _ocr(Image.open(io.BytesIO(data)))}]
    return [{"page": 1, "text": data.decode("utf-8", errors="ignore")}]  # .txt / .md
