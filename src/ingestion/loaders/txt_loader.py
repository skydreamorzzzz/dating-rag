"""Loader for plain-text files with encoding detection."""

from pathlib import Path
from src.ingestion.loaders.base import BaseLoader
from src.ingestion.schemas import Document
from src.utils.logger import get_logger

logger = get_logger(__name__)

ENCODINGS_TO_TRY = ["utf-8", "gb18030", "gbk", "gb2312", "big5"]


class TxtLoader(BaseLoader):
    """Load a .txt file, trying common Chinese encodings until one succeeds."""

    def load(self, file_path: Path) -> list[Document]:
        text, used_encoding, warnings = self._read_with_encoding(file_path)

        if used_encoding != "utf-8" and used_encoding is not None:
            msg = f"File decoded as {used_encoding}, not utf-8"
            warnings.append(msg)
            logger.warning("%s: %s", file_path.name, msg)

        doc = Document(
            source_file=file_path.name,
            source_path=str(file_path),
            doc_type="txt",
            text=text,
            warnings=warnings,
        )
        logger.info("Loaded %s (%d chars, encoding=%s)", file_path.name, len(text), used_encoding)
        return [doc]

    def _read_with_encoding(self, file_path: Path) -> tuple[str, str | None, list[str]]:
        warnings: list[str] = []
        last_error: str | None = None
        raw = file_path.read_bytes()

        for enc in ENCODINGS_TO_TRY:
            try:
                text = raw.decode(enc)
                return text, enc, warnings
            except (UnicodeDecodeError, LookupError) as e:
                last_error = str(e)
                continue

        # chardet as last resort
        try:
            import chardet
            detected = chardet.detect(raw)
            enc = detected.get("encoding")
            if enc:
                try:
                    text = raw.decode(enc)
                    warnings.append(f"Encoding detected by chardet as {enc}")
                    return text, enc, warnings
                except (UnicodeDecodeError, LookupError):
                    pass
        except ImportError:
            pass

        # Final fallback: gb18030 with replacement characters for bad bytes
        text = raw.decode("gb18030", errors="replace")
        warnings.append(
            f"No encoding matched cleanly (last error: {last_error}); "
            "decoded as gb18030 with replacement chars"
        )
        return text, "gb18030 (replace)", warnings

    @staticmethod
    def supported_extensions() -> list[str]:
        return [".txt"]
