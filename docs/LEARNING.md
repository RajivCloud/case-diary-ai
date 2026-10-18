# CaseDiary.AI: a learning guide

This guide explains every step of the build. Each step has three parts:

* **Why:** the reason the step exists.
* **What:** what we built.
* **How:** how it works, with the file to open.

Each step ends with the **AI concept** it teaches.

---

## Step 0: Choosing the problem

**Why.** Most RAG demos work like this: a user asks a question, the app retrieves a few chunks once, and the model answers. That only works when one passage holds the answer. Real investigations aren't like that. The answer is spread across many documents and tables, and some sources lie.

**What.** A fictional "digital arrest" cyber-fraud case at Cyber Police Station, Pune City, laid out the way Indian criminal procedure works: FIR, statements, bank and telecom replies, seizure, forensic report, chargesheet.

**How.** The case is designed so that the answer is only reachable in several hops:

`victim's transfer → beneficiary account → OTP forwarding → scam SIM → handset IMEI → the real person`

> **Concept: multi-hop question answering.** If the answer needs facts A, B and C, and you only learn to look for C after finding B, then one search can't work. You need a loop.

---

## Step 1: Ground truth first, then the data (`data/case_truth.json`)

**Why.** If you write documents first and decide the truth later, your clues will contradict each other. You'll also have no way to measure whether the AI got it right.

**What.** An answer key containing:

* the real roles of each person;
* the key links in the evidence;
* two planted lies;
* one red herring (the nephew);
* three chargesheet readiness gaps;
* a bonus link to an archive case.

**How.** Every document and table row was written to agree with the answer key. We then checked the data for consistency. For example, we found that 04-Oct-2026 is a Sunday, when bank branches are closed, so we moved the third transfer to Monday.

> **Concept: synthetic data with ground truth.** It's how you build realistic test sets when real data is private (police files, medical records). The answer key enables **evaluation** later (Step 8).

---

## Step 2: Bulky, noisy data (`scripts/generate_tables.py`, `scripts/generate_archive.py`)

**Why.** Twenty-three short documents fit in one prompt. A judge could fairly ask: "why not just paste everything into Claude?"

**What.**

* About 1,800 call-record rows and 330 bank transactions, with the important rows buried in ordinary daily noise.
* 12 unrelated archive FIRs that use the same vocabulary ("digital arrest", "OTP", "IMPS").

**How.** A seeded random generator writes the noise. Because the seed is fixed, every run produces the same data. The planted rows are written explicitly.

> **Concept: why retrieval exists.** RAG matters when the data is too big, too noisy or too costly to read in full. Real case files are thousands of pages.

---

## Step 3: Chunking (`rag/chunking.py`)

**Why.** Retrieval quality depends on what counts as one unit of meaning.

**What.**

* **One paragraph becomes one chunk.** Each chunk gets a stable citation such as `DOC-14 ¶4`.
* **Each chunk carries metadata:** `case_id`, `doc_type`, `date`, `persons`.

**How.** Each markdown file has a small header (front matter), and paragraphs are separated by blank lines. Before embedding, we add the document title to the start of each chunk, for example "Statement of Imran Shaikh under s.180 BNSS: I was at my shop all day…". Without the title, "I was at my shop all day" has no speaker.

> **Concepts: structure-aware chunking and contextual chunk headers.** Splitting every 500 characters can cut a claim in half. Splitting along the document's own structure keeps each claim whole, and the header keeps its context.

---

## Step 4: Hybrid retrieval (`rag/retriever.py`)

**Why.** Police files mix narrative ("he said he was hacked") with identifiers ("8969204117", "UTR SNBR526100338841"). Each kind of search fails on one of them:

* Embedding search misses exact numbers.
* Keyword search misses paraphrases.

**What.** Two searches whose rankings are merged:

1. **Dense search:** local embeddings from `fastembed` with the `bge-small` model, compared by cosine similarity.
2. **Sparse search:** BM25 keyword scoring.
3. **Merge:** Reciprocal Rank Fusion.

On top of that, **metadata filters** narrow the search by case, document type or person.

**How.**

* **RRF formula:** `score = Σ 1/(60 + rank)`. It uses only each chunk's rank, so the two very different scoring scales never have to be compared.
* **Try it:** the app's *Search lab* tab shows each result's dense rank and BM25 rank side by side.

> **Concepts:** embeddings, cosine similarity, BM25, hybrid search, rank fusion, metadata filtering. (A test proves the filter keeps the look-alike archive case CYB-098 out.)

---

## Step 5: Structured retrieval with SQL (`rag/sql_tools.py`)

**Why.** "Where was Imran's phone between 12:00 and 16:00 on 05-Oct?" is a **filter**, not a similarity question. Turning call records into embeddings would blur exact times and numbers.

