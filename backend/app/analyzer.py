
"""Fact & claim verification + violation detection + evidence mapping + basic correction."""

import json
import re

from google import genai
from google.genai import types

from .config import GEMINI_API_KEY, LLM_MODEL


def _retrieve(content: str, max_chunks: int = 12) -> list[dict]:
    # Lazy import to reduce unnecessary startup memory usage
    from .rag import search

    parts = [
        p.strip()
        for p in re.split(r"\n\s*\n|(?<=[.!?])\s+", content)
        if len(p.strip()) > 25
    ][:40]

    best: dict[str, dict] = {}

    for part in parts or [content[:500]]:
        for hit in search(part, k=3):
            if hit["id"] not in best or hit["distance"] < best[hit["id"]]["distance"]:
                best[hit["id"]] = hit

    return sorted(
        best.values(),
        key=lambda h: h["distance"]
    )[:max_chunks]


SYSTEM = """You are a brand compliance reviewer. You receive CONTENT and numbered GUIDELINE excerpts.
Find every claim or passage in CONTENT that violates a guideline. Only use the given guidelines as the
source of truth; never invent rules. For each violation return a JSON object with keys:
violation (short type, e.g. "Unsupported financial claim"),
detected_text (EXACT verbatim substring copied from CONTENT),
guideline_id (the id like "G2" of the excerpt that contains the rule),
rule (the rule, quoted or closely paraphrased from that excerpt),
reason (one sentence on why the content breaks the rule),
severity ("Critical" | "High" | "Medium" | "Low"),
suggested_fix (a compliant rewrite of detected_text).
Return ONLY a JSON array. Return [] if there are no violations."""


def _parse_json(raw: str) -> list[dict]:
    raw = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.M).strip()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        m = re.search(r"\[.*\]", raw, re.S)
        data = json.loads(m.group(0)) if m else []

    return data if isinstance(data, list) else []


def analyze(content_pages: list[dict]) -> dict:
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY is not set in backend/.env")

    content = "\n\n".join(p["text"] for p in content_pages)

    chunks = _retrieve(content)

    if not chunks:
        raise RuntimeError(
            "Knowledge Hub is empty. Upload a brand guideline document first."
        )

    gmap = {f"G{i+1}": c for i, c in enumerate(chunks)}

    guidelines = "\n\n".join(
        f"[{gid}] ({c['filename']}, page {c['page']})\n{c['text']}"
        for gid, c in gmap.items()
    )

    client = genai.Client(api_key=GEMINI_API_KEY)

    try:
        resp = client.models.generate_content(
            model="gemini-3.8-flash",
            contents=f"GUIDELINES:\n{guidelines}\n\nCONTENT:\n{content}",
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM,
                response_mime_type="application/json",
                temperature=0.1,
                max_output_tokens=8192,
            ),
        )
    except Exception as e:
        raise RuntimeError(f"Gemini API error: {e}")

    raw_findings = _parse_json(resp.text or "[]")

    findings = []

    for f in raw_findings:
        g = gmap.get(f.get("guideline_id"))
        text = f.get("detected_text", "")

        start = content.find(text) if text else -1

        if not g or start < 0:
            continue

        page = next(
            (p["page"] for p in content_pages if text in p["text"]),
            None
        )

        findings.append({
            "violation": f.get("violation"),
            "detected_text": text,
            "location": {
                "start": start,
                "end": start + len(text),
                "page": page
            },
            "evidence": {
                "document": g["filename"],
                "page": g["page"],
                "excerpt": g["text"]
            },
            "rule": f.get("rule"),
            "reason": f.get("reason"),
            "severity": f.get("severity", "Medium"),
            "suggested_fix": f.get("suggested_fix"),
        })

    order = {
        "Critical": 0,
        "High": 1,
        "Medium": 2,
        "Low": 3
    }

    findings.sort(key=lambda x: order.get(x["severity"], 4))

    return {
        "content": content,
        "findings": findings
    }
