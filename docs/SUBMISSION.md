# CaseDiary.AI: an Agentic RAG Assistant for Cyber Police Investigating Officers

**Builder:** Rajiv · **Week:** RAG Agentic Demo · 🌐 **Live app:** https://casediary.streamlit.app · 💻 **GitHub:** https://github.com/RajivCloud/case-diary-ai · 🎬 **Video:** `<video URL>`

> **In one line:** A police station registers a cyber-fraud case and uploads its evidence. An AI agent then follows the money and the phones across documents and 2,000+ records, catches the lies, clears the innocent, drafts a cited chargesheet with a court-readiness check, and answers the officer's questions. The officer reviews and signs off on every finding.

---

## 1. The problem
"Digital arrest", fake-trading-app and mule-account frauds are rising fast in India. For each case, an Investigating Officer (IO) has to connect:
- bank replies and statements;
- call detail records (CDRs), tower locations and handset IMEIs;
- platform, ISP and exchange replies;
- witness and suspect statements, some of which are false.

Then the chargesheet must survive court scrutiny under the BNS, BNSS and BSA. The answer is never in one document, so this is a natural fit for **agentic** RAG rather than "chat with a PDF".

## 2. What the app does (inputs → process → output)
| | |
|---|---|
| **Input 1: the case file** | Entered through the **New Case** wizard: FIR details, parties and identifiers, then documents (PDF, Word, text) and CDR / bank exports (CSV, Excel). Column matching handles each telecom company's and bank's own format. An evidence checklist shows what's missing. |
| **Input 2: the officer's request** | Either **"Investigate this case"** (one click) or any question in **Ask the case**. |
| **Process: the agent** | Claude Opus 5.5 in a ReAct tool loop. Each step it chooses: hybrid RAG search over the documents, SQL over call and bank records (tower timelines, IMEI handset history, transactions), reading a document, or writing to its Case Diary (working memory). Guardrails won't accept a report until every suspect is either charged or cleared, with evidence. |
| **Output** | A **draft chargesheet** (s.193 BNSS): accused and roles, persons cleared, contradicted statements, money-trail graph, timeline, court-readiness gaps and next actions, with **every point cited**. Or a **cited answer** to the question asked. The IO accepts or rejects each finding, signs off, and exports to Word. Everything is written to an audit trail. |

## 3. The app
| Page | Purpose |
|---|---|
| 🗂️ Case Register | All cases with loss, amount frozen, status and evidence completeness; click to open |
| ➕ New Case | 3-step wizard + evidence checklist + record templates + column matching (+ a "load sample kit" demo) |
| 📋 Case Details | Overview, evidence file, timeline, money trail, audit trail |
| 🕵️ Investigate | Full investigation (live or replay) · 💬 Ask the case (suggested or typed questions) |
| 📝 Chargesheet Draft | Per-finding IO review, sign-off, Word export |
| 📊 AI performance | Basic RAG vs agent, evaluation, search lab, architecture |

## 4. Architecture
```
New Case wizard ──► text extraction + column matching ──► documents (paragraph chunks + metadata) ──► dense + BM25 ─► RRF ─┐
                                                      └─► CDR / bank tables (SQLite per case) ──────────────────────────────┤
                                                                                                                             ▼
             case brief + tools built from this case ──►  Claude Opus 5.5 ReAct loop (parallel tool use)  ◄──► Case Diary
                                                                    │                         │
                                                       guardrail gate (suspects resolved)    Ask the case (cited answers)
                                                                    ▼
                                        chargesheet draft + readiness check ──► IO review · sign-off · Word export · audit trail
                                                                    ▼
                                                     evaluation vs answer key (demo cases)
```

## 5. Stack
| Layer | Choice |
|---|---|
| LLM | **Claude Opus 5.5** (Anthropic Python SDK): adaptive thinking, `effort` (medium for investigation, low for Q&A), prompt caching, server-side refusal fallback |
| Agent | Hand-written ReAct loop with native tool use; event stream for live UI, replay and audit |
| Embeddings | **fastembed** `BAAI/bge-small-en-v1.5` (ONNX, CPU), incremental vector cache |
| Keyword search / fusion | **rank-bm25** + Reciprocal Rank Fusion |
| Structured data | **SQLite** per case (CDR, transactions) |
| Ingestion | **pypdf**, **python-docx**, **pandas / openpyxl** (CSV, Excel) |
| UI / hosting | **Streamlit** multipage (`st.navigation`) on Streamlit Community Cloud |
| Export | **python-docx** (Word chargesheet draft) |

## 6. RAG and agent features covered
| # | Feature | Where to see it |
|---|---|---|
| 1 | Multi-format ingestion (PDF, Word, text; CSV, Excel) with column matching and telecom-code normalisation | New Case → step 3 |
| 2 | Structure-aware chunking: one paragraph = one claim = one citation (`DOC-14 ¶4`) | Case Details → Evidence file |
| 3 | Contextual chunk headers (title and type added before embedding) | `rag/chunking.py` |
| 4 | Dense retrieval with local embeddings and incremental indexing | Search lab: *dense rank* |
| 5 | BM25 keyword retrieval (exact phone numbers, IMEIs, UTRs) | Search lab: *BM25 rank* |
| 6 | Hybrid fusion (RRF) | Search lab: *RRF score* |
| 7 | Metadata filtering; deliberate cross-case search to link cases | Search lab scope switch; "Linked cases" in the draft |
| 8 | Structured retrieval: SQL tools (CDR, tower timeline, IMEI history, transactions) | Investigation log: 💸 📞 📍 📱 |
| 9 | Dynamic tool descriptions + case brief, so it works on any case | Same agent, two different cases |
| 10 | Agentic multi-hop retrieval with tool routing (ReAct, parallel calls) | Investigation log |
| 11 | Working memory: Case Diary with source-required entries | Investigate → right panel |
| 12 | Contradiction detection across documents and records | Chargesheet → contradicted statements |
| 13 | Guardrails: step cap, cited facts, submit gate | `agent/loop.py` |
| 14 | Domain verification: court-readiness check (BSA s.63, panch witnesses, BSA s.23) | Chargesheet → 🚩 gaps |
| 15 | Conversational Q&A mode with citations and follow-ups | Investigate → 💬 Ask the case |
| 16 | Human in the loop: per-finding review, sign-off, Word export | Chargesheet Draft |
| 17 | Audit trail of every AI action | Case Details → Audit trail |
| 18 | Fair baseline + evaluation against ground truth + reliability across runs | AI performance |

