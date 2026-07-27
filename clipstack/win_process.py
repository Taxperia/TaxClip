"""
Ön plan uygulama / süreç yardımcıları (Windows).
"""
from __future__ import annotations

import sys
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
        psapi = ctypes.windll.psapi

        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return None

        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if not pid.value:
            return None

        PROCESS_QUERY_INFORMATION = 0x0400
        PROCESS_VM_READ = 0x0010
        handle = kernel32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid.value)
        if not handle:
            return None
        try:
            buf = ctypes.create_unicode_buffer(260)
            if psapi.GetModuleBaseNameW(handle, None, buf, 260):
                return buf.value.lower()
        finally:
            kernel32.CloseHandle(handle)
    except Exception:
        return None
    return None
