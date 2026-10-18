"""Case Details: the case at a glance - FIR facts, parties, evidence file, timeline, money, audit trail."""

import pandas as pd
import streamlit as st

from core import store
from ui.common import badge, hero, lakh, latest_report, require_case
from ui.evidence import evidence_panel
from ui.render import evidence_timeline, money_graph

case_id = require_case()
if not case_id:
    st.stop()
case = store.load_case(case_id)
inv = store.inventory(case_id)
cdr, tx = store.load_table(case_id, "cdr"), store.load_table(case_id, "transactions")

hero(f"📋 {case_id} · FIR {case.get('fir_no')}", f"{case.get('police_station')} · registered {case.get('fir_date')} · "
     f"IO {case.get('io_name')}")
st.markdown(badge(case.get("status", "")), unsafe_allow_html=True)

st.markdown(f"**Fraud type:** {case.get('fraud_type') or '—'}")
m = st.columns(3)
m[0].metric("Loss", lakh(case.get("loss_inr")))
m[1].metric("Frozen", lakh(case.get("frozen_inr")))
m[2].metric("Evidence file", f"{inv['completeness']}%")
m = st.columns(3)
m[0].metric("Documents", inv["documents"])
m[1].metric("Call records", f"{len(cdr):,}")
m[2].metric("Bank transactions", f"{len(tx):,}")

rep_ev, _ = latest_report(case_id)
report = rep_ev["report"] if rep_ev else None

t_over, t_evid, t_time, t_money, t_audit = st.tabs(
    ["Overview", "Evidence file", "Timeline", "Money trail", "Audit trail"])

with t_over:
    c1, c2 = st.columns([3, 2])
    with c1:
        st.markdown("**Brief facts**")
        st.write(case.get("brief_facts") or "—")
        st.markdown("**Sections in FIR:** " + " ".join(f"<span class='pill'>{s}</span>" for s in case.get("sections", [])),
                    unsafe_allow_html=True)
        st.markdown(f"**Complainant:** {case.get('complainant', '—')}")
    with c2:
        if report:
            st.markdown("**AI findings (latest draft)**")
            st.markdown("- Accused: " + ", ".join(a["name"] for a in report.get("accused", [])))
            st.markdown("- Cleared: " + (", ".join(c["name"] for c in report.get("cleared", [])) or "—"))
            st.markdown(f"- Contradictions: {len(report.get('contradictions', []))} · "
                        f"Readiness gaps: {len(report.get('readiness_gaps', []))}")
            if st.button("Open chargesheet draft →"):
                st.switch_page("views/chargesheet.py")
        else:
            st.info("Not investigated yet.")
            if st.button("🕵️ Investigate this case →", type="primary"):
                st.switch_page("views/investigate.py")
    st.markdown("**Parties and identifiers**")
    st.dataframe(pd.DataFrame(case.get("parties", [])), hide_index=True, width="stretch")

with t_evid:
    evidence_panel(case_id)

with t_time:
    if report and report.get("timeline"):
        st.markdown("**Key events (from the AI investigation, cited)**")
        st.dataframe(pd.DataFrame([{**e, "sources": ", ".join(e.get("sources", []))} for e in report["timeline"]]),
                     hide_index=True, width="stretch")
    st.markdown("**Evidence timeline** (FIR, documents and transactions of ₹1 lakh or more)")
    tl = evidence_timeline(case_id)
    st.dataframe(tl, hide_index=True, width="stretch", height=420)

with t_money:
    if report and report.get("money_trail"):
        st.caption("From the AI investigation (amounts merged per pair of accounts).")
        st.graphviz_chart(money_graph(report["money_trail"], case.get("parties", [])), width="stretch")
    elif len(tx):
        big = tx[pd.to_numeric(tx.amount, errors="coerce").fillna(0) >= 100000]
        st.caption("Not investigated yet: large transfers from the uploaded statements.")
        trail = [{"from": r.account_holder, "to": r.counterparty_name or r.mode, "amount": int(r.amount)}
                 for _, r in big[big.direction == "DR"].iterrows()]
        st.graphviz_chart(money_graph(trail, case.get("parties", [])), width="stretch")
    else:
        st.info("No bank records uploaded yet.")

with t_audit:
    st.caption("Every action on this case: documents added, AI tool calls, questions, review decisions. "
               "This is how an investigator can show how a conclusion was reached.")
    log = store.read_audit(case_id)
    if log:
        st.dataframe(pd.DataFrame(log[::-1]), hide_index=True, width="stretch", height=420)
    else:
        st.info("No actions recorded yet.")

if case.get("from_kit"):  # demo cases loaded from a sample kit can be removed and loaded again
    with st.expander("🎬 Demo controls"):
        st.caption(f"This case was loaded from the sample kit `{case['from_kit']}`. Remove it to rehearse the "
                   "New Case → load kit flow again. Real cases have no such button.")
        sure = st.checkbox("Yes, remove this demo case and its files")
        if st.button("Remove demo case", disabled=not sure):
            import shutil
            shutil.rmtree(store.case_dir(case_id))
            st.session_state.case_id = None
            st.switch_page("views/register.py")
