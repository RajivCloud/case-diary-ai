"""The agent loop (ReAct: reason -> act with a tool -> observe -> repeat).

CONCEPT - why a loop and not one call?
  A single RAG call retrieves once, using the user's words. Here every answer
  produces the next question: account -> its owner -> his phone -> the handset
  -> the other SIM in it. Only a loop can follow that chain.

CONCEPT - guardrails
  * step cap so a confused agent can't run forever,
  * diary rules (facts must cite sources),
  * a submit gate: the report is rejected while any suspect is unresolved.
    That is a cheap form of self-verification: the agent must fix its own gap.

Two modes share the same loop:
  run_investigation(case_id)        full investigation -> chargesheet draft
  run_question(case_id, question)   "Ask the case": one question -> cited answer
Both are generators that YIELD events, so the UI can render each step live and
the same events can be saved, replayed and written to the audit trail.
"""

from __future__ import annotations

import time
from typing import Iterator

from agent import llm
from agent.diary import CaseDiary
from agent.prompts import TASK, system_for
from agent.tools import build_tools, execute, to_text
from core import store

MAX_TURNS = 30
MAX_TURNS_ASK = 10


def _same_person(a: str, b: str) -> bool:
    """'Sameer Ansari' matches 'Sameer Yusuf Ansari': same first and last name."""
    ta, tb = a.lower().replace(".", " ").split(), b.lower().replace(".", " ").split()
    return bool(ta and tb) and ta[0] == tb[0] and ta[-1] == tb[-1]


def _check_report(report: dict, diary: CaseDiary) -> list[str]:
    named = [a.get("name", "") for a in report.get("accused", [])]
    named += [c.get("name", "") for c in report.get("cleared", [])]
    problems = [f"Suspect '{s}' is neither accused nor cleared." for s in diary.open_suspects()
                if not any(_same_person(s, n) for n in named)]
    for a in report.get("accused", []):
        if not any(e.get("sources") for e in a.get("evidence", [])):
            problems.append(f"Accused '{a.get('name')}' has no cited evidence.")
    return problems


def _call(client, case_id: str, mode: str, messages: list, effort: str, usage: llm.Usage):
    resp = llm.create(
        client,
        max_tokens=16000,
        system=system_for(case_id, mode),
        tools=build_tools(case_id, mode),
        messages=messages,
        thinking={"type": "adaptive", "display": "summarized"},
        output_config={"effort": effort},
    )
    usage.add(resp.usage)
    return resp


def _narration(resp) -> Iterator[dict]:
    for block in resp.content:
        if block.type == "thinking" and getattr(block, "thinking", ""):
            yield {"type": "thinking", "text": block.thinking}
        elif block.type == "text" and block.text.strip():
            yield {"type": "text", "text": block.text}


