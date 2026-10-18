"""Evidence file panel: checklist, documents, and records import with column matching.

Used by New Case (step 3) and Case Details (Evidence file tab).
"""

from __future__ import annotations

import re

import pandas as pd
import streamlit as st

from core import store

GUESS = {  # source column names commonly seen in telecom / bank exports
    "target_number": ["a party", "a_party", "msisdn", "target", "calling", "own number", "subscriber"],
    "other_number": ["b party", "b_party", "other", "called", "b number", "party b"],
    "call_type": ["call type", "type", "call_type", "usage"],
    "start_time": ["start_time", "datetime", "date time", "timestamp"],
    "duration_sec": ["duration", "dur"],
    "imei": ["imei"],
    "cell_id": ["cell id", "first cell", "cgi", "cell_id", "lac"],
    "cell_location": ["address", "location", "tower", "site"],
    "date": ["date", "txn date", "call date", "value date", "tran date"],
    "time": ["time", "call time"],
    "txn_id": ["txn id", "transaction id", "txn_id", "tran id"],
    "account_no": ["account no", "account number", "a/c", "account_no"],
    "account_holder": ["holder", "account name", "customer name"],
    "txn_time": ["txn_time", "transaction date time", "datetime"],
    "direction": ["dr/cr", "direction", "cr/dr", "type"],
    "amount": ["amount", "amt"],
    "debit": ["withdrawal", "debit", "dr amount", "withdrawal amt"],
    "credit": ["deposit", "credit", "cr amount", "deposit amt"],
    "mode": ["mode", "channel", "instrument"],
    "counterparty_account": ["beneficiary account", "counterparty account", "to account", "remitter account"],
    "counterparty_name": ["beneficiary", "counterparty", "remitter", "party name"],
    "utr": ["utr", "ref", "chq/ref", "reference", "rrn"],
    "remarks": ["narration", "remarks", "description", "particulars"],
    "location": ["atm", "branch", "location"],
}


def _guess(col: str, source_cols: list[str]) -> str:
    norm = {c: re.sub(r"[^a-z0-9/ ]", " ", c.lower()).strip() for c in source_cols}
    if col in source_cols:
        return col
    for hint in GUESS.get(col, []):
        for c, n in norm.items():
            if n == hint:
                return c
    for hint in GUESS.get(col, []):
        for c, n in norm.items():
            if hint in n:
                return c
    return ""


def checklist(case_id: str) -> None:
    inv = store.inventory(case_id)
    st.progress(inv["completeness"] / 100, text=f"Evidence file {inv['completeness']}% complete")
    cols = st.columns(2)
    for i, item in enumerate(inv["items"]):
        mark = "✅" if item["present"] else ("🔴" if item["essential"] else "⚪")
        tag = "essential" if item["essential"] else "helpful"
        unit = "rows" if item["kind"] == "table" else "docs"
        cols[i % 2].markdown(f"{mark} **{item['label']}** <small>({tag}) · {item['count']} {unit}</small>",
                             unsafe_allow_html=True)
    st.caption("Missing items don't stop the investigation: the agent reports them as gaps and next actions.")


def add_documents(case_id: str) -> None:
    files = st.file_uploader("Upload documents (PDF, Word, text)", type=["pdf", "docx", "txt", "md"],
                             accept_multiple_files=True, key=f"docs_{case_id}")
    types = list(store.DOC_TYPES)
    if files:
        st.caption("Check the type, title and date for each document, then add them to the case file.")
        rows = []
        for f in files:
            guess = next((t for t, kw in [("fir", "fir"), ("complaint", "ncrp"), ("complaint", "complaint"),
                                          ("statement_180", "statement"), ("bank_reply", "bank"),
                                          ("telecom_reply", "telecom"), ("telecom_reply", "imei"),
                                          ("platform_reply", "platform"), ("platform_reply", "isp"),
                                          ("seizure_memo", "seizure"), ("arrest_memo", "arrest"),
                                          ("fsl_report", "fsl"), ("fsl_report", "forensic"), ("io_note", "note")]
                          if kw in f.name.lower()), "third_party_letter")
            c1, c2, c3, c4 = st.columns([2, 2, 3, 1.3])
            c1.markdown(f"📄 `{f.name}`")
            t = c2.selectbox("Type", types, index=types.index(guess), format_func=lambda x: store.DOC_TYPES[x],
                             key=f"t_{case_id}_{f.name}", label_visibility="collapsed")
            title = c3.text_input("Title", value=re.sub(r"[_-]+", " ", f.name.rsplit(".", 1)[0]).strip().title(),
                                  key=f"ti_{case_id}_{f.name}", label_visibility="collapsed")
            date = c4.text_input("Date", placeholder="YYYY-MM-DD", key=f"dt_{case_id}_{f.name}",
                                 label_visibility="collapsed")
            rows.append((f, t, title, date))
        if st.button(f"➕ Add {len(files)} document(s) to the case file", type="primary", key=f"add_{case_id}"):
            added, failed = [], []
            for f, t, title, date in rows:
                try:
                    text = store.extract_text(f.name, f.getvalue())
                    added.append(store.add_document(case_id, text, t, title, date, source=f.name))
                except Exception as exc:
                    failed.append(f"{f.name}: {exc}")
            if added:
                st.success(f"Added {', '.join(added)}. They are now searchable by the agent.")
            for msg in failed:
                st.error(msg)

    with st.expander("✍️ Or paste a document's text"):
        with st.form(f"paste_{case_id}", clear_on_submit=True):
            c1, c2, c3 = st.columns([2, 3, 1.3])
            t = c1.selectbox("Type", types, format_func=lambda x: store.DOC_TYPES[x])
            title = c2.text_input("Title")
            date = c3.text_input("Date", placeholder="YYYY-MM-DD")
            text = st.text_area("Text (blank line between paragraphs)", height=180)
            if st.form_submit_button("Add document") and text.strip() and title.strip():
                st.success(f"Added {store.add_document(case_id, text, t, title, date, source='pasted')}.")


