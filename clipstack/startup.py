from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

import winreg

from .utils import resource_path

APP_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_NAME = "TaxClip"
APP_EXECUTABLE_NAME = f"{APP_NAME}.exe"
APP_ICON_NAME = f"{APP_NAME}.ico"

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


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _ensure_icon_file() -> Optional[Path]:
    icon_target = _user_data_dir() / APP_ICON_NAME

    for rel in ("assets/icons/logo.ico", "assets/icons/clipboard.ico"):
        ico_source = resource_path(rel)
        if not ico_source.exists():
            continue
        try:
            icon_target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ico_source, icon_target)
            return icon_target
        except Exception:
            pass

    png_source = resource_path("assets/icons/logo.png")
    if not png_source.exists():
        return None

    try:
        from PySide6.QtGui import QImage
    except Exception:
        return None

    try:
        icon_target.parent.mkdir(parents=True, exist_ok=True)
        image = QImage(str(png_source))
    except Exception:
        return None

    if not image.isNull() and image.save(str(icon_target), "ICO"):
        return icon_target
    return None


def _resolve_script_path() -> Path:
    raw_path = (sys.argv[0] or "").strip()
    if raw_path and raw_path not in {"-c", "-m"}:
        try:
            candidate = Path(raw_path).resolve()
            if candidate.exists():
                return candidate
        except Exception:
            pass
    return _project_root() / "main.py"


def _resolve_packaged_executable(script_path: Path) -> Optional[Path]:
    candidates: list[Path] = []
    for root in (script_path.parent, _project_root()):
        candidates.append(root / "dist" / APP_NAME / APP_EXECUTABLE_NAME)
        candidates.append(root / APP_EXECUTABLE_NAME)

    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate).lower()
        if key in seen:
            continue
        seen.add(key)
        try:
            resolved = candidate.resolve()
        except Exception:
            resolved = candidate
        if resolved.exists():
            return resolved
    return None


def _resolve_shortcut_icon(target: Path) -> Optional[Path]:
    if target.exists() and target.name.lower() == APP_EXECUTABLE_NAME.lower():
        return target
    return _ensure_icon_file()


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
        f"$shortcut.Arguments = '{_ps_escape(arguments)}'",
    ]

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

    if getattr(sys, "frozen", False):
        return exe_path, "", exe_path.parent

    script_path = _resolve_script_path()
    packaged_exe = _resolve_packaged_executable(script_path)
    if packaged_exe is not None:
        return packaged_exe, "", packaged_exe.parent

    pythonw = exe_path.with_name("pythonw.exe")
    target = pythonw if pythonw.exists() else exe_path
    arguments = f'"{script_path}"'
    return target, arguments, script_path.parent

def set_launch_at_startup(enable: bool):
    if not sys.platform.startswith("win"):
        return

    target, arguments, working_dir = _resolve_command()

    if enable:
        icon_path = _resolve_shortcut_icon(target)
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
