"""Case Register: every case in the station, its status and key numbers. Click a row to open it."""

import pandas as pd
import streamlit as st

from core import store
from ui.common import hero, lakh

hero("🗂️ Case Register", "Cyber Police Station, Pune City · all cases handled with CaseDiary.AI")

ids = store.list_case_ids()
cases = [store.load_case(c) for c in ids]

m1, m2, m3, m4 = st.columns(4)
m1.metric("Cases", len(cases))
m2.metric("Total loss reported", lakh(sum(int(c.get("loss_inr") or 0) for c in cases)))
m3.metric("Amount frozen", lakh(sum(int(c.get("frozen_inr") or 0) for c in cases)))
m4.metric("Awaiting IO review", sum(c.get("status") == "Chargesheet under review" for c in cases))

left, right = st.columns([4, 1])
left.caption("Select a row to open the case.")
if right.button("➕ Register new case", type="primary", width="stretch"):
    st.session_state.wiz_step = 1
    st.session_state.wiz_case = None
    st.switch_page("views/new_case.py")

if not cases:
    st.info("No cases yet. Register the first one.")
else:
    df = pd.DataFrame([{
        "Case ID": c["case_id"], "FIR date": c.get("fir_date", ""), "Fraud type": c.get("fraud_type", ""),
        "Complainant": c.get("complainant", ""), "Loss (₹ lakh)": round(int(c.get("loss_inr") or 0) / 1e5, 1),
        "Frozen (₹ lakh)": round(int(c.get("frozen_inr") or 0) / 1e5, 1), "IO": c.get("io_name", ""),
        "Status": c.get("status", ""), "Evidence file": f"{store.inventory(c['case_id'])['completeness']}%",
    } for c in cases])
    sel = st.dataframe(df, hide_index=True, width="stretch", on_select="rerun", selection_mode="single-row")
    rows = sel.selection.rows if sel and sel.selection else []
    if rows:
        st.session_state.case_id = df.iloc[rows[0]]["Case ID"]
        st.switch_page("views/case_details.py")

st.divider()
st.markdown("#### How CaseDiary.AI fits the investigation")
c1, c2, c3, c4 = st.columns(4)
c1.markdown("**1. ➕ New Case**  \nRegister the FIR, add parties, upload documents and CDR / bank records.")
c2.markdown("**2. 📋 Case Details**  \nSee the evidence file, what's missing, the timeline and audit trail.")
c3.markdown("**3. 🕵️ Investigate**  \nThe AI agent cross-checks everything, or answers your questions with sources.")
c4.markdown("**4. 📝 Chargesheet**  \nReview the AI's draft finding by finding, sign off, export to Word.")