def run_investigation(case_id: str, task: str = TASK, effort: str = llm.DEFAULT_EFFORT) -> Iterator[dict]:
    client = llm.get_client()
    diary = CaseDiary()
    usage = llm.Usage()
    messages: list = [{"role": "user", "content": task}]
    t0, tool_calls, nudged = time.time(), 0, False
    store.audit(case_id, "AI agent", "investigation started", f"model={llm.MODEL} effort={effort}")
    yield {"type": "start", "task": task, "model": llm.MODEL, "effort": effort, "case_id": case_id}

    for turn in range(1, MAX_TURNS + 1):
        resp = _call(client, case_id, "investigate", messages, effort, usage)
        if resp.stop_reason == "refusal":
            yield {"type": "error", "text": "The model declined this request (refusal)."}
            break
        # Always append the full content (incl. thinking blocks) - required for tool-use continuity.
        messages.append({"role": "assistant", "content": resp.content})
        yield from _narration(resp)

        tool_uses = [b for b in resp.content if b.type == "tool_use"]
        if not tool_uses:
            if nudged:
                yield {"type": "error", "text": "Agent stopped without submitting a report."}
                break
            nudged = True
            messages.append({"role": "user", "content": "Please complete the readiness check and call submit_report."})
            continue

        results, final_report = [], None
        for tu in tool_uses:
            tool_calls += 1
            yield {"type": "tool_call", "name": tu.name, "input": tu.input, "n": tool_calls}
            if tu.name == "submit_report":
                problems = _check_report(tu.input, diary)
                if problems:
                    out = {"rejected": True, "problems": problems,
                           "instruction": "Resolve these, then call submit_report again."}
                    yield {"type": "gate", "problems": problems}
                else:
                    out, final_report = {"accepted": True}, tu.input
            else:
                out = execute(tu.name, tu.input, diary, case_id)
                if tu.name == "update_case_diary":
                    yield {"type": "diary", "entries": diary.as_list()}
            store.audit(case_id, "AI agent", f"tool {tu.name}", to_text(tu.input))
            yield {"type": "tool_result", "name": tu.name, "output": out, "n": tool_calls}
            results.append({"type": "tool_result", "tool_use_id": tu.id, "content": to_text(out),
                            **({"is_error": True} if "error" in out else {})})
        messages.append({"role": "user", "content": results})

        if final_report:
            stats = {**usage.as_dict(), "tool_calls": tool_calls, "turns": turn, "seconds": round(time.time() - t0, 1)}
            store.audit(case_id, "AI agent", "chargesheet draft submitted",
                        f"{len(final_report.get('accused', []))} accused, {tool_calls} tool calls, ${stats['cost_usd']}")
            yield {"type": "report", "report": final_report, "diary": diary.as_list(), "stats": stats}
            return

        if turn == MAX_TURNS - 2:
            messages.append({"role": "user", "content": "Step budget almost used. Finish the readiness check and submit_report now."})

    yield {"type": "done", "diary": diary.as_list(),
           "stats": {**usage.as_dict(), "tool_calls": tool_calls, "seconds": round(time.time() - t0, 1)}}


def run_question(case_id: str, question: str, history: list[dict] | None = None,
                 effort: str = "low") -> Iterator[dict]:
    """Answer one IO question with tools and citations. `history` = earlier [{'q','a'}] turns."""
    client = llm.get_client()
    usage = llm.Usage()
    messages: list = []
    for h in (history or [])[-4:]:  # recent turns give follow-up questions their context
        messages += [{"role": "user", "content": h["q"]}, {"role": "assistant", "content": h["a"]}]
    messages.append({"role": "user", "content": question})
    t0, tool_calls = time.time(), 0
    store.audit(case_id, "IO", "question asked", question)
    yield {"type": "start", "question": question}

    for _ in range(MAX_TURNS_ASK):
        resp = _call(client, case_id, "ask", messages, effort, usage)
        if resp.stop_reason == "refusal":
            yield {"type": "error", "text": "The model declined this request (refusal)."}
            return
        messages.append({"role": "assistant", "content": resp.content})
        tool_uses = [b for b in resp.content if b.type == "tool_use"]
        if not tool_uses:
            answer = "".join(b.text for b in resp.content if b.type == "text").strip()
            stats = {**usage.as_dict(), "tool_calls": tool_calls, "seconds": round(time.time() - t0, 1)}
            store.audit(case_id, "AI agent", "answer given", answer[:300])
            yield {"type": "answer", "text": answer, "stats": stats}
            return
        for ev in _narration(resp):
            if ev["type"] == "thinking":
                yield ev
        results = []
        for tu in tool_uses:
            tool_calls += 1
            yield {"type": "tool_call", "name": tu.name, "input": tu.input, "n": tool_calls}
            out = execute(tu.name, tu.input, None, case_id)
            store.audit(case_id, "AI agent", f"tool {tu.name}", to_text(tu.input))
            yield {"type": "tool_result", "name": tu.name, "output": out, "n": tool_calls}
            results.append({"type": "tool_result", "tool_use_id": tu.id, "content": to_text(out),
                            **({"is_error": True} if "error" in out else {})})
        messages.append({"role": "user", "content": results})
        if len(messages) > 2 * MAX_TURNS_ASK - 2:
            messages.append({"role": "user", "content": "Please answer now with what you have found."})
    yield {"type": "error", "text": "No answer within the step limit."}
