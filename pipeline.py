"""
pipeline.py
Shared batch-processing orchestration for the CLI (main.py) and the GUI
(gui.py).

process_pdfs() runs a list of PDF files through the OCR/matching pipeline
and reports progress through a callback, so any front-end can render the
same run without duplicating the loop that used to live in main().
"""

import shutil
import traceback
from pathlib import Path

from config import TEMP_DIR


def clear_temp_folder(keep=()):
    """
    Delete all files and folders inside the temp directory.

    `keep` is an iterable of paths that must NOT be deleted. This protects
    against the case where the user selected input files that live inside
    the scratch folder (e.g. leftover *_p001.pdf page files from an
    earlier run): deleting them before processing would make every file
    fail with "PDF not found".
    """
    keep = {Path(p).resolve() for p in keep}

    if not TEMP_DIR.exists():
        return

    for item in TEMP_DIR.iterdir():
        try:
            resolved = item.resolve()

            # Never delete a file the user is about to process.
            if resolved in keep:
                continue

            # If a kept file lives inside this subfolder, leave the whole
            # subfolder alone.
            if any(k.is_relative_to(resolved) for k in keep):
                continue

            if item.is_file() or item.is_symlink():
                item.unlink()
            elif item.is_dir():
                shutil.rmtree(item)
        except Exception as e:
            print(f"Unable to delete {item}: {e}")


