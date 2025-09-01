from __future__ import annotations
import json
from pathlib import Path

class Settings:
    def __init__(self, path: Path):
        self.path = Path(path)
        self._data = {
            "first_run": True,
            "language": "tr",
            "theme": "default",
            "hide_after_copy": False,
            "stay_on_top": False,
            "animations": True,
            "max_items": 1000,
            "dedupe_window_ms": 1200,
            "confirm_delete": True,
            "show_toast": True,
            "tray_icon": "assets/icons/tray/tray1.svg",  # .svg olarak güncellendi
            "tray_notifications": True,
            "launch_at_startup": True,
            "hotkey": "windows+v",
            "pause_recording": False,
        }

    def load(self):
        if self.path.exists():
            try:
                self._data.update(json.loads(self.path.read_text("utf-8")))
            except Exception:
                pass

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._data, ensure_ascii=False, indent=2), encoding="utf-8")

    def get(self, key, default=None):
        return self._data.get(key, default)

    def set(self, key, value):
        self._data[key] = value