from __future__ import annotations
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QPalette, QColor
from .utils import resource_path

class ThemeManager:
    # keys: default, dark, light, purple
    def __init__(self):
        self.current = "default"

    def apply(self, theme_key: str):
        self.current = theme_key
        app = QApplication.instance()
        if not app:
            return
        # Load QSS
        qss_file = {
            "default": "styles/theme_default.qss",
            "dark": "styles/theme_dark.qss",
            "light": "styles/theme_light.qss",
            "purple": "styles/theme_purple.qss",
        }.get(theme_key, "styles/theme_default.qss")
        try:
            qss = resource_path(qss_file).read_text("utf-8")
            app.setStyleSheet(qss)
        except Exception:
            pass
        # Palette minimal tweak (özellikle light için)
        pal = app.palette()
        if theme_key == "light":
            pal.setColor(QPalette.Window, QColor("#f4f7fb"))
            pal.setColor(QPalette.Base, QColor("#ffffff"))
            pal.setColor(QPalette.Text, QColor("#111111"))
            pal.setColor(QPalette.WindowText, QColor("#111111"))
        else:
            pal.setColor(QPalette.Window, QColor("#0f172a"))
            pal.setColor(QPalette.Base, QColor("#0f172a"))
            pal.setColor(QPalette.Text, QColor("#e2e8f0"))
            pal.setColor(QPalette.WindowText, QColor("#e2e8f0"))
        app.setPalette(pal)

theme_manager = ThemeManager()