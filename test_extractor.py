"""
test_extractor.py
Regression tests for the label-row filter.

The IGNORE list is matched on whole words, not substrings: company names
like "GREEN INNOVATIONS FOR TOMORROW CORPORATION" contain "VAT" and
"HAPALAI ENERGY GENERATION" contains "TIN", so substring matching used to
silently drop real candidates.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from extractor import ReceiptExtractor, is_label_row  # noqa: E402

extractor = ReceiptExtractor()


def words_for(*texts):
    """Two words per row: text at x=0, amount-style token at x=500."""
    result = []
    for y, text in enumerate(texts):
        result.append({"text": text, "x": 0, "y": y * 50})
        result.append({"text": "1,234.56", "x": 500, "y": y * 50})
    return result


def test_company_containing_vat_is_kept():
    words = words_for("GREEN INNOVATIONS FOR TO")
    cands = extractor.extract(words)
    assert any("INNOVATIONS" in c["text"] for c in cands), cands


def test_company_containing_tin_is_kept():
    words = words_for("HAPALAI ENERGY GENERATIN")
    cands = extractor.extract(words)
    assert any("GENERATIN" in c["text"] for c in cands), cands


def test_company_named_distribution_is_kept():
    words = words_for("CLARK ELECTRIC DISTRIBUTION CORPORATION")
    cands = extractor.extract(words)
    assert any("DISTRIBUTION" in c["text"] for c in cands), cands


def test_label_rows_are_still_dropped():
    words = words_for("TOTAL", "VAT AMOUNT", "CASH", "CHECK", "CHANGE")
    cands = extractor.extract(words)
    assert cands == [], cands


def test_distribution_charges_label_still_dropped():
    words = words_for("DISTRIBUTION CHARGES")
    cands = extractor.extract(words)
    assert cands == [], cands


def test_vatable_sales_label_with_amount_dropped():
    # OCR often reads "NON-VATable Sales <amount>"; the row must not
    # become a candidate even when it carries a real amount.
    words = words_for("NON VATABLE SALES")
    cands = extractor.extract(words)
    assert cands == [], cands


def test_rotated_layout_company_row_found():
    # Upside-down scan: Item(s) lands ABOVE the company row and the
    # Description/Amount headers land below it. The company row must
    # survive the band filter.
    rows_text = [
        ("TOTAL DUE", "623.72"),
        ("CASH/CARD", "623.72"),
        ("Item(s): 1", "623.72"),
        ("SAN CARLOS BIOENERGY, IN", "623.72"),
        ("Description", None),
        ("SC/PWD SIGN", None),
    ]
    words = []
    for y, (text, amount) in enumerate(rows_text):
        words.append({"text": text, "x": 10, "y": y * 40})
        if amount:
            words.append({"text": amount, "x": 500, "y": y * 40})
    cands = extractor.extract(words)
    assert any("BIOENERGY" in c["text"] for c in cands), cands
    # Label rows stay filtered out even in the reversed layout.
    assert not any("TOTAL" in c["text"] for c in cands), cands
    assert not any("CASH" in c["text"] for c in cands), cands


def test_rotated_layout_garbled_item_anchor():
    # No Item(s) anchor and the band after Description has no amounts:
    # fall back to all rows so the company row still surfaces.
    rows_text = [
        ("TOTAL DUE", "623.72"),
        ("SAN CARLOS BIOENERGY, IN", "623.72"),
        ("Description", None),
        ("BUS. STYLE : OTHERS", None),
    ]
    words = []
    for y, (text, amount) in enumerate(rows_text):
        words.append({"text": text, "x": 10, "y": y * 40})
        if amount:
            words.append({"text": amount, "x": 500, "y": y * 40})
    cands = extractor.extract(words)
    assert any("BIOENERGY" in c["text"] for c in cands), cands


def test_item_row_filtered_in_fallback():
    # No Description anchor -> fallback to all rows; the Item(s) row
    # must not survive as a candidate.
    words = words_for("ITEM(S): 1", "SAN CARLOS BIOENERGY, IN")
    cands = extractor.extract(words)
    assert any("BIOENERGY" in c["text"] for c in cands), cands
    assert not any("ITEM" in c["text"] for c in cands), cands


def test_is_label_row_whole_word():
    assert not is_label_row("GREEN INNOVATIONS FOR TO", ("VAT",))
    assert not is_label_row("HAPALAI ENERGY GENERATIN", ("TIN",))
    assert is_label_row("VAT AMOUNT", ("VAT",))
    assert is_label_row("TOTAL DUE", ("TOTAL",))
    assert is_label_row("SC/PWD", ("SC/PWD",))
    assert is_label_row("NON VAT SALES", ("NON VAT",))


def main():
    tests = [
        test_company_containing_vat_is_kept,
        test_company_containing_tin_is_kept,
        test_company_named_distribution_is_kept,
        test_label_rows_are_still_dropped,
        test_distribution_charges_label_still_dropped,
        test_vatable_sales_label_with_amount_dropped,
        test_is_label_row_whole_word,
        test_rotated_layout_company_row_found,
        test_rotated_layout_garbled_item_anchor,
        test_item_row_filtered_in_fallback,
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
