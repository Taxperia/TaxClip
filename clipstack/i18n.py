from __future__ import annotations
import json
from pathlib import Path
from PySide6.QtCore import QObject, Signal
from .utils import resource_path

class I18n(QObject):
    languageChanged = Signal(str)

    def __init__(self):
        super().__init__()
        self._lang_code = "en"
        self._catalog = {}
        self._fallback = {}
        self.load_language("en")  # fallback

    def load_language(self, lang_code: str):
        self._lang_code = lang_code
        # Fallback (en)
        en_path = resource_path("assets/i18n/en.json")
        try:
            self._fallback = json.loads(en_path.read_text("utf-8"))
        except Exception:
            self._fallback = {}
        # Desired
        path = resource_path(f"assets/i18n/{lang_code}.json")
        try:
            self._catalog = json.loads(path.read_text("utf-8"))
        except Exception:
            self._catalog = {}
        self.languageChanged.emit(lang_code)

    def t(self, key: str) -> str:
        if key in self._catalog:
            return self._catalog[key]
        return self._fallback.get(key, key)

i18n = I18n()