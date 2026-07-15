"""LibreOffice-based conversion helpers for legacy Office formats."""

from pathlib import Path
import shutil
import subprocess

from src.utils.config import INTERIM_DIR
from src.utils.logger import get_logger

logger = get_logger(__name__)

LEGACY_TARGETS = {
    ".doc": ".docx",
    ".ppt": ".pptx",
}


def convert_with_libreoffice(
    input_path: Path,
    output_dir: Path | None = None,
) -> Path:
    """Convert a legacy Office file to its modern XML format.

    Supported conversions are ``.doc`` to ``.docx`` and ``.ppt`` to ``.pptx``.
    Converted files are written to ``data/interim/`` by default.

    Raises:
        ValueError: if the extension is unsupported.
        RuntimeError: if LibreOffice is unavailable or conversion fails.
    """
    input_path = Path(input_path)
    suffix = input_path.suffix.lower()
    target_suffix = LEGACY_TARGETS.get(suffix)
    if target_suffix is None:
        raise ValueError(f"LibreOffice conversion is not configured for '{suffix}'")

    executable = shutil.which("libreoffice") or shutil.which("soffice")
    if executable is None:
        raise RuntimeError(
            "LibreOffice is required to convert legacy Office files. "
            "Install libreoffice or convert the file manually first."
        )

    output_dir = Path(output_dir) if output_dir else INTERIM_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    expected_output = output_dir / f"{input_path.stem}{target_suffix}"
    if expected_output.exists() and expected_output.stat().st_mtime >= input_path.stat().st_mtime:
        logger.info("Using existing converted file %s", expected_output)
        return expected_output

    cmd = [
        executable,
        "--headless",
        "--convert-to",
        target_suffix.lstrip("."),
        "--outdir",
        str(output_dir),
        str(input_path),
    ]
    logger.info("Converting %s to %s via LibreOffice", input_path.name, target_suffix)

    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(f"LibreOffice failed to convert {input_path.name}: {detail}")

    if not expected_output.exists():
        matches = sorted(output_dir.glob(f"{input_path.stem}.*"))
        converted = next((p for p in matches if p.suffix.lower() == target_suffix), None)
        if converted is None:
            detail = (result.stdout or result.stderr or "").strip()
            raise RuntimeError(
                f"LibreOffice reported success but no {target_suffix} output was found "
                f"for {input_path.name}. {detail}"
            )
        expected_output = converted

    return expected_output
