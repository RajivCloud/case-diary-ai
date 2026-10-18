"""Generate the sample case kit CYB-131-2026: a fake stock-trading-app fraud, as RAW files
the way a police station receives them (Word / text documents, an Excel bank export,
a bank CSV in its own format, a telecom CDR export with MOC/MTC codes).

The kit is loaded through the same pipeline as the New Case wizard (core/sample_kit.py).
Truth first: answer_key.json is written from the same facts as the documents and rows.

Run: python scripts/generate_kit_131.py
"""

from __future__ import annotations

import csv
import json
import random
from datetime import datetime, timedelta
from pathlib import Path

import docx
import pandas as pd

KIT = Path(__file__).resolve().parent.parent / "sample_upload" / "CYB-131-2026"
rng = random.Random(131)

VICTIM, ADMIN, FAISAL, VINOD = "9850123478", "7387004512", "9820456631", "9922310045"
IMEI = {VICTIM: "352900114562219", ADMIN: "355412097781230", FAISAL: "359112086654327", VINOD: "861555043219087"}
CELL = {"PUN": ("PUN-BNR-06", "Baner, Pune"), "BWD": ("BWD-NZM-04", "Nizampura, Bhiwandi"),
        "BWD2": ("BWD-KLW-01", "Kalyan Road, Bhiwandi"), "CSN": ("CSN-OSM-02", "Osmanpura, Chh. Sambhajinagar")}

