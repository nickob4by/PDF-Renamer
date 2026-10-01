"""
test_loaders.py
Unit tests for the enhanced Excel and billing periods data loaders.
"""

import sys
import tempfile
from pathlib import Path
import openpyxl

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from billing_period import load_billing_periods
from matcher import ReceiptMatcher


def test_billing_periods_various_formats():
    content = """
# Comments should be ignored
SI_DASURECO__0005173_0223_2025
SI_DASURECO_0006671_0323_2025
SI_DASURECO__TS-WFP-227F73-0000086_0525_2026
0044866_0825
0046298_0925
0055978 0426
0054461: 0326
"""
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write(content)
        temp_path = Path(f.name)

    try:
        periods = load_billing_periods(temp_path)
        assert periods.get("0005173") == "0223"
        assert periods.get("0006671") == "0323"
        assert periods.get("TS-WFP-227F73-0000086") == "0525"
        # Suffix automatically indexed
        assert periods.get("0000086") == "0525"
        assert periods.get("0044866") == "0825"
        assert periods.get("0046298") == "0925"
        assert periods.get("0055978") == "0426"
        assert periods.get("0054461") == "0326"
    finally:
        temp_path.unlink(missing_ok=True)


def test_billing_periods_filename_space_fallback():
    with tempfile.TemporaryDirectory() as tmp_dir:
        file_path = Path(tmp_dir) / "billing period.txt"
        file_path.write_text("SI_DASURECO__0057514_0526_2026\n", encoding="utf-8")
        
        # Pass a non-existent path with the alternative name in the same folder
        queried_path = Path(tmp_dir) / "billing_periods.txt"
        periods = load_billing_periods(queried_path)
        assert periods.get("0057514") == "0526"


def test_excel_loader_for_or_sheet():
    wb = openpyxl.Workbook()
    # Add an empty first sheet
    ws_cover = wb.active
    ws_cover.title = "Summary"
    ws_cover.append(["Summary Report", "Confidential"])
    
    # Add 'FOR OR' sheet with titles, extra columns, NET column, and TOTAL row
    ws_for_or = wb.create_sheet("FOR OR")
    ws_for_or.append(["Collection Report"])
    ws_for_or.append(["For the month of June 2026"])
    ws_for_or.append([])
    ws_for_or.append([
        "Account Number", "STL ID", "NAME", "BILLING NUMBER",
        "VATABLE + ZERO-RATED", "VAT", "EWT", "NET", "REMARKS"
    ])
    ws_for_or.append([
        "126-105-17-084", "1590EC", "1590 ENERGY CORPORATION",
        "TS-WF-239F-0057514S", -3440.45, -412.85, 0, -3853.30, ""
    ])
    ws_for_or.append([
        "126-105-17-467", "3BEC", "3 BARRACUDA ENERGY CORP.",
        "TS-WF-239F-0057514S", -4520.74, 0, 0, -4520.74, ""
    ])
    ws_for_or.append([
        "", "", "", "TOTAL", -30989758.31, -2582024.05, 0, -33571782.36, ""
    ])
    ws_for_or.append([
        "Extra row after total that should be ignored", "SHOULD_NOT_LOAD", "", "", 0, 0, 0, 100, ""
    ])

    with tempfile.NamedTemporaryFile("wb", suffix=".xlsx", delete=False) as f:
        wb.save(f.name)
        excel_path = Path(f.name)

    try:
        matcher = ReceiptMatcher(excel_path=excel_path)
        assert len(matcher.records) == 2, f"Expected 2 records, got {len(matcher.records)}"
        
        rec1 = matcher.records[0]
        assert rec1["stl_id"] == "1590EC"
        assert rec1["name"] == "1590 ENERGY CORPORATION"
        assert rec1["billing_number"] == "0057514"
        assert rec1["raw_billing"] == "TS-WF-239F-0057514S"
        assert rec1["amount"] == 3853.30

        rec2 = matcher.records[1]
        assert rec2["stl_id"] == "3BEC"
        assert rec2["name"] == "3 BARRACUDA ENERGY CORP."
        assert rec2["billing_number"] == "0057514"
        assert rec2["amount"] == 4520.74
    finally:
        excel_path.unlink(missing_ok=True)


def main():
    tests = [
        test_billing_periods_various_formats,
        test_billing_periods_filename_space_fallback,
        test_excel_loader_for_or_sheet,
    ]

    failed = 0
    for test in tests:
        try:
            test()
            print(f"PASS  {test.__name__}")
        except Exception as e:
            failed += 1
            print(f"FAIL  {test.__name__}: {e}")

    print(f"\n{len(tests) - failed}/{len(tests)} tests passed")
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
