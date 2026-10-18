"""Case store: how a case lives on disk.

    data/cases/<CASE-ID>/
        case.json         FIR details, parties, identifiers, status
        documents/        evidence documents as text, one paragraph per claim
        tables/           cdr.csv, transactions.csv in standard columns
        runs/             investigation results, chargesheet drafts, Q&A history
        review.json       the IO's accept / reject decisions on the draft
        audit.jsonl       every AI action on the case (who, what, when)
        answer_key.json   OPTIONAL ground truth for demo cases; never read by the agent

WHY files and not a database? Each case folder is easy to inspect, version and ship
with the demo. A real deployment would put the same structure in a database
behind the department's network (see docs/SUBMISSION.md, roadmap).
"""

from __future__ import annotations

import io
import json
import re
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
CASES_DIR = ROOT / "data" / "cases"
ARCHIVE_DIR = ROOT / "data" / "archive"

STATUSES = ["Evidence collection", "Investigated", "Chargesheet under review", "Reviewed by IO"]

DOC_TYPES = {
    "fir": "FIR (s.173 BNSS)",
    "complaint": "Complaint / NCRP acknowledgement",
    "statement_180": "Statement under s.180 BNSS",
    "bank_reply": "Bank reply (KYC / statement / freeze)",
    "telecom_reply": "Telecom reply (CAF / CDR cover / IMEI)",
    "platform_reply": "Platform / app / ISP reply",
    "seizure_memo": "Seizure / search panchnama",
    "arrest_memo": "Arrest memo",
    "fsl_report": "Forensic (FSL) report",
    "io_note": "IO observation note",
    "case_diary": "Case diary (s.192 BNSS)",
    "third_party_letter": "Other letter / record",
}

# What the agent needs for a cyber financial-fraud case. Essential items drive the
# completeness meter; missing items become readiness gaps in the agent's report.
CHECKLIST = [
    {"key": "fir", "label": "FIR", "kind": "doc", "types": ["fir"], "essential": True},
    {"key": "complaint", "label": "Complaint / NCRP acknowledgement", "kind": "doc", "types": ["complaint"], "essential": True},
    {"key": "statements", "label": "Statements (victim, witnesses, suspects)", "kind": "doc", "types": ["statement_180"], "essential": True},
    {"key": "bank", "label": "Bank replies (victim + beneficiary KYC/statements)", "kind": "doc", "types": ["bank_reply"], "essential": True},
    {"key": "cdr", "label": "Call detail records (CSV/Excel)", "kind": "table", "table": "cdr", "essential": True},
    {"key": "txns", "label": "Bank transactions (CSV/Excel)", "kind": "table", "table": "transactions", "essential": True},
    {"key": "telecom", "label": "Telecom subscriber (CAF) / IMEI replies", "kind": "doc", "types": ["telecom_reply"], "essential": False},
    {"key": "platform", "label": "Platform / app / ISP replies", "kind": "doc", "types": ["platform_reply"], "essential": False},
    {"key": "seizure", "label": "Seizure / search panchnamas", "kind": "doc", "types": ["seizure_memo"], "essential": False},
    {"key": "fsl", "label": "Forensic (FSL) report", "kind": "doc", "types": ["fsl_report"], "essential": False},
]