# ------------------------------------------------------------------ documents (raw text)
DOCS = [
    ("01_NCRP_complaint.txt", "complaint", "NCRP complaint acknowledgement - Kavita Deshmukh", "2026-10-08", "Kavita Deshmukh", """
National Cyber Crime Reporting Portal. Acknowledgement No. 31510260004461 dated 08-Oct-2026, 18:20 hrs, through 1930 helpline. Category: Online Financial Fraud - Investment / Trading Fraud.

Complainant: Mrs. Kavita Deshmukh, age 52, Principal, Vidya Niketan School, residing at B-602, Silver Oak Society, Baner, Pune 411045. Mobile 9850123478.

On 28-Aug-2026 I was added to a ChatWave group "GoldenBull IPO Club" by the admin "Dr. Arvind Mehta (SEBI-registered analyst)", mobile 7387004512. He told members to install the "GB Pro Trade" app from a link and to invest through it for IPO allotments.

Between 03-Sep and 29-Sep-2026 I transferred Rs 24,50,000 in six transfers to accounts given in the app: Shree Sai Traders (Godavari Bank), Neha Patil (Konkan Small Finance Bank) and Sunrise Agro Exports. The app showed a profit of Rs 61 lakh. When I tried to withdraw, I was asked to pay 15 percent "tax" first. I paid Rs 3,50,000 as tax on 29-Sep but was asked for more. Then I understood it was a fraud.

My colleague Sunil Joshi had recommended this group to me. Requested action: freeze the beneficiary accounts.
"""),
    ("02_FIR_131_2026.docx", "fir", "First Information Report No. 131/2026, Cyber Police Station, Pune City", "2026-10-12", "Kavita Deshmukh; Rahul Kadam", """
FIRST INFORMATION REPORT (under Section 173 BNSS). District: Pune City. Police Station: Cyber Police Station, Shivajinagar. FIR No. 131/2026. Date and time of FIR: 12-Oct-2026, 11:40 hrs.

Acts and sections: Bharatiya Nyaya Sanhita, 2023 - Sections 318(4), 319(2), 336(3), 61(2); Information Technology Act, 2000 - Section 66D.

Occurrence of offence: 28-Aug-2026 to 29-Sep-2026, through the ChatWave messaging app and the "GB Pro Trade" application.

Complainant: Mrs. Kavita Deshmukh, age 52, Baner, Pune. Mobile 9850123478.

Details of known / suspected / unknown accused: unknown person using mobile 7387004512 as "Dr. Arvind Mehta"; operators of the app "GB Pro Trade" (domain gbprotrade.app); holders of Godavari Bank account 60450012783 (Shree Sai Traders), Konkan SFB account 50210066120044 (Neha Patil) and the account of Sunrise Agro Exports.

Property involved: Rs 24,50,000 transferred from Deccan Urban Co-operative Bank account 20117745902 of the complainant.

Action taken: case registered; investigation entrusted to PSI Rahul Kadam, Cyber Police Station, Pune City.
"""),
    ("03_statement_Kavita_Deshmukh.docx", "statement_180", "Statement of Mrs. Kavita Deshmukh under Section 180 BNSS", "2026-10-12", "Kavita Deshmukh; Sunil Joshi", """
Statement recorded by PSI Rahul Kadam on 12-Oct-2026. I, Kavita Deshmukh, age 52, Principal, residing at Baner, Pune, state as follows.

My colleague Sunil Joshi, a senior teacher in our school, told me in August that he was earning good profits in an IPO group and shared the ChatWave group link. On 28-Aug the admin "Dr. Arvind Mehta" added me. Mehta sir also called me on my phone from 7387004512 a few times and spoke in Hindi.

I installed the GB Pro Trade app. It showed my deposits and profits. I made transfers by net banking from my Deccan Urban Bank account: Rs 2,00,000 on 03-Sep, Rs 4,50,000 on 10-Sep and Rs 6,00,000 on 22-Sep to Shree Sai Traders; Rs 3,50,000 on 15-Sep and Rs 5,00,000 on 25-Sep to Neha Patil; and Rs 3,50,000 on 29-Sep to Sunrise Agro Exports as the "15 percent tax".

I suspect Sunil Joshi is part of this gang because he brought me into the group and kept encouraging me to invest more. I have no other suspicion.

I have saved screenshots of the app, the group chat and the payment receipts. I will hand them over on a pen drive.
"""),
    ("04_Deccan_Urban_Bank_reply.txt", "bank_reply", "Deccan Urban Co-op Bank reply - complainant's account debits", "2026-10-13", "Kavita Deshmukh", """
Deccan Urban Co-operative Bank, Baner branch, Pune. Reply to notice under Section 94 BNSS dated 12-Oct-2026. Account No. 20117745902, holder Kavita Deshmukh.

Six outward transfers were made by net banking from the customer's registered device between 03-Sep and 29-Sep-2026, totalling Rs 24,50,000, to: Shree Sai Traders, Godavari Bank A/c 60450012783 (three transfers, Rs 12,50,000); Neha Patil, Konkan Small Finance Bank A/c 50210066120044 (two transfers, Rs 8,50,000); Sunrise Agro Exports, Marudhar Co-operative Bank A/c 0451300912 (one transfer, Rs 3,50,000).

The account statement for 01-Aug-2026 to 12-Oct-2026 is enclosed as an Excel file with a certificate under Section 63 of the Bharatiya Sakshya Adhiniyam signed by the Branch Manager.
"""),
    ("05_Godavari_Bank_reply_Shree_Sai_Traders.txt", "bank_reply", "Godavari Bank reply - account of Shree Sai Traders (Vinod Gaikwad)", "2026-10-14", "Vinod Gaikwad", """
Godavari Bank, Osmanpura branch, Chhatrapati Sambhajinagar. Reply to notice under Section 94 BNSS. Current account No. 60450012783 in the name of "Shree Sai Traders", sole proprietor Vinod Ramdas Gaikwad, age 41, Osmanpura, Chhatrapati Sambhajinagar. Registered mobile 9922310045. Net banking is registered only to the proprietor; no other authorised signatory or user exists on the account.

Between 03-Sep and 22-Sep-2026 the account received Rs 12,50,000 from Kavita Deshmukh, Rs 4,00,000 from Sunil Joshi (07-Sep and 18-Sep) and other credits. Outward IMPS transfers totalling Rs 14,20,000 were made to "CoinVault Technologies - P2P escrow" with the reference "FQ Digital". Each outward IMPS was authorised by an OTP sent by SMS (sender GDVBNK) to the registered mobile 9922310045.

On 23-Sep-2026 at 13:10 hrs a self-cheque cash withdrawal of Rs 3,00,000 was made at the branch counter. The cheque was presented by the proprietor Vinod Gaikwad in person; his signature was verified and his identity was checked by the cashier. Branch CCTV for that date has been preserved.

The account statement is enclosed in electronic form with a certificate under Section 63 BSA. Debit freeze applied on 13-Oct-2026; balance at freeze Rs 4,22,400.
"""),
    ("06_Konkan_SFB_reply_Neha_Patil.txt", "bank_reply", "Konkan Small Finance Bank reply - account of Neha Patil", "2026-10-14", "Neha Patil", """
Konkan Small Finance Bank, Kothrud branch, Pune. Reply to notice under Section 94 BNSS. Savings account No. 50210066120044, holder Neha Suresh Patil, age 20, student, Karve Nagar, Pune. Registered mobile 9067113452.

The account received Rs 3,50,000 on 15-Sep and Rs 5,00,000 on 25-Sep-2026 from Kavita Deshmukh. The funds were withdrawn through ATM KSFB-BWD-0021, Kalyan Road, Bhiwandi (Rs 1,96,000 on 16-Sep and Rs 2,00,000 on 26-Sep) and Rs 4,00,000 was sent by IMPS to "CoinVault Technologies - P2P escrow" with the reference "FQ Digital".

The account holder resides in Pune; all ATM withdrawals took place in Bhiwandi. The statement is enclosed with a certificate under Section 63 BSA. Debit freeze applied on 13-Oct-2026; balance at freeze Rs 55,000.
"""),
    ("07_statement_Vinod_Gaikwad.docx", "statement_180", "Statement of Vinod Gaikwad under Section 180 BNSS", "2026-10-15", "Vinod Gaikwad; Ganesh Shinde", """
Statement recorded at Chhatrapati Sambhajinagar on 15-Oct-2026. I, Vinod Ramdas Gaikwad, age 41, proprietor of Shree Sai Traders, Osmanpura, state as follows.

I run a small agricultural supplies business. My accountant Ganesh Shinde handles all the banking work of the firm, including net banking. If any wrong money came into my account, he must have misused it without my knowledge.

I did not know about these credits from Pune and I never withdrew any large amount in September. I do not know anyone called Dr. Arvind Mehta or Faisal. I do not trade in crypto.

My mobile number is 9922310045. I will cooperate with the investigation.
"""),
    ("08_statement_Ganesh_Shinde.txt", "statement_180", "Statement of Ganesh Shinde (accountant) under Section 180 BNSS", "2026-10-15", "Ganesh Shinde; Vinod Gaikwad", """
Statement recorded on 15-Oct-2026. I, Ganesh Shinde, age 34, part-time accountant for Shree Sai Traders and two other shops, state as follows.

I prepare the GST returns and the cash book of Shree Sai Traders. I do not have the net-banking login of the current account. Vinod sheth keeps the login and the registered phone himself and makes all online payments.

From 20-Sep to 26-Sep-2026 I was admitted at Sahyog Hospital, Chhatrapati Sambhajinagar, for dengue. My discharge summary is attached. I have not seen the bank statement for September.
"""),
    ("09_statement_Neha_Patil.txt", "statement_180", "Statement of Neha Patil under Section 180 BNSS", "2026-10-16", "Neha Patil", """
Statement recorded at Cyber Police Station, Pune, on 16-Oct-2026. I, Neha Suresh Patil, age 20, student of B.Sc., Karve Nagar, Pune, state as follows.

In August a person called "Aamir bhai" contacted me on Instagram and offered Rs 10,000 for "renting" my bank account for a gaming business. I gave him my passbook, debit card, cheque book and the SIM card of my registered mobile 9067113452 through a courier to Bhiwandi.

I received Rs 10,000 in cash through a friend. I did not know the money would come from a fraud. I have never met Aamir bhai and I do not know anyone named Faisal or Arvind Mehta. I have not withdrawn any money in Bhiwandi.
"""),
    ("10_statement_Sunil_Joshi.txt", "statement_180", "Statement of Sunil Joshi under Section 180 BNSS", "2026-10-16", "Sunil Joshi", """
Statement recorded on 16-Oct-2026. I, Sunil Joshi, age 55, senior teacher, Vidya Niketan School, Baner, state as follows.

I joined the GoldenBull IPO Club group in July after seeing an advertisement. I believed the profits shown in the app and recommended the group to my colleague Kavita Deshmukh. I am very sorry for this.

I myself transferred Rs 2,50,000 on 07-Sep and Rs 1,50,000 on 18-Sep-2026 to Shree Sai Traders on the instructions of the group, and I have lost Rs 4,00,000. I filed my own complaint on the 1930 helpline, acknowledgement No. 31510260004389 dated 07-Oct-2026.
"""),
    ("11_hosting_provider_reply_gbprotrade.txt", "platform_reply", "Hosting provider reply - admin panel of gbprotrade.app", "2026-10-17", "", """
Reply of the hosting provider of the domain gbprotrade.app to a notice under Section 94 BNSS. The domain hosts the "GB Pro Trade" web application and its administrator panel.

The administrator account "gbadmin" logged in to the panel from IP address 49.36.112.87 on 02-Sep-2026 at 22:10, 09-Sep-2026 at 23:05, 21-Sep-2026 at 21:40 and 28-Sep-2026 at 22:55 hrs IST. The panel was used to edit the "profit" figures shown to users, including the account of the user registered with mobile 9850123478.

The logs are provided in electronic form with a certificate under Section 63 BSA.
"""),
    ("12_ISP_reply_SkyLink.txt", "platform_reply", "ISP reply - subscriber of IP address 49.36.112.87", "2026-10-17", "Faisal Qureshi", """
Reply of the Nodal Officer, SkyLink Broadband, to a notice under Section 94 BNSS regarding IP address 49.36.112.87 at the dates and times listed by the hosting provider.

At all four times the IP address was allotted to the fibre broadband connection of subscriber Faisal Ahmed Qureshi, Flat 4, Al-Noor Complex, Nizampura, Bhiwandi, District Thane. Registered contact mobile 9820456631. KYC verified with Aadhaar at installation in March 2025.

The IP allocation logs are provided with a certificate under Section 63 BSA signed by the Nodal Officer.
"""),
    ("13_CoinVault_exchange_reply.txt", "platform_reply", "CoinVault crypto exchange reply - P2P merchant FQ Digital", "2026-10-17", "Faisal Qureshi", """
Email reply received on 17-Oct-2026 from the compliance team of CoinVault Technologies, a crypto exchange, to a notice under Section 94 BNSS.

The P2P merchant account "FQ Digital" is registered to Faisal Ahmed Qureshi, Bhiwandi, mobile 9820456631, KYC with PAN and Aadhaar. Between 04-Sep and 30-Sep-2026 the merchant received INR deposits into the P2P escrow from Godavari Bank account 60450012783 (Shree Sai Traders) totalling Rs 14,20,000 and from Konkan SFB account 50210066120044 (Neha Patil) totalling Rs 4,00,000. The INR was converted to USDT and withdrawn to external wallets.

This is an email reply. A signed copy and the certificate under Section 63 BSA will be sent separately.
"""),
    ("14_telecom_reply_7387004512.txt", "telecom_reply", "Telecom reply - subscriber of 7387004512 ('Dr. Arvind Mehta')", "2026-10-14", "Arvind Mehta", """
Reply of the Nodal Officer, Airwave Telecom, to notice under Section 94 BNSS. Mobile number 7387004512: subscriber name Arvind Mehta, address given as Satellite, Ahmedabad, Gujarat. Activated on 20-Aug-2026 through point-of-sale agent "Royal Mobile", Kalyan Road, Bhiwandi.

Address verification: no person by this name at the address. The SIM appears to have been issued on forged documents.

Call detail records with IMEI and cell-site locations for 7387004512 for 01-Aug to 12-Oct-2026 are provided in electronic form with a certificate under Section 63 BSA. CDRs of 9850123478, 9820456631 and 9922310045 obtained from their operators are also enclosed, each with a Section 63 certificate.
"""),
    ("15_complainant_letter_screenshots.txt", "third_party_letter", "Complainant's letter submitting screenshots on pen drive", "2026-10-13", "Kavita Deshmukh", """
Letter dated 13-Oct-2026 from Mrs. Kavita Deshmukh to the Investigating Officer, Cyber Police Station, Pune City.

I am submitting a pen drive containing 46 screenshots: the GoldenBull IPO Club group chat, messages from "Dr. Arvind Mehta" (7387004512), the GB Pro Trade app screens showing my "portfolio" and "profit", and my net-banking receipts.

The screenshots were taken on my mobile phone between 28-Aug and 08-Oct-2026. No certificate has been prepared for them.
"""),
]

