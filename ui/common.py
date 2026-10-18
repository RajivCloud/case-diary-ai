"""Shared UI: styling, sidebar (case selector, live-AI access), helpers used by every page."""

from __future__ import annotations

import json
import os

import streamlit as st
from dotenv import load_dotenv

from core import store

load_dotenv(store.ROOT / ".env")  # local runs: ANTHROPIC_API_KEY / ACCESS_CODE from .env

CSS = """<style>
.block-container {padding-top: 1.4rem;}
.hero {background: linear-gradient(90deg,#0b2545,#13315c); color:#fff; padding:16px 22px; border-radius:12px; margin-bottom:10px;}
.hero h1 {color:#fff; margin:0; font-size:1.7rem;} .hero p {margin:4px 0 0; color:#dbe7f5;}
.pill {display:inline-block; background:#eef4fb; color:#13315c; border-radius:999px; padding:2px 10px;
       margin:2px 4px 2px 0; font-size:0.8em;}
.badge {display:inline-block; border-radius:6px; padding:2px 8px; font-size:0.8em; font-weight:600; color:#fff;}
.step {border:1px solid rgba(128,128,128,.25); border-radius:8px; padding:6px 10px; margin:5px 0;}
.card {border:1px solid rgba(128,128,128,.25); border-radius:10px; padding:12px 16px; margin:6px 0;}
</style>"""

STATUS_COLOR = {"Evidence collection": "#b9770e", "Investigated": "#2e86c1",
                "Chargesheet under review": "#8e44ad", "Reviewed by IO": "#1e8449"}


def secret(name: str) -> str | None:
    try:
        return st.secrets.get(name) or os.getenv(name)
    except Exception:
        return os.getenv(name)


def lakh(x) -> str:
    try:
        return f"₹{int(x) / 1e5:.1f} lakh"
    except (TypeError, ValueError):
        return "—"


def badge(status: str) -> str:
    return f"<span class='badge' style='background:{STATUS_COLOR.get(status, '#666')}'>{status}</span>"


def hero(title: str, subtitle: str) -> None:
    st.markdown(f"<div class='hero'><h1>{title}</h1><p>{subtitle}</p></div>", unsafe_allow_html=True)


def sidebar() -> None:
    ss = st.session_state
    ids = store.list_case_ids()
    if ids and ss.get("case_id") not in ids:
        ss.case_id = ids[0]
    with st.sidebar:
        st.markdown("### 🕵️ CaseDiary.AI")
        st.caption("AI investigation assistant · Cyber Police")
        if ids:
            ss.case_id = st.selectbox("Active case", ids, index=ids.index(ss.case_id),
                                      format_func=lambda c: f"{c} · {store.load_case(c).get('fraud_type', '')[:24]}")
            st.markdown(badge(store.load_case(ss.case_id).get("status", "")), unsafe_allow_html=True)
        st.divider()
        expected = secret("ACCESS_CODE")
        if expected:
            code = st.text_input("Live AI access code", type="password",
                                 help="Recorded investigations and suggested questions work without it.")
            ss.live_ok = code == expected
        else:
            ss.live_ok = True
        ss.live_ok = ss.live_ok and bool(secret("ANTHROPIC_API_KEY"))
        st.caption("⚡ Live AI: **enabled**" if ss.live_ok else "🔒 Live AI: locked (replay & suggested questions only)")
        ss.effort = st.select_slider("Reasoning effort (live runs)", ["low", "medium", "high"], value=ss.get("effort", "medium"))
        st.divider()
        st.warning("Demo data is **fictional**. The AI assists the Investigating Officer; it never decides guilt.",
                   icon="⚖️")


def require_case() -> str | None:
    cid = st.session_state.get("case_id")
    if not cid:
        st.info("No case selected. Register a case first.")
        return None
    return cid


def latest_report(case_id: str) -> tuple[dict | None, list[dict]]:
    """Newest agent run (recorded or live) that produced a report: (report_event, events)."""
    runs = sorted((store.case_dir(case_id) / "runs").glob("agent_run*.json"), key=lambda p: p.stat().st_mtime,
                  reverse=True)
    for p in runs:
        events = json.loads(p.read_text(encoding="utf-8"))
        rep = next((e for e in events if e["type"] == "report"), None)
        if rep:
            return rep, events
    return None, []
