"""Generate the bulky, structured evidence: call detail records and bank transactions.

WHY a script (and not hand-written rows)?
  Real case files contain thousands of CDR rows and hundreds of transactions.
  The handful of rows that matter are buried in noise. A seeded script lets us
  plant the important rows exactly (they must agree with case_truth.json and the
  documents) and then bury them in realistic noise, the same way every run.

Run:  python scripts/generate_tables.py
Out:  data/tables/cdr.csv, data/tables/transactions.csv
"""

from __future__ import annotations

import csv
import random
from datetime import datetime, timedelta
from pathlib import Path

SEED = 114  # same seed -> same data every time (reproducible demo and eval)
OUT = Path(__file__).resolve().parent.parent / "data" / "cases" / "CYB-114-2026" / "tables"

# ---------------------------------------------------------------------------
# Cast: numbers, handsets and the cell towers they normally sit on
# ---------------------------------------------------------------------------
VICTIM = "9822041763"
SCAM_CALLER = "7303518246"  # "courier" caller
SCAM_CBI = "8969204117"     # "CBI officer Vikram Rathore"
ROHIT = "9371662405"
IMRAN = "9890447120"
ANIL = "9845012377"
SAMEER = "9765330812"
ARCHIVE_VICTIM = "9881234560"  # victim of the older archive case CYB-098-2026

IMEI_MAIN = "356938112847152"   # Sameer's smartphone (personal SIM, then scam SIM)
IMEI_KEYPAD = "861234055591027"  # keypad phone used with 7303518246
IMEI_SAMEER_OLD = "359876045512338"  # spare handset for Sameer's SIM during scam window

CELLS = {
    "PUN-KTH-11": "Kothrud, Pune",
    "PUN-KTH-02": "Karve Road, Pune",
    "PUN-HDP-07": "Hadapsar, Pune",
    "NSK-BHD-03": "Bhadrakali, Nashik",
    "NSK-DWK-02": "Dwarka Circle, Nashik",
    "NSK-NRD-04": "Nashik Road, Nashik",
    "NSK-HWY-05": "Chandwad, Nashik district",
    "MLG-KDW-01": "Kidwai Road, Malegaon",
    "BLR-BRK-12": "Brookefield, Bengaluru",
    "BLR-WTF-03": "Whitefield, Bengaluru",
}

START = datetime(2026, 9, 1)
END = datetime(2026, 10, 8, 23, 59)

rng = random.Random(SEED)


