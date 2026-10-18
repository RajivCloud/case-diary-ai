"""Tool definitions the agent can call, built for the selected case, and the code that runs them.

CONCEPT - tool use (function calling)
  Claude never touches our data directly. We describe each tool (name, purpose,
  JSON input schema). Claude replies with a `tool_use` block ("call query_cdr
  with number=..."), our code runs it, and we send the result back.

CONCEPT - dynamic tool descriptions
  The descriptions are generated from the selected case: which phone numbers we
  hold CDRs for, which bank accounts we hold statements for, who they belong to.
  The same agent therefore works on any case the IO loads, with no code changes.
"""

from __future__ import annotations

import json

from agent.diary import ENTRY_TYPES, CaseDiary
from core.store import DOC_TYPES, load_case
from rag import sql_tools
from rag.chunking import load_document
from rag.retriever import get_retriever

_src = {"type": "array", "items": {"type": "string"},
        "description": "Citations, e.g. 'DOC-14 ¶4', 'CDR 9890447120 2026-10-05 14:21', 'TXN T00123'."}


def _label_numbers(case_id: str) -> str:
    parties = load_case(case_id).get("parties", [])
    who = {p.get("phone"): f"{p.get('name')} - {p.get('role')}" for p in parties if p.get("phone")}
    held = sql_tools.numbers_held(case_id)
    return ", ".join(f"{n} ({who[n]})" if n in who else n for n in held) or "none uploaded yet"


def _label_accounts(case_id: str) -> str:
    acc = sql_tools.accounts_held(case_id)
    return ", ".join(f"{a['account_no']} ({a['holder']}, {a['bank']})" for a in acc) or "none uploaded yet"


