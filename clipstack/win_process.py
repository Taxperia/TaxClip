"""
Ön plan uygulama / süreç yardımcıları (Windows).
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional


def get_foreground_process_name() -> Optional[str]:
    """Aktif pencerenin exe adını döndür (örn. chrome.exe)."""
    if sys.platform != "win32":
        return None
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return None

        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if not pid.value:
            return None

        # PROCESS_QUERY_LIMITED_INFORMATION elevated/protected processes için
        # PSAPI + PROCESS_VM_READ yaklaşımından daha güvenilir ve daha az yetki ister.
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
        if not handle:
            return None
        try:
            size = wintypes.DWORD(32768)
            buf = ctypes.create_unicode_buffer(size.value)
            if kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
                return Path(buf.value).name.lower()
        finally:
            kernel32.CloseHandle(handle)
    except Exception:
        return None
    return None