# ------------------------------------------------------------------ CDR (telecom export format)
cdr_rows: list[dict] = []
TYPE = {"CALL_OUT": "MOC", "CALL_IN": "MTC", "SMS_OUT": "SMS-MO", "SMS_IN": "SMS-MT", "DATA": "GPRS"}


def add(a, b, kind, when: datetime, dur, cell_key):
    cid, addr = CELL[cell_key]
    cdr_rows.append({"A Party": "91" + a, "B Party": b, "Call Date": when.strftime("%d/%m/%Y"),
                     "Call Time": when.strftime("%H:%M:%S"), "Duration (sec)": dur, "Call Type": TYPE[kind],
                     "IMEI": IMEI[a], "First Cell ID": cid, "First Cell Address": addr})


def call(a, a_cell, b, b_cell, when, dur, kind="CALL"):
    add(a, b, f"{kind}_OUT", when, dur, a_cell)
    if b in IMEI:
        add(b, a, f"{kind}_IN", when, dur, b_cell)


T = lambda s: datetime.strptime(s, "%Y-%m-%d %H:%M")  # noqa: E731
# "Dr. Mehta" calls the victim; admin SIM and Faisal's own SIM are always on the same Bhiwandi towers
for s in ["2026-08-28 19:30", "2026-09-02 20:10", "2026-09-09 21:15", "2026-09-21 19:45", "2026-09-28 20:30",
          "2026-09-30 11:20", "2026-10-06 18:05"]:
    call(ADMIN, "BWD", VICTIM, "PUN", T(s), rng.randint(300, 1500))
