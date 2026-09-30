import os
import sys
from pathlib import Path

# ============================================================
# PATHS
# ============================================================


def _app_base_dir():
    """
    Folder that holds the app's data files (master.xlsx, billing_periods.txt).

    In normal runs this is the source folder. When frozen by PyInstaller it
    is the folder containing the executable (onedir build), or the bundle
    extraction folder (onefile build), so the bundled data files are found
    there. For onedir builds you can simply drop an updated master.xlsx next
    to the .exe without rebuilding.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


BASE_DIR = _app_base_dir()


def _runtime_dir(name):
    """
    Writable folder for scratch files / logs.

    Source runs keep them under the project. Frozen runs use
    %LOCALAPPDATA%\\PDFAutoRename so the packaged app still works when the
    exe folder is read-only (Program Files, a shared drive, etc.).
    """
    if getattr(sys, "frozen", False):
        base = Path(os.environ.get(
            "LOCALAPPDATA", str(Path.home()))
        ) / "PDFAutoRename"
        return base / name
    return BASE_DIR / name

INPUT_DIR = Path(r"\\10.0.0.9\Accounting\Nicko\OR Renamer\Input")
OUTPUT_DIR = Path(r"\\10.0.0.9\Accounting\Nicko\OR Renamer\Output")
FAILED_DIR = Path(r"\\10.0.0.9\Accounting\Nicko\OR Renamer\Failed")

# Matched pages whose billing period cannot be resolved from
# billing_periods.txt land here, for manual renaming.
UNKNOWN_DIR = OUTPUT_DIR / "Unknown Billing Period"
TEMP_DIR = _runtime_dir("temp")
LOG_DIR = _runtime_dir("logs")

# Create folders automatically.
# Network shares may be temporarily unreachable; warn instead of
# crashing the whole program at import time.


def _ensure_dir(path, label):
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        print(f"WARNING: Cannot access {label} folder {path}: {e}")


_ensure_dir(INPUT_DIR, "Input")
_ensure_dir(OUTPUT_DIR, "Output")
_ensure_dir(UNKNOWN_DIR, "Unknown Billing Period")
_ensure_dir(FAILED_DIR, "Failed")
_ensure_dir(TEMP_DIR, "Temp")
_ensure_dir(LOG_DIR, "Log")

# ============================================================
# OCR SETTINGS
# ============================================================

OCR_LANGUAGE = "en"
USE_ANGLE_CLASSIFIER = True

# ============================================================
# IMAGE CROP (Percentage-based)
# ============================================================

CROP_LEFT = 0.03
CROP_TOP = 0.28
CROP_RIGHT = 0.99
CROP_BOTTOM = 0.70

# ============================================================
# EXTRACTION SETTINGS
# ============================================================

ROW_TOLERANCE = 12

# ============================================================
# MATCHING SETTINGS
# ============================================================

MIN_MATCH_SCORE = 90

# ============================================================
# LOGGING
# ============================================================

LOG_LEVEL = "INFO"

# ============================================================
# PERFORMANCE
# ============================================================
OCR_DPI = 3.0
WORKERS = 2

DEBUG = False
def debug(*args, **kwargs):
    if DEBUG:
        print(*args, **kwargs)