TABLE_COLUMNS = {
    "cdr": ["target_number", "other_number", "call_type", "start_time", "duration_sec", "imei", "cell_id", "cell_location"],
    "transactions": ["txn_id", "account_no", "account_holder", "bank", "txn_time", "direction", "amount", "mode",
                     "counterparty_account", "counterparty_name", "utr", "remarks", "location"],
}
TABLE_HELP = {
    "cdr": {
        "target_number": "Phone number whose CDR this is (A party)",
        "other_number": "Other party (B party); blank for data sessions",
        "call_type": "CALL_IN / CALL_OUT / SMS_IN / SMS_OUT / DATA",
        "start_time": "Date and time (YYYY-MM-DD HH:MM:SS)",
        "duration_sec": "Duration in seconds",
        "imei": "Handset IMEI",
        "cell_id": "First cell / tower id",
        "cell_location": "Tower address / area",
    },
    "transactions": {
        "txn_id": "Unique id (auto-filled if missing)",
        "account_no": "Account the statement belongs to",
        "account_holder": "Name of the account holder",
        "bank": "Bank name",
        "txn_time": "Date and time",
        "direction": "DR (debit) or CR (credit)",
        "amount": "Amount in rupees (whole number)",
        "mode": "RTGS / IMPS / NEFT / UPI / ATM / CASH",
        "counterparty_account": "Other account number",
        "counterparty_name": "Other party name",
        "utr": "UTR / reference number",
        "remarks": "Narration / remarks",
        "location": "ATM / branch location",
    },
}


# ----------------------------------------------------------------- cases
def case_dir(case_id: str) -> Path:
    return CASES_DIR / case_id


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def make_case_id(fir_no: str | int, year: str | int) -> str:
    digits = re.sub(r"\D", "", str(fir_no)) or "0"
    return f"CYB-{int(digits):03d}-{year}"


def list_case_ids() -> list[str]:
    return sorted(p.name for p in CASES_DIR.iterdir() if (p / "case.json").exists()) if CASES_DIR.exists() else []


def load_case(case_id: str) -> dict:
    return json.loads((case_dir(case_id) / "case.json").read_text(encoding="utf-8"))


def save_case(meta: dict) -> None:
    d = case_dir(meta["case_id"])
    for sub in ("documents", "tables", "runs"):
        (d / sub).mkdir(parents=True, exist_ok=True)
    meta.setdefault("created_at", _now())
    meta["updated_at"] = _now()
    (d / "case.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")


def set_status(case_id: str, status: str) -> None:
    meta = load_case(case_id)
    if STATUSES.index(status) >= STATUSES.index(meta.get("status", STATUSES[0])):
        meta["status"] = status
        save_case(meta)


# ----------------------------------------------------------------- documents
def parse_front_matter(raw: str) -> tuple[dict, str]:
    if not raw.startswith("---"):
        return {}, raw
    _, header, body = raw.split("---", 2)
    meta = {}
    for line in header.strip().splitlines():
        key, _, value = line.partition(":")
        meta[key.strip()] = value.strip()
    return meta, body.strip()


def list_documents(case_id: str) -> list[dict]:
    out = []
    for f in sorted((case_dir(case_id) / "documents").glob("*.md")):
        meta, body = parse_front_matter(f.read_text(encoding="utf-8"))
        meta["paragraphs"] = len([p for p in body.split("\n\n") if p.strip()])
        meta["file"] = f.name
        out.append(meta)
    return out


def _next_doc_id(case_id: str) -> str:
    nums = [int(m.group(1)) for d in list_documents(case_id) if (m := re.match(r"DOC-(\d+)", d.get("doc_id", "")))]
    return f"DOC-{(max(nums) + 1 if nums else 1):02d}"


