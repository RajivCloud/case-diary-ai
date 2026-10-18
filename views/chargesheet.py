"""Chargesheet Draft: the agent's draft Final Report, reviewed finding-by-finding by the IO."""

import json
from datetime import datetime

import pandas as pd
import streamlit as st

from core import store
from core.export import build_docx, item_key
from ui.common import badge, hero, latest_report, require_case
from ui.render import cite_inspector, money_graph

case_id = require_case()
if not case_id:
    st.stop()
case = store.load_case(case_id)
hero(f"📝 Chargesheet Draft · {case_id}", "Draft Final Report (s.193 BNSS) prepared by the AI agent, for the IO's review")

rep_ev, _ = latest_report(case_id)
if not rep_ev:
    st.info("No draft yet. Run the investigation on the **🕵️ Investigate** page.")
    st.stop()
report = rep_ev["report"]
review = store.load_review(case_id)
dec = review.setdefault("decisions", {})
OPTIONS = ["Pending", "Accept", "Reject", "Needs work"]


def review_widget(section: str, i: int, label: str) -> None:
    k = item_key(section, i)
    cur = dec.get(k, {})
    c1, c2 = st.columns([1, 3])
    choice = c1.selectbox("IO decision", OPTIONS, index=OPTIONS.index(cur.get("decision", "Pending")),
                          key=f"d_{case_id}_{k}", label_visibility="collapsed")
    note = c2.text_input("Note", value=cur.get("note", ""), key=f"n_{case_id}_{k}", label_visibility="collapsed",
                         placeholder=f"IO note on {label} (optional)")
    if choice != cur.get("decision", "Pending") or note != cur.get("note", ""):
        dec[k] = {"decision": choice, "note": note}
        store.save_review(case_id, review)
        store.audit(case_id, case.get("io_name") or "IO", f"review {choice}", f"{k} {label} {note}")


s = rep_ev["stats"]
st.markdown(f"{badge(case.get('status', ''))} &nbsp; Prepared by the AI agent in {s.get('tool_calls')} lookups · "
            f"{s.get('seconds')} s. Every point cites its source. **Nothing is final until the IO signs off.**",
            unsafe_allow_html=True)

total = sum(len(report.get(k, [])) for k in ("accused", "cleared", "contradictions", "readiness_gaps"))
decided = sum(1 for v in dec.values() if v.get("decision") not in (None, "Pending"))
st.progress(decided / total if total else 0, text=f"IO review: {decided}/{total} findings decided")

st.markdown("### Summary")
st.markdown(report.get("summary", ""))
if report.get("suggested_sections"):
    st.markdown(" ".join(f"<span class='pill'>{x}</span>" for x in report["suggested_sections"]),
                unsafe_allow_html=True)

st.markdown("### 👥 Accused")
for i, a in enumerate(report.get("accused", [])):
    with st.container(border=True):
        st.markdown(f"**{a['name']}** — {a['role']}")
        for e in a.get("evidence", []):
            st.markdown(f"- {e['point']}  \n  <small>{' · '.join(e.get('sources', []))}</small>", unsafe_allow_html=True)
        review_widget("accused", i, a["name"])

st.markdown("### 🟢 Examined and cleared")
for i, c in enumerate(report.get("cleared", [])):
    with st.container(border=True):
        st.markdown(f"**{c['name']}**: {c['reason']}  \n<small>{' · '.join(c.get('sources', []))}</small>",
                    unsafe_allow_html=True)
        review_widget("cleared", i, c["name"])

st.markdown("### ⚠️ Statements contradicted by records")
for i, c in enumerate(report.get("contradictions", [])):
    with st.container(border=True):
        st.markdown(f"**{c['person']}** claimed: *{c['claim']}*  \n**Records show:** {c['contradicted_by']}  \n"
                    f"<small>{' · '.join(c.get('sources', []))}</small>", unsafe_allow_html=True)
        review_widget("contradictions", i, c["person"])

st.markdown("### 💸 Money trail")
if report.get("money_trail"):
    st.graphviz_chart(money_graph(report["money_trail"], case.get("parties", [])), width="stretch")

st.markdown("### 🚩 Readiness gaps (fix before filing)")
for i, g in enumerate(report.get("readiness_gaps", [])):
    with st.container(border=True):
        st.markdown(f"**{g['issue']}**  \nImpact: {g['impact']}  \nFix: {g['fix']}  \n"
                    f"<small>{' · '.join(g.get('sources', []))}</small>", unsafe_allow_html=True)
        review_widget("readiness_gaps", i, g["issue"][:40])

if report.get("next_actions"):
    st.markdown("### ✅ Next actions for the IO")
    st.dataframe(pd.DataFrame(report["next_actions"]), hide_index=True, width="stretch")
if report.get("linked_cases"):
    st.markdown("### 🔗 Linked cases")
    for lc in report["linked_cases"]:
        st.markdown(f"- {lc}")

cite_inspector(json.dumps(report, ensure_ascii=False), key=f"cite_cs_{case_id}", case_id=case_id)

st.divider()
st.markdown("### Sign-off and export")
c1, c2, c3 = st.columns([2, 1, 1])
who = c1.text_input("Reviewed by (IO name and rank)", value=review.get("reviewed_by") or case.get("io_name", ""))
if c2.button("✍️ Sign off as IO", type="primary", disabled=decided < total):
    review.update(reviewed_by=who, reviewed_at=datetime.now().strftime("%d-%m-%Y %H:%M"))
    store.save_review(case_id, review)
    store.set_status(case_id, "Reviewed by IO")
    store.audit(case_id, who, "chargesheet draft signed off", f"{decided} findings reviewed")
    st.success("Signed off. Status: Reviewed by IO.")
if decided < total:
    c2.caption("Decide every finding to enable sign-off.")
c3.download_button("⬇️ Export Word (.docx)", data=build_docx(case, report, review),
                   file_name=f"{case_id}_chargesheet_draft.docx",
                   mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
st.caption("Rejected findings are left out of the export; accepted ones carry the IO's notes.")
