import json
import unittest

from clipstack.backup_crypto import deserialize_backup, serialize_backup


class BackupCryptoTests(unittest.TestCase):
    def _sample(self):
        return {
            "version": "1.0",
            "clips": [{"text_content": "secret"}],
            "notes": [],
            "reminders": [],
            "snippets": [],
            "todos": [],
            "drawings": [],
        }

    def test_encrypted_backup_does_not_expose_content(self):
        encoded = serialize_backup(self._sample(), "correct horse")
        self.assertNotIn("secret", encoded)
        self.assertEqual(deserialize_backup(encoded, "correct horse"), self._sample())

    def test_wrong_password_is_rejected(self):
        encoded = serialize_backup(self._sample(), "correct horse")
        with self.assertRaises(ValueError):
            deserialize_backup(encoded, "wrong")

    def test_plain_legacy_backup_is_validated(self):
        encoded = json.dumps(self._sample())
        self.assertEqual(deserialize_backup(encoded), self._sample())

    def test_unknown_schema_is_rejected(self):
        broken = self._sample()
        broken["clips"] = "not-a-list"
        with self.assertRaises(ValueError):
            deserialize_backup(json.dumps(broken))


if __name__ == "__main__":
    unittest.main()