def to_paragraphs(text: str) -> list[str]:
    """Normalise extracted text into paragraphs (one claim each).

    Text from PDFs often has hard line breaks and no blank lines. We keep real
    paragraphs when they exist, otherwise regroup lines into ~600-character blocks.
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    paras = [re.sub(r"\s*\n\s*", " ", p).strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if len(paras) >= 2 or (paras and len(paras[0]) < 900):
        return paras
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
    out, cur = [], ""
    for ln in lines:
        cur = f"{cur} {ln}".strip()
        if len(cur) > 600 and cur.endswith((".", ":", ";")):
            out.append(cur)
            cur = ""
    if cur:
        out.append(cur)
    return out


def extract_text(filename: str, data: bytes) -> str:
    """Text from an uploaded PDF, Word, text or markdown file."""
    name = filename.lower()
    if name.endswith(".pdf"):
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(data))
        return "\n\n".join((page.extract_text() or "") for page in reader.pages)
    if name.endswith(".docx"):
        import docx
        d = docx.Document(io.BytesIO(data))
        return "\n\n".join(p.text for p in d.paragraphs if p.text.strip())
    raw = data.decode("utf-8", errors="replace")
    if name.endswith(".md"):
        _, raw = parse_front_matter(raw)
    return raw


def add_document(case_id: str, text: str, doc_type: str, title: str, date: str = "",
                 persons: str = "", source: str = "") -> str:
    doc_id = _next_doc_id(case_id)
    paras = to_paragraphs(text)
    if not paras:
        raise ValueError("No readable text found (scanned PDFs need OCR).")
    slug = re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")[:40] or "document"
    header = (f"---\ndoc_id: {doc_id}\ncase_id: {case_id}\ndoc_type: {doc_type}\ntitle: {title}\n"
              f"date: {date}\npersons: {persons}\nsource: {source}\n---\n")
    (case_dir(case_id) / "documents" / f"{doc_id}_{slug}.md").write_text(header + "\n\n".join(paras) + "\n",
                                                                      encoding="utf-8")
    audit(case_id, "IO", "document added", f"{doc_id} {title} ({len(paras)} paragraphs)")
    return doc_id


# ----------------------------------------------------------------- tables
def table_path(case_id: str, kind: str) -> Path:
    return case_dir(case_id) / "tables" / f"{kind}.csv"


def load_table(case_id: str, kind: str) -> pd.DataFrame:
    p = table_path(case_id, kind)
    if not p.exists():
        return pd.DataFrame(columns=TABLE_COLUMNS[kind])
    return pd.read_csv(p, dtype=str, keep_default_na=False)


def read_tabular(filename: str, data: bytes) -> pd.DataFrame:
    if filename.lower().endswith((".xlsx", ".xls")):
        return pd.read_excel(io.BytesIO(data), dtype=str).fillna("")
    return pd.read_csv(io.BytesIO(data), dtype=str, keep_default_na=False)


def map_columns(df: pd.DataFrame, kind: str, mapping: dict, constants: dict | None = None) -> pd.DataFrame:
    """Turn a bank/telecom export into our standard columns.

    mapping: standard column -> source column. Special keys:
      cdr:          "date" + "time"   (when date and time are separate columns)
      transactions: "debit" + "credit" (when amounts are in two columns, sets direction)
    constants: standard column -> fixed value (e.g. account_no for a single-account statement)
    """
    constants = constants or {}
    out = pd.DataFrame(index=df.index)
    for col in TABLE_COLUMNS[kind]:
        src = mapping.get(col)
        out[col] = df[src].astype(str).str.strip() if src else constants.get(col, "")
    time_col = "start_time" if kind == "cdr" else "txn_time"
    if not mapping.get(time_col) and mapping.get("date"):
        out[time_col] = (df[mapping["date"]].astype(str).str.strip() + " " +
                         (df[mapping["time"]].astype(str).str.strip() if mapping.get("time") else "00:00:00"))
    out[time_col] = pd.to_datetime(out[time_col], errors="coerce", dayfirst=True,
                                   format="mixed").dt.strftime("%Y-%m-%d %H:%M:%S")
    if kind == "transactions":
        if mapping.get("debit") or mapping.get("credit"):
            def num(col):
                if not col:
                    return pd.Series(0, index=df.index)
                return pd.to_numeric(df[col].astype(str).str.replace(",", "").str.strip(), errors="coerce").fillna(0)
            dr, cr = num(mapping.get("debit")), num(mapping.get("credit"))
            out["direction"] = ["DR" if d > 0 else "CR" for d in dr]
            out["amount"] = (dr + cr).astype(int).astype(str)
        out["amount"] = out["amount"].str.replace(",", "").str.split(".").str[0]
        out["direction"] = (out["direction"].str.upper().str.strip().str[:2]
                            .replace({"DE": "DR", "D": "DR", "CE": "CR", "C": "CR"}))
        missing = out["txn_id"] == ""
        out.loc[missing, "txn_id"] = [f"T{i:05d}" for i in range(1, int(missing.sum()) + 1)]
    if kind == "cdr":
        codes = {"MOC": "CALL_OUT", "MTC": "CALL_IN", "OUTGOING": "CALL_OUT", "INCOMING": "CALL_IN",
                 "SMS-MO": "SMS_OUT", "SMSMO": "SMS_OUT", "SMS-MT": "SMS_IN", "SMSMT": "SMS_IN",
                 "GPRS": "DATA", "DATA": "DATA"}  # common telecom export codes -> our types
        ct = out["call_type"].str.upper().str.strip()
        out["call_type"] = ct.map(codes).fillna(ct.str.replace(" ", "_"))
        out["target_number"] = out["target_number"].str[-10:]
        out["other_number"] = out["other_number"].str.replace(r"^\+?91", "", regex=True)
    return out.dropna(subset=[time_col])


def save_table(case_id: str, kind: str, df: pd.DataFrame) -> int:
    """Append rows to the case table (duplicates removed). Returns total rows."""
    existing = load_table(case_id, kind)
    merged = pd.concat([existing, df[TABLE_COLUMNS[kind]]], ignore_index=True).drop_duplicates()
    if kind == "transactions" and merged["txn_id"].duplicated().any():
        merged["txn_id"] = [f"T{i:05d}" for i in range(1, len(merged) + 1)]
    sort_col = "start_time" if kind == "cdr" else "txn_time"
    merged = merged.sort_values(["target_number" if kind == "cdr" else "account_no", sort_col])
    table_path(case_id, kind).parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(table_path(case_id, kind), index=False)
    audit(case_id, "IO", f"{kind} table updated", f"{len(df)} rows added, {len(merged)} total")
    return len(merged)


def template_csv(kind: str) -> bytes:
    return (",".join(TABLE_COLUMNS[kind]) + "\n").encode("utf-8")


# ----------------------------------------------------------------- evidence inventory
def inventory(case_id: str) -> dict:
    docs = list_documents(case_id)
    types = {d.get("doc_type") for d in docs}
    rows = []
    for item in CHECKLIST:
        if item["kind"] == "doc":
            n = sum(1 for d in docs if d.get("doc_type") in item["types"])
        else:
            n = len(load_table(case_id, item["table"]))
        rows.append({**item, "count": n, "present": n > 0})
    essential = [r for r in rows if r["essential"]]
    score = (sum(r["present"] for r in essential) * 2 + sum(r["present"] for r in rows if not r["essential"])) / (
        len(essential) * 2 + len(rows) - len(essential))
    return {"items": rows, "completeness": round(score * 100), "documents": len(docs), "doc_types": types}


# ----------------------------------------------------------------- runs, review, audit
def save_run(case_id: str, name: str, obj) -> None:
    p = case_dir(case_id) / "runs" / f"{name}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=2, ensure_ascii=False, default=str), encoding="utf-8")


def load_run(case_id: str, name: str):
    p = case_dir(case_id) / "runs" / f"{name}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def load_review(case_id: str) -> dict:
    p = case_dir(case_id) / "review.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {"decisions": {}, "reviewed_by": None}


def save_review(case_id: str, review: dict) -> None:
    (case_dir(case_id) / "review.json").write_text(json.dumps(review, indent=2, ensure_ascii=False), encoding="utf-8")


def audit(case_id: str, actor: str, action: str, detail: str = "") -> None:
    p = case_dir(case_id) / "audit.jsonl"
    if not p.parent.exists():
        return
    with open(p, "a", encoding="utf-8") as f:
        f.write(json.dumps({"time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "actor": actor,
                            "action": action, "detail": detail[:500]}, ensure_ascii=False) + "\n")


def read_audit(case_id: str) -> list[dict]:
    p = case_dir(case_id) / "audit.jsonl"
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()] if p.exists() else []


def answer_key(case_id: str) -> dict | None:
    """Only the evaluation reads this. The agent and retriever never do."""
    p = case_dir(case_id) / "answer_key.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None
