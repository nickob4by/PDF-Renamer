import re

from config import ROW_TOLERANCE
from config import debug

AMOUNT_PATTERN = re.compile(
    r'^\d{1,3}(?:,\d{3})*(?:\.\d{2})$|^\d+\.\d{2}$'
)


def is_label_row(text, labels):
    """
    True if the row reads like a payment/label row rather than a company row.

    Uses whole-word token matching. A plain substring check would silently
    drop real company names: "INNOVATIONS" contains "VAT" and "GENERATION"
    contains "TIN", so e.g. GREEN INNOVATIONS FOR TOMORROW CORPORATION
    would never form a candidate.

    Limitation: a company whose name consists of label words as whole
    tokens (e.g. "TOTAL POWER CORP") is still treated as a label. None of
    the current master records collide; revisit if new companies appear.
    """

    tokens = set(re.findall(r"[A-Z0-9]+", text.upper()))

    for phrase in labels:
        phrase_tokens = set(re.findall(r"[A-Z0-9]+", phrase))

        if phrase_tokens and phrase_tokens.issubset(tokens):
            return True

    return False


class ReceiptExtractor:

    def extract(self, words):
        """
        Convert OCR words into structured row candidates.
        """

        rows = self._group_rows(words)
        rows = self._repair_company_amount(rows)
        rows = self._company_rows(rows)

        candidates = []

        for row in rows:

            amount = None
            text_parts = []

            for word in row["words"]:

                token = word["text"]

                normalized = self._normalize_amount(token)

                if normalized is not None:
                    amount = normalized
                else:
                    text_parts.append(token)

            text = " ".join(text_parts).strip()
            if amount is None:
              continue

            if not text:
             continue

            upper = text.upper()

            IGNORE = (
                "TOTAL",
                "CASH",
                "CARD",
                "LESS",
                "WITHHOLDING",
                "CHECK",
                "CHANGE",
                "BALANCE",
                "VAT",
                "VATABLE",
                "DISTRIBUTION CHARGES",
                "PASS-THROUGH",
                "PASS THROUGH",
                "NON-VAT",
                "NON VAT",
                "SC/PWD",
                "OSCA",
                "TIN",
                "BUS. STYLE",
                "BUS STYLE",
                # Item(s) rows carry the line amount and can surface via the
                # all-rows fallback in _company_rows (upside-down scans).
                "ITEM",
                "ITEMS",
            )

            if is_label_row(upper, IGNORE):
                continue

            candidates.append({
                "text": text,
                "amount": amount,
                "y": row["y"],
                "words": row["words"]
            })
            
        debug("\n===== RETURNING CANDIDATES =====")
        for c in candidates:
            debug(c)

        return candidates
    def _company_rows(self, rows):
        """
        Return the company row(s) of the receipt.

        Anchors on the 'Description' / 'Item(s)' column headers. Normal
        scans read top-to-bottom (Description, company row, Item(s));
        upside-down scans read in reverse, so the Item(s) row lands ABOVE
        the Description row with the company row still between them.
        Falls back to the original rows when no Description is found, or
        when the anchored band carries no amount (reversed/garbled
        anchors) - the label filter in extract() still drops label rows.
        """

        desc_idx = None
        item_idx = None

        for i, row in enumerate(rows):

            text = " ".join(
                w["text"] for w in row["words"]
            ).upper()

            normalized = (
                text.replace("1", "I")
                    .replace("L", "I")
                    .replace("{", "")
                    .replace("}", "")
            )

            if desc_idx is None and "DESCRIPT" in normalized:
                desc_idx = i
                continue

            item_check = (
                normalized.upper()
                    .replace(" ", "")
                    .replace("(", "")
                    .replace(")", "")
                    .replace("{", "")
                    .replace("}", "")
                    .replace(":", "")
                    .replace("1", "")
            )

            if (
                item_idx is None
                and (
                    "ITEM" in item_check
                    or "ITEMS" in item_check
                    or "ITEN" in item_check
                    or "ITAM" in item_check
                )
            ):
                item_idx = i

        if desc_idx is None:
            return rows

        if item_idx is not None and item_idx < desc_idx:
            # Upside-down scan: the company row sits between
            # Item(s) and Description.
            band = rows[item_idx + 1:desc_idx]
        else:
            band = (
                rows[desc_idx + 1:]
                if item_idx is None
                else rows[desc_idx + 1:item_idx]
            )

        company_rows = [
            row for row in band
            if " ".join(w["text"] for w in row["words"]).strip()
        ]

        if not company_rows:
            return rows

        # A company row always carries an amount. If the anchored band
        # has none, the anchors were reversed or garbled; fall back to
        # all rows and let the label filter sort it out.
        if not any(
            self._normalize_amount(w["text"]) is not None
            for row in company_rows
            for w in row["words"]
        ):
            return rows

        debug("\n=== COMPANY ROWS ===")
        for row in company_rows:
            debug(">", " ".join(w["text"] for w in row["words"]))
        return company_rows

    def _normalize_amount(self, token):
        """
        Normalize OCR amount formats.

        Examples:
            1,888.44 -> 1888.44
            1.888.44 -> 1888.44
            1888.44  -> 1888.44
        """

        token = token.strip()

        # Standard format
        if AMOUNT_PATTERN.match(token):
            return float(token.replace(",", ""))

        # OCR sometimes mistakes commas for periods
        if token.count(".") == 2:

            left, middle, right = token.split(".")

            if (
                left.isdigit()
                and middle.isdigit()
                and right.isdigit()
                and len(right) == 2
            ):

                normalized = f"{left},{middle}.{right}"

                if AMOUNT_PATTERN.match(normalized):
                    return float(normalized.replace(",", ""))

        return None

    def _repair_company_amount(self, rows):
        """
        Repair company rows by copying the amount from the following
        Item(s) row when appropriate.
        """

        IGNORE = (
            "TOTAL",
            "LESS",
            "VAT",
            "CASH",
            "CHECK",
            "CHANGE",
            "BALANCE",
            "DISCOUNT",
            "VATABLE",
            "DISTRIBUTION CHARGES",
            "SC/PWD",
            "SC/PWN",
        )

        def _is_label(text):
            return is_label_row(text, IGNORE)

        for i in range(len(rows) - 1):

            current = rows[i]
            nxt = rows[i + 1]

            # Check whether the company row already has its own amount
            company_amount = None

            for word in current["words"]:
                amt = self._normalize_amount(word["text"])
                if amt is not None:
                    company_amount = amt
                    break
            current_text = " ".join(
                w["text"] for w in current["words"]
            ).upper()

            next_text = " ".join(
                w["text"] for w in nxt["words"]
            ).upper()

            # Skip obvious non-company rows
            if _is_label(current_text):
                continue

        
            normalized_next = (
                next_text
                    .replace("{", "M")
                    .replace("}", "M")
                    .replace(":", "")
                    .replace("1", "")
                    .replace(" ", "")
                )

            if "ITEM" not in normalized_next:
                    continue

            item_amount = None

            for word in nxt["words"]:

                amt = self._normalize_amount(word["text"])

                if amt is not None:
                    item_amount = amt
                    break

            if item_amount is None:
                continue
            # Company row already has a valid amount.
            # Don't overwrite it with the Item(s) amount.
            if company_amount is not None:
                continue
            # Remove any existing amount from the company row
            new_words = []

            for word in current["words"]:

                if self._normalize_amount(word["text"]) is None:
                    new_words.append(word)

            # Append the corrected amount
            new_words.append({
                "text": f"{item_amount:.2f}",
                "x": 9999,
                "y": current["y"]
            })

            current["words"] = new_words

        return rows

    def _group_rows(self, words):
        """
        Group OCR words into visual rows.
        """

        if not words:
            return []

        words = sorted(
            words,
            key=lambda w: (w["y"], w["x"])
        )

        rows = []

        current = {
            "y": words[0]["y"],
            "words": [words[0]]
        }

        for word in words[1:]:

            if abs(word["y"] - current["y"]) <= ROW_TOLERANCE:

                current["words"].append(word)

            else:

                current["words"].sort(
                    key=lambda w: w["x"]
                )

                rows.append(current)

                current = {
                    "y": word["y"],
                    "words": [word]
                }

        current["words"].sort(
            key=lambda w: w["x"]
        )

        rows.append(current)

        return rows