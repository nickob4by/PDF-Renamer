from datetime import datetime
import shutil
from pathlib import Path

from config import OUTPUT_DIR, FAILED_DIR


class ReceiptRenamer:
    """
    Handles filename generation and saving of matched/unmatched PDFs.

    Target folders are configurable per instance so the GUI can rename
    into user-chosen directories; they default to the config paths.
    """

    def __init__(self, output_dir=OUTPUT_DIR, failed_dir=FAILED_DIR,
                 unknown_dir=None):
        self.output_dir = Path(output_dir)
        self.failed_dir = Path(failed_dir)
        if unknown_dir is not None:
            self.unknown_dir = Path(unknown_dir)
        else:
            self.unknown_dir = self.output_dir / "Unknown Billing Period"

    @staticmethod
    def _unique_path(destination):
        """
        Return a destination path that does not overwrite an existing file.
        Appends _2, _3, ... when the target name is already taken.
        """

        if not destination.exists():
            return destination

        for i in range(2, 10000):
            candidate = destination.with_name(
                f"{destination.stem}_{i}{destination.suffix}"
            )
            if not candidate.exists():
                return candidate

        raise FileExistsError(
            f"Cannot find a free filename for {destination}"
        )

    def build_filename(self, match):
        """
        Build the final filename.

        Format:
        SI_DASURECO_<STL_ID>_<BILLING_NUMBER>_<YYYYMMDD>.pdf
        """

        today = datetime.today().strftime("%Y%m%d")

        return (
        f"SI_DASURECO_"
        f"{match['stl_id']}_"
        f"{match['billing_number']}_"
        f"{match['billing_period']}_"
        f"{today}.pdf"
    )

    def save(self, source_pdf, match):
        """
        Save a matched PDF into the output folder.
        """

        filename = self.build_filename(match)

        self.output_dir.mkdir(parents=True, exist_ok=True)

        destination = self._unique_path(self.output_dir / filename)

        shutil.copy2(source_pdf, destination)

        return destination

    def save_unknown(self, source_pdf, match):
        """
        Save a matched PDF whose billing period is unknown into the
        manual-review folder, so it can be renamed by hand.
        """

        filename = self.build_filename(match)

        self.unknown_dir.mkdir(parents=True, exist_ok=True)

        destination = self._unique_path(self.unknown_dir / filename)

        shutil.copy2(source_pdf, destination)

        return destination

    def save_failed(self, source_pdf):
        """
        Save an unmatched PDF into the failed folder.
        """

        self.failed_dir.mkdir(parents=True, exist_ok=True)

        destination = self._unique_path(
            self.failed_dir / source_pdf.name
        )

        shutil.copy2(source_pdf, destination)

        return destination