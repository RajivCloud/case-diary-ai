"""Fast tests (no API calls): data consistency, case store, retrieval, SQL tools, diary rules, guardrail."""

import json

import pandas as pd
import pytest

from agent.diary import CaseDiary
from agent.loop import _check_report, _same_person
from agent.prompts import case_brief
from agent.tools import build_tools
from core import store
from rag import sql_tools
from rag.chunking import load_all_chunks, load_document
from rag.retriever import HybridRetriever

CASE = "CYB-114-2026"


@pytest.fixture(scope="module")
def retriever():
    return HybridRetriever(use_dense=False)  # BM25 only: fast and offline


def test_every_document_chunks_with_citations():
    chunks = load_all_chunks()
    case = [c for c in chunks if c.case_id == CASE]
    assert len({c.doc_id for c in case}) == 23
    assert all(c.chunk_id.startswith(c.doc_id + " ¶") for c in chunks)


def test_money_trail_matches_answer_key():
    key = store.answer_key(CASE)
    tx = store.load_table(CASE, "transactions")
    to_rohit = tx[(tx.account_no == "50210043318876") & (tx.counterparty_name == "Suresh Kulkarni")].amount.astype(int).sum()
    to_imran = tx[(tx.account_no == "31082290447") & (tx.direction == "CR")
                  & (tx.counterparty_name == "Rohit Pawar")].amount.astype(int).sum()
    assert to_rohit == key["money_trail"]["victim_to_rohit"]
    assert to_imran == key["money_trail"]["rohit_to_imran"]


def test_metadata_filter_keeps_archive_out(retriever):
    hits = retriever.search("digital arrest courier parcel narcotics", k=8, case_id=CASE)
    assert hits and all(h["case_id"] == CASE for h in hits)
    everything = retriever.search("digital arrest courier parcel narcotics", k=8)
    assert any(h["case_id"] == "CYB-098-2026" for h in everything)


def test_keyword_search_finds_exact_number(retriever):
    hits = retriever.search("356938112847152", k=3)
    assert any(h["cite"].startswith(("DOC-09", "DOC-18", "DOC-20")) for h in hits)


def test_alibi_is_broken_by_tower_timeline():
    t = sql_tools.location_timeline(CASE, "9890447120", "2026-10-05 12:00", "2026-10-05 16:00")
    assert "Dwarka Circle, Nashik" in [m["cell_location"] for m in t["movements"]]


def test_imei_shows_sim_swap_in_order():
    seq = sql_tools.imei_lookup(CASE, imei="356938112847152")["sim_sequence"]
    assert [s["target_number"] for s in seq] == ["9765330812", "8969204117", "9765330812"]


def test_unknown_number_gives_helpful_error():
    assert "No CDR held" in sql_tools.query_cdr(CASE, "9999999999")["error"]


def test_tool_descriptions_are_built_from_the_case():
    tools = {t["name"]: t for t in build_tools(CASE)}
    assert "9890447120 (Imran Shaikh" in tools["query_cdr"]["description"]
    assert "50210043318876" in tools["query_transactions"]["description"]
    assert "submit_report" not in {t["name"] for t in build_tools(CASE, mode="ask")}


def test_case_brief_lists_documents_and_never_the_answer_key():
    brief = case_brief(CASE)
    assert "DOC-23" in brief and "FIR 114/2026" in brief
    assert "mastermind" not in brief.lower() and "red herring" not in brief.lower()


def test_diary_rejects_unsourced_facts():
    d = CaseDiary()
    out = d.add([{"type": "FACT", "text": "Imran was in Nashik"},
                 {"type": "FACT", "text": "Imran was in Nashik", "sources": ["CDR 9890447120 2026-10-05 14:21"]}])
    assert out["added"] == 1 and len(out["rejected"]) == 1


def test_submit_gate_requires_resolving_suspects():
    d = CaseDiary()
    d.add([{"type": "SUSPECT", "text": "wife suspects nephew", "person": "Anil Kulkarni"}])
    report = {"accused": [{"name": "Sameer Ansari", "role": "operator",
                           "evidence": [{"point": "x", "sources": ["DOC-09 ¶2"]}]}], "cleared": []}
    assert _check_report(report, d)
    report["cleared"] = [{"name": "Anil Kulkarni", "reason": "in Bengaluru", "sources": ["DOC-16 ¶3"]}]
    assert not _check_report(report, d)


def test_gate_matches_full_and_short_names():
    assert _same_person("Sameer Ansari", "Sameer Yusuf Ansari")
    assert not _same_person("Anil Kulkarni", "Suresh Kulkarni")


def test_read_document_prefers_the_active_case():
    doc = load_document("DOC-07", CASE)
    assert doc and doc["case_id"] == CASE and doc["paragraphs"][0]["cite"] == "DOC-07 ¶1"


def test_inventory_for_complete_case():
    inv = store.inventory(CASE)
    assert inv["completeness"] == 100 and inv["documents"] == 23


def test_column_mapping_bank_export_with_debit_credit_columns():
    raw = pd.DataFrame({"Txn Date": ["05/10/2026", "06/10/2026"], "Time": ["14:31", "12:15"],
                        "Narration": ["ATM WDL", "NEFT from X"], "Withdrawal": ["50,000", ""],
                        "Deposit": ["", "1,20,000"]})
    out = store.map_columns(raw, "transactions",
                            {"date": "Txn Date", "time": "Time", "remarks": "Narration",
                             "debit": "Withdrawal", "credit": "Deposit"},
                            constants={"account_no": "123", "account_holder": "A", "bank": "B"})
    assert list(out.direction) == ["DR", "CR"] and list(out.amount) == ["50000", "120000"]
    assert out.txn_time.iloc[0] == "2026-10-05 14:31:00" and out.account_no.iloc[0] == "123"


def test_paragraphs_from_pdf_like_text():
    text = "\n".join(["Line of a statement that goes on."] * 60)
    paras = store.to_paragraphs(text)
    assert len(paras) > 1 and all(len(p) < 1200 for p in paras)


def test_answer_key_checks_are_valid_json_rules():
    rules = store.answer_key(CASE)["checks"]
    assert len(rules) == 12 and all(r["kind"] in ("accused", "cleared", "text") for r in rules)
    json.dumps(rules)


def test_sample_kit_ingests_raw_formats(tmp_path, monkeypatch):
    """The raw kit (Word/text docs, Excel + bank CSV, telecom CDR export) goes through the New Case pipeline."""
    from core import sample_kit
    monkeypatch.setattr(store, "CASES_DIR", tmp_path)
    cid = sample_kit.load_kit(sample_kit.KITS_DIR / "CYB-131-2026", include_recorded=False)
    assert len(store.list_documents(cid)) == 15
    cdr, tx = store.load_table(cid, "cdr"), store.load_table(cid, "transactions")
    assert set(cdr.call_type) <= {"CALL_IN", "CALL_OUT", "SMS_IN", "SMS_OUT", "DATA"}
    assert cdr.target_number.str.len().eq(10).all() and tx.txn_time.str.match(r"\d{4}-\d{2}-\d{2} ").all()
    victim_out = tx[(tx.account_no == "20117745902") & (tx.direction == "DR")].amount.astype(int)
    assert victim_out[victim_out >= 100000].sum() == 2450000
    assert tx.txn_id.is_unique