def ts(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%d %H:%M:%S")


def fmt(d: datetime) -> str:
    return d.strftime("%Y-%m-%d %H:%M:%S")


def rand_number() -> str:
    return rng.choice("6789") + "".join(rng.choice("0123456789") for _ in range(9))


# ---------------------------------------------------------------------------
# CDR
# ---------------------------------------------------------------------------
cdr: list[dict] = []


def add_cdr(target, other, kind, when, dur, imei, cell):
    cdr.append({
        "target_number": target, "other_number": other, "call_type": kind,
        "start_time": fmt(when) if isinstance(when, datetime) else when,
        "duration_sec": dur, "imei": imei, "cell_id": cell, "cell_location": CELLS[cell],
    })


def both_sides(a, a_imei, a_cell, b, b_imei, b_cell, when, dur, kind="CALL"):
    """Record one event in both parties' CDRs (only for numbers we hold CDRs for)."""
    out_kind, in_kind = f"{kind}_OUT", f"{kind}_IN"
    add_cdr(a, b, out_kind, when, dur, a_imei, a_cell)
    if b_imei:
        add_cdr(b, a, in_kind, when, dur, b_imei, b_cell)


def sameer_imei(when: datetime) -> str:
    return IMEI_SAMEER_OLD if datetime(2026, 9, 30, 8) <= when < datetime(2026, 10, 7, 9, 31) else IMEI_MAIN


# --- Planted rows: the facts the investigation depends on -------------------
VICTIM_IMEI = "490154203237518"
ROHIT_IMEI = "353918107744120"
IMRAN_IMEI = "352114096628301"
ANIL_IMEI = "357201093361845"

# 1) Courier call and the CBI "digital arrest" calls to the victim (03-05 Oct)
both_sides(SCAM_CALLER, IMEI_KEYPAD, "NSK-BHD-03", VICTIM, VICTIM_IMEI, "PUN-KTH-11",
           ts("2026-10-03 10:12:04"), 1460)
for day, times in {
    "2026-10-03": ["10:41:10", "12:05:33", "14:20:02", "15:31:47", "16:58:20", "19:40:11", "22:15:09"],
    "2026-10-04": ["08:02:15", "10:30:44", "13:12:09", "16:45:30", "20:05:51"],
    "2026-10-05": ["07:55:02", "10:48:19", "11:16:40", "12:30:05"],
}.items():
    for t in times:
        when = ts(f"{day} {t}")
        victim_cell = "PUN-KTH-02" if t in ("15:31:47", "16:58:20", "11:16:40") else "PUN-KTH-11"
        both_sides(SCAM_CBI, IMEI_MAIN, "NSK-BHD-03", VICTIM, VICTIM_IMEI, victim_cell,
                   when, rng.randint(600, 3400))
# data sessions of the scam SIM (ConnectX video) from Bhadrakali
d = datetime(2026, 9, 30, 8, 5)
while d < datetime(2026, 10, 6, 21, 14):
    add_cdr(SCAM_CBI, "", "DATA", d, rng.randint(300, 3600), IMEI_MAIN, "NSK-BHD-03")
    d += timedelta(minutes=rng.randint(90, 300))
add_cdr(SCAM_CBI, "", "DATA", ts("2026-10-06 21:14:00"), 120, IMEI_MAIN, "NSK-BHD-03")

# 2) OTP forwarding: bank OTP SMS to Rohit, forwarded to the scam SIM within a minute
otp_times = ["2026-10-03 15:51:12", "2026-10-03 15:57:30", "2026-10-03 17:13:05",
             "2026-10-03 17:19:40", "2026-10-03 17:25:22", "2026-10-05 11:29:08",
             "2026-10-05 11:33:15", "2026-10-05 11:39:02"]
for t in otp_times:
    when = ts(t)
    add_cdr(ROHIT, "KSFBNK", "SMS_IN", when, 0, ROHIT_IMEI, "PUN-HDP-07")
    fwd = when + timedelta(seconds=rng.randint(15, 45))
    both_sides(ROHIT, ROHIT_IMEI, "PUN-HDP-07", SCAM_CBI, IMEI_MAIN, "NSK-BHD-03", fwd, 0, kind="SMS")

# 3) Imran <-> scam SIM and Imran <-> Sameer
both_sides(IMRAN, IMRAN_IMEI, "MLG-KDW-01", SCAM_CBI, IMEI_MAIN, "NSK-BHD-03", ts("2026-10-03 15:35:10"), 94)
both_sides(IMRAN, IMRAN_IMEI, "MLG-KDW-01", SCAM_CBI, IMEI_MAIN, "NSK-BHD-03", ts("2026-10-05 11:15:42"), 51)
for t in ["2026-09-08 19:22:10", "2026-09-14 13:05:44", "2026-09-21 21:40:03", "2026-09-25 09:12:30", "2026-09-27 18:30:00"]:
    both_sides(SAMEER, IMEI_MAIN, "NSK-BHD-03", IMRAN, IMRAN_IMEI, "MLG-KDW-01", ts(t), rng.randint(40, 400))
# 25-Sep: Imran in Pune with Rohit at the bank
add_cdr(IMRAN, rand_number(), "CALL_OUT", ts("2026-09-25 12:02:11"), 75, IMRAN_IMEI, "PUN-HDP-07")
add_cdr(IMRAN, ROHIT, "CALL_OUT", ts("2026-09-25 11:48:40"), 33, IMRAN_IMEI, "PUN-HDP-07")
add_cdr(ROHIT, IMRAN, "CALL_IN", ts("2026-09-25 11:48:40"), 33, ROHIT_IMEI, "PUN-HDP-07")

# 4) Imran's movements on 05-Oct: Malegaon -> highway -> Dwarka Circle ATM -> call Sameer -> back
imran_day = [
    ("2026-10-05 09:40:12", "MLG-KDW-01"), ("2026-10-05 12:35:50", "MLG-KDW-01"),
    ("2026-10-05 13:22:05", "NSK-HWY-05"), ("2026-10-05 14:21:33", "NSK-DWK-02"),
    ("2026-10-05 14:46:10", "NSK-DWK-02"), ("2026-10-05 15:08:44", "NSK-DWK-02"),
    ("2026-10-05 16:10:20", "NSK-HWY-05"), ("2026-10-05 17:32:02", "MLG-KDW-01"),
]
for t, cell in imran_day:
    add_cdr(IMRAN, rand_number(), rng.choice(["CALL_OUT", "CALL_IN"]), ts(t), rng.randint(20, 200), IMRAN_IMEI, cell)
both_sides(IMRAN, IMRAN_IMEI, "NSK-DWK-02", SAMEER, IMEI_SAMEER_OLD, "NSK-BHD-03", ts("2026-10-05 14:52:18"), 63)
add_cdr(IMRAN, "", "DATA", ts("2026-10-05 14:49:02"), 60, IMRAN_IMEI, "NSK-DWK-02")
# 06-Oct: Nashik Road branch cash withdrawal
add_cdr(IMRAN, rand_number(), "CALL_OUT", ts("2026-10-06 12:02:40"), 45, IMRAN_IMEI, "NSK-NRD-04")
add_cdr(IMRAN, SAMEER, "CALL_OUT", ts("2026-10-06 12:40:15"), 88, IMRAN_IMEI, "NSK-NRD-04")
add_cdr(SAMEER, IMRAN, "CALL_IN", ts("2026-10-06 12:40:15"), 88, IMEI_SAMEER_OLD, "NSK-BHD-03")

# 5) Archive link: the courier number also called the victim of an older case
add_cdr(SCAM_CALLER, ARCHIVE_VICTIM, "CALL_OUT", ts("2026-08-21 11:04:30"), 980, IMEI_KEYPAD, "NSK-BHD-03")
add_cdr(SCAM_CALLER, ARCHIVE_VICTIM, "CALL_OUT", ts("2026-08-21 13:30:12"), 640, IMEI_KEYPAD, "NSK-BHD-03")

# --- Noise: ordinary daily life for each number we hold CDRs for --------------
def anil_cell(when: datetime) -> str:
    if datetime(2026, 9, 20, 8) <= when < datetime(2026, 9, 28, 17):
        return "PUN-KTH-11"  # stayed with uncle in Kothrud
    if when.weekday() < 5 and 9 <= when.hour < 19:
        return "BLR-WTF-03"
    return "BLR-BRK-12"


def imran_cell(when: datetime) -> str:
    if when.date() == datetime(2026, 9, 25).date() and 9 <= when.hour < 17:
        return "PUN-HDP-07"
    return "MLG-KDW-01"


profiles = {
    VICTIM: dict(imei=lambda w: VICTIM_IMEI, cell=lambda w: "PUN-KTH-11", per_day=(2, 6), contacts=18),
    ROHIT: dict(imei=lambda w: ROHIT_IMEI, cell=lambda w: "PUN-HDP-07", per_day=(6, 14), contacts=40),
    IMRAN: dict(imei=lambda w: IMRAN_IMEI, cell=imran_cell, per_day=(8, 18), contacts=60),
    ANIL: dict(imei=lambda w: ANIL_IMEI, cell=anil_cell, per_day=(4, 10), contacts=30),
    SAMEER: dict(imei=sameer_imei, cell=lambda w: "NSK-BHD-03", per_day=(3, 9), contacts=35),
    SCAM_CALLER: dict(imei=lambda w: IMEI_KEYPAD, cell=lambda w: "NSK-BHD-03", per_day=(0, 3), contacts=25),
}
for number, p in profiles.items():
    contacts = [rand_number() for _ in range(p["contacts"])]
    day = START
    while day <= END:
        # Imran's 05-Oct is fully planted above; keep noise out of the window that matters
        n = rng.randint(*p["per_day"])
        for _ in range(n):
            when = day + timedelta(hours=rng.randint(7, 22), minutes=rng.randint(0, 59), seconds=rng.randint(0, 59))
            if number == IMRAN and when.date() == datetime(2026, 10, 5).date() and 12 <= when.hour < 18:
                continue
            if number == SAMEER and datetime(2026, 9, 30) <= when < datetime(2026, 10, 7):
                pass  # still active on the spare handset
            if number == SCAM_CALLER and when > datetime(2026, 10, 5, 23):
                continue
            kind = rng.choices(["CALL_OUT", "CALL_IN", "SMS_IN", "SMS_OUT", "DATA"], [30, 30, 15, 5, 20])[0]
            other = "" if kind == "DATA" else rng.choice(contacts)
            dur = 0 if kind.startswith("SMS") else rng.randint(10, 900)
            add_cdr(number, other, kind, when, dur, p["imei"](when), p["cell"](when))
        day += timedelta(days=1)

cdr.sort(key=lambda r: (r["target_number"], r["start_time"]))

# ---------------------------------------------------------------------------
# Bank transactions
# ---------------------------------------------------------------------------
ACCTS = {
    "victim": ("10020034571", "Suresh Kulkarni", "Sahyadri National Bank"),
    "rohit": ("50210043318876", "Rohit Pawar", "Konkan Small Finance Bank"),
    "imran": ("31082290447", "Shaikh Mobile Point (Imran Shaikh)", "Narmada Bank"),
}
txns: list[dict] = []
counter = [0]


def add_txn(acct_key, when, direction, amount, mode, cp_acct, cp_name, remarks, location="", utr=""):
    acct, holder, bank = ACCTS[acct_key]
    counter[0] += 1
    txns.append({
        "txn_id": f"T{counter[0]:05d}", "account_no": acct, "account_holder": holder, "bank": bank,
        "txn_time": when, "direction": direction, "amount": amount, "mode": mode,
        "counterparty_account": cp_acct, "counterparty_name": cp_name, "utr": utr,
        "remarks": remarks, "location": location,
    })


def transfer(src, dst, when, amount, mode, utr, remarks=""):
    s, d = ACCTS[src], ACCTS[dst]
    add_txn(src, when, "DR", amount, mode, d[0], d[1], remarks, utr=utr)
    add_txn(dst, when, "CR", amount, mode, s[0], s[1], remarks, utr=utr)


# Planted: victim -> Rohit (RTGS)
transfer("victim", "rohit", "2026-10-03 15:40:00", 950000, "RTGS", "SNBR526100338841", "RTGS at branch")
transfer("victim", "rohit", "2026-10-03 17:05:00", 1200000, "RTGS", "SNBR526100341192", "RTGS at branch")
transfer("victim", "rohit", "2026-10-05 11:20:00", 1700000, "RTGS", "SNBR528100015530", "RTGS at branch")

# Planted: Rohit -> layers (IMPS, each just after an OTP)
outs = [
    ("2026-10-03 15:52:01", "imran", 490000), ("2026-10-03 15:58:12", "BAPI", 460000),
    ("2026-10-03 17:14:00", "imran", 490000), ("2026-10-03 17:20:31", "BAPI", 400000),
    ("2026-10-03 17:26:05", "imran", 310000), ("2026-10-05 11:30:02", "imran", 490000),
    ("2026-10-05 11:34:10", "imran", 360000), ("2026-10-05 11:40:00", "HEMANT", 840000),
]
for i, (when, dst, amt) in enumerate(outs):
    utr = f"IMPS6{27 + i:02d}{rng.randint(100000, 999999)}"
    if dst == "imran":
        transfer("rohit", "imran", when, amt, "IMPS", utr, "NB transfer")
    elif dst == "BAPI":
        add_txn("rohit", when, "DR", amt, "IMPS", "7700118245", "Bapi Mondal (Bengal Rural Bank)", "NB transfer", utr=utr)
    else:
        add_txn("rohit", when, "DR", amt, "IMPS", "0451200381", "Hemant Saini (Marudhar Co-op Bank)", "NB transfer", utr=utr)

# Planted: account rent, Imran -> Rohit
transfer("imran", "rohit", "2026-09-27 18:41:09", 15000, "UPI", "UPI626918330421", "acct rent")

# Planted: Imran cash-out
for i, t in enumerate(["14:31:30", "14:33:41", "14:35:52", "14:38:05", "14:40:20", "14:43:58"]):
    add_txn("imran", f"2026-10-05 {t}", "DR", [50000, 50000, 50000, 50000, 50000, 47000][i], "ATM",
            "", "", "ATM WDL NB-NSK-0417", location="ATM NB-NSK-0417 Dwarka Circle, Nashik")
add_txn("imran", "2026-10-05 15:20:44", "DR", 940000, "IMPS", "6620045519", "Gulshan Traders", "supplier payment", utr="IMPS6281045520")
add_txn("imran", "2026-10-06 12:15:00", "DR", 900000, "CASH", "", "", "SELF CHQ 000117", location="Nashik Road branch")

# Noise: normal life
d = START
while d <= END:
    if d.day == 1:
        add_txn("victim", fmt(d + timedelta(hours=10)), "CR", 78450, "NEFT", "", "Pension - Savitribai Phule Univ", "pension")
    for _ in range(rng.randint(0, 2)):
        add_txn("victim", fmt(d + timedelta(hours=rng.randint(8, 20), minutes=rng.randint(0, 59))), "DR",
                rng.choice([120, 340, 560, 899, 1450, 2300, 3100]), "UPI", "", rng.choice(
                    ["Kothrud Medicals", "MSEDCL electricity", "Fresh Mart", "Pune Gas", "Book Corner", "Milk dairy"]), "UPI")
    for _ in range(rng.randint(0, 2)):
        add_txn("rohit", fmt(d + timedelta(hours=rng.randint(9, 22), minutes=rng.randint(0, 59))), "DR",
                rng.choice([20, 45, 60, 120, 199, 249, 350]), "UPI", "", rng.choice(
                    ["College canteen", "Mobile recharge", "Tea stall", "Xerox shop", "Bus pass"]), "UPI")
    for _ in range(rng.randint(3, 8)):
        cr = rng.random() < 0.6
        add_txn("imran", fmt(d + timedelta(hours=rng.randint(10, 21), minutes=rng.randint(0, 59))), "CR" if cr else "DR",
                rng.choice([450, 799, 1200, 2500, 4999, 8999, 12500, 15999, 21000]), "UPI", "",
                rng.choice(["Walk-in customer", "Phone repair", "Accessories", "Distributor Malegaon", "Spare parts Nashik"]),
                "UPI")
    d += timedelta(days=1)
add_txn("rohit", "2026-08-11 12:10:00", "CR", 500, "CASH", "", "", "account opening deposit")
add_txn("rohit", "2026-09-10 11:00:00", "CR", 12000, "NEFT", "", "MahaDBT scholarship", "scholarship")

txns.sort(key=lambda r: (r["account_no"], r["txn_time"]))


def write(name, rows):
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / name, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {len(rows):>5} rows -> {OUT / name}")


if __name__ == "__main__":
    write("cdr.csv", cdr)
    write("transactions.csv", txns)
