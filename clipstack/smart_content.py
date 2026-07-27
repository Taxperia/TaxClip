"""
Akıllı içerik tanıma — URL, JSON, renk, e-posta, telefon, dosya yolu, kod, base64, markdown.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional


class ContentKind(str, Enum):
    URL = "url"
    EMAIL = "email"
    PHONE = "phone"
    HEX_COLOR = "hex_color"
    JSON = "json"
    FILE_PATH = "file_path"
    CODE = "code"
    BASE64_IMAGE = "base64_image"
    BASE64_TEXT = "base64_text"
    MARKDOWN = "markdown"
    LONG_TEXT = "long_text"
    PLAIN = "plain"


@dataclass
class SmartContent:
    kind: ContentKind
    title: str
    summary: str
    meta: dict


_URL_RE = re.compile(r"^https?://[^\s]+$", re.I)
_EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
_PHONE_RE = re.compile(r"^(?:\+90|0)?[\s\-]?\(?5\d{2}\)?[\s\-]?\d{3}[\s\-]?\d{2}\s?\d{2}$")
_HEX_RE = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")
_FILE_PATH_RE = re.compile(r'^(?:[a-zA-Z]:\\|\\\\)[^\n\r*]{1,500}$')
_BASE64_RE = re.compile(r"^(?:data:image/[^;]+;base64,)?[A-Za-z0-9+/=\s]{40,}$")
_MD_HINTS = re.compile(r"(^#{1,6}\s|^\*\s|^\-\s|```|\[.+\]\(.+\))", re.M)


def _short(text: str, n: int = 80) -> str:
    t = (text or "").strip().replace("\n", " ")
    return t if len(t) <= n else t[: n - 1] + "…"


def detect_language(code: str) -> str:
    """Basit dil tahmini (Pygments lexer ile)."""
    try:
        from pygments.lexers import guess_lexer
        lexer = guess_lexer(code)
        return getattr(lexer, "name", "text") or "text"
    except Exception:
        return "text"


def hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    if len(h) == 8:
        h = h[:6]
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def analyze_text(text: str) -> SmartContent:
    raw = (text or "").strip()
    if not raw:
        return SmartContent(ContentKind.PLAIN, "Boş", "", {})

    if _URL_RE.match(raw):
        return SmartContent(ContentKind.URL, "Bağlantı", _short(raw), {"url": raw})

    if _EMAIL_RE.match(raw):
        return SmartContent(ContentKind.EMAIL, "E-posta", raw, {"email": raw})

    if _PHONE_RE.match(raw.replace(" ", "")):
        return SmartContent(ContentKind.PHONE, "Telefon", raw, {"phone": raw})

    if _HEX_RE.match(raw):
        rgb = hex_to_rgb(raw)
        return SmartContent(
            ContentKind.HEX_COLOR,
            f"Renk {raw.upper()}",
            f"RGB({rgb[0]}, {rgb[1]}, {rgb[2]})",
            {"hex": raw, "rgb": rgb},
        )

    # JSON
    if (raw.startswith("{") and raw.endswith("}")) or (raw.startswith("[") and raw.endswith("]")):
        try:
            parsed = json.loads(raw)
            pretty = json.dumps(parsed, ensure_ascii=False, indent=2)
            return SmartContent(
                ContentKind.JSON,
                "JSON",
                _short(pretty, 100),
                {"pretty": pretty, "compact": json.dumps(parsed, ensure_ascii=False, separators=(",", ":"))},
            )
        except Exception:
            pass

    # Dosya yolu
    if _FILE_PATH_RE.match(raw) and ("\\" in raw or raw.startswith("/")):
        p = Path(raw)
        exists = p.exists()
        return SmartContent(
            ContentKind.FILE_PATH,
            p.name or "Dosya yolu",
            str(p),
            {"path": str(p), "exists": exists, "is_dir": p.is_dir() if exists else False},
        )

    # Base64 görsel
    b64 = raw
    if raw.lower().startswith("data:image/") and ";base64," in raw:
        b64 = raw.split(";base64,", 1)[1]
    if len(raw) > 80 and _BASE64_RE.match(raw.replace("\n", "")):
        try:
            import base64
            data = base64.b64decode(b64.strip(), validate=False)
            if data[:8] == b"\x89PNG\r\n\x1a\n" or data[:3] == b"\xff\xd8\xff" or data[:6] in (b"GIF87a", b"GIF89a"):
                return SmartContent(ContentKind.BASE64_IMAGE, "Base64 görsel", f"{len(data)} bayt", {"bytes": data})
            # metin gibi görünüyorsa
            try:
                decoded = data.decode("utf-8")
                if decoded.isprintable() or "\n" in decoded:
                    return SmartContent(ContentKind.BASE64_TEXT, "Base64 metin", _short(decoded), {"text": decoded})
            except Exception:
                pass
        except Exception:
            pass

    # Markdown
    if _MD_HINTS.search(raw) and len(raw) > 20:
        return SmartContent(ContentKind.MARKDOWN, "Markdown", _short(raw), {"markdown": raw})

    # Kod benzeri
    code_hints = ("{", "}", "def ", "function ", "import ", "class ", "=>", ";\n", "#!/")
    if any(h in raw for h in code_hints) and ("\n" in raw or len(raw) > 40):
        lang = detect_language(raw)
        return SmartContent(ContentKind.CODE, f"Kod ({lang})", _short(raw), {"language": lang, "code": raw})

    if len(raw) > 200:
        first_line = raw.splitlines()[0].strip() if raw.splitlines() else raw
        title = _short(first_line, 48) or "Uzun metin"
        return SmartContent(ContentKind.LONG_TEXT, title, _short(raw, 120), {"length": len(raw)})

    return SmartContent(ContentKind.PLAIN, _short(raw, 40), _short(raw, 100), {})


def format_file_size(num_bytes: int) -> str:
    units = ["B", "KB", "MB", "GB"]
    size = float(num_bytes)
    for unit in units:
        if size < 1024 or unit == units[-1]:
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{num_bytes} B"


def describe_paths(paths: list[str]) -> str:
    lines = []
    for p in paths[:8]:
        path = Path(p)
        if not path.exists():
            lines.append(f"⚠ {path.name} (mevcut değil)")
            continue
        try:
            if path.is_dir():
                lines.append(f"📁 {path.name}")
            else:
                lines.append(f"📄 {path.name} ({format_file_size(path.stat().st_size)})")
        except OSError:
            lines.append(f"📄 {path.name}")
    if len(paths) > 8:
        lines.append(f"… +{len(paths) - 8} dosya daha")
    return "\n".join(lines)
