from openpyxl import load_workbook
from rapidfuzz import fuzz
import re
from pathlib import Path

from config import debug
from billing_period import load_billing_periods
from config import BASE_DIR, MIN_MATCH_SCORE

OCR_CONFUSIONS = {
    ("7", "1"), ("1", "7"),
    ("8", "3"), ("3", "8"),
    ("5", "6"), ("6", "5"),
    ("0", "8"), ("8", "0"),
    ("2", "7"), ("7", "2"),
}

# Dash characters that appear in Excel names (en dash U+2013, em dash
# U+2014, minus U+2212, ASCII hyphen) but are almost never reproduced by
# OCR. The receipt line for "JOBIN –SQM INC." OCRs as "JORIN GSOMINC.",
# so keeping the dash on the Excel side alone dragged the fuzzy score
# below the threshold (84.44 vs 85 required). Strip them on both sides.


def normalize_company_name(text):
    """
    Normalize company names before fuzzy matching.
    Keep this conservative for now.
    """

    text = text.upper()

    # Remove punctuation and dash characters (ASCII hyphen, en/em dash,
    # minus sign U+2212)
    text = re.sub(r"[.,:;()\-\u2013\u2014\u2212]", " ", text)

    # Collapse multiple spaces
    text = " ".join(text.split())

    return text
