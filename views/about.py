"""AI performance & how it works: basic RAG vs agent, evaluation, search lab, architecture."""

import re

import pandas as pd
import streamlit as st

from core import store
from ui.common import hero, latest_report, require_case

case_id = require_case()
hero("📊 AI performance & how it works",
     "For reviewers: why an agent, how it is measured, and the RAG techniques underneath")
if not case_id:
    st.stop()

t_cmp, t_eval, t_lab, t_arch = st.tabs(["⚖️ Basic RAG vs Agent", "📊 Evaluation", "🔬 Search lab", "🧠 How it works"])

with t_cmp:
    st.markdown(f"**Case {case_id}.** Same question, same model, same retriever, different architecture.")
    st.caption("Basic RAG searches once with the question (top 8 paragraphs of this case) and answers. The agent "
               "plans, searches many times, queries SQL tables, verifies statements and keeps a diary.")
    base = store.load_run(case_id, "baseline_run")
    ev = store.load_run(case_id, "eval")
    rep_ev, _ = latest_report(case_id)
    a, b = st.columns(2)
    with a:
        st.markdown("#### 🙂 Basic RAG (retrieve once → answer)")
        if base:
            st.caption("Retrieved: " + " · ".join(h["cite"] for h in base["retrieved"]))
            with st.container(height=520):
                st.markdown(re.sub(r"^#{1,3} ", "##### ", base["answer"], flags=re.M))
        else:
            st.info("No baseline run recorded for this case.")
    with b:
        st.markdown("#### 🕵️ CaseDiary agent (plan → tools → verify → report)")
        if rep_ev:
            r = rep_ev["report"]
            with st.container(height=520):
                st.markdown(r["summary"])
                st.markdown("**Accused:** " + ", ".join(f"{x['name']} ({x['role']})" for x in r["accused"]))
                st.markdown("**Cleared:** " + (", ".join(x["name"] for x in r["cleared"]) or "—"))
                st.markdown(f"**Contradictions:** {len(r['contradictions'])} · **Readiness gaps:** {len(r['readiness_gaps'])}")
        else:
            st.info("Not investigated yet.")
    if ev and ev.get("baseline") and ev.get("agent"):
        n = len(ev["agent"]["checks"])
        c1, c2 = st.columns(2)
        c1.metric("Basic RAG: answer-key checks", f"{sum(ev['baseline']['checks'].values())}/{n}")
        c2.metric("Agent: answer-key checks", f"{sum(ev['agent']['checks'].values())}/{n}")

with t_eval:
    ev = store.load_run(case_id, "eval")
    if not store.answer_key(case_id):
        st.info("This case has no answer key (normal for real cases). Evaluation runs on demo cases whose truth we "
                "wrote: see CYB-114-2026.")
    elif not ev or not ev.get("agent"):
        st.info("Run `python eval/run_eval.py --case " + case_id + "` after recording runs.")
    else:
        st.caption("Demo cases have a ground-truth answer key the agent never sees. Each check is a transparent "
                   "rule in the case's answer_key.json, applied the same way to both systems.")
        rows = [{"Check": k, "Basic RAG": "✅" if (ev.get("baseline") or {}).get("checks", {}).get(k) else "❌",
                 "Agent": "✅" if v else "❌"} for k, v in ev["agent"]["checks"].items()]
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
        ag, bs = ev["agent"], ev.get("baseline")
        m = st.columns(4)
        m[0].metric("Basic RAG", f"{sum(bs['checks'].values())}/{len(rows)}" if bs else "—")
        m[1].metric("Agent", f"{sum(ag['checks'].values())}/{len(rows)}")
        m[2].metric("Agent tool calls", ag["stats"]["tool_calls"])
        m[3].metric("Agent cost / run", f"${ag['stats']['cost_usd']:.2f}",
                    f"basic RAG ${bs['stats']['cost_usd']:.3f}" if bs else None, delta_color="off")
        st.caption(f"{ag['stats']['cache_read_tokens']:,} input tokens served from the prompt cache in this run.")
        if ev.get("agent_runs"):
            st.markdown("**Reliability: every recorded agent run, scored the same way**")
            st.dataframe(pd.DataFrame([{"run": k, "score": f"{v['score']}/{v['of']}", "tool calls": v["tool_calls"],
                                        "seconds": v["seconds"], "cost (USD)": v["cost_usd"]}
                                       for k, v in ev["agent_runs"].items()]), hide_index=True)
        with st.expander("How the checks were made fair"):
            st.markdown(
                "- Related clues must appear in the **same line / record**; scattered keywords don't count.\n"
                "- The agent must list names in structured `accused` / `cleared` fields; the baseline only has "
                "to mention them.\n"
                "- During development a looser rubric gave the baseline credit for 'catching' lies it said it "
                "could not find; the rubric was tightened and applied to both systems.")

