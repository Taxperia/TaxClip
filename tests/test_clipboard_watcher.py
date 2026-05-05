import unittest
from unittest.mock import patch

from PySide6.QtCore import QByteArray, QMimeData
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

    def add_item(self, item_type, text, image_bytes, html, created_at):
        self.added.append((item_type, text, image_bytes, html, created_at))
        return {"id": len(self.added)}


class ClipboardWatcherImageStabilizationTests(unittest.TestCase):
    def test_native_windows_png_format_still_needs_mime_png_stabilization(self):
        watcher = ClipboardWatcher(
            _FakeClipboard(QImage(), QMimeData()),
            _FakeStorage(),
            _FakeSettings(),
        )

        native_png_only = QMimeData()
        native_png_only.setData('application/x-qt-windows-mime;value="PNG"', QByteArray(b"png"))
        self.assertTrue(watcher._image_mime_needs_stabilization(native_png_only))

        mime_png = QMimeData()
        mime_png.setData("image/png", QByteArray(b"png"))
        self.assertFalse(watcher._image_mime_needs_stabilization(mime_png))

    def test_duplicate_raw_image_still_queues_stabilization(self):
        image = QImage(32, 24, QImage.Format.Format_ARGB32)
        image.fill(0xFF1E90FF)

        mime_data = QMimeData()
        mime_data.setImageData(image)

        storage = _FakeStorage()
        watcher = ClipboardWatcher(_FakeClipboard(image, mime_data), storage, _FakeSettings())

        scheduled_delays = []

        def capture_timer(delay_ms, _callback):
            scheduled_delays.append(delay_ms)

        with (
            patch("clipstack.clipboard_watcher.QTimer.singleShot", side_effect=capture_timer),
            patch("clipstack.clipboard_watcher.copy_to_clipboard_safely", return_value=True) as copy_mock,
        ):
            watcher._on_clip_changed()
            watcher._on_clip_changed()

        self.assertEqual([item[0] for item in storage.added], [ClipItemType.IMAGE])
        self.assertEqual(copy_mock.call_count, 2)
        self.assertEqual(scheduled_delays, [80, 200, 500, 80, 200, 500])


if __name__ == "__main__":
    unittest.main()
