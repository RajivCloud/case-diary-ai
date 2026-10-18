"""Rendering helpers shared by the pages."""

from __future__ import annotations

import html
import json
import re

import pandas as pd
import streamlit as st

from core import store
from rag.chunking import load_all_chunks

TOOL_ICON = {
    "search_case_files": "🔎", "read_document": "📄", "query_transactions": "💸", "query_cdr": "📞",
    "location_timeline": "📍", "imei_lookup": "📱", "update_case_diary": "📓", "submit_report": "📝",
}
TOOL_LABEL = {
    "search_case_files": "Hybrid search (RAG)", "read_document": "Read document",
    "query_transactions": "SQL: bank transactions", "query_cdr": "SQL: call records",
    "location_timeline": "SQL: tower timeline", "imei_lookup": "SQL: handset (IMEI) history",
    "update_case_diary": "Write to Case Diary", "submit_report": "Submit chargesheet draft",
}
DIARY_STYLE = {
    "FACT": ("✅", "#1f7a4d"), "LEAD": ("🧭", "#3b6fb6"), "CONTRADICTION": ("⚠️", "#c0392b"),
    "SUSPECT": ("👤", "#b9770e"), "CLEARED": ("🟢", "#138d75"), "GAP": ("🚩", "#8e44ad"),
}
CITE = re.compile(r"(DOC-\d+ ¶\d+|CYB-\d+-\d{4}-FIR ¶\d+)")


def chunk_map(case_id: str) -> dict:
    """Citation -> chunk, preferring the active case (doc ids repeat across cases)."""
    out = {}
    for c in load_all_chunks():
        if c.chunk_id not in out or c.case_id == case_id:
            out[c.chunk_id] = c
    return out


# ------------------------------------------------------------------ investigation steps
def summarize_input(name: str, args: dict) -> str:
    if name == "search_case_files":
        extra = " (incl. other cases)" if args.get("include_archive") else ""
        return f"“{args.get('query', '')}”{extra}"
    if name == "update_case_diary":
        n = len(args.get("entries", []))
        return f"{n} entr{'y' if n == 1 else 'ies'}"
    if name == "submit_report":
        return f"{len(args.get('accused', []))} accused, {len(args.get('readiness_gaps', []))} gaps"
    return ", ".join(f"{k}={v}" for k, v in args.items())


def summarize_output(name: str, out: dict) -> str:
    if "error" in out:
        return f"error: {out['error']}"
    if name == "search_case_files":
        return " · ".join(h["cite"] for h in out.get("results", [])) or "no results"
    if name in ("query_transactions", "query_cdr"):
        s = f"{out.get('total_rows', 0)} rows"
        return s + (f", sum ₹{out['sum_amount']:,}" if "sum_amount" in out else "")
    if name == "location_timeline":
        return " → ".join(m["cell_location"] for m in out.get("movements", [])) or "no records"
    if name == "imei_lookup":
        seq = out.get("sim_sequence") or out.get("handset_sequence") or []
        key = "target_number" if "sim_sequence" in out else "imei"
        return " → ".join(f"{s[key]} ({s['from'][:10]}…{s['to'][:10]})" for s in seq) or "no records"
    if name == "update_case_diary":
        return f"added {out.get('added')}" + (f", rejected {len(out['rejected'])}" if out.get("rejected") else "")
    if name == "read_document":
        return out.get("title", "")
    if name == "submit_report":
        return "accepted ✅" if out.get("accepted") else "rejected by guardrail ❌"
    return ""


def step_html(ev: dict, call_input: dict) -> str:
    name = ev["name"]
    return (f"<div class='step'><b>#{ev['n']} {TOOL_ICON.get(name, '🔧')} {TOOL_LABEL.get(name, name)}</b> "
            f"<span class='pill'>{html.escape(summarize_input(name, call_input))}</span><br>"
            f"<span style='font-size:.85em'>→ {html.escape(summarize_output(name, ev['output']))}</span></div>")


def render_event(ev: dict, log, diary_box, state: dict, now=None) -> None:
    t = ev["type"]
    if t == "tool_call":
        state["pending"] = ev
        if now is not None:
            now.info(f"**Step {ev['n']}:** {TOOL_ICON.get(ev['name'], '🔧')} {TOOL_LABEL.get(ev['name'], ev['name'])}"
                     f" — {summarize_input(ev['name'], ev['input'])}")
    elif t == "thinking":
        log.markdown(f"<div class='step' style='opacity:.8'>💭 <i>{html.escape(ev['text'][:600])}</i></div>",
                     unsafe_allow_html=True)
    elif t == "text":
        log.markdown(f"<div class='step'>🗣️ {html.escape(ev['text'][:600])}</div>", unsafe_allow_html=True)
    elif t == "tool_result":
        call = state.pop("pending", {"input": {}})
        log.markdown(step_html(ev, call.get("input", {})), unsafe_allow_html=True)
    elif t == "gate":
        log.error("🛑 Guardrail rejected the report: " + "; ".join(ev["problems"]))
    elif t == "diary" and diary_box is not None:
        with diary_box.container():
            for e in ev["entries"][::-1]:
                diary_entry(e)
    elif t == "error":
        log.error(ev["text"])


