import base64
import unittest

from clipstack.utils_crypto import decrypt_aes256, encrypt_aes256, hash_password, verify_password


class CryptoUtilsTests(unittest.TestCase):
    def test_encrypt_decrypt_round_trip(self):
        encrypted = encrypt_aes256("gizli veri", "correct horse battery staple")

        self.assertEqual(decrypt_aes256(encrypted, "correct horse battery staple"), "gizli veri")

    def test_decrypt_rejects_wrong_password(self):
        encrypted = encrypt_aes256("gizli veri", "correct password")

        with self.assertRaises(ValueError):
            decrypt_aes256(encrypted, "wrong password")

    def test_decrypt_rejects_unsupported_short_payload(self):
        unsupported_payload = base64.b64encode(b"legacy-or-invalid").decode("utf-8")

        with self.assertRaises(ValueError):
            decrypt_aes256(unsupported_payload, "password")

    def test_password_hash_verify(self):
        stored_hash = hash_password("master password")

        self.assertTrue(verify_password("master password", stored_hash))
        self.assertFalse(verify_password("wrong password", stored_hash))


if __name__ == "__main__":
    unittest.main()
