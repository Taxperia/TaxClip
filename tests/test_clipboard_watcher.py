import unittest
from unittest.mock import patch

from PySide6.QtCore import QMimeData
from PySide6.QtGui import QImage

from clipstack.clipboard_watcher import ClipboardWatcher
from clipstack.storage import ClipItemType


class _FakeSignal:
    def connect(self, callback):
        self.callback = callback


class _FakeClipboard:
    def __init__(self, image: QImage, mime_data: QMimeData):
        self.dataChanged = _FakeSignal()
        self._image = image
        self._mime_data = mime_data

    def image(self):
        return self._image

    def mimeData(self):
        return self._mime_data


class _FakeSettings:
    def get(self, _key, default=None):
        return default


class _FakeStorage:
    def __init__(self):
        self.added = []

    def add_item(self, item_type, text, image_bytes, html, created_at, source_app=None):
        self.added.append((item_type, text, image_bytes, html, created_at))
        return {"id": len(self.added)}


class ClipboardWatcherImageCaptureTests(unittest.TestCase):
    def test_raw_image_is_recorded_without_rewriting_source_clipboard(self):
        image = QImage(32, 24, QImage.Format.Format_ARGB32)
        image.fill(0xFF1E90FF)

        mime_data = QMimeData()
        mime_data.setImageData(image)

        storage = _FakeStorage()
        watcher = ClipboardWatcher(_FakeClipboard(image, mime_data), storage, _FakeSettings())
        watcher._poll_timer.stop()

        # Regression guard: Print Screen içeriği izlenirken sistem panosu yeniden
        # yazılmamalı. Yeniden yazma, kullanıcının Ctrl+V işlemiyle yarışıyordu.
        with patch(
            "clipstack.clipboard_watcher.copy_to_clipboard_safely",
            create=True,
        ) as copy_mock, patch(
            "clipstack.clipboard_watcher.get_foreground_process_name",
            return_value="explorer.exe",
        ):
            watcher._on_clip_changed()
            watcher._on_clip_changed()

        self.assertEqual([item[0] for item in storage.added], [ClipItemType.IMAGE])
        copy_mock.assert_not_called()

    def test_excluded_app_is_snapshotted_once_and_not_saved_later(self):
        image = QImage()
        mime_data = QMimeData()
        mime_data.setText("password: secret-value")
        storage = _FakeStorage()
        watcher = ClipboardWatcher(_FakeClipboard(image, mime_data), storage, _FakeSettings())
        watcher._poll_timer.stop()

        with patch(
            "clipstack.clipboard_watcher.get_foreground_process_name",
            return_value="keepass.exe",
        ) as process_mock:
            watcher._on_clip_changed()

        self.assertEqual(storage.added, [])
        self.assertEqual(watcher._last_poll_text, "password: secret-value")
        process_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