def add_records(case_id: str) -> None:
    kind = st.radio("Record type", ["cdr", "transactions"], horizontal=True, key=f"kind_{case_id}",
                    format_func=lambda k: "📞 Call detail records (CDR)" if k == "cdr" else "💸 Bank statement")
    c1, c2 = st.columns([3, 1])
    up = c1.file_uploader("Upload CSV or Excel exactly as received", type=["csv", "xlsx"], key=f"rec_{case_id}_{kind}")
    c2.download_button("⬇️ Standard template", store.template_csv(kind), file_name=f"{kind}_template.csv",
                       help="Use this format to skip column matching.", key=f"tpl_{case_id}_{kind}")
    if not up:
        return
    try:
        raw = store.read_tabular(up.name, up.getvalue())
    except Exception as exc:
        st.error(f"Could not read the file: {exc}")
        return
    src = list(raw.columns)
    st.caption(f"{len(raw):,} rows · columns found: {', '.join(src)}")
    st.dataframe(raw.head(5), hide_index=True, width="stretch")

    st.markdown("**Match the columns** (auto-filled where we recognised the name; check before importing)")
    opts = [""] + src
    mapping, constants = {}, {}
    fields = list(store.TABLE_COLUMNS[kind])
    extra = ["date", "time"] if kind == "cdr" else ["date", "time", "debit", "credit"]
    grid = st.columns(3)
    for i, col in enumerate(fields + extra):
        helptext = store.TABLE_HELP[kind].get(col, {"date": "Date column (if date and time are separate)",
                                                    "time": "Time column (if separate)",
                                                    "debit": "Withdrawal / debit amount column",
                                                    "credit": "Deposit / credit amount column"}.get(col, ""))
        g = _guess(col, src)
        mapping[col] = grid[i % 3].selectbox(col, opts, index=opts.index(g) if g in opts else 0, help=helptext,
                                             key=f"map_{case_id}_{kind}_{col}") or None
    if kind == "transactions":
        st.markdown("**Statement details** (used when the file has no such column)")
        k1, k2, k3 = st.columns(3)
        constants["account_no"] = k1.text_input("Account number", key=f"c_acc_{case_id}")
        constants["account_holder"] = k2.text_input("Account holder", key=f"c_hold_{case_id}")
        constants["bank"] = k3.text_input("Bank", key=f"c_bank_{case_id}")
    else:
        constants["target_number"] = st.text_input("Phone number this CDR belongs to (if not a column)",
                                                   key=f"c_tn_{case_id}")
    try:
        mapped = store.map_columns(raw, kind, {k: v for k, v in mapping.items() if v}, constants)
    except Exception as exc:
        st.error(f"Column matching problem: {exc}")
        return
    st.markdown(f"**Preview in standard format** · {len(mapped):,} valid rows")
    st.dataframe(mapped.head(8), hide_index=True, width="stretch")
    if st.button(f"📥 Import {len(mapped):,} rows", type="primary", key=f"imp_{case_id}_{kind}"):
        total = store.save_table(case_id, kind, mapped)
        st.success(f"Imported. The case now has {total:,} {kind} rows, queryable by the agent's SQL tools.")


def evidence_panel(case_id: str) -> None:
    checklist(case_id)
    t1, t2, t3 = st.tabs(["📄 Documents on file", "➕ Add documents", "📊 Add CDR / bank records"])
    with t1:
        docs = store.list_documents(case_id)
        if docs:
            df = pd.DataFrame([{"Doc": d.get("doc_id"), "Type": store.DOC_TYPES.get(d.get("doc_type"), d.get("doc_type")),
                                "Title": d.get("title"), "Date": d.get("date"), "¶": d.get("paragraphs")} for d in docs])
            st.dataframe(df, hide_index=True, width="stretch")
            pick = st.selectbox("Read a document", [d["doc_id"] for d in docs], key=f"read_{case_id}",
                                format_func=lambda x: f"{x} · {next(d['title'] for d in docs if d['doc_id'] == x)}")
            from rag.chunking import load_document
            doc = load_document(pick, case_id)
            for p in (doc or {}).get("paragraphs", []):
                st.markdown(f"`{p['cite']}` {p['text']}")
        else:
            st.info("No documents yet.")
        for kind in ("cdr", "transactions"):
            t = store.load_table(case_id, kind)
            if len(t):
                with st.expander(f"{'📞 Call records' if kind == 'cdr' else '💸 Bank transactions'} · {len(t):,} rows"):
                    st.dataframe(t, hide_index=True, width="stretch", height=260)
    with t2:
        add_documents(case_id)
    with t3:
        add_records(case_id)
