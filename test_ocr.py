from config import INPUT_DIR, TEMP_DIR
from ocr import OCRReader
from splitter import split_pdf


def find_source_pdf():
    """Return the first receipt PDF we can actually read."""
    if INPUT_DIR.exists():
        inputs = sorted(INPUT_DIR.glob("*.pdf"))
        if inputs:
            return inputs[0]
    pages = sorted(TEMP_DIR.glob("*.pdf"))
    if pages:
        return pages[0]
    return None


def main():
    source = find_source_pdf()

    if source is None:
        print(
            "No PDF found in the input folder or temp folder. "
            "Place a receipt PDF in the input folder and re-run."
        )
        return

    pages = split_pdf(source)

    if not pages:
        print(f"{source.name} has no pages; nothing to OCR.")
        return

    page = pages[0]

    ocr = OCRReader()

    image = ocr.pdf_to_image(page)

    words = ocr.image_to_text(image)

    for word in words:
        print(word["text"])


if __name__ == "__main__":
    main()