## 7. Results
| | CYB-114-2026 · "digital arrest" (₹38.5 L) | CYB-131-2026 · fake trading app (₹24.5 L), **unseen case loaded through New Case** |
|---|---|---|
| Basic RAG (same model and retriever, retrieve once) | 2 / 12 | 4 / 13 |
| **CaseDiary agent** | **12 / 12** (2 of 2 runs) | **12 / 13**, no code or prompt changes (missed only the bonus archive link) |
| Agent tool calls · time · cost | ~40 · 135–175 s · $0.58–0.79 | 40 · 134 s · $0.63 |
| Ask the case (per question) | 2–11 lookups · 14–27 s · $0.06–0.18 | similar |

**What the agent found that one-shot RAG couldn't:**
- **CYB-114:** the fake-KYC scam SIM ran in the operator's own handset (an IMEI SIM swap). The mule's alibi ("I was in Malegaon") was broken by tower data and the ATM. The suspected nephew was cleared by Bengaluru towers. A linked archive case was found through the same courier number.
- **CYB-131:** the app's admin panel was traced to the operator's home broadband (IP → ISP subscriber). The crypto-exchange KYC matched the same person. The scam SIM always sat on the same towers as the operator's own SIM. The account holder's "my accountant did it" was contradicted by OTPs and a self-cheque he presented in person. The colleague the victim suspected turned out to be a co-victim.
- **Readiness gaps it found beyond the planted ones:** missing hash values at seizure, an employer record without a s.63 certificate, a crypto-exchange reply received only by email.

## 8. Why it's different
1. **It's a workflow tool, not a chatbot.** Register → evidence → investigate → review → export, with a status and an audit trail per case.
2. **It works on new cases.** A second, unseen case with a different scam and different evidence formats was loaded through the UI and investigated with no code changes.
3. **It's court-aware.** It checks whether the case will **hold up in court**, not just who did it.
4. **It's honest.** Every claim is cited and checkable in one click. There's a fair baseline and transparent scoring rules. A rubric that was too generous to the baseline was found and tightened during development, and that's documented.
5. **The human stays in charge.** Nothing is final until the IO decides each finding.

## 9. Responsible AI
- **Fictional data only.** Every person, number, account, bank and case is invented.
- **Assistive, not decisive.** The agent uses "the evidence indicates" language; every finding needs IO review; sign-off is the IO's.
- **Accountable.** Every AI tool call, question and decision is logged with a timestamp.
- **Safe public demo.** Recorded runs and suggested questions by default; live AI behind an access code.
- **Production path.** The department's own network, a real database, role-based access (IO / SHO / supervisor), and possibly on-premises models. Real case data must never be uploaded to a public demo.

## 10. Limitations and roadmap
- **No OCR yet.** Scanned PDFs need OCR before ingestion.
- **English only.** Hindi and Marathi statements would need cross-lingual embeddings.
- **Rule-based evaluation.** Next step: add LLM-as-judge and review by practitioners.
- **Auto-drafted notices.** The s.94 BNSS notices to banks and telecom companies could be drafted from the next-action list.
- **Cross-station alerts** when the same phone number or account appears in another district's case.

---

## Appendix: 3-minute demo video script
| Time | Screen | Say |
|---|---|---|
| 0:00–0:15 | Case Register | "Cyber police handle digital-arrest and fake-trading frauds where the evidence is scattered across banks, telecom companies and statements. CaseDiary.AI is an AI investigation assistant for the officer." |
| 0:15–0:45 | New Case → load the sample kit → Case Details | "A new case arrives: a fake trading app, ₹24.5 lakh. The inspector registers it and uploads the raw files: Word statements, an Excel bank export, the telecom company's CDR format. The checklist shows the evidence file is 88% complete." |
| 0:45–1:35 | Investigate → replay | "The agent investigates. It follows the money with SQL, traces the app's admin login IP to a broadband subscriber in Bhiwandi, matches the crypto-exchange KYC, and finds the scam SIM always on the same towers as that person's own phone. The Case Diary fills up live." |
| 1:35–1:55 | Ask the case: "Is Sunil Joshi involved?" | "The officer can ask anything. The victim suspected her colleague. The records show he's a co-victim who lost ₹4 lakh to the same account." |
| 1:55–2:30 | Chargesheet Draft: accused, contradictions, money graph, 🚩 gaps → accept a finding → export | "The draft chargesheet cites every point and flags what would fail in court: screenshots without a s.63 certificate, an exchange reply received only by email. The IO accepts or rejects each finding, signs off and exports to Word." |
| 2:30–2:50 | AI performance | "Basic RAG with the same model scores far lower. The agent scores 12 of 13 on this unseen case and 12/12 on the first, at well under a dollar a case." |
| 2:50–3:00 | Case Details → Audit trail | "Every AI action is logged. The officer stays in charge." |