class ReceiptMatcher:

    def __init__(self, excel_path=None, billing_periods_path=None):
        """
        Optional custom data files (used by the GUI). Defaults to
        master.xlsx / billing_periods.txt next to the program.
        """
        self.records = self._load_excel(excel_path)
        self.billing_periods = load_billing_periods(
            billing_periods_path
            if billing_periods_path is not None
            else BASE_DIR / "billing_periods.txt"
        )
        debug("TEST:", self.billing_periods.get("0055978"))
        self.amount_index = self._build_amount_index()

    def _load_excel(self, excel_path=None):
        """
        Load the Excel master file into memory.
        """

        excel_path = Path(excel_path) if excel_path is not None else (
            BASE_DIR / "master.xlsx"
        )

        if not excel_path.exists():
            raise FileNotFoundError(
                f"Excel file not found:\n{excel_path}"
            )

        workbook = load_workbook(
            excel_path,
            data_only=True,
            read_only=True
        )

        # 1. Target sheet selection: prioritize 'FOR OR'
        target_sheet = None
        for name in workbook.sheetnames:
            norm = name.strip().upper().replace("_", " ").replace("-", " ")
            if norm == "FOR OR" or norm.startswith("FOR OR"):
                target_sheet = workbook[name]
                break

        sheets_to_try = [target_sheet] if target_sheet else []
        for name in workbook.sheetnames:
            s = workbook[name]
            if s not in sheets_to_try:
                sheets_to_try.append(s)

        STL_VARIANTS = {"STL ID", "BUYER STL ID", "STL_ID", "STLID"}
        NAME_VARIANTS = {
            "NAME", "BUYER FULL NAME", "COMPANY", "COMPANY NAME", "PARTICULARS"
        }
        BILLING_VARIANTS = {
            "BILLING NUMBER", "TRANSACTION NO (SELLER)", "TRANSACTION NO",
            "BILLING NO", "INVOICE NO", "BILLING"
        }
        NET_VARIANTS = {"NET", "NET AMOUNT", "NET_AMOUNT", "TOTAL NET", "AMOUNT"}

        records = []

        for sheet in sheets_to_try:
            col_stl = col_name = col_billing = col_net = None
            header_found = False

            for row in sheet.iter_rows(values_only=True):
                if not row or all(c is None for c in row):
                    continue

                cells_str = [
                    str(c).strip().upper().replace("\n", " ").replace("\r", " ")
                    if c is not None else ""
                    for c in row
                ]

                # Check if this row is the header
                if not header_found:
                    for idx, val in enumerate(cells_str):
                        if val in STL_VARIANTS and col_stl is None:
                            col_stl = idx
                        elif val in NAME_VARIANTS and col_name is None:
                            col_name = idx
                        elif val in BILLING_VARIANTS and col_billing is None:
                            col_billing = idx
                        elif val in NET_VARIANTS and col_net is None:
                            col_net = idx

                    if (
                        col_stl is not None
                        and col_name is not None
                        and col_billing is not None
                        and col_net is not None
                    ):
                        header_found = True
                    continue

                # Stop when reaching summary / total rows
                if "TOTAL" in cells_str or any(
                    c.startswith("TOTAL") or c.startswith("GRAND TOTAL")
                    for c in cells_str if c
                ):
                    break

                if len(row) <= max(col_stl, col_name, col_billing, col_net):
                    continue

                val_stl = row[col_stl]
                val_name = row[col_name]
                val_billing = row[col_billing]
                val_net = row[col_net]

                if (
                    val_stl is None
                    or val_name is None
                    or val_billing is None
                    or val_net is None
                ):
                    continue

                try:
                    stl_id = str(val_stl).strip()
                    name = str(val_name).strip().upper()
                    raw_billing = str(val_billing).strip()
                    billing_number = raw_billing.split("-")[-1]
                    had_suffix_s = billing_number.endswith(("S", "s"))
                    billing_number = billing_number.rstrip("S").rstrip("s")

                    if had_suffix_s:
                        debug(
                            f"WARNING: STL={stl_id}  Billing={billing_number}"
                        )

                    if isinstance(val_net, (int, float)):
                        amount = abs(float(val_net))
                    else:
                        amt_str = str(val_net).replace(",", "").strip()
                        amount = abs(float(amt_str))

                    if not stl_id or not name or not billing_number:
                        continue

                except (TypeError, ValueError):
                    continue

                records.append({
                    "stl_id": stl_id,
                    "name": name,
                    "billing_number": billing_number,
                    "raw_billing": raw_billing,
                    "amount": amount
                })

            if records:
                break

        # Fallback to legacy index-based loading if dynamic headers were not detected
        if not records and workbook.active:
            sheet = workbook.active
            for row in sheet.iter_rows(min_row=2, values_only=True):
                if row[0] is None or len(row) < 4:
                    continue
                if any(cell is None for cell in row[:4]):
                    continue
                try:
                    stl_id = str(row[0]).strip()
                    name = str(row[1]).strip().upper()
                    raw_billing = str(row[2]).strip()
                    billing_number = raw_billing.split("-")[-1]
                    had_suffix_s = billing_number.endswith(("S", "s"))
                    billing_number = billing_number.rstrip("S").rstrip("s")
                    amount = abs(float(str(row[3]).replace(",", "").strip()))
                except (TypeError, ValueError):
                    continue

                records.append({
                    "stl_id": stl_id,
                    "name": name,
                    "billing_number": billing_number,
                    "raw_billing": raw_billing,
                    "amount": amount
                })

        workbook.close()

        debug(f"Loaded {len(records)} records from Excel.")

        return records

    def _build_amount_index(self):
        """
        Build a fast lookup dictionary keyed by amount.
        """

        index = {}

        for record in self.records:

            amount = round(record["amount"], 2)

            if amount not in index:
                index[amount] = []

            index[amount].append(record)

        return index

    def _normalize_amount(self, amount):
        """
        Convert an amount into a comparable digit string.

        Example:
            7759.08 -> "775908"
        """

        return (
            f"{float(amount):.2f}"
            .replace(".", "")
            .replace(",", "")
            .lstrip("0")
        )

    def _digit_similarity(self, a, b):
        """
        Compare two digits and return a similarity score.
        """

        # Exact match
        if a == b:
            return 1.0

        # Common OCR mistake
        if (a, b) in OCR_CONFUSIONS:
            return 0.8

        # Completely different
        return 0.0
        
    def _build_result(self, best, confidence):

        key = best["billing_number"]
        raw_key = best.get("raw_billing", "")

        debug("\n===== MATCH debug =====")
        debug(f"STL ID         : {best['stl_id']}")
        debug(f"Billing Number : '{best['billing_number']}'")
        debug("========================")

        # billing_periods.txt uses the bare number for older records
        # ("0055978") but the full billing string for newer ones
        # ("TS-WFP-227F73-0000086"), so try both forms.
        billing_period = self.billing_periods.get(key)
        if billing_period is None and raw_key:
            billing_period = self.billing_periods.get(raw_key)
        if billing_period is None:
            billing_period = "UNKNOWN"

        debug("\n===== BILLING PERIOD LOOKUP =====")
        debug("Lookup key :", repr(key))
        debug("Key exists :", key in self.billing_periods)
        debug("Raw key    :", repr(raw_key))
        debug("Raw exists :", raw_key in self.billing_periods)
        debug("Value      :", billing_period)
        debug("=================================\n")

        return {
            "matched": True,
            "confidence": confidence,
            "stl_id": best["stl_id"],
            "billing_number": best["billing_number"],
            "billing_period": billing_period,
            "name": best["name"],
            "amount": best["amount"]
        }
    def _amount_similarity(self, actual, expected):
        """
        Compare two amounts while allowing OCR mistakes.
        Returns 0-100.
        """

        actual = f"{actual:.2f}".replace(".", "")
        expected = f"{expected:.2f}".replace(".", "")

        return fuzz.ratio(actual, expected)

    def company_score(self, text):
        """
        Returns the best matching Excel row and its score.
        """

        best = None
        best_score = 0

        for row in self.records:
            score = fuzz.token_sort_ratio(text, row["name"])

            if score > best_score:
                best_score = score
                best = row

        return best, best_score

    def prefix_name_score(self, ocr_name, excel_name):
        """
        Handles truncated receipt descriptions.
        Example:
        GREEN INNOVATIONS FOR TO
        GREEN INNOVATIONS FOR TOMORROW CORPORATION
        """

        ocr_name = normalize_company_name(ocr_name)
        excel_name = normalize_company_name(excel_name)

        if excel_name.startswith(ocr_name):
            return 100

        return 0
    
    def match(self, candidate):
        """
        Match one OCR candidate against Excel.
        """

        if candidate["amount"] is None:
            return {
                "matched": False,
                "reason": "No amount found."
            }

        amount = round(candidate["amount"], 2)

        possible = self.amount_index.get(amount, [])

        # ---------------------------------
        # Stage 2 fallback
        # ---------------------------------

        use_fallback = False

        if not possible:
            use_fallback = True
            possible = self.records

        candidate_name = normalize_company_name(
            candidate["text"]
            )
        if use_fallback:
            debug("\n========== FALLBACK MODE ==========")
            debug("No exact amount match.")
            debug("Searching all Excel records...")
            debug("===================================")
        if use_fallback:
            required_score = 80
        else:

            if len(possible) == 1:
                required_score = 70

            elif len(possible) <= 3:
                required_score = 85

            else:
                required_score = 82

        debug("\n========== OCR CANDIDATE ==========")
        debug("Amount :", candidate["amount"])
        debug("Name   :", candidate_name)
        debug("===================================")
        

        best = None
        best_score = 0

        # ---------------------------------
        # Fuzzy Match
        # ---------------------------------

        for record in possible:

            excel_name = normalize_company_name(
                record["name"]
            )

            token_score = fuzz.token_set_ratio(
                candidate_name,
                excel_name
            )

            partial_score = fuzz.partial_ratio(
                candidate_name,
                excel_name
            )

            ratio_score = fuzz.ratio(
                candidate_name,
                excel_name
            )

            company_score = max(
                token_score,
                partial_score,
                ratio_score
            )

            prefix_score = self.prefix_name_score(
                candidate_name,
                excel_name
            )

            company_score = max(
                company_score,
                prefix_score
            )

            # Compare amount also
            amount_score = self._amount_similarity(
                candidate["amount"],
                record["amount"]
            )

            # Do not reject early.
            # Let combined score decide.
            if use_fallback and company_score < 65:
                continue

            # Weighted scoring
            score = (
                company_score * 0.60 +
                amount_score * 0.40
            )

            debug(f"{score:6.2f} | {excel_name}")

            if score > best_score:
                best_score = score
                best = record

            # ---------------------------------
            # If only ONE record has this amount,
            # allow a lower score because the
            # amount already uniquely identifies it.
            # ---------------------------------
        if best is None:
            return {
                "matched": False,
                "reason": "No candidate matched."
            }

        debug("----------------------------------------")
        debug(f"Best Score : {best_score:.2f}")
        debug(f"Required   : {required_score}")
        debug("----------------------------------------")
        debug("\n----- BEST MATCH -----")
        debug("Best Name :", best["name"])
        debug("Best Score:", best_score)
        debug("Required  :", required_score)
        debug("----------------------")

        if best_score < required_score:
            return {
                "matched": False,
                "reason": f"Low confidence ({best_score:.2f}%)",
                "confidence": best_score
            }


        return self._build_result(best, best_score)