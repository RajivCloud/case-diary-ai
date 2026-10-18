# 🕵️ CaseDiary.AI

**An agentic RAG investigation assistant for Cyber Police Investigating Officers (IOs).**

🌐 **Live demo:** https://casediary.streamlit.app · 📄 [Submission write-up](docs/SUBMISSION.md) · 🎓 [Learning guide](docs/LEARNING.md)

A station registers a cyber-fraud case and uploads its evidence: FIR, statements, bank and telecom replies, call detail records and bank statements, in whatever format they arrive. The AI agent then:
- **follows the money and follows the phones** across documents and records;
- **catches statements that the records contradict**, and **clears the wrongly suspected**;
- **drafts a chargesheet** with every claim cited, plus a court-readiness check;
- **answers the IO's questions** with sources.

The IO reviews each finding, signs off and exports a Word draft.

> ⚖️ All people, phone numbers, accounts, banks and cases in this repo are **fictional**, made for a training demo. The agent assists the IO; it never decides guilt. BNS / BNSS / BSA section numbers are used for realism; verify them before any real-world use.

## The app

| Page | What the police do there |
|---|---|
| 🗂️ **Case Register** | All cases: loss, amount frozen, status, how complete the evidence file is. Click a row to open a case. |
| ➕ **New Case** | A 3-step wizard. **(1)** FIR details. **(2)** Parties and identifiers (phones, accounts). **(3)** Evidence: upload PDF, Word or text documents, and CDR / bank exports as CSV or Excel, with **column matching** for each telecom company's or bank's own format, guided by an **evidence checklist** and completeness meter. |
| 📋 **Case Details** | Overview, evidence file (read any document), timeline, money-trail graph, **audit trail** of every action. |
| 🕵️ **Investigate** | **Full investigation:** watch the agent work step by step while its Case Diary fills up, ending in a chargesheet draft. **💬 Ask the case:** type a question and get a cited answer. |
| 📝 **Chargesheet Draft** | The draft Final Report (s.193 BNSS). The IO **accepts, rejects or annotates each finding**, signs off, and **exports to Word**. |
| 📊 **AI performance** | Basic RAG vs agent, evaluation against an answer key, a hybrid-search lab, architecture. |

## Demo cases
| Case | Fraud | How it gets into the app | Agent score vs answer key |
|---|---|---|---|
| CYB-114-2026 | "Digital arrest" (fake CBI officer), ₹38.5 L | Pre-loaded | **12/12** (2 runs) · basic RAG 2/12 |
| CYB-131-2026 | Fake stock-trading app, ₹24.5 L | **Loaded through the New Case pipeline** from raw files in `sample_upload/CYB-131-2026/` (Word/text documents, an Excel bank export, a bank CSV in its own format, a telecom CDR export with MOC/MTC codes) | **12/13** on first run, no code or prompt changes · basic RAG 4/13 |

The agent was built on CYB-114. CYB-131 was then generated with different people, a different scam, different evidence and a different identification method (admin-panel IP → ISP subscriber; crypto-exchange KYC). It was investigated with **no code or prompt changes**.

## RAG and agent features
1. Ingestion of PDF, Word and text documents, plus CSV/Excel records with column matching and telecom-code normalisation.
2. Structure-aware chunking (one paragraph per chunk) with contextual headers and metadata.
3. Local embeddings (fastembed `bge-small-en-v1.5`, ONNX) with **incremental indexing**.
4. BM25 keyword search, fused with dense search by Reciprocal Rank Fusion.
5. Metadata filtering (case / document type / person); other cases searched only on purpose, to find links between cases.
6. Structured retrieval: per-case SQLite tools for CDRs, tower timelines, IMEI history and transactions.
7. **Dynamic tool descriptions and a case brief** built from each case: the same agent works on any case.
8. Claude Opus 5.5 ReAct loop with native, parallel tool use; a separate low-effort Q&A mode.
9. External working memory (the Case Diary), whose entries must cite sources.
10. Guardrails: a step cap and a submit gate that rejects the report until every suspect is resolved.
11. A court-readiness check: BSA s.63 certificates, independent panch witnesses, s.23 BSA admissions, forensic steps.
12. Human in the loop: per-finding IO review, sign-off, Word export.
13. An audit trail of every AI tool call, question and review decision.
14. A fair baseline (same model, same retriever, retrieve once) and evaluation against ground truth.
15. Prompt caching, server-side refusal fallback, replay mode, and an access code for live AI.

## Run it locally
```bash
python -m venv .venv
.venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
echo ANTHROPIC_API_KEY=sk-ant-... > .env
streamlit run app.py
```
Recorded investigations and the suggested questions work **without an API key**. Live investigations and your own questions need a key in `.env`. Set `ACCESS_CODE` in `.env` or in Streamlit secrets to protect live AI on a public link.

Regenerate demo data, record runs and evaluate:
```bash
python scripts/generate_tables.py && python scripts/generate_archive.py && python scripts/generate_kit_131.py
python scripts/record_runs.py --case CYB-114-2026          # baseline + agent (~$0.6–0.8 per agent run)
python scripts/record_questions.py --case CYB-114-2026     # suggested questions (~$0.06–0.18 each)
python eval/run_eval.py                                     # scores every case that has an answer key
pytest -q                                                   # fast tests, no API calls
```

## Project layout
```
app.py                     navigation (st.navigation) + shared sidebar
views/                     register · new_case · case_details · investigate · chargesheet · about
ui/                        common (sidebar, styles), render (steps, diary, graph, timeline), evidence (uploads, column matching)
core/store.py              case folders: case.json, documents, tables, runs, review, audit
core/sample_kit.py         loads a raw "case kit" through the same ingestion pipeline
core/export.py             Word export of the reviewed chargesheet draft
rag/                       chunking · hybrid retriever (dense + BM25 + RRF) · SQL tools
agent/                     tools (built per case) · prompts (case brief) · loop (investigate + ask) · diary · baseline · llm
eval/run_eval.py           scoring against each case's answer_key.json
data/cases/<CASE-ID>/      case.json · documents/ · tables/ · runs/ · review.json · audit.jsonl · answer_key.json (demo only)
data/archive/              closed cases (retrieval noise and cross-case links)
sample_upload/             raw case kits for the New Case demo
docs/                      LEARNING.md (why / what / how) · SUBMISSION.md
```

## Deploy (Streamlit Community Cloud)
1. Push this repo to GitHub as a public repo.
2. On share.streamlit.io choose **New app**, pick the repo, set the main file to `app.py`, and choose Python 3.13.
3. Under **Advanced settings → Secrets**, add:
   ```toml
   ANTHROPIC_API_KEY = "sk-ant-..."
   ACCESS_CODE = "choose-a-code"
   ```
4. Deploy. Recorded runs and suggested questions work for everyone; give reviewers the access code for live AI.

Note: Streamlit Cloud's disk is temporary. Cases created on the public demo disappear when the app restarts. A real deployment would keep the same case structure in a database on the department's own network.
