"""
page_verdict.py
Deep module: one receipt page -> one verdict.

Absorbs the per-page decision path that used to live in main's loop:
render the page, try each crop variant, OCR it, extract candidates,
match each candidate, keep the best match with an early exit at high
confidence, and build the would-be filename.

Side-effect free: this module never writes to Output/Failed. It returns
a verdict; saving and dry-run presentation stay in main.
"""


class PageVerdict:

    EARLY_EXIT_CONFIDENCE = 90

    def __init__(self, ocr, cropper, extractor, matcher, renamer):

        self.ocr = ocr
        self.cropper = cropper
        self.extractor = extractor
        self.matcher = matcher
        self.renamer = renamer

    def verdict_for(self, page):
        """
        Return a verdict dict for one single-page PDF.

        Matched:
            matched, company, stl_id, billing_number, billing_period,
            confidence, amount, filename
        Unmatched:
            matched=False, reason
        """

        image = self.ocr.pdf_to_image(page)

        best_match = None

        for cropped in self.cropper.get_crop_variants(image):

            words = self.ocr.image_to_text(cropped)

            if not words:
                continue

            candidates = self.extractor.extract(words)

            if not candidates:
                continue

            for candidate in candidates:

                result = self.matcher.match(candidate)

                if not result["matched"]:
                    continue

                if (
                    best_match is None
                    or result["confidence"] > best_match["confidence"]
                ):
                    best_match = result

            # Optional: stop early if confidence is very high
            if (
                best_match
                and best_match["confidence"] >= self.EARLY_EXIT_CONFIDENCE
            ):
                break

        if best_match is None:
            return {
                "matched": False,
                "reason": "No matching company found.",
            }

        return {
            "matched": True,
            "company": best_match["name"],
            "stl_id": best_match["stl_id"],
            "billing_number": best_match["billing_number"],
            "billing_period": best_match["billing_period"],
            "confidence": best_match["confidence"],
            "amount": best_match["amount"],
            "filename": self.renamer.build_filename(best_match),
        }
