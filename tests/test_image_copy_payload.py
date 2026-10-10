import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from clipstack.storage import ClipItemType
from clipstack.ui.main_window import HistoryWindow


class ImageCopyPayloadTests(unittest.TestCase):
    def test_image_copy_uses_fresh_hydrated_database_blob(self):
        image_bytes = b"fresh-image-bytes"
        host = SimpleNamespace(
            storage=SimpleNamespace(
                get_item=Mock(return_value={
                    "id": 7,
                    "item_type": int(ClipItemType.IMAGE),
                    "image_blob": image_bytes,
                    "ocr_text": "",
                }),
                record_item_use=Mock(),
            ),
            settings={"show_toast": False, "tray_notifications": False, "hide_after_copy": False},
            _toast=None,
            _notifier=None,
        )

        with patch("clipstack.ui.main_window.copy_to_clipboard_safely", return_value=True) as copy_mock:
            HistoryWindow.on_copy_requested(host, 7, ClipItemType.IMAGE, None)

        copy_mock.assert_called_once_with(host, ClipItemType.IMAGE, image_bytes)
        host.storage.record_item_use.assert_called_once_with(7)


if __name__ == "__main__":
    unittest.main()
