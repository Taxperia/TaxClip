# GitHub Security Finding - Resolved

## Finding

GitHub reported weak password-based key derivation because sensitive password data was previously passed through a direct SHA-256 hash.

## Resolution

The legacy SHA-256 password key derivation path was removed from `clipstack/utils_crypto.py`.

Current encryption now uses:

- PBKDF2-HMAC-SHA256 with a per-encryption random salt
- AES-256-GCM authenticated encryption
- constant-time password hash comparison via `hmac.compare_digest`

## Compatibility Note

Old AES-CFB payloads derived directly from SHA-256 are no longer decrypted. This is intentional to remove the weak cryptographic path flagged by GitHub.

## Validation

Added crypto regression tests in `tests/test_utils_crypto.py`.