d = datetime(2026, 8, 20, 9)
while d < datetime(2026, 10, 12):
    for _ in range(rng.randint(2, 5)):
        w = d + timedelta(hours=rng.randint(0, 13), minutes=rng.randint(0, 59))
        cell = "BWD2" if 10 <= w.hour < 14 and rng.random() < 0.5 else "BWD"
        add(ADMIN, "", "DATA", w, rng.randint(200, 3000), cell)
        add(FAISAL, "", "DATA", w + timedelta(minutes=rng.randint(1, 9)), rng.randint(200, 3000), cell)
    d += timedelta(days=1)
# Vinod: OTP SMS before each CoinVault IMPS, and calls to the admin number after victim credits
coinvault_out = ["2026-09-04 11:40", "2026-09-08 12:15", "2026-09-11 10:20", "2026-09-19 16:05", "2026-09-23 10:45",
                 "2026-09-23 15:30"]
for s in coinvault_out:
    w = T(s) - timedelta(minutes=1)
    add(VINOD, "GDVBNK", "SMS_IN", w, 0, "CSN")
for s in ["2026-09-03 11:25", "2026-09-07 15:05", "2026-09-10 15:50", "2026-09-18 12:30", "2026-09-22 10:40",
          "2026-09-23 13:35"]:
    call(VINOD, "CSN", ADMIN, "BWD", T(s), rng.randint(40, 240))
