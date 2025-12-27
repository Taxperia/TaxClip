from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

import winreg

from .utils import resource_path

APP_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_NAME = "TaxClip"

STARTUP_SHORTCUT_NAME = "TaxClip.lnk"


def _startup_folder() -> Path:
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
    return Path.home() / "AppData" / "Roaming" / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"


def _user_data_dir() -> Path:
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / "TaxClip"
    return Path.home() / "AppData" / "Roaming" / "TaxClip"


def _shortcut_path() -> Path:
    return _startup_folder() / STARTUP_SHORTCUT_NAME


def _ps_escape(value: str) -> str:
    return value.replace("'", "''")


def _ensure_icon_file() -> Optional[Path]:
    icon_target = _user_data_dir() / "TaxClip.ico"
    if icon_target.exists():
        return icon_target

    svg_source = resource_path("assets/icons/clipboard.svg")
    if not svg_source.exists():
        return None

    try:
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QImage, QPainter
        from PySide6.QtSvg import QSvgRenderer
    except Exception:
        return None

    try:
        icon_target.parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        return None

    image = QImage(256, 256, QImage.Format_ARGB32)
    image.fill(Qt.transparent)

    renderer = QSvgRenderer(str(svg_source))
    if not renderer.isValid():
        return None

    painter = QPainter(image)
    renderer.render(painter)
    painter.end()

    if image.save(str(icon_target), "ICO"):
        return icon_target
    return None


def _write_shortcut(target: Path, arguments: str, working_dir: Path, icon_path: Optional[Path]) -> bool:
    shortcut_path = _shortcut_path()
    try:
        shortcut_path.parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        return False

    script_parts = [
        "$shell = New-Object -ComObject WScript.Shell",
        f"$shortcut = $shell.CreateShortcut('{_ps_escape(str(shortcut_path))}')",
        f"$shortcut.TargetPath = '{_ps_escape(str(target))}'",
    ]

    if arguments:
        script_parts.append(f"$shortcut.Arguments = '{_ps_escape(arguments)}'")

    if working_dir:
        script_parts.append(f"$shortcut.WorkingDirectory = '{_ps_escape(str(working_dir))}'")

    if icon_path and icon_path.exists():
        script_parts.append(f"$shortcut.IconLocation = '{_ps_escape(str(icon_path))}'")

    script_parts.append("$shortcut.Save()")

    try:
        subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                "; ".join(script_parts),
            ],
            check=True,
        )
        return True
    except Exception:
        return False


def _remove_shortcut() -> None:
    shortcut = _shortcut_path()
    try:
        if shortcut.exists():
            shortcut.unlink()
    except Exception:
        pass


def _set_run_key(value: Optional[str]) -> None:
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, APP_RUN_KEY, 0, winreg.KEY_ALL_ACCESS) as key:
        if value:
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, value)
        else:
            try:
                winreg.DeleteValue(key, APP_NAME)
            except FileNotFoundError:
                pass


def _get_existing_run_value() -> Optional[str]:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, APP_RUN_KEY, 0, winreg.KEY_READ) as key:
            val, _ = winreg.QueryValueEx(key, APP_NAME)
            return str(val)
    except FileNotFoundError:
        return None


def _resolve_command() -> tuple[Path, str, Path]:
    exe_path = Path(sys.executable).resolve()
    script_path = Path(sys.argv[0]).resolve()

    if getattr(sys, "frozen", False):
        return exe_path, "", exe_path.parent

    pythonw = exe_path.with_name("pythonw.exe")
    target = pythonw if pythonw.exists() else exe_path
    arguments = f'"{script_path}"'
    return target, arguments, script_path.parent

def set_launch_at_startup(enable: bool):
    if not sys.platform.startswith("win"):
        return

    target, arguments, working_dir = _resolve_command()

    if enable:
        icon_path = _ensure_icon_file()
        if _write_shortcut(target, arguments, working_dir, icon_path):
            _set_run_key(None)
            return

        # Fallback to legacy registry approach if shortcut creation fails
        _set_run_key(f'"{target}" {arguments}'.strip())
        return

    _remove_shortcut()
    _set_run_key(None)


def is_launch_at_startup() -> bool:
    if _shortcut_path().exists():
        return True
    return bool(_get_existing_run_value())