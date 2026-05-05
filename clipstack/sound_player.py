from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, Signal, QUrl, QCoreApplication, qInstallMessageHandler

_HAS_MULTIMEDIA = True
try:  # pragma: no cover - import guard
    from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
except ImportError:  # pragma: no cover - gracefully handle missing module
    QAudioOutput = None  # type: ignore
    QMediaPlayer = None  # type: ignore
    _HAS_MULTIMEDIA = False

_RUNTIME_BACKEND_AVAILABLE: Optional[bool] = None
_LAST_BACKEND_ERROR = ""


@contextmanager
def _suppress_qmediaplayer_warning():
    previous_handler = None

    def handler(msg_type, context, message):  # pragma: no cover - Qt callback
        text = str(message or "")
        if "QMediaPlayer" in text and "Not available" in text:
            return
        if previous_handler:
            previous_handler(msg_type, context, message)

    try:
        previous_handler = qInstallMessageHandler(handler)
        yield
    finally:
        qInstallMessageHandler(previous_handler)


def _probe_runtime_backend() -> bool:
    global _RUNTIME_BACKEND_AVAILABLE, _LAST_BACKEND_ERROR

    if not _HAS_MULTIMEDIA or QMediaPlayer is None or QAudioOutput is None:
        _RUNTIME_BACKEND_AVAILABLE = False
        _LAST_BACKEND_ERROR = "QtMultimedia module could not be imported"
        return False

    if _RUNTIME_BACKEND_AVAILABLE is not None:
        return _RUNTIME_BACKEND_AVAILABLE

    if QCoreApplication.instance() is None:
        return True

    probe_audio = None
    probe_player = None
    try:
        with _suppress_qmediaplayer_warning():
            probe_audio = QAudioOutput()
            probe_player = QMediaPlayer()
            probe_player.setAudioOutput(probe_audio)

        available = bool(probe_player.isAvailable())
        if available:
            _LAST_BACKEND_ERROR = ""
        else:
            _LAST_BACKEND_ERROR = probe_player.errorString() or "QtMultimedia backend is not available"
        _RUNTIME_BACKEND_AVAILABLE = available
        return available
    except Exception as exc:
        _LAST_BACKEND_ERROR = str(exc) or "QtMultimedia backend is not available"
        _RUNTIME_BACKEND_AVAILABLE = False
        return False
    finally:
        for obj in (probe_player, probe_audio):
            if obj is None:
                continue
            try:
                obj.deleteLater()
            except Exception:
                pass


class SoundPlayer(QObject):
    """Thin wrapper around QMediaPlayer with a simple error signal."""

    playbackFailed = Signal(str)

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        if QMediaPlayer is None or QAudioOutput is None:
            raise RuntimeError("QtMultimedia backend is not available")
        if not _probe_runtime_backend():
            raise RuntimeError(get_sound_backend_error())

        self._audio = QAudioOutput(self)
        self._audio.setVolume(1.0)

        with _suppress_qmediaplayer_warning():
            self._player = QMediaPlayer(self)
        self._player.setAudioOutput(self._audio)
        if not self._player.isAvailable():
            raise RuntimeError(self._player.errorString() or get_sound_backend_error())
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
    """Return True when QtMultimedia is importable and the runtime backend is usable."""
    return _probe_runtime_backend()


def get_sound_backend_error() -> str:
    _probe_runtime_backend()
    return _LAST_BACKEND_ERROR or "QtMultimedia backend is not available"


__all__ = ["SoundPlayer", "is_sound_backend_available", "get_sound_backend_error"]
