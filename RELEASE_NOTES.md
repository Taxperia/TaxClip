# 🚀 TaxClip v4.0 Release Notes

## 📋 Overview
This major release introduces a fully functional Reminders system, sound notifications, 5 new themes, and significant UI improvements.

---

## ✨ New Features

### 🔔 Reminders System (Full Implementation)
- **Complete Reminder Management**: Create, edit, delete, and manage reminders
- **Smart Notifications**: Popup notifications when reminders are triggered
- **Snooze Options**: 5, 10, or 30 minute snooze buttons
- **Repeat Types**: 
  - None (one-time)
  - Daily
  - Weekly
  - Monthly
- **Quick Time Selection**: 1 hour, 3 hours, Tomorrow, 1 week buttons
- **Active/Inactive Toggle**: Enable or disable reminders with a switch
- **Reminders Tab**: New dedicated tab in main window
- New UI components:
  - `reminder_dialog.py` - Create/edit reminder dialog
  - `reminder_notification.py` - Popup notification dialog
  - `reminder_widget.py` - Reminder card widget
  - `reminder_manager.py` - Background reminder checker

### 🔊 Sound System
- **Custom Notification Sounds**: Play sounds when reminders trigger
- **6 Pre-built Sounds**: Various notification tones included
- **Custom Sound Selection**: Choose your own .wav/.mp3 files
- **Sound Test Button**: Preview sounds in settings
- **QtMultimedia Backend**: High-quality audio playback
- New module: `sound_player.py` with `SoundPlayer` class

### 🎨 5 New Themes (Total: 9 Themes)

| Theme | Colors | Style |
|-------|--------|-------|
| 🌆 **Cyberpunk** | Neon pink + Purple + Cyan | Futuristic, glowing |
| 🌅 **Sunset** | Orange + Pink + Yellow | Warm, relaxing |
| 💚 **Matrix** | Green + Black | Terminal/hacker style |
| 🌊 **Ocean** | Blue + Turquoise | Calm, aquatic |
| 🎮 **Retro (XP)** | XP Blue + Gray | Windows XP nostalgia |

### 🖤 Dark Theme Redesign
- **True Black Background**: `#0a0a0a` instead of dark blue
- **Minimal Gray Palette**: Clean monochrome design
- **White Accents**: Instead of blue highlights
- **Premium Look**: Minimalist, modern appearance

---

## 🎨 UI/UX Improvements

### Reminder Cards
- Modern horizontal card design
- Left border accent color
- Title + time in same row
- Edit, Delete buttons with icons
- Toggle switch for active/inactive state

### Settings Dialog Enhancements
- **New Reminders Tab**: Sound selection and settings
- Theme dropdown now shows 9 themes with emoji icons
- Sound selection dropdown with 6 pre-built options
- Sound test button

---

## 🔧 Technical Changes

### New Files

| File | Description |
|------|-------------|
| `clipstack/sound_player.py` | Audio playback with QtMultimedia |
| `clipstack/reminder_manager.py` | Background reminder checker |
| `clipstack/ui/reminder_dialog.py` | Create/edit reminder dialog |
| `clipstack/ui/reminder_notification.py` | Popup notification dialog |
| `clipstack/ui/reminder_widget.py` | Reminder card widget |
| `styles/theme_cyberpunk.qss` | Cyberpunk theme |
| `styles/theme_sunset.qss` | Sunset theme |
| `styles/theme_matrix.qss` | Matrix theme |
| `styles/theme_ocean.qss` | Ocean theme |
| `styles/theme_retro.qss` | Retro XP theme |
| `assets/sounds/*.mp3` | 6 notification sounds |

### Database Updates
- Reminders table now fully utilized
- Added `last_triggered` column for snooze tracking
- Added `mark_reminder_triggered()` function
- Added `update_reminder_time()` function
- Added `set_reminder_active()` function

### Code Architecture
- `ReminderManager` class for background checking (2 second interval)
- `SoundPlayer` wrapper around `QMediaPlayer`
- Signal-based notification system (`reminder_triggered` signal)
- Snooze functionality with time recalculation

---

## ⚙️ New Settings

| Setting | Description | Default |
|---------|-------------|---------|
| `reminder_sound` | Sound file path for reminders | `"default"` |
| `reminder_sound_enabled` | Enable/disable reminder sounds | `true` |
| `reminder_popup_enabled` | Show popup notifications | `true` |

---

## 📦 Included Assets

### Notification Sounds
- `bright-notification-352449.mp3`
- `chime-alert-demo-309545.mp3`
- `new-notification-010-352755.mp3`
- `new-notification-014-363678.mp3`
- `new-notification-016-350210.mp3`
- `new-notification-3-398649.mp3`

---

## 🐛 Bug Fixes & Improvements

- Fixed reminder timing with `skip_past` parameter (no old reminder spam on startup)
- Fixed snooze button time calculation
- Improved theme switching with instant preview
- Better error handling in sound playback
- Reminder cards now properly update on language change

---

## 📝 Migration Notes

When migrating from v3 to v4:
1. New themes are automatically available
2. Existing reminders (if any from v3 preparation) will work
3. Sound files are bundled with the application
4. No manual migration required

---

**Full Changelog**: v3.0...v4.0
