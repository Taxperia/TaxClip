from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, Signal, QUrl

_HAS_MULTIMEDIA = True
try:  # pragma: no cover - import guard
    from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
except ImportError:  # pragma: no cover - gracefully handle missing module
    QAudioOutput = None  # type: ignore
    QMediaPlayer = None  # type: ignore
    _HAS_MULTIMEDIA = False


class SoundPlayer(QObject):
    """Thin wrapper around QMediaPlayer with a simple error signal."""

    playbackFailed = Signal(str)

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        if QMediaPlayer is None or QAudioOutput is None:
            raise RuntimeError("QtMultimedia backend is not available")

        self._audio = QAudioOutput(self)
        self._audio.setVolume(1.0)

        self._player = QMediaPlayer(self)
        self._player.setAudioOutput(self._audio)
        self._player.errorOccurred.connect(self._on_error)

    def play(self, file_path: str | Path, volume: float = 1.0) -> None:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Sound file not found: {path}")

        volume = max(0.0, min(volume, 1.0))
        self._audio.setVolume(volume)

        self._player.stop()
        self._player.setSource(QUrl.fromLocalFile(str(path)))
        self._player.play()

    def stop(self) -> None:
        self._player.stop()

    def set_volume(self, volume: float) -> None:
        volume = max(0.0, min(volume, 1.0))
        self._audio.setVolume(volume)

    def _on_error(self, error: QMediaPlayer.Error, error_string: str) -> None:  # type: ignore[attr-defined]
        if error == QMediaPlayer.Error.NoError:  # type: ignore[attr-defined]
            return
        message = error_string or "Unknown playback error"
        self.playbackFailed.emit(message)


def is_sound_backend_available() -> bool:
    """Return True when QtMultimedia is importable."""
    return _HAS_MULTIMEDIA


__all__ = ["SoundPlayer", "is_sound_backend_available"]
