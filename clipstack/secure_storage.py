"""
Windows DPAPI tabanlı güvenli depolama yardımcıları.
Hassas verileri (OAuth token, TOTP secret) kullanıcı oturumuna bağlı şifreler.
"""
from __future__ import annotations

import base64
import sys
from typing import Optional


def _is_windows() -> bool:
    return sys.platform == "win32"


def protect_data(plaintext: bytes, entropy: Optional[bytes] = None) -> bytes:
    """DPAPI ile şifrele; Windows dışı platformlarda base64 fallback."""
    if not plaintext:
        return b""
    if not _is_windows():
        return base64.b64encode(plaintext)

    import ctypes
    from ctypes import wintypes

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32

    def _blob(data: bytes) -> DATA_BLOB:
        buf = ctypes.create_string_buffer(data)
        return DATA_BLOB(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))

    in_blob = _blob(plaintext)
    out_blob = DATA_BLOB()
    entropy_blob = _blob(entropy) if entropy else None

    flags = 0  # CRYPTPROTECT_UI_FORBIDDEN = 0x1 optional; keep default for user-scope
    ok = crypt32.CryptProtectData(
        ctypes.byref(in_blob),
        None,
        ctypes.byref(entropy_blob) if entropy_blob else None,
        None,
        None,
        flags,
        ctypes.byref(out_blob),
    )
    if not ok:
        raise OSError(f"CryptProtectData failed: {ctypes.GetLastError()}")

    try:
        protected = ctypes.string_at(out_blob.pbData, out_blob.cbData)
    finally:
        kernel32.LocalFree(out_blob.pbData)

    return protected


def unprotect_data(protected: bytes, entropy: Optional[bytes] = None) -> bytes:
    """DPAPI ile çöz; Windows dışı platformlarda base64 fallback."""
    if not protected:
        return b""
    if not _is_windows():
        return base64.b64decode(protected)

    import ctypes
    from ctypes import wintypes

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32

    def _blob(data: bytes) -> DATA_BLOB:
        buf = ctypes.create_string_buffer(data)
        return DATA_BLOB(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))

    in_blob = _blob(protected)
    out_blob = DATA_BLOB()
    entropy_blob = _blob(entropy) if entropy else None

    ok = crypt32.CryptUnprotectData(
        ctypes.byref(in_blob),
        None,
        ctypes.byref(entropy_blob) if entropy_blob else None,
        None,
        None,
        0,
        ctypes.byref(out_blob),
    )
    if not ok:
        raise OSError(f"CryptUnprotectData failed: {ctypes.GetLastError()}")

    try:
        plaintext = ctypes.string_at(out_blob.pbData, out_blob.cbData)
    finally:
        kernel32.LocalFree(out_blob.pbData)

    return plaintext


def protect_text(text: str, entropy: Optional[bytes] = None) -> bytes:
    return protect_data(text.encode("utf-8"), entropy)


def unprotect_text(protected: bytes, entropy: Optional[bytes] = None) -> str:
    return unprotect_data(protected, entropy).decode("utf-8")


# Dosya formatı: b"DPAPI1:" + protected_bytes
_DPAPI_MAGIC = b"DPAPI1:"


def write_protected_file(path, text: str, entropy: Optional[bytes] = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    protected = protect_text(text, entropy)
    path.write_bytes(_DPAPI_MAGIC + protected)


def read_protected_file(path, entropy: Optional[bytes] = None) -> Optional[str]:
    if not path.exists():
        return None
    raw = path.read_bytes()
    if raw.startswith(_DPAPI_MAGIC):
        return unprotect_text(raw[len(_DPAPI_MAGIC):], entropy)
    # Eski düz metin formatı (geriye uyumluluk)
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return None
