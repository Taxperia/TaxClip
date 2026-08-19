"""Kart ortak yardımcılar — tip rozeti, tarih, kod vurgusu, görünüm modu."""
from __future__ import annotations

from PySide6.QtCore import Qt, QSize
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QToolButton, QWidget, QSizePolicy

from ..utils import svg_icon


CARD_W = 260
CARD_H = 168
LIST_H = 76


def format_card_date(raw: str) -> str:
    if not raw:
        return ""
    try:
        date_part = str(raw).split(" ")[0]
        y, m, d = date_part.split("-")
        return f"{d}.{m}.{y}"
    except Exception:
        return str(raw)[:16]


def highlight_code(text: str, max_chars: int = 400) -> str:
    """QLabel RichText için renkli kod — span yerine <font> (QSS color mirasını aşar)."""
    import re

    snippet = text if len(text) <= max_chars else text[: max_chars - 1] + "…"
    try:
        from pygments import highlight
        from pygments.lexers import guess_lexer, TextLexer
        from pygments.formatters import HtmlFormatter
        try:
            lexer = guess_lexer(snippet)
        except Exception:
            lexer = TextLexer()
        formatter = HtmlFormatter(
            noclasses=True,
            nobackground=True,
            style="monokai",
            nowrap=True,
        )
        html = highlight(snippet, lexer, formatter)
        html = re.sub(
            r'<span style="color:\s*([^";]+)[^"]*"[^>]*>',
            r'<font color="\1">',
            html,
            flags=re.IGNORECASE,
        )
        html = html.replace("</span>", "</font>")
        return (
            "<div style='font-family: Consolas, Cascadia Mono, monospace; "
            f"font-size: 10px; line-height: 1.35; white-space: pre-wrap;'>{html}</div>"
        )
    except Exception:
        escaped = (
            snippet.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        )
        return (
            f"<pre style='font-size:10px; white-space:pre-wrap; margin:0;'>"
            f"<font color='#cbd5e1'>{escaped}</font></pre>"
        )


def apply_card_view_mode(widget: QWidget, mode: str, preview: QLabel | None = None) -> None:
    """grid | list — kart boyutunu ve önizleme yüksekliğini ayarla."""
    mode = "list" if mode == "list" else "grid"
    widget._view_mode = mode
    if mode == "list":
        widget.setMinimumSize(320, LIST_H)
        widget.setMaximumSize(16777215, LIST_H)
        try:
            sp = widget.sizePolicy()
            sp.setHorizontalPolicy(QSizePolicy.Expanding)
            sp.setVerticalPolicy(QSizePolicy.Fixed)
            widget.setSizePolicy(sp)
        except Exception:
            pass
        if preview is not None:
            preview.setMaximumHeight(28)
            preview.setWordWrap(False)
    else:
        widget.setMinimumSize(CARD_W, CARD_H)
        widget.setMaximumSize(CARD_W, CARD_H)
        widget.setFixedSize(CARD_W, CARD_H)
        try:
            sp = widget.sizePolicy()
            sp.setHorizontalPolicy(QSizePolicy.Fixed)
            sp.setVerticalPolicy(QSizePolicy.Fixed)
            widget.setSizePolicy(sp)
        except Exception:
            pass
        if preview is not None:
            preview.setMaximumHeight(16777215)
            preview.setWordWrap(True)


def make_type_badge(icon_path: str = "assets/icons/type_text.svg", glyph: str = "T") -> QFrame:
    badge = QFrame()
    badge.setObjectName("ItemTypeBadge")
    badge.setFixedSize(28, 28)
    badge.setAttribute(Qt.WA_StyledBackground, True)
    lay = QHBoxLayout(badge)
    lay.setContentsMargins(0, 0, 0, 0)
    icon = QLabel()
    icon.setAlignment(Qt.AlignCenter)
    icon.setFixedSize(28, 28)
    icon.setStyleSheet("background: transparent; border: none;")
    try:
        icon.setPixmap(svg_icon(icon_path).pixmap(QSize(16, 16)))
    except Exception:
        icon.setText(glyph)
    lay.addWidget(icon)
    return badge


def make_tool_button(object_name: str, icon_path: str = "", tip: str = "", text: str = "") -> QToolButton:
    btn = QToolButton()
    btn.setObjectName(object_name)
    btn.setAutoRaise(True)
    btn.setStyleSheet("background: transparent; border: none;")
    btn.setIconSize(QSize(16, 16))
    if tip:
        btn.setToolTip(tip)
    if icon_path:
        try:
            btn.setIcon(svg_icon(icon_path))
        except Exception:
            if text:
                btn.setText(text)
    elif text:
        btn.setText(text)
    return btn