for s in ["2026-08-25 18:10", "2026-09-05 20:20", "2026-09-24 19:00"]:
    call(VINOD, "CSN", FAISAL, "BWD", T(s), rng.randint(60, 400))
# noise
for num, cell, per in [(VICTIM, "PUN", (3, 8)), (FAISAL, "BWD", (4, 10)), (VINOD, "CSN", (5, 12)), (ADMIN, "BWD", (0, 2))]:
    contacts = ["9" + "".join(rng.choice("0123456789") for _ in range(9)) for _ in range(25)]
    d = datetime(2026, 8, 20)
    while d < datetime(2026, 10, 12):
        for _ in range(rng.randint(*per)):
            w = d + timedelta(hours=rng.randint(7, 22), minutes=rng.randint(0, 59), seconds=rng.randint(0, 59))
            k = rng.choice(["CALL_OUT", "CALL_IN", "SMS_IN"])
            add(num, rng.choice(contacts), k, w, 0 if k.startswith("SMS") else rng.randint(10, 600), cell)
        d += timedelta(days=1)
cdr_rows.sort(key=lambda r: (r["A Party"], datetime.strptime(r["Call Date"] + r["Call Time"], "%d/%m/%Y%H:%M:%S")))

# ------------------------------------------------------------------ bank statements (three formats)
victim_rows, sai_rows, neha_rows = [], [], []


def v(date_s, narration, ref, wd=0, dep=0):
    victim_rows.append({"Txn Date": date_s, "Value Date": date_s, "Narration": narration, "Chq/Ref No": ref,
                        "Withdrawal Amt": f"{wd:,.2f}" if wd else "", "Deposit Amt": f"{dep:,.2f}" if dep else ""})


for dt, nar, ref, amt in [("03-09-2026", "IMPS/SHREE SAI TRADERS/GODAVARI BANK/60450012783", "IMPS624611052231", 200000),
                          ("10-09-2026", "RTGS/SHREE SAI TRADERS/GODAVARI BANK/60450012783", "DUCBR525310044518", 450000),
                          ("15-09-2026", "IMPS/NEHA PATIL/KONKAN SFB/50210066120044", "IMPS625812440917", 350000),
                          ("22-09-2026", "RTGS/SHREE SAI TRADERS/GODAVARI BANK/60450012783", "DUCBR526510009921", 600000),
                          ("25-09-2026", "RTGS/NEHA PATIL/KONKAN SFB/50210066120044", "DUCBR526810016730", 500000),
                          ("29-09-2026", "RTGS/SUNRISE AGRO EXPORTS/MARUDHAR CO-OP BANK/0451300912", "DUCBR527210011204", 350000)]:
    v(dt, nar, ref, wd=amt)
d = datetime(2026, 8, 1)
while d <= datetime(2026, 10, 12):
    if d.day == 1:
        v(d.strftime("%d-%m-%Y"), "NEFT/SALARY/VIDYA NIKETAN TRUST", f"N{rng.randint(10**9, 10**10)}", dep=118500)
    if rng.random() < 0.5:
        v(d.strftime("%d-%m-%Y"), rng.choice(["UPI/D-MART BANER", "UPI/MSEDCL", "UPI/BANER MEDICAL", "ACH/LIC PREMIUM",
                                              "UPI/AMAZON PAY"]), f"UPI{rng.randint(10**9, 10**10)}",
          wd=rng.choice([450, 1200, 2399, 3600, 8800]))
    d += timedelta(days=1)