**What.** The tables live in SQLite, and the agent gets precise tools:

* `query_cdr` and `query_transactions` filter the raw records;
* `location_timeline` shows tower movements in time order (the alibi checker);
* `imei_lookup` shows which SIMs ran in a handset, and in what order.

**How.** The tools return **ordered segments**, not totals. Our first version grouped by total, and that hid the SIM swap: Sameer's SIM, then the scam SIM, then Sameer's SIM again. Order is evidence.

> **Concepts: structured RAG / text-to-tool routing.** Choose the retrieval method by data type. The agent decides which tool fits each question.

---

## Step 6: Tools and the agent loop (`agent/tools.py`, `agent/loop.py`)

**Why.** Each finding raises the next question. Only a loop can follow that chain.

**What.**

* Eight tools are described to Claude: search, read, 4 SQL tools, diary, submit.
* A **ReAct loop** repeats: Claude reasons, calls tools, and reads the results.

**How.**

1. We send Claude the system prompt, the tool descriptions and the conversation.
2. Claude replies with `tool_use` blocks, which may come several at once (parallel calls).
3. Our code runs each tool and sends back `tool_result` blocks.
4. Steps 1–3 repeat until Claude calls `submit_report`.

The **tool descriptions** are effectively part of the prompt. They are how Claude decides between text search and SQL.

> **Concepts:** function calling / tool use, ReAct, parallel tool calls, tool routing. A few model details: Opus 5.5 always thinks adaptively; we set `effort` and show its summarized reasoning in the log.

---

## Step 7: Memory and guardrails (`agent/diary.py`, submit gate)

**Why.**

* Long investigations bury early findings under tool output.
* Agents sometimes "finish" early with loose ends.

**What.**

* **A Case Diary** (working memory) with entry types FACT, LEAD, CONTRADICTION, SUSPECT, CLEARED and GAP. A FACT without a source is rejected.
* **A submit gate:** the report is rejected while any suspect is neither accused nor cleared.

**How.** The diary is a Python object that the agent writes to through a tool, and the UI renders it live. The gate returns the problems to the agent as the tool result, so the agent fixes its own gaps and tries again.

> **Concepts:** external memory / agent state, grounding (citation requirement), self-verification loops, guardrails.

---

## Step 8: The baseline comparison and evaluation (`agent/baseline.py`, `eval/run_eval.py`)

**Why.** "It looks good" is not evidence. To show the agent helps, compare it with a fair baseline and measure both.

**What.**

* **Baseline:** the same retriever and the same model, but it searches once and answers once.
* **Evaluation:** 12 transparent checks against the answer key, applied to both systems.

**How.** The agent is held to a stricter standard. Names must appear in its structured `accused` and `cleared` lists, while the baseline only has to mention them. The evaluation also records tool calls, seconds, tokens and cost.

**What actually happened, and the lesson.** The first rubric matched keywords anywhere in the text. Basic RAG scored 5/12, including "caught both lies", even though its answer said *"No statement in these excerpts is directly contradicted by a record."* We made the rubric stricter: related clues must appear in the **same line or record**. Basic RAG dropped to 2/12. Then two checks wrongly failed the agent:
- It wrote "Sameer **Yusuf** Ansari". We fixed this with first-name + last-name matching, and fixed the same bug in the guardrail.
- It split one gap across its `impact` and `fix` fields. We fixed this by treating one record as one unit.

Final result: **basic RAG 2/12, agent 12/12 on both recorded runs.** Read the outputs before trusting a score. A grader can be wrong in either direction.

> **Concepts:** ablation (change one thing at a time), evaluation against ground truth, auditing your own evaluator, reliability across runs, cost and latency trade-offs.

---

## Step 9: Production touches (`agent/llm.py`, `app.py`)

**Why.** A public demo link must be cheap, safe and reliable.

**What.**

* **Prompt caching:** the system prompt, tools and history prefix are reused across loop steps, which makes each step cheaper.
* **Server-side refusal fallback** (`fallbacks="default"`): crime-related text can occasionally trip a safety classifier, and this lets the API retry on a recommended model.
* **Replay mode:** a recorded real run plays back, free and instant.
* **Live mode:** runs the real agent, behind an access code and a per-session limit.

> **Concepts:** prompt caching (exact prefix match, which is why the prompts contain no timestamps), cost control, safe deployment.

---

---

# Part 2: from a demo to a tool a police station could use

## Step 10: One folder per case (`core/store.py`)

**Why.** The first version was hard-wired to one case: the case ID, phone numbers and accounts were written into the code and prompts. A real station has many cases, and inspectors can't edit code.

