from __future__ import annotations
from pathlib import Path
from PySide6.QtCore import QObject, QEvent
from PySide6.QtWidgets import QApplication, QToolTip, QWidget
from PySide6.QtGui import QPalette, QColor, QFont
from .utils import resource_path


_TOOLTIP_STYLE_MARKER_BEGIN = "/*__taxclip_tooltip_theme_begin__*/"
_TOOLTIP_STYLE_MARKER_END = "/*__taxclip_tooltip_theme_end__*/"


class _TooltipStyleEnforcer(QObject):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._tooltip_qss = ""

    def set_tooltip_qss(self, tooltip_qss: str):
        self._tooltip_qss = tooltip_qss.strip()

    def refresh_all_widgets(self):
        app = QApplication.instance()
        if not app:
            return
        for widget in app.allWidgets():
            self._apply(widget)

    def eventFilter(self, obj, event):  # pragma: no cover - Qt callback
        if not self._tooltip_qss or not isinstance(obj, QWidget):
            return False

        if event.type() in (
            QEvent.Type.Polish,
            QEvent.Type.Show,
            QEvent.Type.StyleChange,
            QEvent.Type.DynamicPropertyChange,
        ):
            self._apply(obj)
        return False

    def _strip_tooltip_block(self, stylesheet: str) -> str:
        style = stylesheet or ""
        start = style.find(_TOOLTIP_STYLE_MARKER_BEGIN)
        end = style.find(_TOOLTIP_STYLE_MARKER_END)
        if start == -1 or end == -1 or end < start:
            return style
        end += len(_TOOLTIP_STYLE_MARKER_END)
        combined = (style[:start] + style[end:]).strip()
        return combined

    def _apply(self, widget: QWidget):
        if widget is None:
            return

        current = widget.styleSheet() or ""
        cleaned = self._strip_tooltip_block(current).strip()
        if not cleaned:
            return

        tooltip_block = (
            f"\n{_TOOLTIP_STYLE_MARKER_BEGIN}\n"
            f"{self._tooltip_qss}\n"
            f"{_TOOLTIP_STYLE_MARKER_END}\n"
        )
        expected = f"{cleaned}\n{tooltip_block}".strip()
        if current.strip() == expected:
            return
        widget.setStyleSheet(expected)


