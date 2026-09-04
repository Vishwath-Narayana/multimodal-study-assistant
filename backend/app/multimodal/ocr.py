"""`OCRProvider` implementations.

`TesseractOCRProvider` wraps the system `tesseract` binary via
`pytesseract`. `is_available()` is a real reachability check (calls
`pytesseract.get_tesseract_version()`), not just "was a provider object
constructed" — so a missing binary reports `UNAVAILABLE` rather than
raising deep inside ingestion (spec section 10/23).

`NullOCRProvider` is the default when `Settings.ocr_provider` is empty.
"""

from __future__ import annotations

from pathlib import Path

from app.ingestion.models import VisionStatus
from app.multimodal.interfaces import OCRProvider
from app.multimodal.models import OCRResult


class NullOCRProvider(OCRProvider):
    def extract(self, image_path: Path) -> OCRResult:
        return OCRResult(status=VisionStatus.UNAVAILABLE, text=None, engine=None)

    def is_available(self) -> bool:
        return False

    @property
    def engine_id(self) -> str:
        return ""


class TesseractOCRProvider(OCRProvider):
    def __init__(self) -> None:
        self._availability_checked = False
        self._available = False

    @property
    def engine_id(self) -> str:
        return "tesseract"

    def is_available(self) -> bool:
        if self._availability_checked:
            return self._available
        self._availability_checked = True
        try:
            import pytesseract

            pytesseract.get_tesseract_version()
            self._available = True
        except Exception:  # noqa: BLE001 - any failure means "not usable"
            self._available = False
        return self._available

    def extract(self, image_path: Path) -> OCRResult:
        if not self.is_available():
            return OCRResult(status=VisionStatus.UNAVAILABLE, text=None, engine=self.engine_id)
        try:
            import pytesseract
            from PIL import Image

            with Image.open(image_path) as img:
                text = pytesseract.image_to_string(img)
        except Exception:  # noqa: BLE001 - engine ran but failed on this image
            return OCRResult(status=VisionStatus.FAILED, text=None, engine=self.engine_id)
        return OCRResult(status=VisionStatus.AVAILABLE, text=text.strip(), engine=self.engine_id)