def s(date_s, time_s, part, ref, debit=0, credit=0):
    sai_rows.append({"Tran Date": date_s, "Tran Time": time_s, "Particulars": part, "Ref No": ref,
                     "Debit": debit or "", "Credit": credit or "", "Branch": "OSMANPURA"})


for dt, tm, part, cr in [("03/09/2026", "11:06", "BY IMPS KAVITA DESHMUKH DUCB", 200000),
                         ("07/09/2026", "14:51", "BY IMPS SUNIL JOSHI SNB", 250000),
                         ("10/09/2026", "15:21", "BY RTGS KAVITA DESHMUKH DUCB", 450000),
                         ("18/09/2026", "12:17", "BY IMPS SUNIL JOSHI SNB", 150000),
                         ("12/09/2026", "17:40", "BY IMPS RAMESH NAIK HDB", 120000),
                         ("22/09/2026", "10:16", "BY RTGS KAVITA DESHMUKH DUCB", 600000),
                         ("26/09/2026", "11:02", "BY IMPS PRIYA SHAH KTB", 80000)]:
    s(dt, tm, part, f"R{rng.randint(10**8, 10**9)}", credit=cr)
for (stamp, amt) in zip(coinvault_out, [190000, 245000, 205000, 280000, 300000, 200000]):
    dt = datetime.strptime(stamp, "%Y-%m-%d %H:%M")
    s(dt.strftime("%d/%m/%Y"), dt.strftime("%H:%M"), "TO IMPS COINVAULT TECHNOLOGIES P2P ESCROW REF FQ DIGITAL",
      f"I{rng.randint(10**8, 10**9)}", debit=amt)
s("23/09/2026", "13:10", "TO SELF CHQ 004412 CASH WDL AT BRANCH", "CHQ004412", debit=300000)
d = datetime(2026, 8, 1)
while d <= datetime(2026, 10, 12):
    for _ in range(rng.randint(0, 3)):
        cr = rng.random() < 0.55
        s(d.strftime("%d/%m/%Y"), f"{rng.randint(10, 19)}:{rng.randint(0, 59):02d}",
          rng.choice(["BY UPI FARMER", "TO UPI SEEDS SUPPLIER", "BY CASH DEP", "TO UPI TRANSPORT", "BY UPI SHOP"]),
          f"U{rng.randint(10**8, 10**9)}", **({"credit": rng.choice([1500, 4200, 9800, 15000])} if cr else
                                              {"debit": rng.choice([2200, 6400, 11000])}))
    d += timedelta(days=1)

ACC_N = ("50210066120044", "Neha Patil", "Konkan Small Finance Bank")


def n(t, direction, amount, mode, cp_acct, cp_name, remarks, location=""):
    neha_rows.append({"txn_id": "", "account_no": ACC_N[0], "account_holder": ACC_N[1], "bank": ACC_N[2],
                      "txn_time": t, "direction": direction, "amount": amount, "mode": mode,
                      "counterparty_account": cp_acct, "counterparty_name": cp_name, "utr": f"K{rng.randint(10**8, 10**9)}",
                      "remarks": remarks, "location": location})


n("2026-09-15 12:41:00", "CR", 350000, "IMPS", "20117745902", "Kavita Deshmukh", "IMPS credit")
n("2026-09-25 16:31:00", "CR", 500000, "RTGS", "20117745902", "Kavita Deshmukh", "RTGS credit")
for t, a in [("2026-09-16 10:02:00", 49000), ("2026-09-16 10:04:30", 49000), ("2026-09-16 10:07:10", 49000),
             ("2026-09-16 10:09:40", 49000), ("2026-09-26 11:15:00", 50000), ("2026-09-26 11:17:20", 50000),
             ("2026-09-26 11:19:45", 50000), ("2026-09-26 11:22:05", 50000)]:
    n(t, "DR", a, "ATM", "", "", "ATM WDL KSFB-BWD-0021", "ATM KSFB-BWD-0021 Kalyan Road, Bhiwandi")
n("2026-09-17 09:30:00", "DR", 150000, "IMPS", "", "CoinVault Technologies P2P escrow", "IMPS ref FQ DIGITAL")
n("2026-09-27 09:45:00", "DR", 250000, "IMPS", "", "CoinVault Technologies P2P escrow", "IMPS ref FQ DIGITAL")
n("2026-08-12 13:00:00", "CR", 1000, "CASH", "", "", "Opening deposit")

