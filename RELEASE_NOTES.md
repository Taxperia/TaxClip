# TaxClip v1.2.3

Stability, responsiveness, and settings experience update.

## Highlights

- **Stable history layout:** fixed the ninth card and ninth skeleton briefly appearing over the first card when the window opens from the system tray. All nine placeholders now receive their final geometry before the first paint.
- **Responsive database search:** fuzzy search now runs on a worker thread with its own SQLite connection, searches unloaded history items, and only loads full image payloads for the displayed results.
- **Reliable Settings window:** prevented repeated miniature child windows, guarded against duplicate Settings instances, and fixed `QThread: Destroyed while thread is still running` shutdown crashes.
- **Redesigned Settings UI:** added a modern navigation shell, consistent setting rows and controls, theme-aware styling, and a completely redesigned About page.
- **Preview close fix:** the native close button in the preview window now closes the preview correctly.

## User interface

- Removed the sidebar Quick Actions section.
- Fixed parent/visibility handling for history cards, loaders, and skeleton placeholders.
- Removed the skeleton opacity effect that could leave stale paint artifacts on Windows.
- Reworked the About page with product highlights, update status, and external links.
- Removed the AI-development badge and authors section from About.
- Improved toggle styling and visual consistency across Settings pages.

## Performance and reliability

- Added debounced, non-blocking fuzzy search with stale-result protection.
- Reduced search memory usage by excluding image BLOBs from the initial candidate scan.
- Added deterministic cleanup for skeleton widgets and stale FlowLayout entries.
- Deferred FFmpeg and Google Drive checks until their Settings pages are opened.
- Kept Settings background workers alive until they finish, preventing shutdown crashes.
- Prepared and laid out history cards while the main window is hidden to eliminate first-frame card jumps.

## Repository maintenance

- Local agent instructions, progress notes, planning files, memory-bank content, build artifacts, and Python bytecode are excluded from Git.
- Version metadata updated to **1.2.3**.

## Install

```bash
pip install -r requirements.txt
python main.py
```

**Full Changelog:** https://github.com/Taxperia/TaxClip/compare/v1.2.2...v1.2.3
