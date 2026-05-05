import unittest
from unittest.mock import patch

from clipstack.ocr_manager import OCRManager, _WIN_OCR_SCRIPT_B64


class OCRManagerWindowsCommandTests(unittest.TestCase):
    @patch.object(OCRManager, "_check_tesseract", return_value=False)
    @patch.object(OCRManager, "_check_win_ocr", return_value=True)
    @patch("clipstack.ocr_manager.subprocess.run")
    def test_windows_ocr_uses_encoded_command_and_env_vars(self, mock_run, _mock_check_win, _mock_check_tesseract):
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "test"
        mock_run.return_value.stderr = ""

        manager = OCRManager()
        text = manager._extract_win_ocr(b"fake png bytes", "tur+eng")

        self.assertEqual(text, "test")
        args, kwargs = mock_run.call_args
        command = args[0]
        self.assertIn("-EncodedCommand", command)
        self.assertIn(_WIN_OCR_SCRIPT_B64, command)
        self.assertNotIn("-Command", command)
        self.assertEqual(kwargs["env"]["CLIPSTACK_OCR_LANG"], "tr")
        self.assertTrue(kwargs["env"]["CLIPSTACK_OCR_IMAGE_PATH"].lower().endswith(".png"))
        self.assertEqual(kwargs["encoding"], "utf-8")
        self.assertTrue(kwargs["text"])


if __name__ == "__main__":
    unittest.main()