def build_tools(case_id: str, mode: str = "investigate") -> list[dict]:
    tools = [
        {
            "name": "search_case_files",
            "description": (
                "Hybrid (semantic + keyword) search over the paragraphs of this case's documents: FIR, complaint, "
                "statements, bank/telecom/platform replies, seizure memos, forensic reports, IO notes, case diary. "
                "Searches only the active case by default. Set include_archive=true to search the station's other "
                "cases and closed archive too (to find linked cases by phone number, account or modus operandi). "
                "Returns paragraphs with citations like 'DOC-14 ¶4'. Use specific queries; run several."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "doc_type": {"type": "string", "enum": list(DOC_TYPES)},
                    "person": {"type": "string", "description": "Only paragraphs mentioning this person."},
                    "include_archive": {"type": "boolean"},
                    "k": {"type": "integer", "description": "Number of paragraphs (default 6, max 12)."},
                },
                "required": ["query"],
            },
        },
        {
            "name": "read_document",
            "description": "Read one whole document of this case by id (e.g. 'DOC-07'), or an archive document by its id, with numbered paragraphs.",
            "input_schema": {"type": "object", "properties": {"doc_id": {"type": "string"}}, "required": ["doc_id"]},
        },
        {
            "name": "query_transactions",
            "description": (
                f"SQL lookup over the bank statements held in this case. Accounts held: {_label_accounts(case_id)}. "
                "Filter by account, counterparty account/name, time window (YYYY-MM-DD or YYYY-MM-DD HH:MM), "
                "minimum amount, mode (RTGS/IMPS/UPI/ATM/CASH/NEFT). Returns rows with txn_id and a sum. "
                "Use this to follow the money."
            ),
            "input_schema": {"type": "object", "properties": {
                "account_no": {"type": "string"}, "counterparty": {"type": "string"},
                "start": {"type": "string"}, "end": {"type": "string"},
                "min_amount": {"type": "integer"}, "mode": {"type": "string"}}},
        },
        {
            "name": "query_cdr",
            "description": (
                f"SQL lookup over call detail records held in this case, for: {_label_numbers(case_id)}. Each row: "
                "other_number, call_type (CALL_IN/CALL_OUT/SMS_IN/SMS_OUT/DATA), start_time, duration, IMEI, cell "
                "tower. Filter by other_number, time window, call_type. Use to find who contacted whom and when."
            ),
            "input_schema": {"type": "object", "properties": {
                "number": {"type": "string"}, "other_number": {"type": "string"},
                "start": {"type": "string"}, "end": {"type": "string"}, "call_type": {"type": "string"}},
                "required": ["number"]},
        },
        {
            "name": "location_timeline",
            "description": "Ordered tower-location movements of a phone number in a time window, from the CDR. "
                           "Use to verify or break alibis ('I was at my shop all day').",
            "input_schema": {"type": "object", "properties": {
                "number": {"type": "string"}, "start": {"type": "string"}, "end": {"type": "string"}},
                "required": ["number", "start", "end"]},
        },
        {
            "name": "imei_lookup",
            "description": "Handset analysis from the CDR. Give an IMEI to see which SIM numbers ran in that handset "
                           "and when (in order), or a number to see which handsets (IMEIs) it ran in. A SIM swap "
                           "inside one handset links a fake-KYC SIM to the real user of that phone.",
            "input_schema": {"type": "object", "properties": {"imei": {"type": "string"}, "number": {"type": "string"}}},
        },
    ]
    if mode == "ask":
        return tools
    return tools + [
        {
            "name": "update_case_diary",
            "description": (
                "Write findings into the Case Diary (your working memory, shown live to the Investigating Officer). "
                "Entry types: " + "; ".join(f"{k} = {v}" for k, v in ENTRY_TYPES.items()) + ". "
                "Record findings as you go, not only at the end. FACT, CONTRADICTION, CLEARED and GAP entries "
                "without sources are rejected. For SUSPECT and CLEARED set `person`."
            ),
            "input_schema": {"type": "object", "properties": {"entries": {"type": "array", "items": {
                "type": "object",
                "properties": {"type": {"type": "string", "enum": list(ENTRY_TYPES)}, "text": {"type": "string"},
                               "person": {"type": "string"}, "sources": _src},
                "required": ["type", "text"]}}}, "required": ["entries"]},
        },
        {
            "name": "submit_report",
            "description": (
                "Submit the draft Final Report (chargesheet draft, s.193 BNSS) when the investigation is complete. "
                "It is rejected if any SUSPECT in the diary is neither named as accused nor cleared."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "summary": {"type": "string", "description": "5-8 sentence narrative of what the evidence shows."},
                    "accused": {"type": "array", "items": {"type": "object", "properties": {
                        "name": {"type": "string"}, "role": {"type": "string"},
                        "evidence": {"type": "array", "items": {"type": "object", "properties": {
                            "point": {"type": "string"}, "sources": _src}, "required": ["point", "sources"]}},
                    }, "required": ["name", "role", "evidence"]}},
                    "cleared": {"type": "array", "items": {"type": "object", "properties": {
                        "name": {"type": "string"}, "reason": {"type": "string"}, "sources": _src},
                        "required": ["name", "reason", "sources"]}},
                    "contradictions": {"type": "array", "items": {"type": "object", "properties": {
                        "person": {"type": "string"}, "claim": {"type": "string"},
                        "contradicted_by": {"type": "string"}, "sources": _src},
                        "required": ["person", "claim", "contradicted_by", "sources"]}},
                    "money_trail": {"type": "array", "items": {"type": "object", "properties": {
                        "from": {"type": "string"}, "to": {"type": "string"}, "amount": {"type": "integer"},
                        "when": {"type": "string"}, "sources": _src}, "required": ["from", "to", "amount"]}},
                    "timeline": {"type": "array", "description": "8-15 key events in time order.",
                                 "items": {"type": "object", "properties": {
                                     "when": {"type": "string"}, "event": {"type": "string"}, "sources": _src},
                                     "required": ["when", "event"]}},
                    "readiness_gaps": {"type": "array", "items": {"type": "object", "properties": {
                        "issue": {"type": "string"}, "impact": {"type": "string"},
                        "fix": {"type": "string"}, "sources": _src}, "required": ["issue", "impact", "fix"]}},
                    "next_actions": {"type": "array", "description": "Concrete next steps for the IO, most urgent first.",
                                     "items": {"type": "object", "properties": {
                                         "action": {"type": "string"}, "why": {"type": "string"}},
                                         "required": ["action"]}},
                    "linked_cases": {"type": "array", "items": {"type": "string"}},
                    "suggested_sections": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["summary", "accused", "cleared", "contradictions", "money_trail", "readiness_gaps"],
            },
        },
    ]


def execute(name: str, args: dict, diary: CaseDiary | None, case_id: str) -> dict:
    """Run one tool call. Errors are returned (not raised) so the agent can recover."""
    try:
        if name == "search_case_files":
            k = max(1, min(int(args.get("k") or 6), 12))
            scope = None if args.get("include_archive") else case_id
            hits = get_retriever().search(args["query"], k=k, case_id=scope,
                                          doc_type=args.get("doc_type"), person=args.get("person"))
            return {"results": hits} if hits else {"results": [], "hint": "No match; broaden the query or drop filters."}
        if name == "read_document":
            return load_document(args["doc_id"], case_id) or {"error": f"No document {args['doc_id']}"}
        if name == "query_transactions":
            return sql_tools.query_transactions(case_id, **args)
        if name == "query_cdr":
            return sql_tools.query_cdr(case_id, **args)
        if name == "location_timeline":
            return sql_tools.location_timeline(case_id, **args)
        if name == "imei_lookup":
            return sql_tools.imei_lookup(case_id, **args)
        if name == "update_case_diary" and diary is not None:
            return diary.add(args.get("entries", []))
        return {"error": f"Unknown tool {name}"}
    except Exception as exc:  # bad arguments etc. -> tell the model, let it retry
        return {"error": f"{type(exc).__name__}: {exc}"}


def to_text(result: dict) -> str:
    return json.dumps(result, ensure_ascii=False, default=str)
