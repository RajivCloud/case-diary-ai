"""New Case: a 3-step wizard - FIR details, parties & identifiers, evidence file."""

from datetime import date

import pandas as pd
import streamlit as st

from core import store
from core.sample_kit import list_kits, load_kit
from ui.common import hero
from ui.evidence import evidence_panel

ss = st.session_state
ss.setdefault("wiz_step", 1)
ss.setdefault("wiz_case", None)

hero("➕ Register a new case", "Step-by-step: FIR details → parties & identifiers → evidence file → investigate")

FRAUD_TYPES = ["Digital arrest (impersonation of CBI / police)", "Fake stock-trading / investment app",
               "Part-time job / task fraud", "Loan app harassment / extortion", "SIM swap / account takeover",
               "OLX / marketplace fraud", "Sextortion", "Business email compromise", "Other"]
SECTIONS = ["BNS 318(4)", "BNS 319(2)", "BNS 204", "BNS 61(2)", "BNS 336", "BNS 340", "BNS 111", "BNS 308",
            "IT Act 66C", "IT Act 66D", "IT Act 66E", "IT Act 67"]
ROLES = ["Victim / complainant", "Witness", "Suspect", "Suspect number", "Beneficiary account holder",
         "Account holder", "Person named by family", "Other"]

steps = ["1 · FIR details", "2 · Parties & identifiers", "3 · Evidence file"]
st.markdown(" → ".join(f"**{s}**" if i + 1 == ss.wiz_step else s for i, s in enumerate(steps)))

with st.expander("🎬 Demo: load a sample case kit (raw files as a station would receive them)"):
    st.caption("Runs the same pipeline as the steps below: text extraction, paragraph chunking, and column "
               "matching of a bank / telecom export in their own formats.")
    for kit in list_kits():
        c1, c2 = st.columns([3, 1])
        c1.markdown(f"📦 `{kit.name}` · {len(list(kit.iterdir()))} files")
        exists = (store.case_dir(kit.name) / "case.json").exists()
        if c2.button("Already loaded" if exists else "Load kit", key=f"kit_{kit.name}", disabled=exists):
            with st.spinner("Ingesting documents and records…"):
                cid = load_kit(kit)
            ss.case_id = cid
            st.success(f"{cid} registered with its evidence file.")
            st.switch_page("views/case_details.py")

# ------------------------------------------------------------------ step 1: FIR details
if ss.wiz_step == 1:
    with st.form("fir"):
        st.markdown("#### FIR details")
        c1, c2, c3 = st.columns(3)
        fir_no = c1.text_input("FIR number*", placeholder="e.g. 140")
        fir_date = c2.date_input("Date of FIR*", value=date.today(), max_value=date.today())
        ps = c3.text_input("Police station*", value="Cyber Police Station, Pune City")
        c1, c2 = st.columns(2)
        fraud = c1.selectbox("Fraud type*", FRAUD_TYPES)
        sections = c2.multiselect("Sections in FIR", SECTIONS, default=["BNS 318(4)", "IT Act 66D"])
        c1, c2, c3 = st.columns(3)
        loss = c1.number_input("Amount lost (₹)*", min_value=0, step=1000)
        frozen = c2.number_input("Amount frozen so far (₹)", min_value=0, step=1000)
        io = c3.text_input("Investigating Officer*", placeholder="e.g. PI Meera Deshpande")
        complainant = st.text_input("Complainant*")
        facts = st.text_area("Brief facts*", height=110, placeholder="What happened, when, how the money was sent…")
        if st.form_submit_button("Save and continue →", type="primary"):
            if not all([fir_no, ps, io, complainant, facts]):
                st.error("Please fill all fields marked *.")
            else:
                cid = store.make_case_id(fir_no, fir_date.year)
                if (store.case_dir(cid) / "case.json").exists():
                    st.error(f"{cid} already exists. Open it from the Case Register.")
                else:
                    store.save_case({"case_id": cid, "fir_no": f"{fir_no}/{fir_date.year}", "fir_date": str(fir_date),
                                     "police_station": ps, "district": ps.split(",")[-1].strip(), "fraud_type": fraud,
                                     "sections": sections, "loss_inr": int(loss), "frozen_inr": int(frozen),
                                     "io_name": io, "complainant": complainant, "brief_facts": facts,
                                     "parties": [], "status": "Evidence collection"})
                    store.audit(cid, io, "case registered", f"FIR {fir_no}/{fir_date.year}")
                    ss.wiz_case, ss.case_id, ss.wiz_step = cid, cid, 2
                    st.rerun()

# ------------------------------------------------------------------ step 2: parties
elif ss.wiz_step == 2:
    cid = ss.wiz_case or ss.case_id
    case = store.load_case(cid)
    st.markdown(f"#### Parties & identifiers · {cid}")
    st.caption("Add everyone known so far, with phone numbers and bank accounts. The agent uses these labels "
               "when it reads call records and statements. Unknown persons: write the number and role "
               "(e.g. 'Unknown caller', 'Suspect number').")
    base = case.get("parties") or [{"name": case.get("complainant", ""), "role": "Victim / complainant",
                                    "phone": "", "account_no": "", "bank": "", "notes": ""}]
    edited = st.data_editor(pd.DataFrame(base, columns=["name", "role", "phone", "account_no", "bank", "notes"]),
                            num_rows="dynamic", width="stretch", hide_index=True,
                            column_config={"role": st.column_config.SelectboxColumn("role", options=ROLES)})
    c1, c2 = st.columns([1, 5])
    if c1.button("← Back"):
        ss.wiz_step = 1
        st.rerun()
    if c2.button("Save and continue →", type="primary"):
        parties = [{k: ("" if pd.isna(v) else str(v)) for k, v in r.items()} for r in edited.to_dict("records")
                   if str(r.get("name") or r.get("phone") or "").strip()]
        case["parties"] = parties
        store.save_case(case)
        store.audit(cid, case.get("io_name", "IO"), "parties updated", f"{len(parties)} parties")
        ss.wiz_step = 3
        st.rerun()

# ------------------------------------------------------------------ step 3: evidence
else:
    cid = ss.wiz_case or ss.case_id
    st.markdown(f"#### Evidence file · {cid}")
    evidence_panel(cid)
    st.divider()
    c1, c2, c3 = st.columns([1, 2, 2])
    if c1.button("← Back"):
        ss.wiz_step = 2
        st.rerun()
    if c2.button("📋 Open case details", width="stretch"):
        ss.wiz_step = 1
        st.switch_page("views/case_details.py")
    if c3.button("🕵️ Start investigation →", type="primary", width="stretch"):
        ss.wiz_step = 1
        st.switch_page("views/investigate.py")
