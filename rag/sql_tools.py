"""Structured evidence (CDRs, bank transactions) queried with SQL, not embeddings.

CONCEPT - "not everything should be embedded"
  "Where was 9890447120 between 14:00 and 15:30 on 05-Oct?" is a FILTER, not a
  similarity search. Embedding thousands of CDR rows would blur exact times and
  numbers. So each case's tables go into SQLite and the agent gets precise query
  tools. Choosing between text search and SQL is one of the agent's decisions.

All functions take the case_id first and return small JSON-friendly dicts.
"""

from __future__ import annotations

import sqlite3

from core.store import TABLE_COLUMNS, load_table, table_path

MAX_ROWS = 40  # keep tool results small; the agent can narrow its query
_cache: dict[str, tuple[tuple, sqlite3.Connection]] = {}


def _db(case_id: str) -> sqlite3.Connection:
    """In-memory SQLite for one case, rebuilt when its CSV files change."""
    stamp = tuple(table_path(case_id, k).stat().st_mtime_ns if table_path(case_id, k).exists() else 0
                  for k in TABLE_COLUMNS)
    if case_id in _cache and _cache[case_id][0] == stamp:
        return _cache[case_id][1]
    con = sqlite3.connect(":memory:", check_same_thread=False)
    con.row_factory = sqlite3.Row
    for kind, cols in TABLE_COLUMNS.items():
        df = load_table(case_id, kind)
        con.execute(f"CREATE TABLE {kind} ({', '.join(cols)})")
        con.executemany(f"INSERT INTO {kind} VALUES ({', '.join('?' for _ in cols)})",
                        df[cols].itertuples(index=False, name=None))
    _cache[case_id] = (stamp, con)
    return con


def _run(case_id: str, sql: str, params: list) -> list[dict]:
    return [dict(r) for r in _db(case_id).execute(sql, params).fetchall()]


def _norm_time(t: str | None, end: bool = False) -> str | None:
    """Accept '2026-10-05' or '2026-10-05 14:00' and make it comparable."""
    if not t:
        return None
    t = t.strip().replace("T", " ")
    if len(t) == 10:
        return t + (" 23:59:59" if end else " 00:00:00")
    if len(t) == 16:
        return t + (":59" if end else ":00")
    return t


def numbers_held(case_id: str) -> list[str]:
    return [r["target_number"] for r in _run(case_id, "SELECT DISTINCT target_number FROM cdr ORDER BY 1", [])]


def accounts_held(case_id: str) -> list[dict]:
    return _run(case_id, "SELECT account_no, MAX(account_holder) AS holder, MAX(bank) AS bank, COUNT(*) AS rows "
                         "FROM transactions GROUP BY account_no ORDER BY 1", [])


def query_cdr(case_id: str, number: str, other_number: str | None = None, start: str | None = None,
              end: str | None = None, call_type: str | None = None) -> dict:
    held = numbers_held(case_id)
    if number not in held:
        return {"error": f"No CDR held for {number}. CDRs available for: {', '.join(held) or 'none uploaded'}"}
    sql, p = "SELECT * FROM cdr WHERE target_number = ?", [number]
    if other_number:
        sql += " AND other_number = ?"; p.append(other_number)
    if start:
        sql += " AND start_time >= ?"; p.append(_norm_time(start))
    if end:
        sql += " AND start_time <= ?"; p.append(_norm_time(end, end=True))
    if call_type:
        sql += " AND call_type = ?"; p.append(call_type.upper())
    rows = _run(case_id, sql + " ORDER BY start_time", p)
    return {"total_rows": len(rows), "rows": rows[:MAX_ROWS], "truncated": len(rows) > MAX_ROWS,
            "hint": "Narrow with start/end/other_number if truncated."}


def _segments(rows: list[dict], key: str) -> list[dict]:
    """Collapse time-ordered rows into runs of the same value (e.g. same tower).

    Ordering matters for alibis and handset swaps: "Malegaon -> Nashik -> Malegaon"
    is evidence; "Malegaon: 2 events, Nashik: 5 events" hides it.
    """
    segs: list[dict] = []
    for r in rows:
        if segs and segs[-1][key] == r[key]:
            segs[-1]["to"] = r["start_time"]; segs[-1]["events"] += 1
        else:
            segs.append({key: r[key], "from": r["start_time"], "to": r["start_time"], "events": 1,
                         **({"cell_id": r["cell_id"]} if key == "cell_location" else {})})
    return segs


def location_timeline(case_id: str, number: str, start: str, end: str) -> dict:
    """Ordered tower movements of a number in a time window - the alibi checker."""
    rows = _run(case_id, "SELECT * FROM cdr WHERE target_number = ? AND start_time BETWEEN ? AND ? "
                         "ORDER BY start_time", [number, _norm_time(start), _norm_time(end, end=True)])
    return {"number": number, "window": [start, end], "movements": _segments(rows, "cell_location")[:MAX_ROWS]}


def imei_lookup(case_id: str, imei: str | None = None, number: str | None = None) -> dict:
    """Which SIMs ran in a handset (by IMEI), or which handsets a SIM ran in (by number), in time order."""
    if imei:
        rows = _run(case_id, "SELECT * FROM cdr WHERE imei = ? ORDER BY start_time", [imei])
        return {"imei": imei, "sim_sequence": _segments(rows, "target_number")}
    if number:
        rows = _run(case_id, "SELECT * FROM cdr WHERE target_number = ? ORDER BY start_time", [number])
        return {"number": number, "handset_sequence": _segments(rows, "imei")}
    return {"error": "Give imei or number"}


def query_transactions(case_id: str, account_no: str | None = None, counterparty: str | None = None,
                       start: str | None = None, end: str | None = None,
                       min_amount: int | None = None, mode: str | None = None) -> dict:
    sql, p = "SELECT * FROM transactions WHERE 1=1", []
    if account_no:
        sql += " AND account_no = ?"; p.append(account_no)
    if counterparty:
        sql += " AND (counterparty_account = ? OR counterparty_name LIKE ?)"; p += [counterparty, f"%{counterparty}%"]
    if start:
        sql += " AND txn_time >= ?"; p.append(_norm_time(start))
    if end:
        sql += " AND txn_time <= ?"; p.append(_norm_time(end, end=True))
    if min_amount:
        sql += " AND CAST(amount AS INTEGER) >= ?"; p.append(int(min_amount))
    if mode:
        sql += " AND mode = ?"; p.append(mode.upper())
    rows = _run(case_id, sql + " ORDER BY txn_time", p)
    total = sum(int(r["amount"] or 0) for r in rows)
    return {"total_rows": len(rows), "sum_amount": total, "rows": rows[:MAX_ROWS], "truncated": len(rows) > MAX_ROWS}