def process_pdfs(pdf_files, output_dir, failed_dir=None, dry_run=False,
                 master_file=None, billing_periods_file=None,
                 on_progress=None, should_cancel=None):
    """
    Process a batch of PDF files through the OCR/matching pipeline.

    pdf_files           : list[Path] - PDF files to process (each may be
                          multi-page).
    output_dir          : Path/str  - folder where matched PDFs are saved.
    failed_dir          : Path/str or None - folder for unmatched pages.
                          Defaults to <output_dir>/Failed.
    dry_run             : bool - preview renames without writing anything.
    master_file         : Path/str or None - custom master.xlsx (defaults to
                          the file next to the program).
    billing_periods_file: Path/str or None - custom billing_periods.txt
                          (defaults to the file next to the program).
    on_progress         : callable(dict) or None - receives events:
                       {"phase": "startup", "message": ...}
                       {"phase": "ready", "total_pages", "input_files",
                        "excel_records", "skipped"}
                       {"phase": "page", "current", "total", "filename",
                        "status", "company", "billing", "billing_period",
                        "confidence", "saved_as", "success", "failed",
                        "error": Exception or None}
    should_cancel: callable() -> bool or None - checked between pages.

    Returns a dict: {success, failed, unknown, skipped, total_pages,
                     excel_records, cancelled}
    """

    output_dir = Path(output_dir)
    failed_dir = Path(failed_dir) if failed_dir is not None else (
        output_dir / "Failed"
    )

    def emit(state):
        if on_progress:
            on_progress(state)

    # Ensure target folders exist. Network shares can be flaky - warn
    # instead of crashing.
    for folder in (output_dir, failed_dir):
        try:
            folder.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            print(f"WARNING: Cannot access output folder {folder}: {e}")

    # Never wipe files the user just selected as input (they may live in
    # the scratch folder), nor any active data files.
    keep_list = list(pdf_files)
    if master_file:
        keep_list.append(master_file)
    if billing_periods_file:
        keep_list.append(billing_periods_file)
    clear_temp_folder(keep=keep_list)

    emit({"phase": "startup", "message": "Loading OCR engine..."})

    if should_cancel and should_cancel():
        return {"cancelled": True, "success": 0, "failed": 0, "unknown": 0,
                "skipped": [], "total_pages": 0, "excel_records": 0}

    # Heavy imports live here so the GUI window appears instantly and the
    # CLI --help path never pays for PaddleOCR/CV2.
    from splitter import split_pdf
    from ocr import OCRReader
    from cropper import ReceiptCropper
    from extractor import ReceiptExtractor
    from matcher import ReceiptMatcher
    from renamer import ReceiptRenamer
    from page_verdict import PageVerdict

    ocr = OCRReader()
    cropper = ReceiptCropper()
    extractor = ReceiptExtractor()
    matcher = ReceiptMatcher(
        excel_path=master_file,
        billing_periods_path=billing_periods_file,
    )
    renamer = ReceiptRenamer(output_dir=output_dir, failed_dir=failed_dir)
    verdicts = PageVerdict(ocr, cropper, extractor, matcher, renamer)

    # -------------------------------
    # Count total pages first
    # -------------------------------
    pdf_pages = []
    skipped = []

    for pdf in pdf_files:
        if should_cancel and should_cancel():
            break
        try:
            pdf_pages.append((pdf, split_pdf(pdf)))
        except Exception as e:
            skipped.append(pdf.name)
            print(f"ERROR: Could not read {pdf.name}: {e}")
            print("Skipping this file and continuing with the rest.")

    total_pages = sum(len(pages) for _, pages in pdf_pages)

    if should_cancel and should_cancel():
        return {"cancelled": True, "success": 0, "failed": 0, "unknown": 0,
                "skipped": skipped, "total_pages": 0,
                "excel_records": len(matcher.records)}

    emit({
        "phase": "ready",
        "total_pages": total_pages,
        "input_files": len(pdf_files),
        "excel_records": len(matcher.records),
        "skipped": list(skipped),
    })

    success = 0
    failed = 0
    unknown = 0

    # -------------------------------
    # Process pages
    # -------------------------------
    for pdf, pages in pdf_pages:

        for page in pages:

            if should_cancel and should_cancel():
                return {
                    "cancelled": True,
                    "success": success,
                    "failed": failed,
                    "unknown": unknown,
                    "skipped": skipped,
                    "total_pages": total_pages,
                    "excel_records": len(matcher.records),
                }

            try:

                verdict = verdicts.verdict_for(page)

                if not verdict["matched"]:
                    raise ValueError(verdict["reason"])

                is_unknown = verdict["billing_period"] == "UNKNOWN"

                if dry_run:
                    # Mirror the real run, including _2/_3 suffixes for
                    # filenames that already exist (read-only check).
                    target_dir = (
                        renamer.unknown_dir if is_unknown
                        else renamer.output_dir
                    )
                    output_name = renamer._unique_path(
                        target_dir / verdict["filename"]
                    ).name
                else:
                    if is_unknown:
                        output_name = renamer.save_unknown(page, verdict).name
                    else:
                        output_name = renamer.save(page, verdict).name

                success += 1
                if is_unknown:
                    unknown += 1

                emit({
                    "phase": "page",
                    "current": success + failed,
                    "total": total_pages,
                    "filename": pdf.name,
                    "status": (
                        "✓ Matched (dry-run)" if dry_run
                        else "✓ Matched - UNKNOWN period (manual)"
                        if is_unknown else "✓ Matched"
                    ),
                    "company": verdict["company"],
                    "billing": verdict["billing_number"],
                    "billing_period": verdict["billing_period"],
                    "confidence": f"{verdict['confidence']:.2f}%",
                    "saved_as": output_name,
                    "success": success,
                    "failed": failed,
                    "unknown": unknown,
                    "error": None,
                })

            except Exception as e:

                traceback.print_exc()

                if dry_run:
                    saved = None
                else:
                    try:
                        saved = renamer.save_failed(page)
                    except Exception as save_err:
                        print(
                            f"ERROR: Could not save failed copy: {save_err}"
                        )
                        saved = None

                failed += 1

                emit({
                    "phase": "page",
                    "current": success + failed,
                    "total": total_pages,
                    "filename": pdf.name,
                    "status": (
                        "✗ ERROR (dry-run)" if dry_run else "✗ ERROR"
                    ),
                    "company": "",
                    "billing": "",
                    "billing_period": "",
                    "confidence": "",
                    "saved_as": (
                        page.name if dry_run
                        else (saved.name if saved else "(not saved)")
                    ),
                    "success": success,
                    "failed": failed,
                    "unknown": unknown,
                    "error": e,
                })

    return {
        "cancelled": False,
        "success": success,
        "failed": failed,
        "unknown": unknown,
        "skipped": skipped,
        "total_pages": total_pages,
        "excel_records": len(matcher.records),
        "dry_run": dry_run,
    }
