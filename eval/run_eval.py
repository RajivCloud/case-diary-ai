"""Score the baseline RAG and the agent against a case's answer key.

CONCEPT - evaluation against ground truth
  "It looks right" is not evidence. For demo cases we wrote the truth, so each
  case folder has answer_key.json with transparent grading rules ("checks").
  The SAME rules are applied to both systems. The agent is held to a stricter
  standard: names must be in its structured `accused` / `cleared` lists, while
  the baseline only has to mention them.

  Text rules use [^\\n] so related clues must sit in the same line / record;
  scattered keywords don't count. (Lesson from development: a looser rubric once
  gave the baseline credit for "catching" lies it said it could not find.)

Run: python eval/run_eval.py --case CYB-114-2026
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import store  # noqa: E402


def strings(obj) -> list[str]:
    """Flatten a JSON report into lines. One record (a gap, a contradiction, an evidence point)
    becomes ONE line, the same unit as one bullet line in the baseline's prose answer."""
    if isinstance(obj, str):
        return [obj]
    if isinstance(obj, list):
        return [s for v in obj for s in strings(v)]
    if isinstance(obj, dict):
        nested = [v for v in obj.values() if isinstance(v, dict) or (isinstance(v, list) and v and isinstance(v[0], dict))]
        flat = [v if isinstance(v, str) else " ".join(map(str, v)) if isinstance(v, list) else str(v)
                for v in obj.values() if not any(v is n for n in nested)]
        return [" | ".join(flat)] + [s for v in nested for s in strings(v)]
    return []


def same(a: str, b: str) -> bool:
    """'Sameer Ansari' == 'Sameer Yusuf Ansari'; 'Imran' == 'Imran Rafiq Shaikh'."""
    ta, tb = a.lower().split(), b.lower().split()
    return bool(ta and tb) and ta[0] == tb[0] and (len(ta) == 1 or ta[-1] == tb[-1])


def run_checks(rules: list[dict], text: str, accused: list[str] | None, cleared: list[str] | None) -> dict[str, bool]:
    out = {}
    for r in rules:
        if r["kind"] == "accused":
            ok = any(same(r["person"], a) for a in accused) if accused is not None else bool(
                re.search(r["person"], text, re.I))
        elif r["kind"] == "cleared":
            ok = any(same(r["person"], c) for c in cleared) if cleared is not None else bool(
                re.search(rf"{r['person']}[^\n]{{0,300}}(clear|no evidence|not involved|innocent|alibi)", text, re.I))
        else:
            ok = all(re.search(p, text, re.I) for p in r["all"])
        out[r["name"]] = ok
    return out


def score_report_events(events: list[dict], rules: list[dict]) -> dict | None:
    rep = next((e for e in events if e["type"] == "report"), None)
    if not rep:
        return None
    report = rep["report"]
    text = "\n".join(strings(report) + strings(rep.get("diary", [])))
    res = run_checks(rules, text, [a["name"] for a in report.get("accused", [])],
                     [c["name"] for c in report.get("cleared", [])])
    return {"checks": res, "stats": rep["stats"], "citations": len(re.findall(r"DOC-\d+ ¶\d+|CDR |TXN ", text))}


def evaluate(case_id: str, verbose: bool = True) -> dict | None:
    key = store.answer_key(case_id)
    if not key or "checks" not in key:
        if verbose:
            print(f"{case_id}: no answer key - nothing to score (normal for real cases)")
        return None
    rules = key["checks"]
    base_run = store.load_run(case_id, "baseline_run")
    base = None
    if base_run:
        base = {"checks": run_checks(rules, base_run["answer"], None, None), "stats": base_run["stats"],
                "citations": len(re.findall(r"DOC-\d+ ¶\d+", base_run["answer"]))}
    runs, agent = {}, None
    for p in sorted((store.case_dir(case_id) / "runs").glob("agent_run*.json")):
        r = score_report_events(json.loads(p.read_text(encoding="utf-8")), rules)
        if r:
            runs[p.stem] = {"score": sum(r["checks"].values()), "of": len(r["checks"]), **r["stats"]}
            if p.stem == "agent_run":
                agent = r
    out = {"case_id": case_id, "baseline": base, "agent": agent, "agent_runs": runs}
    store.save_run(case_id, "eval", out)
    if verbose:
        print(f"\n{case_id}\n{'Check':<68} {'Baseline':>9} {'Agent':>7}")
        for r in rules:
            n = r["name"]
            print(f"{n:<68} {'PASS' if base and base['checks'][n] else '-':>9} "
                  f"{'PASS' if agent and agent['checks'][n] else '-':>7}")
        if base:
            print(f"Baseline: {sum(base['checks'].values())}/{len(rules)}  stats={base['stats']}")
        for name, r in runs.items():
            print(f"{name}: {r['score']}/{r['of']} · {r['tool_calls']} tool calls · {r['seconds']} s · ${r['cost_usd']}")
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", help="case id (default: every case with an answer key)")
    a = ap.parse_args()
    for cid in ([a.case] if a.case else store.list_case_ids()):
        evaluate(cid)
