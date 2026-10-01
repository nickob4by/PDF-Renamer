import re
from pathlib import Path


def load_billing_periods(txt_path):
    """
    Load billing number -> billing period mapping.

    Supports:
        - Exact file path or alternative filenames ('billing period.txt', 'billing_periods.txt')
        - SI_DASURECO__<NUMBER>_<PERIOD>_<YEAR> (single or double underscore)
        - Delimited text like '<NUMBER> <PERIOD>' or '<NUMBER>: <PERIOD>'
        - Dual indexing by full transaction ID and numeric suffix

    Returns:
        {
            "0055978": "0426",
            "0054461": "0326",
            ...
        }
    """

    periods = {}
    txt_path = Path(txt_path)

    if not txt_path.exists():
        for alt_name in (
            "billing_periods.txt",
            "billing period.txt",
            "billing_period.txt",
            "billingperiods.txt",
        ):
            alt_path = txt_path.with_name(alt_name)
            if alt_path.exists():
                txt_path = alt_path
                break

    if not txt_path.exists():
        return periods

    with open(txt_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()

            if not line or line.startswith("#"):
                continue

            # Strip optional SI_DASURECO__ prefix (e.g. "SI_DASURECO__0044866_0825_20251114" -> "0044866_0825_20251114")
            clean = re.sub(r"(?i)^SI_DASURECO_+", "", line).strip()

            # Priority 1: Format with trailing date/year e.g. "0044866_0825_20251114" or "0044866_0825_2025"
            m1 = re.match(r"^([A-Za-z0-9\-]+)[_\s,:;]+(\d{4})[_\s,:;]+\d{4,8}$", clean)
            # Priority 2: Direct concise format e.g. "0044866_0825" or "0044866 0825"
            m2 = re.match(r"^([A-Za-z0-9\-]+)[_\s,:;]+(\d{4})$", clean)
            
            m = m1 or m2
            if m:
                billing_number = m.group(1).strip()
                billing_period = m.group(2).strip()
            else:
                parts = [p for p in line.split("_") if p]
                if len(parts) >= 2:
                    billing_number = parts[-2].strip()
                    billing_period = parts[-1].strip()
                else:
                    continue

            periods[billing_number] = billing_period

            # Also index by numeric suffix (e.g. TS-WFP-227F73-0000086 -> 0000086)
            # and strip trailing 'S' marker if present
            suffix = billing_number.split("-")[-1].rstrip("S").rstrip("s")
            if suffix:
                periods[suffix] = billing_period

    return periods