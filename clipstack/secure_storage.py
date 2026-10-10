"""
Windows DPAPI tabanlı güvenli depolama yardımcıları.
Hassas verileri (OAuth token, TOTP secret) kullanıcı oturumuna bağlı şifreler.
"""
from __future__ import annotations

import os
import sys
import tempfile
from typing import Optional


def _is_windows() -> bool:
    return sys.platform == "win32"


def protect_data(plaintext: bytes, entropy: Optional[bytes] = None) -> bytes:
    """DPAPI ile şifrele. TaxClip yalnızca Windows'ta güvenli depolama sunar."""
    if not plaintext:
        return b""
    if not _is_windows():
        raise RuntimeError("Güvenli depolama yalnızca Windows DPAPI ile kullanılabilir.")

    import ctypes
    from ctypes import wintypes

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32

    in_buffer = ctypes.create_string_buffer(plaintext)
    in_blob = DATA_BLOB(len(plaintext), ctypes.cast(in_buffer, ctypes.POINTER(ctypes.c_char)))
    out_blob = DATA_BLOB()
    entropy_buffer = ctypes.create_string_buffer(entropy) if entropy else None
    entropy_blob = (
        DATA_BLOB(len(entropy), ctypes.cast(entropy_buffer, ctypes.POINTER(ctypes.c_char)))
        if entropy_buffer is not None else None
    )

    flags = 0x1  # CRYPTPROTECT_UI_FORBIDDEN
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
    """DPAPI ile çöz."""
    if not protected:
        return b""
    if not _is_windows():
        raise RuntimeError("Güvenli depolama yalnızca Windows DPAPI ile kullanılabilir.")

    import ctypes
    from ctypes import wintypes

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32

    in_buffer = ctypes.create_string_buffer(protected)
    in_blob = DATA_BLOB(len(protected), ctypes.cast(in_buffer, ctypes.POINTER(ctypes.c_char)))
    out_blob = DATA_BLOB()
    entropy_buffer = ctypes.create_string_buffer(entropy) if entropy else None
    entropy_blob = (
        DATA_BLOB(len(entropy), ctypes.cast(entropy_buffer, ctypes.POINTER(ctypes.c_char)))
        if entropy_buffer is not None else None
    )

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
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", prefix=f".{path.name}.", suffix=".tmp",
            dir=path.parent, delete=False,
        ) as handle:
            temp_path = handle.name
            handle.write(_DPAPI_MAGIC + protected)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except OSError:
                pass


def read_protected_file(path, entropy: Optional[bytes] = None) -> Optional[str]:
    if not path.exists():
        return None
    raw = path.read_bytes()
    if raw.startswith(_DPAPI_MAGIC):
        return unprotect_text(raw[len(_DPAPI_MAGIC):], entropy)
    # Düz metin/base64 fallback güvenli depolama sayılmaz; fail-closed.
    return None
