"""Load a sample "case kit" (a folder of raw files as a police station would receive them)
through the SAME ingestion pipeline the New Case wizard uses: text extraction,
paragraph chunking, column matching for CDR / bank exports.

A kit folder contains kit.json:
  {"case": {...FIR details...},
   "documents": [{"file", "doc_type", "title", "date", "persons"}],
   "records":   [{"file", "kind", "mapping", "constants"}],
   "answer_key": "answer_key.json",          # optional, demo only
   "recorded":  ["agent_run.json", ...]}     # optional recorded runs for replay
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from core import store

KITS_DIR = store.ROOT / "sample_upload"


def list_kits() -> list[Path]:
    return sorted(p for p in KITS_DIR.iterdir() if (p / "kit.json").exists()) if KITS_DIR.exists() else []


def load_kit(kit: Path, include_recorded: bool = True) -> str:
    spec = json.loads((kit / "kit.json").read_text(encoding="utf-8"))
    meta = {**spec["case"], "status": "Evidence collection"}
    case_id = meta["case_id"]
    if (store.case_dir(case_id) / "case.json").exists():
        raise FileExistsError(f"{case_id} already exists")
    store.save_case(meta)
    store.audit(case_id, meta.get("io_name", "IO"), "case registered", f"from sample kit {kit.name}")
    for d in spec.get("documents", []):
        f = kit / d["file"]
        text = store.extract_text(f.name, f.read_bytes())
        store.add_document(case_id, text, d["doc_type"], d["title"], d.get("date", ""), d.get("persons", ""), f.name)
    for r in spec.get("records", []):
        f = kit / r["file"]
        raw = store.read_tabular(f.name, f.read_bytes())
        store.save_table(case_id, r["kind"], store.map_columns(raw, r["kind"], r["mapping"], r.get("constants")))
    if spec.get("answer_key") and (kit / spec["answer_key"]).exists():
        shutil.copy(kit / spec["answer_key"], store.case_dir(case_id) / "answer_key.json")
    if include_recorded:
        for name in spec.get("recorded", []):
            if (kit / name).exists():
                shutil.copy(kit / name, store.case_dir(case_id) / "runs" / name)
        if (store.case_dir(case_id) / "runs" / "agent_run.json").exists():
            store.set_status(case_id, "Chargesheet under review")
    return case_id
