import winreg
from pathlib import Path
import sys

APP_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_NAME = "TaxClip"

def set_launch_at_startup(enable: bool):
    exe_path = sys.executable
    script_path = Path(sys.argv[0]).resolve()

    # If running frozen (PyInstaller), use exe. Else use pythonw to run script.
    if getattr(sys, 'frozen', False):
        cmd = f"\"{exe_path}\""
    else:
        # Prefer pythonw.exe to avoid console window
        pythonw = Path(exe_path).with_name("pythonw.exe")
        python_cmd = f"\"{pythonw if pythonw.exists() else exe_path}\" \"{script_path}\""
        cmd = python_cmd

    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, APP_RUN_KEY, 0, winreg.KEY_ALL_ACCESS) as key:
        if enable:
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, cmd)
        else:
            try:
                winreg.DeleteValue(key, APP_NAME)
            except FileNotFoundError:
                pass

def is_launch_at_startup() -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, APP_RUN_KEY, 0, winreg.KEY_READ) as key:
            val, _ = winreg.QueryValueEx(key, APP_NAME)
            return bool(val)
    except FileNotFoundError:
        return False