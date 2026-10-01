"""
test_matcher.py
Regression tests for company-name normalization.

The Excel master stores "JOBIN –SQM INC." with an en dash (U+2013).
OCR reads the receipt line as "JORIN GSOMINC." (dash-free, with B/R and
S/G noise), and with the dash kept on the Excel side the weighted fuzzy
score landed at 84.44 vs the 85 required - so the record never matched.
Dash characters are now stripped on both sides before scoring.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from matcher import normalize_company_name, ReceiptMatcher  # noqa: E402

matcher = ReceiptMatcher()
# Ensure JOBIN test fixture record is present in matcher for unit testing
if not any(r.get("stl_id") == "JOBIN" for r in matcher.records):
    matcher.records.append({
        "stl_id": "JOBIN",
        "name": "JOBIN \u2013SQM INC.",
        "billing_number": "0058469",
        "raw_billing": "TS-WAD-234F207-0058469",
        "amount": 0.18
    })
    matcher.amount_index = matcher._build_amount_index()


def test_ascii_dash_stripped():
    assert normalize_company_name("JOBIN -SQM INC.") == "JOBIN SQM INC"


def test_en_dash_stripped():
    assert normalize_company_name("JOBIN \u2013SQM INC.") == "JOBIN SQM INC"


def test_em_dash_and_minus_stripped():
    assert normalize_company_name("A \u2014B") == "A B"
    assert normalize_company_name("A \u2212B") == "A B"


def test_n_tilde_preserved():
    # UPLB's name contains U+00D1; do not strip non-ASCII letters.
    assert "\u00d1" in normalize_company_name("UNIVERSIDAD \u00d1U\u00d1OZ CO")


def test_jobin_osom_reading_matches():
    # Variant 0 OCR reading of the receipt line.
    result = matcher.match({
        "text": "JORIN OSOM INC.",
        "amount": 0.18,
    })
    assert result["matched"], result
    assert result["stl_id"] == "JOBIN", result


def test_jobin_gsomin_reading_matches():
    # Variants 2/3 OCR reading (the one that previously scored 84.44).
    result = matcher.match({
        "text": "JORIN GSOMINC.",
        "amount": 0.18,
    })
    assert result["matched"], result
    assert result["stl_id"] == "JOBIN", result
    assert result["confidence"] >= 85, result


def main():
    tests = [
        test_ascii_dash_stripped,
        test_en_dash_stripped,
        test_em_dash_and_minus_stripped,
        test_n_tilde_preserved,
        test_jobin_osom_reading_matches,
        test_jobin_gsomin_reading_matches,
    ]

    failed = 0
    for test in tests:
        try:
            test()
            print(f"PASS  {test.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL  {test.__name__}: {e}")

    print(f"\n{len(tests) - failed}/{len(tests)} tests passed")
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
