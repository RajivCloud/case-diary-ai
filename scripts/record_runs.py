"""Run the baseline and/or the agent on a case, print progress, and save the runs.

Saved runs power Replay mode in the app (free, instant, never flaky during
review) and are scored by eval/run_eval.py.

Run:  python scripts/record_runs.py --case CYB-114-2026 [--only agent|baseline] [--name agent_run]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent.baseline import run_baseline  # noqa: E402
from agent.loop import run_investigation  # noqa: E402
from core import store  # noqa: E402


def short(obj, n=160) -> str:
    s = json.dumps(obj, ensure_ascii=False, default=str)
    return s if len(s) <= n else s[:n] + "..."


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", required=True)
    ap.add_argument("--only", choices=["agent", "baseline"])
    ap.add_argument("--effort", default="medium")
    ap.add_argument("--name", default="agent_run", help="file name for the agent run")
    args = ap.parse_args()

    if args.only in (None, "baseline"):
        print("== Baseline RAG ==")
        b = run_baseline(args.case, effort=args.effort)
        store.save_run(args.case, "baseline_run", b)
        print(b["answer"][:800], "\n", b["stats"])

    if args.only in (None, "agent"):
        print("\n== Agent ==")
        events = []
        for ev in run_investigation(args.case, effort=args.effort):
            events.append(ev)
            if ev["type"] == "tool_call":
                print(f"#{ev['n']:>2} {ev['name']} {short(ev['input'])}", flush=True)
            elif ev["type"] == "gate":
                print("   GATE:", ev["problems"], flush=True)
            elif ev["type"] in ("error", "report", "done"):
                print(ev["type"].upper(), short(ev.get("stats") or ev.get("text"), 400), flush=True)
        store.save_run(args.case, args.name, events)
        if any(e["type"] == "report" for e in events):
            store.set_status(args.case, "Investigated")
        print(f"saved {len(events)} events")


if __name__ == "__main__":
    main()
