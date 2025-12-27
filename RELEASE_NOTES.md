# 🚀 TaxClip v3.0 Release Notes

## 📋 Overview
ClipStack has been rebranded to TaxClip. This release includes significant improvements in security, note-taking, and user experience.

---

## ✨ New Features

### 🔐 Security & Encryption
- **AES-256 Encryption**: Clipboard contents and notes can now be encrypted
  - User-defined password protection for your data
  - Password prompt on application startup when enabled
  - New `utils_crypto.py` module for secure encryption infrastructure

### 📝 Notes System (New Feature)
- **Notes Tab**: New "Notes" tab in the main window
- **Add Notes**: Quick note adding dialog
- **Edit Notes**: Edit existing notes
- **Delete Notes**: Single and bulk note deletion
- **Copy Notes**: Copy notes to clipboard
- New UI components:
  - `note_widget.py` - Note cards
  - `about_dialog.py` - About dialog
  - `item_preview_dialog.py` - Item preview dialog

### ⌨️ Multiple Hotkeys Support
- **Main Hotkey**: Open history window (existing)
- **Paste Last**: Paste last copied item with a single key (`hotkey_paste_last`)
- **Quick Note**: Save notes instantly with global hotkey (`hotkey_quick_note`)

### 🗑️ Auto-Delete
- Automatically delete items older than specified days
- Duration options: 7, 10, 14, 30, 60, 90, 120, 180, 365 days
- Option to keep favorites from deletion (`auto_delete_keep_fav`)

### 👁️ Item Preview Dialog
- Full-screen preview window
- Readable view for text/HTML content
- Scrollable preview for images
- Copy, Save, and Share buttons

### 🔔 Reminders System (Preparation)
- Database infrastructure prepared for reminders system
- CRUD functions: `add_reminder()`, `list_reminders()`, `get_reminder()`

---

## 🎨 UI/UX Improvements

### Pagination & Lazy Loading
- Infinite scroll with pagination (`PAGE_SIZE = 30`)
- Faster initial loading (`PRIME_COUNT = 9`)
- Separate loading state tracking for each tab
- `LoaderWidget` for visual loading indicator

### Settings Dialog Enhancements
- **New Security Tab**: Encryption and auto-delete settings
- Improved hotkey capture (`normalize_combo()` function)
- Larger window size (760x640)

### Tab Visibility Logic
- Tab-based button visibility
- "Add Note" and "Clear All Notes" buttons in Notes tab

---

## 🔧 Technical Changes

### Database Schema Updates
- New `notes` table added
- New `reminders` table added (preparation)
- Structural changes for encrypted data support

### Code Architecture
- Added `settings` parameter to `Storage` class
- Encryption/decryption integrated into all CRUD operations
- New signals in `HotkeyBridge` class: `paste_last`, `quick_note`
- Multiple `HotkeyManager` instance support

---

## 📦 New Files

| File | Description |
|------|-------------|
| `clipstack/utils_crypto.py` | AES-256 encryption module |
| `clipstack/ui/note_widget.py` | Note card widget |
| `clipstack/ui/about_dialog.py` | About dialog |
| `clipstack/ui/item_preview_dialog.py` | Item preview dialog |
| `TaxClip.spec` | PyInstaller build file |

---

## ⚙️ New Settings

| Setting | Description | Default |
|---------|-------------|---------|
| `encrypt_data` | Enable data encryption | `false` |
| `encryption_key` | Encryption key (runtime) | `null` |
| `hotkey_paste_last` | Paste last item hotkey | `""` |
| `hotkey_quick_note` | Quick note hotkey | `""` |
| `auto_delete_enabled` | Auto-delete | `false` |
| `auto_delete_days` | Delete after (days) | `7` |
| `auto_delete_keep_fav` | Keep favorites | `true` |

---

## 🐛 Bug Fixes & Improvements

- Improved hotkey normalization
- More reliable data read/write operations
- Better error handling and user notifications

---

## 📝 Migration Notes

When migrating from v1.3 to v1.4:
1. Data directory has changed - you may need to manually migrate your data
2. When encryption is enabled, existing data is not encrypted (only new data)
3. Settings file will contain new keys

---

**Full Changelog**: v1.3...v1.4
