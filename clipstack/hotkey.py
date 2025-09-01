import threading
import ctypes
from ctypes import wintypes
from typing import Optional, Callable

# Windows constants
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
WM_HOTKEY = 0x0312

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

VK_MAP = {
    "space": 0x20,
    "insert": 0x2D,
    "delete": 0x2E,
    "home": 0x24,
    "end": 0x23,
    "pgup": 0x21,
    "pgdn": 0x22,
    "up": 0x26,
    "down": 0x28,
    "left": 0x25,
    "right": 0x27,
    "tab": 0x09,
    "escape": 0x1B,
    "esc": 0x1B,
    "enter": 0x0D,
    "return": 0x0D,
    "backspace": 0x08,
}

def _parse_hotkey(hotkey: str) -> Optional[tuple[int, int]]:
    if not hotkey:
        return None
    parts = [p.strip().lower() for p in hotkey.split("+") if p.strip()]
    if not parts:
        return None
    mods = 0
    key_vk = None
    for p in parts:
        if p in ("ctrl", "control"):
            mods |= MOD_CONTROL
        elif p == "shift":
            mods |= MOD_SHIFT
        elif p in ("alt", "menu"):
            mods |= MOD_ALT
        elif p in ("win", "windows", "cmd"):
            mods |= MOD_WIN
        else:
            # key part
            if p in VK_MAP:
                key_vk = VK_MAP[p]
            elif p.startswith("f") and p[1:].isdigit():
                n = int(p[1:])
                if 1 <= n <= 24:
                    key_vk = 0x70 + (n - 1)  # VK_F1=0x70
            elif len(p) == 1:
                ch = p.upper()
                if "A" <= ch <= "Z" or "0" <= ch <= "9":
                    key_vk = ord(ch)
    if key_vk is None:
        return None
    return mods, key_vk

class HotkeyManager:
    def __init__(self):
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._tid = None  # thread id for PostThreadMessage
        self._registered = False
        self._hotkey_id = 1
        self._callback: Optional[Callable[[], None]] = None

    def register(self, hotkey: str, callback: Callable[[], None]) -> bool:
        parsed = _parse_hotkey(hotkey)
        if not parsed:
            return False
        mods, vk = parsed
        self.unregister()
        self._callback = callback
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, args=(mods, vk), daemon=True)
        self._thread.start()
        # Biraz bekleyip kayıt sonucunu kontrol edelim
        for _ in range(50):
            if self._registered or not self._thread.is_alive():
                break
            kernel32.Sleep(10)
        return self._registered

    def unregister(self):
        if self._thread and self._thread.is_alive():
            self._stop.set()
            if self._tid:
                user32.PostThreadMessageW(self._tid, 0x0012, 0, 0)  # WM_QUIT
            self._thread.join(timeout=1.0)
        self._thread = None
        self._registered = False
        self._tid = None

    def _run(self, mods: int, vk: int):
        self._tid = kernel32.GetCurrentThreadId()
        if not user32.RegisterHotKey(None, self._hotkey_id, mods, vk):
            self._registered = False
            return
        self._registered = True

        msg = wintypes.MSG()
        while not self._stop.is_set():
            ret = user32.GetMessageW(ctypes.byref(msg), 0, 0, 0)
            if ret == 0:  # WM_QUIT
                break
            if msg.message == WM_HOTKEY and msg.wParam == self._hotkey_id:
                try:
                    if self._callback:
                        self._callback()
                except Exception:
                    pass
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

        user32.UnregisterHotKey(None, self._hotkey_id)
        self._registered = False
        self._tid = None