# ------------------------------------------------------------------ answer key (demo only)
L = r"[^\n]"
ANSWER_KEY = {
    "_note": "ANSWER KEY for the sample kit. The agent never reads it; only eval/run_eval.py does.",
    "case_id": "CYB-131-2026",
    "story": "Faisal Qureshi (Bhiwandi) ran the fake GB Pro Trade app and the 'Dr. Arvind Mehta' number 7387004512 "
             "(fake KYC). Vinod Gaikwad knowingly ran Shree Sai Traders as a mule and passed money to Faisal's "
             "CoinVault P2P merchant 'FQ Digital'. Neha Patil rented her account kit; it was operated from Bhiwandi. "
             "Sunil Joshi is a co-victim and Ganesh Shinde had no access - both red herrings.",
    "checks": [
        {"name": "Operator identified (Faisal Qureshi)", "kind": "accused", "person": "Faisal Qureshi"},
        {"name": "Mule account holder identified (Vinod Gaikwad)", "kind": "accused", "person": "Vinod Gaikwad"},
        {"name": "Rented account identified (Neha Patil)", "kind": "accused", "person": "Neha Patil"},
        {"name": "Red herring cleared (Sunil Joshi, co-victim)", "kind": "cleared", "person": "Sunil Joshi"},
        {"name": "Red herring cleared (Ganesh Shinde, accountant)", "kind": "cleared", "person": "Ganesh Shinde"},
        {"name": "Lie caught: Vinod blames accountant vs OTPs / self-cheque", "kind": "text", "all": [
            f"(Vinod|Gaikwad){L}{{0,400}}(accountant|Ganesh)",
            f"(Vinod|Gaikwad){L}{{0,400}}(self-?cheque|OTP|GDVBNK|in person)"
            f"|(self-?cheque|OTP|GDVBNK|in person){L}{{0,400}}(Vinod|Gaikwad)"]},
        {"name": "Key link: admin-panel IP 49.36.112.87 -> ISP subscriber Faisal", "kind": "text", "all": [
            f"49\\.36\\.112\\.87{L}{{0,300}}Faisal|Faisal{L}{{0,300}}49\\.36\\.112\\.87"]},
        {"name": "Key link: CoinVault P2P 'FQ Digital' KYC -> Faisal", "kind": "text", "all": [
            f"(CoinVault|FQ Digital){L}{{0,300}}Faisal|Faisal{L}{{0,300}}(CoinVault|FQ Digital)"]},
        {"name": "Key link: scam SIM co-located with Faisal's own SIM", "kind": "text", "all": [
            f"7387004512{L}{{0,400}}9820456631|9820456631{L}{{0,400}}7387004512"]},
        {"name": "Gap: screenshots lack BSA s.63 certificate", "kind": "text", "all": [
            f"screenshot{L}{{0,300}}63|63{L}{{0,300}}screenshot"]},
        {"name": "Gap: CoinVault reply is an email without certificate", "kind": "text", "all": [
            f"CoinVault{L}{{0,300}}(63|certificate|email|signed)"]},
        {"name": "Money: Rs 12.5 lakh to Shree Sai Traders traced", "kind": "text", "all": ["12,50,000|12\\.5 ?(L|lakh)|1250000"]},
        {"name": "Bonus: linked archive case CYB-090-2026 found", "kind": "text", "all": ["CYB-090"]},
    ],
}

