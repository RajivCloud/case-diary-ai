"""The Case Diary: the agent's working memory (mirrors the IO's diary under s.192 BNSS).

CONCEPT - external memory / agent state
  An LLM forgets nothing within one call but has no notebook across a long
  investigation, and long tool outputs push early findings out of focus.
  We give it a structured notebook it must write into. Benefits:
    * the agent re-reads a compact summary instead of raw tool dumps,
    * the UI can show the investigation evolving live,
    * we can enforce rules (a FACT must cite a source).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

ENTRY_TYPES = {
    "FACT": "established fact, must cite sources",
    "LEAD": "something to follow up",
    "CONTRADICTION": "a statement conflicts with records, must cite both sides",
    "SUSPECT": "person whose role must be confirmed or cleared",
    "CLEARED": "person cleared by evidence, must cite sources",
    "GAP": "chargesheet readiness gap (missing certificate, weak seizure, etc.)",
}
NEEDS_SOURCES = {"FACT", "CONTRADICTION", "CLEARED", "GAP"}


@dataclass
class DiaryEntry:
    n: int
    type: str
    text: str
    sources: list[str] = field(default_factory=list)
    person: str = ""


class CaseDiary:
    def __init__(self) -> None:
        self.entries: list[DiaryEntry] = []

    def add(self, items: list[dict]) -> dict:
        added, rejected = [], []
        for it in items:
            etype = str(it.get("type", "")).upper()
            sources = [s for s in it.get("sources", []) if s]
            if etype not in ENTRY_TYPES:
                rejected.append(f"unknown type {etype!r}")
                continue
            if etype in NEEDS_SOURCES and not sources:
                rejected.append(f"{etype} '{it.get('text', '')[:50]}' rejected: cite at least one source")
                continue
            e = DiaryEntry(len(self.entries) + 1, etype, it.get("text", ""), sources, it.get("person", ""))
            self.entries.append(e)
            added.append(asdict(e))
        return {"added": len(added), "rejected": rejected, "diary_size": len(self.entries)}

    def open_suspects(self) -> list[str]:
        """Suspects not yet resolved (neither cleared nor named in a later FACT/CONTRADICTION)."""
        suspects = {e.person for e in self.entries if e.type == "SUSPECT" and e.person}
        cleared = {e.person for e in self.entries if e.type == "CLEARED" and e.person}
        return sorted(suspects - cleared)

    def as_list(self) -> list[dict]:
        return [asdict(e) for e in self.entries]