def diary_entry(e: dict) -> None:
    icon, color = DIARY_STYLE.get(e["type"], ("•", "#666"))
    person = f" <b>{html.escape(e['person'])}</b> —" if e.get("person") else ""
    st.markdown(
        f"<div style='border-left:4px solid {color};padding:4px 10px;margin:4px 0;'>"
        f"<span style='color:{color};font-weight:600;font-size:0.8em'>{icon} {e['type']}</span><br>"
        f"{person} {html.escape(e['text'])}</div>", unsafe_allow_html=True)
    if e.get("sources"):
        st.caption(" ".join(f"`{s}`" for s in e["sources"]))


# ------------------------------------------------------------------ money trail graph
NODE_ALIASES = [  # the model names the same account in different ways; map known patterns to one node
    (("atm",), "Cash: ATM"),
    (("self-cheque", "self cheque", "cheque", "branch cash"), "Cash: branch withdrawal"),
    (("crypto", "usdt", "p2p", "exchange", "coinvault"), "Crypto exchange"),
]


def _node(name: str, parties: list[dict]) -> str:
    low = name.lower()
    for p in parties:  # a known party first: match by first+last name or account number
        nm = p.get("name", "")
        tokens = nm.lower().split()
        if (p.get("account_no") and p["account_no"] in name) or (len(tokens) >= 2 and tokens[0] in low and tokens[-1] in low):
            return f"{nm}\n({p.get('role', '')[:28]})"
    for keys, label in NODE_ALIASES:
        if any(k in low for k in keys):
            return label
    return " ".join(re.sub(r"[()/,]", " ", name).split()[:3])


def money_graph(trail: list[dict], parties: list[dict]) -> str:
    edges: dict[tuple[str, str], int] = {}
    for t in trail:
        key = (_node(t.get("from", "?"), parties), _node(t.get("to", "?"), parties))
        if key[0] != key[1]:  # skip self-loops created by merging aliases
            edges[key] = edges.get(key, 0) + int(t.get("amount") or 0)
    lines = ['digraph G { rankdir=LR; bgcolor="transparent";',
             'node [shape=box, style="rounded,filled", fillcolor="#fdf2e9", fontname="Helvetica", fontsize=11];',
             'edge [fontname="Helvetica", fontsize=10, color="#c0392b"];']
    for (a, b), amt in edges.items():
        lines.append(f'{json.dumps(a)} -> {json.dumps(b)} [label="₹{amt / 1e5:.1f} L"];')
    lines.append("}")
    return "\n".join(lines)


# ------------------------------------------------------------------ citations
def cite_inspector(text: str, key: str, case_id: str) -> None:
    cites = sorted(set(CITE.findall(text)), key=lambda c: (c.split(" ")[0], int(c.split("¶")[1])))
    if not cites:
        return
    pick = st.selectbox("🔍 Inspect a cited source paragraph", ["—"] + cites, key=key)
    cm = chunk_map(case_id)
    if pick != "—" and pick in cm:
        c = cm[pick]
        st.info(f"**{c.chunk_id} — {c.title}** ({c.date}, case {c.case_id})\n\n{c.text}")


# ------------------------------------------------------------------ timeline
def evidence_timeline(case_id: str, min_amount: int = 100000) -> pd.DataFrame:
    """Deterministic timeline: FIR, every document by date, and large transactions."""
    c = store.load_case(case_id)
    rows = [{"when": c.get("fir_date", ""), "event": f"FIR {c.get('fir_no')} registered", "source": "case.json",
             "kind": "📄 Case"}]
    for d in store.list_documents(case_id):
        rows.append({"when": d.get("date", ""), "event": d.get("title", ""), "source": d.get("doc_id"),
                     "kind": "📄 Document"})
    tx = store.load_table(case_id, "transactions")
    if len(tx):
        big = tx[pd.to_numeric(tx.amount, errors="coerce").fillna(0) >= min_amount]
        big = big[big.direction == "DR"]
        for _, r in big.iterrows():
            to = r.counterparty_name or r.location or r.mode
            rows.append({"when": r.txn_time, "event": f"{r.account_holder} → {to}: ₹{int(r.amount):,} ({r.mode})",
                         "source": f"TXN {r.txn_id}", "kind": "💸 Money"})
    df = pd.DataFrame(rows)
    return df.sort_values("when").reset_index(drop=True) if len(df) else df