# ------------------------------------------------------------------ kit manifest
KIT_JSON = {
    "case": {
        "case_id": "CYB-131-2026", "fir_no": "131/2026", "fir_date": "2026-10-12",
        "police_station": "Cyber Police Station, Pune City", "district": "Pune City",
        "fraud_type": "Fake stock-trading / investment app",
        "sections": ["BNS 318(4)", "BNS 319(2)", "BNS 336", "BNS 61(2)", "IT Act 66D"],
        "loss_inr": 2450000, "frozen_inr": 477400, "io_name": "PSI Rahul Kadam", "complainant": "Mrs. Kavita Deshmukh",
        "brief_facts": "A school principal was added to a 'GoldenBull IPO Club' chat group by a fake SEBI analyst "
                       "'Dr. Arvind Mehta', installed a fake trading app 'GB Pro Trade' showing false profits, and "
                       "transferred Rs 24.5 lakh in six transfers to three accounts, the last as a fake 'tax'.",
        "parties": [
            {"name": "Kavita Deshmukh", "role": "Victim / complainant", "phone": VICTIM, "account_no": "20117745902",
             "bank": "Deccan Urban Co-op Bank", "notes": "Baner, Pune"},
            {"name": "Sunil Joshi", "role": "Person named by complainant", "phone": "", "account_no": "", "bank": "",
             "notes": "Colleague who recommended the group"},
            {"name": "Unknown ('Dr. Arvind Mehta')", "role": "Suspect number", "phone": ADMIN, "account_no": "",
             "bank": "", "notes": "ChatWave group admin"},
            {"name": "Vinod Gaikwad", "role": "Beneficiary account holder", "phone": VINOD, "account_no": "60450012783",
             "bank": "Godavari Bank", "notes": "Shree Sai Traders, Chh. Sambhajinagar"},
            {"name": "Neha Patil", "role": "Beneficiary account holder", "phone": "9067113452",
             "account_no": "50210066120044", "bank": "Konkan Small Finance Bank", "notes": "Student, Pune"},
            {"name": "Faisal Qureshi", "role": "Other", "phone": FAISAL, "account_no": "", "bank": "",
             "notes": "Bhiwandi; CDR obtained"},
        ],
        "suggested_questions": [
            "Who operated the 'Dr. Arvind Mehta' number and the GB Pro Trade app? What links them?",
            "Is Sunil Joshi, who recommended the group, involved?",
            "Vinod Gaikwad blames his accountant. Do the records support that?",
            "Trace the Rs 24.5 lakh account by account.",
            "What evidence is still missing before chargesheet?",
        ],
    },
    "documents": [{"file": f, "doc_type": t, "title": ti, "date": da, "persons": pe} for f, t, ti, da, pe, _ in DOCS],
    "records": [
        {"file": "victim_statement_DeccanUrban.xlsx", "kind": "transactions",
         "mapping": {"date": "Txn Date", "remarks": "Narration", "counterparty_name": "Narration", "utr": "Chq/Ref No",
                     "debit": "Withdrawal Amt", "credit": "Deposit Amt"},
         "constants": {"account_no": "20117745902", "account_holder": "Kavita Deshmukh",
                       "bank": "Deccan Urban Co-op Bank", "mode": ""}},
        {"file": "GodavariBank_60450012783.csv", "kind": "transactions",
         "mapping": {"date": "Tran Date", "time": "Tran Time", "remarks": "Particulars",
                     "counterparty_name": "Particulars", "utr": "Ref No", "debit": "Debit", "credit": "Credit"},
         "constants": {"account_no": "60450012783", "account_holder": "Shree Sai Traders (Vinod Gaikwad)",
                       "bank": "Godavari Bank"}},
        {"file": "KonkanSFB_50210066120044_standard.csv", "kind": "transactions",
         "mapping": {c: c for c in ["txn_id", "account_no", "account_holder", "bank", "txn_time", "direction", "amount",
                                    "mode", "counterparty_account", "counterparty_name", "utr", "remarks", "location"]}},
        {"file": "CDR_export_4_numbers.csv", "kind": "cdr",
         "mapping": {"target_number": "A Party", "other_number": "B Party", "date": "Call Date", "time": "Call Time",
                     "duration_sec": "Duration (sec)", "call_type": "Call Type", "imei": "IMEI",
                     "cell_id": "First Cell ID", "cell_location": "First Cell Address"}},
    ],
    "answer_key": "answer_key.json",
    "recorded": ["agent_run.json", "baseline_run.json", "qa_suggested.json", "eval.json"],
}


def main() -> None:
    KIT.mkdir(parents=True, exist_ok=True)
    for fname, _t, _ti, _d, _p, body in DOCS:
        paras = [p.strip() for p in body.strip().split("\n\n")]
        if fname.endswith(".docx"):
            doc = docx.Document()
            for p in paras:
                doc.add_paragraph(p)
            doc.save(KIT / fname)
        else:
            (KIT / fname).write_text("\n\n".join(paras) + "\n", encoding="utf-8")
    pd.DataFrame(victim_rows).to_excel(KIT / "victim_statement_DeccanUrban.xlsx", index=False)
    pd.DataFrame(sai_rows).to_csv(KIT / "GodavariBank_60450012783.csv", index=False)
    pd.DataFrame(neha_rows).to_csv(KIT / "KonkanSFB_50210066120044_standard.csv", index=False)
    with open(KIT / "CDR_export_4_numbers.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(cdr_rows[0]))
        w.writeheader()
        w.writerows(cdr_rows)
    (KIT / "answer_key.json").write_text(json.dumps(ANSWER_KEY, indent=2, ensure_ascii=False), encoding="utf-8")
    (KIT / "kit.json").write_text(json.dumps(KIT_JSON, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"kit written to {KIT}: {len(DOCS)} documents, {len(cdr_rows)} CDR rows, "
          f"{len(victim_rows) + len(sai_rows) + len(neha_rows)} transactions")


if __name__ == "__main__":
    main()
