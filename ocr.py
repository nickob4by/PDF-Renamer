import fitz
import numpy as np
import cv2
from paddleocr import PaddleOCR

from config import OCR_LANGUAGE, USE_ANGLE_CLASSIFIER


class OCRReader:
    def __init__(self):
        self.ocr = PaddleOCR(
            use_angle_cls=USE_ANGLE_CLASSIFIER,
            lang=OCR_LANGUAGE,
            show_log=False
        )

    def pdf_to_image(self, pdf_path):
        """
        Convert the first page of a PDF into a NumPy image.
        """

        doc = fitz.open(pdf_path)

        try:
            page = doc.load_page(0)

            # 3x scale ≈ 216 DPI
            from config import OCR_DPI

            pix = page.get_pixmap(
                matrix=fitz.Matrix(OCR_DPI, OCR_DPI)
                )   

            image = np.frombuffer(
                pix.samples,
                dtype=np.uint8
            )

            image = image.reshape(
                pix.height,
                pix.width,
                pix.n
            )

            return image

        finally:
            doc.close()

    def image_to_text(self, image):
        """
        Run PaddleOCR on an OpenCV image.

        Returns:
            list[dict]
        """

        result = self.ocr.ocr(image, cls=True)

        words = []

        if not result:
            return words

        for block in result:

            if block is None:
                continue

            for item in block:

                if item is None:
                    continue

                box = item[0]

                text = item[1][0].strip()
                confidence = float(item[1][1])

                if not text:
                    continue

                xs = [p[0] for p in box]
                ys = [p[1] for p in box]

                words.append({
                    "text": text,
                    "x": min(xs),
                    "y": min(ys),
                    "confidence": confidence
                })

        # Sort top-to-bottom then left-to-right
        words.sort(
            key=lambda w: (
                w["y"],
                w["x"]
            )
        )

        return words