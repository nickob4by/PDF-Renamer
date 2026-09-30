"""
splitter.py
Split a PDF into individual one-page PDF files.
"""

from pathlib import Path
import fitz  # PyMuPDF

from config import TEMP_DIR
from logger import logger


def split_pdf(pdf_path):
    """
    Split a PDF into individual page PDFs.

    Args:
        pdf_path (str or Path): Path to the input PDF.

    Returns:
        list[Path]: List of generated PDF page paths.
    """

    pdf_path = Path(pdf_path)

    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    TEMP_DIR.mkdir(exist_ok=True)

    output_files = []

    logger.info(f"Opening PDF: {pdf_path.name}")

    document = fitz.open(pdf_path)

    logger.info(f"Found {len(document)} page(s).")

    try:
        for page_num in range(len(document)):
            new_pdf = fitz.open()
            try:
                new_pdf.insert_pdf(
                    document,
                    from_page=page_num,
                    to_page=page_num
                )

                output_file = TEMP_DIR / f"{pdf_path.stem}_p{page_num + 1:03}.pdf"

                new_pdf.save(output_file)

                output_files.append(output_file)

                logger.info(f"Created: {output_file.name}")
            finally:
                new_pdf.close()
    finally:
        document.close()

    logger.info("PDF splitting completed.")

    return output_files