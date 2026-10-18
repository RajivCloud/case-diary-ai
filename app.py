"""CaseDiary.AI - an agentic RAG investigation assistant for Cyber Police Investigating Officers.

Run locally:  streamlit run app.py
"""

from __future__ import annotations

import streamlit as st

from ui.common import CSS, sidebar

st.set_page_config(page_title="CaseDiary.AI", page_icon="🕵️", layout="wide")
st.markdown(CSS, unsafe_allow_html=True)

PAGES = {
    "Station": [
        st.Page("views/register.py", title="Case Register", icon="🗂️", default=True),
        st.Page("views/new_case.py", title="New Case", icon="➕"),
    ],
    "Active case": [
        st.Page("views/case_details.py", title="Case Details", icon="📋"),
        st.Page("views/investigate.py", title="Investigate", icon="🕵️"),
        st.Page("views/chargesheet.py", title="Chargesheet Draft", icon="📝"),
    ],
    "About": [
        st.Page("views/about.py", title="AI performance & how it works", icon="📊"),
    ],
}

nav = st.navigation(PAGES)
sidebar()
nav.run()
