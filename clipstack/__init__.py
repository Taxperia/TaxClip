from pathlib import Path
import sys

__app_name__ = "TaxClip"


def _load_version() -> str:
    candidates = []

    if hasattr(sys, "_MEIPASS"):
        candidates.append(Path(sys._MEIPASS) / "version.txt")

    candidates.append(Path(__file__).resolve().parent.parent / "version.txt")

    for path in candidates:
        try:
            if path.exists():
                version = path.read_text(encoding="utf-8").strip()
                if version:
                    return version
        except Exception:
            continue

    return "1.0.0"


__version__ = _load_version()
