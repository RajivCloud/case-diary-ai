"""Pre-record answers to a case's suggested questions (for the free, instant buttons in "Ask the case").

Run: python scripts/record_questions.py --case CYB-114-2026
Questions come from case.json -> "suggested_questions" (or a default list).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent.loop import run_question  # noqa: E402
from core import store  # noqa: E402

DEFAULT_QUESTIONS = [
    "Where did the victim's money go? Trace it account by account.",
    "Which statements are contradicted by the phone or bank records?",
    "Who is the person behind the scam phone numbers, and what links them?",
    "Is anyone wrongly suspected?",
    "What evidence is still missing before we can file the chargesheet?",
]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", required=True)
    ap.add_argument("--effort", default="low")
    a = ap.parse_args()
    qs = store.load_case(a.case).get("suggested_questions") or DEFAULT_QUESTIONS
    recorded = []
    for q in qs:
        print(f"\nQ: {q}", flush=True)
        events = list(run_question(a.case, q, effort=a.effort))
        ans = next((e for e in events if e["type"] == "answer"), None)
        print((ans or {}).get("text", "NO ANSWER")[:600], "\n", (ans or {}).get("stats"), flush=True)
        recorded.append({"q": q, "events": events})
    store.save_run(a.case, "qa_suggested", recorded)


if __name__ == "__main__":
    main()