with t_lab:
    st.caption("Dense = embedding similarity (meaning). BM25 = keyword match (exact numbers, names). RRF fuses "
               "the two rankings. Try a phone number, then a paraphrase such as “he said his account was hacked”.")
    q = st.text_input("Query", "he was at his shop the whole day")
    c1, c2 = st.columns(2)
    scope = c1.radio("Scope", [f"This case only ({case_id})", "Whole station (all cases + archive)"], horizontal=True)
    k = c2.slider("Top k", 3, 12, 6)
    if q:
        from rag.retriever import get_retriever
        hits = get_retriever().search(q, k=k, case_id=None if scope.startswith("Whole") else case_id)
        st.dataframe(pd.DataFrame([{"cite": h["cite"], "case": h["case_id"], "dense rank": h["dense_rank"],
                                    "BM25 rank": h["bm25_rank"], "RRF score": h["score"], "text": h["text"]}
                                   for h in hits]), hide_index=True, width="stretch")

with t_arch:
    st.graphviz_chart("""digraph A { rankdir=LR; bgcolor="transparent"; node [shape=box, style="rounded,filled",
      fontname="Helvetica", fontsize=11, fillcolor="#eef4fb"];
      newc [label="New Case wizard\\nFIR · parties · uploads"]; ingest [label="Text extraction\\n+ column matching"];
      docs [label="Documents\\n(paragraph chunks + metadata)"]; tables [label="CDR · bank tables\\n(SQLite per case)"];
      idx [label="Dense (bge-small)\\n+ BM25 → RRF"];
      agent [label="Claude Opus 5.5\\nReAct tool loop", fillcolor="#fdebd0"];
      diary [label="Case Diary\\n(working memory)"]; gate [label="Guardrails\\nsources · suspects resolved"];
      report [label="Chargesheet draft\\n+ readiness check", fillcolor="#d5f5e3"]; ask [label="Ask the case\\n(cited answers)", fillcolor="#d5f5e3"];
      io [label="IO review\\n+ Word export + audit", fillcolor="#fcf3cf"];
      newc -> ingest; ingest -> docs -> idx -> agent; ingest -> tables -> agent; agent -> diary -> agent;
      agent -> gate -> report -> io; agent -> ask; }""")
    st.markdown("""
| Concept | Where | Why it matters here |
|---|---|---|
| Structure-aware chunking + contextual headers | `rag/chunking.py` | One paragraph = one claim = one citation (`DOC-14 ¶4`) |
| Hybrid retrieval (dense + BM25) with RRF | `rag/retriever.py` | Narratives need meaning; phone numbers and UTRs need exact match |
| Incremental indexing | vector cache by text hash | New cases become searchable in seconds |
| Metadata filtering | `case_id`, `doc_type`, `person` | Keeps other cases out unless the agent looks for links |
| Structured retrieval (SQL tools) | `rag/sql_tools.py` | Times, towers and amounts are filters, not similarity |
| Dynamic tool descriptions + case brief | `agent/tools.py`, `agent/prompts.py` | The same agent works on any case loaded, no code changes |
| Agentic loop with tool routing | `agent/loop.py` | Each answer creates the next question (multi-hop) |
| External memory | `agent/diary.py` | Findings survive long tool outputs; shown live |
| Guardrails / self-verification | submit gate, cited facts | Report rejected until every suspect is resolved |
| Human in the loop | Chargesheet review + sign-off | Nothing is final until the IO decides |
| Audit trail | `audit.jsonl` per case | Shows how every conclusion was reached |
| Evaluation vs ground truth | `eval/run_eval.py` | Measured, not "looks right" |
| Prompt caching + refusal fallback | `agent/llm.py` | Lower cost per step; robust on sensitive crime text |
""")
