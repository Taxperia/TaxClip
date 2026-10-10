import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from clipstack.biometric_auth import BiometricAuth
from clipstack.gdrive_sync import GoogleDriveSync
from clipstack.secure_storage import _DPAPI_MAGIC
from clipstack.sensitive_detector import contains_sensitive_data, verify_totp_for_sensitive
from clipstack.settings import Settings
from clipstack.storage import ClipItemType, Storage
from clipstack.totp_manager import TOTPManager
from clipstack.ui.item_preview_dialog import validate_share_server_url
from clipstack.updater import (
    MAX_UPDATE_BYTES,
    check_for_updates,
    download_update,
    verify_windows_authenticode,
)


class _Settings:
    def __init__(self, **values):
        self.values = values

    def get(self, key, default=None):
        return self.values.get(key, default)

    def set(self, key, value):
        self.values[key] = value


class SecurityFixTests(unittest.TestCase):
    def test_windows_hello_fails_closed(self):
        auth = BiometricAuth()
        self.assertFalse(auth.is_available())
        self.assertFalse(auth.authenticate()[0])

    def test_sensitive_detection_is_independent_from_mask_preferences(self):
        settings = _Settings(
            sensitive_data_detection=True,
            mask_passwords=False,
            mask_credit_cards=False,
            mask_api_keys=False,
            mask_emails=False,
            mask_phones=False,
            mask_tc_ids=False,
            mask_ibans=False,
        )
        self.assertTrue(contains_sensitive_data("password: top-secret", settings))

    def test_sensitive_totp_missing_secret_fails_closed(self):
        settings = _Settings(totp_for_sensitive=True)
        with patch("clipstack.totp_manager.TOTPManager.is_enabled", return_value=False):
            self.assertFalse(verify_totp_for_sensitive(settings))

    def test_totp_rate_limit_locks_after_five_failures(self):
        TOTPManager._failed_attempts = 0
        TOTPManager._locked_until = 0.0
        TOTPManager._accepted_codes = {}
        manager = TOTPManager(_Settings())
        fake_pyotp = SimpleNamespace(
            TOTP=lambda _secret: SimpleNamespace(verify=lambda *_args, **_kwargs: False)
        )
        with patch("clipstack.totp_manager.TOTP_AVAILABLE", True), patch.object(
            manager, "get_secret", return_value="JBSWY3DPEHPK3PXP"
        ), patch("clipstack.totp_manager.pyotp", fake_pyotp, create=True):
            for _ in range(5):
                self.assertFalse(manager.verify("123456"))
        self.assertGreater(manager.retry_after_seconds(), 0)

    def test_totp_code_cannot_be_replayed(self):
        TOTPManager._failed_attempts = 0
        TOTPManager._locked_until = 0.0
        TOTPManager._accepted_codes = {}
        manager = TOTPManager(_Settings())
        fake_pyotp = SimpleNamespace(
            TOTP=lambda _secret: SimpleNamespace(verify=lambda *_args, **_kwargs: True)
        )
        with patch("clipstack.totp_manager.TOTP_AVAILABLE", True), patch.object(
            manager, "get_secret", return_value="JBSWY3DPEHPK3PXP"
        ), patch("clipstack.totp_manager.pyotp", fake_pyotp, create=True):
            self.assertTrue(manager.verify("123456"))
            self.assertFalse(manager.verify("123456"))

    def test_updater_rejects_missing_hash_before_network(self):
        with self.assertRaises(ValueError):
            download_update("https://github.com/taxperia/taxclip/releases/download/v1/TaxClip.exe")

    def test_updater_rejects_cross_host_redirect(self):
        response = SimpleNamespace(
            url="https://attacker.example/TaxClip.exe",
            headers={"content-length": "4"},
            raise_for_status=lambda: None,
            iter_content=lambda chunk_size: [b"test"],
        )
        with patch("clipstack.updater.REQUESTS_AVAILABLE", True), patch(
            "clipstack.updater.requests.get", return_value=response
        ), self.assertRaises(ValueError):
            download_update(
                "https://github.com/taxperia/taxclip/releases/download/v2/TaxClip.exe",
                sha256_expected="0" * 64,
            )

    def test_updater_rejects_oversized_download_before_writing(self):
        response = SimpleNamespace(
            url="https://objects.githubusercontent.com/TaxClip.exe",
            headers={"content-length": str(MAX_UPDATE_BYTES + 1)},
            raise_for_status=lambda: None,
            iter_content=lambda chunk_size: [],
        )
        with patch("clipstack.updater.REQUESTS_AVAILABLE", True), patch(
            "clipstack.updater.requests.get", return_value=response
        ), self.assertRaises(ValueError):
            download_update(
                "https://github.com/taxperia/taxclip/releases/download/v2/TaxClip.exe",
                sha256_expected="0" * 64,
            )

    def test_updater_rejects_unsigned_zip_packages(self):
        with self.assertRaises(ValueError):
            download_update(
                "https://github.com/taxperia/taxclip/releases/download/v2/TaxClip.zip",
                sha256_expected="0" * 64,
            )

    def test_updater_rejects_url_credentials_and_nonstandard_port(self):
        for url in (
            "https://attacker@github.com/taxperia/taxclip/releases/download/v2/TaxClip.exe",
            "https://github.com:8443/taxperia/taxclip/releases/download/v2/TaxClip.exe",
        ):
            with self.subTest(url=url), self.assertRaises(ValueError):
                download_update(url, sha256_expected="0" * 64)

    def test_share_server_rejects_host_and_userinfo_confusion(self):
        rejected = (
            "https://taxclip.com.attacker.example",
            "https://taxclip.com@attacker.example",
            "https://attacker.example@taxclip.com",
            "https://taxclip.com:8443",
            "http://taxclip.com",
        )
        for url in rejected:
            with self.subTest(url=url):
                self.assertFalse(validate_share_server_url(url)[0])
        self.assertTrue(validate_share_server_url("https://taxclip.com")[0])
        self.assertTrue(validate_share_server_url("http://localhost:5000")[0])

    def test_update_check_ignores_zip_only_release(self):
        response = SimpleNamespace(
            url="https://api.github.com/repos/taxperia/taxclip/releases/latest",
            raise_for_status=lambda: None,
            json=lambda: {
                "tag_name": "v99.0.0",
                "assets": [{
                    "name": "TaxClip.zip",
                    "browser_download_url": "https://github.com/taxperia/taxclip/releases/download/v99/TaxClip.zip",
                }],
                "zipball_url": "https://api.github.com/repos/taxperia/taxclip/zipball/v99",
            },
        )
        with patch("clipstack.updater.REQUESTS_AVAILABLE", True), patch(
            "clipstack.updater.requests.get", return_value=response
        ):
            self.assertIsNone(check_for_updates("taxperia", "taxclip", "1.0.0"))

    def test_authenticode_rejects_unknown_valid_signer(self):
        unknown = "A" * 64
        with patch("clipstack.updater._authenticode_info", return_value=("Valid", unknown)), patch(
            "clipstack.updater._trusted_update_signers", return_value={"B" * 64}
        ):
            self.assertFalse(verify_windows_authenticode("TaxClip.exe"))

    def test_authenticode_accepts_pinned_valid_signer(self):
        trusted = "A" * 64
        with patch("clipstack.updater._authenticode_info", return_value=("Valid", trusted)), patch(
            "clipstack.updater._trusted_update_signers", return_value={trusted}
        ):
            self.assertTrue(verify_windows_authenticode("TaxClip.exe"))

    def test_share_api_key_is_kept_out_of_plain_settings(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings_path = Path(tmp) / "settings.json"
            settings = Settings(settings_path)
            settings.set("share_api_key", "top-secret-api-key")
            settings.save()
            self.assertNotIn("top-secret-api-key", settings_path.read_text("utf-8"))
            self.assertNotIn("top-secret-api-key", settings_path.with_suffix(".secrets").read_bytes().decode("latin1"))

            loaded = Settings(settings_path)
            loaded.load()
            self.assertEqual(loaded.get("share_api_key"), "top-secret-api-key")

    def test_legacy_plain_google_token_is_migrated_to_dpapi(self):
        with tempfile.TemporaryDirectory() as tmp:
            token_path = Path(tmp) / "google_token.json"
            legacy = '{"token":"legacy-token","refresh_token":"legacy-refresh"}'
            token_path.write_text(legacy, encoding="utf-8")
            sync = GoogleDriveSync()
            sync.token_path = token_path

            self.assertEqual(sync._read_token(), legacy)
            protected = token_path.read_bytes()
            self.assertTrue(protected.startswith(_DPAPI_MAGIC))
            self.assertNotIn(b"legacy-token", protected)

    def test_storage_migrates_existing_text_and_external_images(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            image_dir = root / "images"
            settings = _Settings(
                encrypt_data=False,
                save_images_externally=True,
                external_images_path=str(image_dir),
                sensitive_data_detection=False,
                max_items=1000,
            )
            storage = Storage(root / "test.db", settings)
            note = "plain note"
            png = b"\x89PNG\r\n\x1a\nexample"
            storage.add_note(note, "2026-01-01 00:00:00")
            image_row = storage.add_item(
                ClipItemType.IMAGE, None, png, None, "2026-01-01 00:00:01"
            )
            image_id = int(image_row["id"])

            storage.migrate_encryption("test-password", True)
            settings.set("encrypt_data", True)
            settings.set("encryption_key", "test-password")

            raw_note = storage.conn.execute("SELECT content FROM notes").fetchone()[0]
            raw_path = storage.conn.execute(
                "SELECT text_content FROM clip_items WHERE id = ?", (image_id,)
            ).fetchone()[0]
            self.assertNotIn(note, raw_note)
            self.assertNotIn(str(image_dir), raw_path)
            self.assertEqual(storage.list_notes()[0]["content"], note)
            self.assertEqual(storage.get_item(image_id)["image_blob"], png)

            storage.migrate_encryption("test-password", False)
            settings.set("encrypt_data", False)
            settings.set("encryption_key", None)
            self.assertEqual(storage.conn.execute("SELECT content FROM notes").fetchone()[0], note)
            self.assertEqual(storage.get_item(image_id)["image_blob"], png)
            storage.conn.close()

    def test_external_image_loader_rejects_path_outside_configured_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            allowed = root / "images"
            allowed.mkdir()
            settings = _Settings(
                encrypt_data=False,
                external_images_path=str(allowed),
                sensitive_data_detection=False,
                max_items=1000,
            )
            storage = Storage(root / "test.db", settings)
            row = {
                "item_type": int(ClipItemType.IMAGE),
                "image_blob": None,
                "text_content": r"\\attacker.example\share\capture.png",
            }

            self.assertEqual(storage._hydrate_external_image(dict(row)), row)
            storage.conn.close()

    def test_search_and_sort_inputs_cannot_inject_sql(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings = _Settings(
                encrypt_data=False,
                sensitive_data_detection=False,
                max_items=1000,
            )
            storage = Storage(Path(tmp) / "test.db", settings)
            storage.add_item(
                ClipItemType.TEXT, "normal content", None, None,
                "2026-01-01 00:00:00",
            )
            attack = "'; DROP TABLE clip_items; --"
            self.assertEqual(storage.search_items(query=attack), [])
            self.assertEqual(len(storage.list_items(sort=attack)), 1)
            count = storage.conn.execute("SELECT COUNT(*) FROM clip_items").fetchone()[0]
            self.assertEqual(count, 1)
            storage.conn.close()


if __name__ == "__main__":
    unittest.main()