class ThemeManager:
    # keys: default, dark, light, purple, cyberpunk, sunset, matrix, ocean, retro
    def __init__(self):
        self.current = "default"
        self._tooltip_enforcer: _TooltipStyleEnforcer | None = None

    def apply(self, theme_key: str):
        self.current = theme_key
        app = QApplication.instance()
        if not app:
            return

        if self._tooltip_enforcer is None:
            self._tooltip_enforcer = _TooltipStyleEnforcer(app)
            app.installEventFilter(self._tooltip_enforcer)

        # Load QSS
        qss_file = {
            "default": "styles/theme_default.qss",
            "dark": "styles/theme_dark.qss",
            "light": "styles/theme_light.qss",
            "purple": "styles/theme_purple.qss",
            "cyberpunk": "styles/theme_cyberpunk.qss",
            "sunset": "styles/theme_sunset.qss",
            "matrix": "styles/theme_matrix.qss",
            "ocean": "styles/theme_ocean.qss",
            "retro": "styles/theme_retro.qss",
        }.get(theme_key, "styles/theme_default.qss")
        try:
            qss = resource_path(qss_file).read_text("utf-8")
            tooltip_qss = self._build_tooltip_qss(theme_key)
            app.setStyleSheet(f"{qss.rstrip()}\n\n{tooltip_qss}\n")
            self._tooltip_enforcer.set_tooltip_qss(tooltip_qss)
            self._tooltip_enforcer.refresh_all_widgets()
            self._apply_tooltip_palette(theme_key, app)
        except Exception:
            pass
        # Palette minimal tweak
        pal = app.palette()
        if theme_key == "light":
            pal.setColor(QPalette.Window, QColor("#f4f7fb"))
            pal.setColor(QPalette.Base, QColor("#ffffff"))
            pal.setColor(QPalette.Text, QColor("#111111"))
            pal.setColor(QPalette.WindowText, QColor("#111111"))
        elif theme_key == "retro":
            pal.setColor(QPalette.Window, QColor("#0078d7"))
            pal.setColor(QPalette.Base, QColor("#ffffff"))
            pal.setColor(QPalette.Text, QColor("#000000"))
            pal.setColor(QPalette.WindowText, QColor("#ffffff"))
        elif theme_key == "matrix":
            pal.setColor(QPalette.Window, QColor("#0d0d0d"))
            pal.setColor(QPalette.Base, QColor("#001a00"))
            pal.setColor(QPalette.Text, QColor("#00ff41"))
            pal.setColor(QPalette.WindowText, QColor("#00ff41"))
        elif theme_key == "cyberpunk":
            pal.setColor(QPalette.Window, QColor("#0d0221"))
            pal.setColor(QPalette.Base, QColor("#1a0933"))
            pal.setColor(QPalette.Text, QColor("#f0e7ff"))
            pal.setColor(QPalette.WindowText, QColor("#f0e7ff"))
        elif theme_key in ("sunset", "ocean"):
            pal.setColor(QPalette.Window, QColor("#1a0a2e"))
            pal.setColor(QPalette.Base, QColor("#1a0a2e"))
            pal.setColor(QPalette.Text, QColor("#ffe5ec"))
            pal.setColor(QPalette.WindowText, QColor("#ffe5ec"))
        else:
            pal.setColor(QPalette.Window, QColor("#0f172a"))
            pal.setColor(QPalette.Base, QColor("#0f172a"))
            pal.setColor(QPalette.Text, QColor("#e2e8f0"))
            pal.setColor(QPalette.WindowText, QColor("#e2e8f0"))
        app.setPalette(pal)

    def _tooltip_colors(self, theme_key: str) -> dict:
        return {
            "default": {"bg": "#0f172a", "fg": "#e6edf3", "border": "#1f2937"},
            "dark": {"bg": "#2a2a2a", "fg": "#ffffff", "border": "#404040"},
            "light": {"bg": "#ffffff", "fg": "#333333", "border": "#cccccc"},
            "purple": {"bg": "#2d1b69", "fg": "#f5efff", "border": "#8b5cf6"},
            "cyberpunk": {"bg": "#12031f", "fg": "#f8f5ff", "border": "#00f6ff"},
            "sunset": {"bg": "#2d1028", "fg": "#fff1f2", "border": "#ff8a5b"},
            "matrix": {"bg": "#001a00", "fg": "#00ff41", "border": "#00c853"},
            "ocean": {"bg": "#09233a", "fg": "#e0f2fe", "border": "#38bdf8"},
            "retro": {"bg": "#ffffcc", "fg": "#000000", "border": "#000000"},
        }.get(theme_key, {"bg": "#0f172a", "fg": "#e6edf3", "border": "#1f2937"})

    def _build_tooltip_qss(self, theme_key: str) -> str:
        colors = self._tooltip_colors(theme_key)
        radius = "0px" if theme_key == "retro" else "6px"
        padding = "4px 8px" if theme_key == "retro" else "6px 10px"
        return (
            "QToolTip {\n"
            f"    background: {colors['bg']};\n"
            f"    color: {colors['fg']};\n"
            f"    border: 1px solid {colors['border']};\n"
            f"    border-radius: {radius};\n"
            f"    padding: {padding};\n"
            "    font-size: 12px;\n"
            "}"
        )

    def _apply_tooltip_palette(self, theme_key: str, app: QApplication):
        colors = self._tooltip_colors(theme_key)
        pal = QToolTip.palette()
        pal.setColor(QPalette.ColorRole.ToolTipBase, QColor(colors["bg"]))
        pal.setColor(QPalette.ColorRole.ToolTipText, QColor(colors["fg"]))
        pal.setColor(QPalette.ColorRole.Base, QColor(colors["bg"]))
        pal.setColor(QPalette.ColorRole.Text, QColor(colors["fg"]))
        pal.setColor(QPalette.ColorRole.Window, QColor(colors["bg"]))
        pal.setColor(QPalette.ColorRole.WindowText, QColor(colors["fg"]))
        pal.setColor(QPalette.ColorRole.Mid, QColor(colors["border"]))
        pal.setColor(QPalette.ColorRole.Dark, QColor(colors["border"]))
        QToolTip.setPalette(pal)

        font = QFont(app.font())
        if font.pointSize() < 10:
            font.setPointSize(10)
        QToolTip.setFont(font)

theme_manager = ThemeManager()
