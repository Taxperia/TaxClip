# TaxClip

**A modern clipboard manager for Windows** — capture text, images, files, and more, with smart cards, privacy controls, encryption, and a system-tray workflow.

Built with Python 3.10+ and PySide6. Developed by [Miyotu](https://miyotu.com).

---

## Features

- **Clipboard history** — automatically saves text, HTML, and images to a local SQLite database
- **File & folder clips** — captures Explorer copy paths (CF_HDROP); open, reveal in folder, or copy the path
- **Smart cards** — detects URLs, JSON, hex colors, emails, phone numbers, code, Markdown, Base64, and file paths with context actions
- **Compact panel** — Win+V-style keyboard-first panel positioned above the taskbar
- **Secret mode** — pause capture for 5/15/30 minutes (or until restart), exclude apps, auto-clear sensitive clipboard content
- **Pins, tags & collections** — organize clips; save items as snippets
- **Snippets, todos, drawings & reminders** — productivity tools beyond plain clipboard history
- **OCR & screen tools** — extract text from images; snipping / capture helpers
- **Security** — optional encryption, sensitive-data masking, Windows Hello / TOTP gates, DPAPI-protected secrets, update SHA-256 verification
- **Sync** — optional Google Drive sync
- **Themes & tray** — system tray app, launch at Windows startup, multiple themes

## Requirements

- Windows 10 or later
- Python 3.10+

## Install & run

```bash
pip install -r requirements.txt
python main.py
```

On first launch, “Start with Windows” is enabled (you can turn it off from the tray menu).

## Hotkeys

- TaxClip tries to register **Win+V** first. If Windows reserves that shortcut, it falls back to **Ctrl+Shift+V** and shows a tray notice.
- Change the hotkey in `%AppData%/TaxClip/settings.json` (`"hotkey"`), then restart. Examples: `windows+v`, `ctrl+shift+v`, `alt+space`.
- Running as administrator can help on some systems where global hooks are restricted.

Useful panel shortcuts (when the history UI is open): ↑/↓ select, Enter copy, Ctrl+Enter paste, Delete, Ctrl+P pin, Ctrl+F search, Alt+1–9, Tab, Esc.

## Usage

- TaxClip runs in the background and shows a tray icon.
- Press the global hotkey to open history (full window or compact panel).
- Hover a card for copy, enlarge, favorite, and delete; click a card to copy (window hide behavior is controlled by `"hide_after_copy"` in settings).
- Use the search bar to filter text/HTML content.

## Data locations

| Data | Path |
|------|------|
| Database | `%AppData%/TaxClip/taxclip.db` |
| Settings | `%AppData%/TaxClip/settings.json` |

Startup registration: `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` → `TaxClip`.

## Build (EXE)

```bash
pip install pyinstaller
build_with_runtime_dir.bat
```

- Uses `--noconsole` to hide the console window.
- App icon is generated from `assets/icons/logo.png` → `assets/icons/logo.ico`.

## License

See [LICENSE.md](LICENSE.md). Personal and educational use only; commercial use is not permitted. Attribution to Miyotu is required.

## Links

- Website: [https://miyotu.com](https://miyotu.com)
- Releases: [GitHub Releases](https://github.com/Taxperia/TaxClip/releases)
