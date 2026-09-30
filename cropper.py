from config import (
    CROP_LEFT,
    CROP_TOP,
    CROP_RIGHT,
    CROP_BOTTOM,
)

class ReceiptCropper:

    def get_crop_variants(self, image):
        height, width = image.shape[:2]

        variants = [
            # Original crop
            (CROP_TOP, CROP_BOTTOM),

            # Shift upward
            (max(0.0, CROP_TOP - 0.04), max(0.0, CROP_BOTTOM - 0.04)),

            # Shift downward
            (min(1.0, CROP_TOP + 0.04), min(1.0, CROP_BOTTOM + 0.04)),

            # Slightly taller crop
            (max(0.0, CROP_TOP - 0.02), min(1.0, CROP_BOTTOM + 0.02)),
        ]

        crops = []

        x1 = int(width * CROP_LEFT)
        x2 = int(width * CROP_RIGHT)

        for top, bottom in variants:
            y1 = int(height * top)
            y2 = int(height * bottom)

            crops.append(
                image[y1:y2, x1:x2]
            )

        return crops