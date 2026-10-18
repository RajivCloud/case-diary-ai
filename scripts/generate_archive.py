"""Write the police station's archive: unrelated cyber-crime FIRs.

WHY: In a real station the case you are working on sits among hundreds of
others. These files are deliberate noise. Several share words with our case
("digital arrest", "OTP", "IMPS", "mule account") so a naive search pulls them in.
The agent must use the case_id metadata filter to stay on its own case, and may
spot a genuine cross-case link (CYB-098-2026 uses the same courier number).

Run: python scripts/generate_archive.py
"""

from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "data" / "archive"

CASES = [
    ("CYB-098-2026", "2026-08-24", "Digital arrest fraud on Mrs. Leela Joshi, Aundh",
     ["FIR 98/2026 under BNS 318(4), 319(2) and IT Act 66D. Complainant Mrs. Leela Joshi, age 71, Aundh, Pune, mobile 9881234560.",
      "On 21-Aug-2026 at about 11:04 hrs she received a call from 7303518246 from a person claiming to be from a courier company, saying a parcel in her name contained narcotics. The call was transferred to a 'Delhi Police officer' on a video call.",
      "She was told to stay on camera and transferred Rs 6,20,000 by IMPS to an account at Marudhar Co-operative Bank, Jaipur. The account holder could not be traced. Investigation pending; the courier number was switched off when checked in August."]),
    ("CYB-071-2026", "2026-06-11", "OLX furniture sale fraud, Baner",
     ["FIR 71/2026 under BNS 318(4). Complainant listed a sofa set on an online marketplace. A buyer posing as an army officer sent a QR code saying it was to 'receive' money.",
      "The complainant scanned the QR code and entered the UPI PIN four times, losing Rs 48,500. The beneficiary UPI ID belonged to a bank in Bharatpur, Rajasthan.",
      "Mule account holder identified; notice issued. Amount of Rs 12,000 frozen."]),
    ("CYB-079-2026", "2026-06-30", "Sextortion video call, Wakad",
     ["FIR 79/2026 under BNS 308 and IT Act 66E, 67. Complainant, a 34-year-old IT employee, received a video call from an unknown woman; the call was recorded.",
      "Callers then threatened to send the edited video to his contacts and posed as a 'YouTube officer' and a 'Delhi crime branch inspector' demanding money. He paid Rs 1,10,000 by UPI.",
      "UPI accounts traced to Mewat region. Request sent to the platform to take down the content."]),
    ("CYB-083-2026", "2026-07-09", "Part-time job / task fraud, Kharadi",
     ["FIR 83/2026 under BNS 318(4), 61(2). Complainant was offered a part-time job of liking hotel reviews on a messaging app and paid small commissions at first.",
      "She was then asked to 'invest' in prepaid tasks and transferred Rs 7,85,000 in 14 IMPS transactions to different accounts.",
      "Funds layered through 11 mule accounts and converted to crypto; Rs 1,02,000 frozen."]),
    ("CYB-086-2026", "2026-07-15", "SIM swap and net-banking fraud, Camp",
     ["FIR 86/2026 under BNS 318(4), 319(2) and IT Act 66C. The complainant's mobile SIM stopped working on 13-Jul-2026 evening.",
      "A duplicate SIM had been issued at a retailer on a forged request. Within two hours OTPs were received on the duplicate SIM and Rs 3,40,000 was transferred out by IMPS.",
      "Retailer's statement recorded. CCTV of the retail outlet obtained with certificate."]),
    ("CYB-088-2026", "2026-07-22", "Instant loan app harassment, Hadapsar",
     ["FIR 88/2026 under BNS 351, 356 and IT Act 67. Complainant took a Rs 8,000 loan through an app that accessed her contacts and gallery.",
      "After repayment, the app operators demanded more money and sent morphed photos to her contacts.",
      "App reported for removal. Payment gateway details requested."]),
    ("CYB-090-2026", "2026-07-29", "Fake stock-trading group fraud, Kothrud",
     ["FIR 90/2026 under BNS 318(4), 61(2). A retired bank officer from Kothrud joined a messaging group promising 300% returns on IPO allotments through a fake trading app.",
      "The app showed fake profits. He invested Rs 52,00,000 in 9 RTGS and IMPS transfers to accounts in different states and could not withdraw.",
      "Accounts traced to shell companies; Rs 9,80,000 frozen. One of the first-layer beneficiary accounts was Godavari Bank A/c 60450012783 (Shree Sai Traders, Chhatrapati Sambhajinagar)."]),
    ("CYB-093-2026", "2026-08-05", "Electricity bill disconnection SMS fraud, Pimpri",
     ["FIR 93/2026 under BNS 318(4) and IT Act 66D. Complainant got an SMS that power would be cut at 9:30 pm unless the bill was updated, with a mobile number to call.",
      "The caller made him install a screen-sharing app and pay Rs 10 'update fee'. Rs 1,96,000 was then debited from his account.",
      "Screen-sharing app session IDs requested from the provider."]),
    ("CYB-095-2026", "2026-08-12", "Matrimonial site impersonation fraud, Aundh",
     ["FIR 95/2026 under BNS 318(4), 319(2). Complainant met a man on a matrimonial site who claimed to be a UK-based doctor.",
      "He said he had sent gifts that were held at customs; a 'customs officer' demanded duties. She paid Rs 4,60,000 in instalments.",
      "Beneficiary accounts in Delhi NCR identified; mule account holders being examined."]),
    ("CYB-101-2026", "2026-09-02", "Credit card reward points phishing, Viman Nagar",
     ["FIR 101/2026 under BNS 318(4) and IT Act 66C, 66D. Complainant clicked an SMS link to redeem credit-card reward points and entered card details and OTP on a fake site.",
      "Rs 92,000 was spent on online gaming wallets within ten minutes.",
      "Phishing domain reported; merchant details requested from the card network."]),
    ("CYB-105-2026", "2026-09-14", "Fake customer care number, Sinhagad Road",
     ["FIR 105/2026 under BNS 318(4). Complainant searched online for a food-delivery refund helpline and called a fake number.",
      "The caller asked him to send Rs 5 through UPI for 'verification' and then collect a refund by entering his PIN; Rs 64,000 was debited in four transactions.",
      "Search-engine listing reported. Mule account in Jamtara region identified."]),
    ("CYB-109-2026", "2026-09-27", "Business email compromise, Hinjewadi",
     ["FIR 109/2026 under BNS 318(4), 336 and IT Act 66C. A software exporter received an email from a look-alike domain of its regular supplier with changed bank details.",
      "The company paid USD 41,000 by SWIFT to a new account in Hong Kong.",
      "Recall request sent through the bank; email headers analysed; domain registrar contacted."]),
]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for case_id, date, title, paras in CASES:
        body = "\n\n".join(paras)
        text = (
            f"---\ndoc_id: {case_id}-FIR\ncase_id: {case_id}\ndoc_type: fir\n"
            f"title: {title}\ndate: {date}\npersons: \n---\n{body}\n"
        )
        (OUT / f"{case_id}_fir.md").write_text(text, encoding="utf-8")
    print(f"wrote {len(CASES)} archive FIRs -> {OUT}")


if __name__ == "__main__":
    main()
