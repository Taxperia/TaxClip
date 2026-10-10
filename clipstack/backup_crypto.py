from __future__ import annotations

import json
from typing import Any

from .utils_crypto import decrypt_aes256, encrypt_aes256


BACKUP_FORMAT = "taxclip-backup"
BACKUP_VERSION = 2
MAX_BACKUP_BYTES = 100 * 1024 * 1024
_COLLECTION_KEYS = ("clips", "notes", "reminders", "snippets", "todos", "drawings")


def validate_backup(data: Any) -> dict:
    if not isinstance(data, dict):
        raise ValueError("Yedek kök değeri nesne olmalıdır.")
    version = str(data.get("version", ""))
    if version not in {"1.0", "2", "2.0"}:
        raise ValueError("Desteklenmeyen yedek sürümü.")
    for key in _COLLECTION_KEYS:
        value = data.get(key, [])
        if not isinstance(value, list):
            raise ValueError(f"Geçersiz yedek alanı: {key}")
        if len(value) > 100_000:
            raise ValueError(f"Yedek alanı çok fazla kayıt içeriyor: {key}")
    return data


def serialize_backup(data: dict, password: str | None = None) -> str:
    validate_backup(data)
    plaintext = json.dumps(data, ensure_ascii=False, separators=(",", ":"), default=str)
    if not password:
        return json.dumps(data, ensure_ascii=False, indent=2, default=str)
    envelope = {
        "format": BACKUP_FORMAT,
        "version": BACKUP_VERSION,
        "encrypted": True,
        "payload": encrypt_aes256(plaintext, password),
    }
    return json.dumps(envelope, ensure_ascii=False, indent=2)


def deserialize_backup(content: str, password: str | None = None) -> dict:
    if len(content.encode("utf-8")) > MAX_BACKUP_BYTES:
        raise ValueError("Yedek dosyası izin verilen boyutu aşıyor.")
    parsed = json.loads(content)
    if isinstance(parsed, dict) and parsed.get("format") == BACKUP_FORMAT:
        if parsed.get("version") != BACKUP_VERSION or parsed.get("encrypted") is not True:
            raise ValueError("Desteklenmeyen şifreli yedek biçimi.")
        if not password:
            raise ValueError("Bu yedek şifreli; veri şifresi gerekli.")
        payload = parsed.get("payload")
        if not isinstance(payload, str):
            raise ValueError("Şifreli yedek verisi eksik.")
        parsed = json.loads(decrypt_aes256(payload, password))
    return validate_backup(parsed)
