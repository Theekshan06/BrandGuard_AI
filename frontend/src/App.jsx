import { useEffect, useState } from "react";

const SEV = { Critical: "sev-critical", High: "sev-high", Medium: "sev-medium", Low: "sev-low" };
const API_URL = "https://brandguard-ai-vkig.onrender.com";

function Highlighted({ content, findings }) {
  const spans = findings.map((f, i) => ({ ...f.location, i })).sort((a, b) => a.start - b.start);
  const out = []; let pos = 0;
  spans.forEach((s) => {
    if (s.start < pos) return;
    out.push(content.slice(pos, s.start));
    out.push(<mark key={s.i} className={SEV[findings[s.i].severity]}>{content.slice(s.start, s.end)}</mark>);
    pos = s.end;
  });
  out.push(content.slice(pos));
  return <pre className="content">{out}</pre>;
}

export default function App() {
  const [docs, setDocs] = useState([]);
  const [text, setText] = useState("");
  const [file, setFile] = useState(null);
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

 const loadDocs = () =>
  fetch(`${API_URL}/api/guidelines`)
    .then((r) => {
      if (!r.ok) throw new Error("Failed to load guidelines");
      return r.json();
    })
    .then(setDocs);
  useEffect(() => { loadDocs(); }, []);

  async function upload(e) {
    const f = e.target.files[0]; if (!f) return;
    setBusy(true); setError("");
    const fd = new FormData(); fd.append("file", f);
    const r = await fetch(`${API_URL}/api/guidelines`, {method: "POST",body: fd});
    if (!r.ok) setError("Upload failed"); 
    await loadDocs(); setBusy(false); e.target.value = "";
  }

  async function remove(id) {
  await fetch(`${API_URL}/api/guidelines/${id}`, {method: "DELETE"});
  loadDocs();}

  async function check() {
    setBusy(true); setError(""); setResult(null);
    const fd = new FormData();
    if (file) fd.append("file", file); else fd.append("text", text);
    const r = await fetch(`${API_URL}/api/analyze`, {method: "POST",body: fd});
    const data = await r.json();
    if (!r.ok) setError(data.detail || "Check failed"); else setResult(data);
    setBusy(false);
  }

  return (
    <div className="app">
      <header><h1>BrandGuard</h1><p>Check content against your brand guidelines, with the evidence.</p></header>
      <main>
        <section className="hub">
          <h2>Knowledge Hub</h2>
          <label className="btn">Upload guideline<input type="file" hidden accept=".pdf,.txt,.md,.png,.jpg,.jpeg" onChange={upload} /></label>
          {docs.length === 0 && <p className="muted">No guidelines yet. Upload a PDF to begin.</p>}
          <ul>{docs.map((d) => (
            <li key={d.id}><div><strong>{d.filename}</strong><span className="muted">{d.pages} pages, {d.chunks} chunks</span></div>
              <button className="link" onClick={() => remove(d.id)}>Delete</button></li>))}</ul>
        </section>

        <section className="check">
          <h2>Check content</h2>
          <textarea rows={7} placeholder="Paste marketing copy here" value={text} onChange={(e) => setText(e.target.value)} disabled={!!file} />
          <div className="row">
            <input type="file" accept=".pdf,.txt,.md,.png,.jpg,.jpeg" onChange={(e) => setFile(e.target.files[0] || null)} />
            <button className="btn primary" disabled={busy || (!file && !text.trim())} onClick={check}>{busy ? "Working..." : "Check content"}</button>
          </div>
          {error && <p className="error">{error}</p>}

          {result && (<>
            <h2>{result.findings.length ? `${result.findings.length} violation${result.findings.length > 1 ? "s" : ""} found` : "No violations found"}</h2>
            <Highlighted content={result.content} findings={result.findings} />
            {result.findings.map((f, i) => (
              <article key={i} className={`finding ${SEV[f.severity]}`}>
                <div className="head"><h3>{f.violation}</h3><span className="badge">{f.severity}</span></div>
                <dl>
                  <dt>Detected text</dt><dd>"{f.detected_text}"</dd>
                  <dt>Evidence</dt><dd>{f.evidence.document}, page {f.evidence.page}</dd>
                  <dt>Relevant rule</dt><dd>{f.rule}</dd>
                  <dt>Reason</dt><dd>{f.reason}</dd>
                  <dt>Suggested fix</dt><dd className="fix">{f.suggested_fix}</dd>
                </dl>
              </article>))}
          </>)}
        </section>
      </main>
    </div>
  );
}
