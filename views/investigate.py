"""Investigate: run the full AI investigation, or ask the case your own questions."""

import time
from datetime import datetime

import streamlit as st

from core import store
from ui.common import hero, latest_report, require_case
from ui.render import cite_inspector, render_event

ss = st.session_state
case_id = require_case()
if not case_id:
    st.stop()
case = store.load_case(case_id)
hero(f"🕵️ Investigate · {case_id}", f"{case.get('fraud_type')} · complainant {case.get('complainant')} · IO {case.get('io_name')}")

inv = store.inventory(case_id)
if inv["completeness"] < 100:
    missing = ", ".join(i["label"] for i in inv["items"] if not i["present"] and i["essential"])
    if missing:
        st.warning(f"Evidence file {inv['completeness']}% complete. Missing essentials: {missing}. "
                   "The agent will still investigate and will list what is missing.")

tab_full, tab_ask = st.tabs(["🕵️ Full investigation → chargesheet draft", "💬 Ask the case"])

# ------------------------------------------------------------------ full investigation
with tab_full:
    st.caption("The agent plans its own lines of inquiry and picks a tool at every step: hybrid RAG search over "
               "documents, SQL over call records and bank statements, and its Case Diary. It finishes with a "
               "draft chargesheet and a court-readiness check.")
    recorded = store.load_run(case_id, "agent_run")
    b1, b2, b3 = st.columns([1.3, 1.3, 2])
    replay = b1.button("▶️ Replay recorded investigation", disabled=not recorded,
                       help="A real earlier run of this agent, played back. Free and instant.")
    live = b2.button("⚡ Run live investigation", type="primary", disabled=not ss.get("live_ok"),
                     help="Runs the agent now with Claude (about 2-3 min, about $0.60).")
    speed = b3.slider("Replay speed", 1, 10, 7, label_visibility="collapsed")
    now = st.empty()
    left, right = st.columns([3, 2])
    with left:
        st.markdown("**Investigation log**")
        log = st.container(height=600)
    with right:
        st.markdown("**📓 Case Diary** (the agent's working memory, newest first)")
        diary_box = st.container(height=600)

    key = f"events_{case_id}"
    if replay or live:
        state, events = {}, []
        if live:
            from agent.loop import run_investigation
            stream = run_investigation(case_id, effort=ss.get("effort", "medium"))
        else:
            stream = iter(recorded)
        with st.spinner("Investigating…"):
            for ev in stream:
                events.append(ev)
                render_event(ev, log, diary_box, state, now)
                if replay and ev["type"] in ("tool_result", "thinking", "diary"):
                    time.sleep(1.2 / speed)
        now.empty()
        ss[key] = events
        if live:
            store.save_run(case_id, f"agent_run_live_{datetime.now():%Y%m%d_%H%M%S}", events)
        rep = next((e for e in events if e["type"] == "report"), None)
        if rep:
            store.set_status(case_id, "Chargesheet under review")
            s = rep["stats"]
            st.success(f"Chargesheet draft ready after {s['tool_calls']} tool calls · {s['seconds']} s · "
                       f"${s['cost_usd']:.2f}. Open **📝 Chargesheet Draft** in the sidebar.")
    else:
        events = ss.get(key)
        if not events:
            _, events = latest_report(case_id)
        if events:
            state = {}
            for ev in events:
                render_event(ev, log, diary_box, state)
        else:
            log.info("No investigation yet. Press **Run live investigation**.")

# ------------------------------------------------------------------ ask the case
with tab_ask:
    st.caption("Ask anything about this case. The agent looks it up (documents, call records, bank records) and "
               "answers with citations. Suggested questions play instantly from recorded answers; your own "
               "questions run live.")
    qkey = f"qa_{case_id}"
    ss.setdefault(qkey, [])
    recorded_qa = {r["q"]: r["events"] for r in (store.load_run(case_id, "qa_suggested") or [])}
    suggestions = case.get("suggested_questions") or list(recorded_qa)

    if suggestions:
        st.markdown("**Suggested questions**")
        cols = st.columns(2)
        for i, q in enumerate(suggestions):
            label = ("⚡ " if q not in recorded_qa else "▶️ ") + q
            if cols[i % len(cols)].button(label, key=f"sq_{case_id}_{i}", width="stretch"):
                ss.pending_q = q

    typed = st.chat_input("Ask about this case, e.g. “Who did Imran call after the ATM withdrawals?”",
                          disabled=not ss.get("live_ok"))
    if typed:
        ss.pending_q = typed
    if not ss.get("live_ok"):
        st.caption("🔒 Typing your own questions needs Live AI (access code in the sidebar). Suggested questions work.")

    for i, turn in enumerate(ss[qkey]):
        with st.chat_message("user", avatar="👮"):
            st.markdown(turn["q"])
        with st.chat_message("assistant", avatar="🕵️"):
            with st.expander(f"How I found this: {turn['tool_calls']} lookups"):
                for line in turn["steps"]:
                    st.markdown(line, unsafe_allow_html=True)
            st.markdown(turn["a"])
            cite_inspector(turn["a"], key=f"cite_{case_id}_{i}", case_id=case_id)

    q = ss.pop("pending_q", None)
    if q:
        with st.chat_message("user", avatar="👮"):
            st.markdown(q)
        with st.chat_message("assistant", avatar="🕵️"):
            status = st.status("Looking it up…", expanded=True)
            steps, answer, tool_calls, state = [], None, 0, {}
            if q in recorded_qa:
                stream, is_replay = iter(recorded_qa[q]), True
            elif ss.get("live_ok"):
                from agent.loop import run_question
                history = [{"q": t["q"], "a": t["a"]} for t in ss[qkey]]
                stream, is_replay = run_question(case_id, q, history, effort="low"), False
            else:
                stream, is_replay = iter([{"type": "error", "text": "Live AI is locked for typed questions."}]), True
            from ui.render import step_html
            for ev in stream:
                if ev["type"] == "tool_call":
                    state["pending"] = ev
                    status.update(label=f"Step {ev['n']}: {ev['name']}")
                elif ev["type"] == "tool_result":
                    tool_calls += 1
                    line = step_html(ev, state.pop("pending", {"input": {}}).get("input", {}))
                    steps.append(line)
                    status.markdown(line, unsafe_allow_html=True)
                    if is_replay:
                        time.sleep(0.25)
                elif ev["type"] == "answer":
                    answer = ev["text"]
                elif ev["type"] == "error":
                    answer = f"⚠️ {ev['text']}"
            status.update(label=f"Done: {tool_calls} lookups", state="complete", expanded=False)
            st.markdown(answer or "No answer.")
        ss[qkey].append({"q": q, "a": answer or "", "steps": steps, "tool_calls": tool_calls})
        st.rerun()