**What.** Each case lives in its own folder, `data/cases/<CASE-ID>/`:
- `case.json`: FIR details, parties, status
- `documents/` and `tables/`: the evidence
- `runs/`: investigations and answers
- `review.json`: the IO's decisions
- `audit.jsonl`: every action
- `answer_key.json`: optional, demo cases only

**How.** Every module takes a `case_id`:
- **Retrieval** filters by it.
- **SQL tools** open that case's own tables.
- **Everything else in the station** becomes "the archive", searched only when the agent looks for links between cases.

> **Concept: multi-tenancy by data partition.** One system, many isolated datasets, with deliberate cross-dataset search.

## Step 11: Ingestion of real-world formats (`core/store.py`, `ui/evidence.py`)

**Why.** Police receive PDFs, Word files and Excel/CSV exports, and every bank and telecom company formats them differently (for example "A Party", "Call Date", "MOC", or separate withdrawal and deposit columns).

**What.**
- **Documents:** text is extracted from PDF (`pypdf`) and Word (`python-docx`), then re-paragraphed.
- **Records:** columns are matched to a standard format, with auto-guessed suggestions.
- **Normalisation:** telecom codes (MOC → CALL_OUT), date + time columns, and debit/credit columns all become one standard shape.

**How.** The sample kit `sample_upload/CYB-131-2026` holds raw files in four different formats. `core/sample_kit.py` loads them through the exact same functions the wizard uses.

> **Concepts:** ETL (extract, transform, load), schema mapping, data normalisation. In practice, most RAG quality problems are ingestion problems.

## Step 12: Incremental indexing (`rag/retriever.py`)

**Why.** When an IO uploads documents, they must become searchable at once, without re-embedding the whole station.

**How.**
- Each paragraph's vector is cached under a hash of its text, so only new paragraphs are embedded.
- The retriever rebuilds itself automatically when any document file changes.

> **Concept: incremental / content-addressed indexing.**

## Step 13: Dynamic tools and a case brief (`agent/tools.py`, `agent/prompts.py`)

**Why.** The agent must work on a case it has never seen, with no code changes.

**What.**
- **Tool descriptions** are generated from the selected case: which numbers we hold CDRs for, whose accounts we hold statements for.
- **A case brief** is added to the system prompt: FIR facts, parties, a table of contents of the documents, and which evidence is still missing.

**How.** The generic instructions stay fixed. Only the case brief changes, and it stays byte-identical for a given case, so prompt caching still works across every step of a run.

> **Concepts:** context engineering, dynamic tool descriptions, "table of contents" grounding.

## Step 14: Ask the case (`run_question` in `agent/loop.py`)

**Why.** Officers have specific questions ("Where was this phone at 3 pm?"), not just "investigate everything".

**What.** The same tools in a shorter loop (up to 10 steps), at low effort, with no diary and no report. It answers directly, gives cited evidence bullets, and says what's missing if the records don't show the answer.

**How.**
- **Follow-up questions** get the last few Q&A turns as context.
- **Suggested questions** play instantly from recorded answers, which is free and reliable for demos.

> **Concepts:** task-specific agent modes, cost and latency tuning with `effort`, conversational memory.

## Step 15: Human in the loop, export and audit (`views/chargesheet.py`, `core/export.py`)

**Why.** In policing, an AI draft must never become a decision by default.

**What.**
- **Per-finding review:** each finding gets Accept, Reject or Needs work, plus an optional note.
- **Sign-off** is only possible after every finding has been decided.
- **Word export** leaves out rejected findings and carries the IO's notes.
- **The audit trail** logs every AI tool call, question and review decision with a timestamp.

> **Concepts:** human-in-the-loop design, accountability, explainability ("how was this conclusion reached?").

## Step 16: The generalisation test (CYB-131-2026)

**Why.** "It works on the case I designed" is weak evidence. A judge will ask whether it's rigged.

**What.** A second case, generated truth-first like the first, but different in every way:
- a different scam (a fake trading app);
- different people;
- a different way to identify the operator (admin-panel IP → ISP subscriber, plus crypto-exchange KYC, plus a scam SIM sitting on the same towers as the operator's own SIM);
- different red herrings (a co-victim, and an accountant who had no access).

**How.** It's loaded through the New Case pipeline from raw files, then investigated with **no code or prompt changes**, and scored against its own answer key.

> **Concepts:** generalisation, held-out evaluation, avoiding over-fitting the prompt to one example.

## Responsible AI in this project

* **Fictional data only.** Every person, number and account is invented.
* **The agent assists; the IO decides.** Its language is "evidence indicates", never a verdict.
* **Every claim cites a source**, and each source opens in one click.
* **It checks admissibility**, not only "who did it": BSA s.63 certificates, independent panch witnesses, and s.23 BSA (an admission to police isn't a confession).
* Legal section numbers are used for realism. Verify them before any real-world use.
