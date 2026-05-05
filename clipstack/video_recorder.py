"""
Video Recording System - FFmpeg GPU Hızlandırmalı
Screenshot, Video Recording, Instant Replay

GPU Desteği:
- NVIDIA NVENC: h264_nvenc (RTX/GTX)
- AMD AMF: h264_amf (RX/Radeon)
- Intel QSV: h264_qsv (Intel GPU)
- CPU Fallback: libx264
"""
import os
import re
import time
import subprocess
import threading
from pathlib import Path
from datetime import datetime
from PySide6.QtCore import QObject, Signal, QThread
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QGuiApplication


class VideoRecorder(QObject):
    """Temel video kayıt yöneticisi"""
    
    recording_started = Signal()
    recording_stopped = Signal(str)  # file_path
    screenshot_taken = Signal(str)  # file_path
    error_occurred = Signal(str)  # error_message
    
    def __init__(self, settings=None):
        super().__init__()
        self.settings = settings
        self.is_recording = False
        self._load_settings()
    
    def _load_settings(self):
        """Ayarları yükle"""
        settings = self.settings or {}
        
        if settings.get("video_save_path"):
            self.output_dir = Path(settings.get("video_save_path"))
        else:
            self.output_dir = Path.home() / "Videos" / "ClipStack"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.fps = settings.get("video_fps", 30)
        
        quality = settings.get("video_quality", "1080p")
        resolution_map = {
            "4K": "3840x2160",
            "1440p": "2560x1440",
            "1080p": "1920x1080",
            "720p": "1280x720",
            "480p": "854x480"
        }
        self.resolution = resolution_map.get(quality, "1920x1080")
        
        self.bitrate = settings.get("video_bitrate", 8000)
        self.format = settings.get("video_format", "mp4")
        self.replay_buffer_seconds = settings.get("instant_replay_buffer_seconds", 30)
        self.record_mic = settings.get("video_record_mic", False)
        self.microphone = settings.get("video_microphone", "default")
        
        print(f"[VIDEO] Ayarlar: {self.fps}FPS, {self.resolution}")
    
    def reload_settings(self):
        """Ayarları yeniden yükle"""
        if not self.is_recording:
            self._load_settings()
    
    def take_screenshot(self) -> str:
        """Ekran görüntüsü al"""
        try:
            screen = QGuiApplication.primaryScreen()
            if not screen:
                raise Exception("Ekran bulunamadı")
            
            pixmap = screen.grabWindow(0)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"screenshot_{timestamp}.png"
            filepath = self.output_dir / filename
            pixmap.save(str(filepath), "PNG")
            
            self.screenshot_taken.emit(str(filepath))
            return str(filepath)
        except Exception as e:
            self.error_occurred.emit(f"Screenshot hatası: {e}")
            return ""
    
    def start_recording(self):
        pass
    
    def stop_recording(self) -> str:
        return ""
    
    def save_instant_replay(self) -> str:
        return ""
    
    def start_instant_replay_buffer(self):
        pass
    
    def stop_instant_replay_buffer(self):
        pass
    
    def get_recording_info(self) -> dict:
        return {
            "is_recording": self.is_recording,
            "output_dir": str(self.output_dir),
            "fps": self.fps,
            "resolution": self.resolution,
            "format": self.format
        }


class AdvancedVideoRecorder(VideoRecorder):
    """
    FFmpeg tabanlı ekran kaydedici - GPU hızlandırmalı
    
    Windows'ta gdigrab kullanır, GPU encoder ile kodlar.
    30/60 FPS sorunsuz çalışır.
    """
    
    def __init__(self, settings=None):
        super().__init__(settings)
        self.ffmpeg_process = None
        self.current_output_file = None
        self.start_time = None
        self._encoder = None
        self._ffmpeg_path = None
        
        # Instant replay
        self.instant_replay_active = False
        self.instant_replay_process = None
        self._audio_devices = None
        
        # FFmpeg ve encoder kontrol
        self._detect_ffmpeg()
        if self._ffmpeg_path:
            self._detect_encoder()

    def reload_settings(self):
        """Ayarları yeniden yükle ve cihaz cache'ini temizle"""
        if not self.is_recording:
            self._audio_devices = None
        super().reload_settings()

    def _run_process_capture_text(self, args, timeout=10):
        result = subprocess.run(
            args,
            capture_output=True,
            timeout=timeout,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
        )
        stdout = (result.stdout or b"").decode("utf-8", errors="ignore")
        stderr = (result.stderr or b"").decode("utf-8", errors="ignore")
        return result.returncode, stdout, stderr
    
    def _detect_ffmpeg(self):
        """FFmpeg kurulumunu kontrol et"""
        # Bundled FFmpeg
        app_dir = Path(__file__).parent.parent
        bundled = app_dir / "ffmpeg" / "ffmpeg.exe"
        
        if bundled.exists():
            self._ffmpeg_path = str(bundled)
            print(f"[FFMPEG] Bundled: {bundled}")
            return
        
        # PATH'te ara
        try:
            result = subprocess.run(
                ["where", "ffmpeg"],
                capture_output=True,
                text=True,
                timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            if result.returncode == 0:
                self._ffmpeg_path = result.stdout.strip().split('\n')[0]
                print(f"[FFMPEG] Sistem: {self._ffmpeg_path}")
                return
        except:
            pass
        
        # Yaygın konumlar
        common_paths = [
            r"C:\ffmpeg\bin\ffmpeg.exe",
            r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
            r"C:\tools\ffmpeg\bin\ffmpeg.exe",
        ]
        for path in common_paths:
            if os.path.exists(path):
                self._ffmpeg_path = path
                print(f"[FFMPEG] Bulundu: {path}")
                return
        
        print("[FFMPEG] FFmpeg bulunamadi! Ekran kaydi calismayacak.")
        print("[FFMPEG] Çözüm: https://www.gyan.dev/ffmpeg/builds/ adresinden indirin")
    
    def _detect_encoder(self):
        """En iyi GPU encoder'ı tespit et"""
        if not self._ffmpeg_path:
            return
        
        encoders = [
            ("h264_nvenc", "NVIDIA NVENC"),
            ("h264_amf", "AMD AMF"),
            ("h264_qsv", "Intel QuickSync"),
            ("libx264", "CPU x264"),
        ]
        
        try:
            _, stdout, stderr = self._run_process_capture_text([self._ffmpeg_path, "-encoders"], timeout=10)
            output = stdout + stderr
            
            for encoder, name in encoders:
                if encoder in output:
                    if encoder != "libx264":
                        if self._test_encoder(encoder):
                            self._encoder = encoder
                            print(f"[FFMPEG] GPU Encoder: {name}")
                            return
                    else:
                        self._encoder = encoder
                        print(f"[FFMPEG] CPU Encoder: {name}")
                        return
        except Exception as e:
            print(f"[FFMPEG] Encoder tespit hatası: {e}")
        
        self._encoder = "libx264"
        print("[FFMPEG] Fallback: CPU libx264")
    
    def _test_encoder(self, encoder: str) -> bool:
        """GPU encoder'ın çalışıp çalışmadığını test et"""
        if not self._ffmpeg_path:
            return False
        
        try:
            # Minimum 256x256 - NVENC bunu gerektiriyor
            result = subprocess.run(
                [
                    self._ffmpeg_path,
                    "-f", "lavfi",
                    "-i", "color=c=black:s=256x256:d=0.1",
                    "-c:v", encoder,
                    "-f", "null",
                    "-"
                ],
                capture_output=True,
                timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            return result.returncode == 0
        except:
            return False
    
    def is_available(self) -> bool:
        """FFmpeg kullanılabilir mi?"""
        return self._ffmpeg_path is not None and self._encoder is not None

    def list_audio_devices(self) -> list[str]:
        """FFmpeg'in gördüğü DirectShow mikrofon aygıtlarını döndür."""
        if self._audio_devices is not None:
            return list(self._audio_devices)

        if not self._ffmpeg_path:
            self._audio_devices = []
            return []

        devices = []
        try:
            _, stdout, stderr = self._run_process_capture_text(
                [self._ffmpeg_path, "-hide_banner", "-list_devices", "true", "-f", "dshow", "-i", "dummy"],
                timeout=10,
            )
            output = stdout + "\n" + stderr
            for line in output.splitlines():
                match = re.search(r'"(.+?)"\s+\(audio\)', line)
                if match:
                    devices.append(match.group(1))
        except Exception as exc:
            print(f"[VIDEO] Mikrofon listesi alınamadı: {exc}")

        self._audio_devices = devices
        return list(devices)

    def _resolve_audio_device(self) -> str | None:
        if not self.record_mic:
            return None

        selected = (self.microphone or "default").strip()
        devices = self.list_audio_devices()

        if selected and selected != "default":
            return selected
        if devices:
            return devices[0]
        return None

    def _append_audio_input(self, cmd: list[str]) -> bool:
        audio_device = self._resolve_audio_device()
        if not audio_device:
            if self.record_mic:
                print("[VIDEO] Mikrofon kaydı açık ama kullanılabilir mikrofon bulunamadı; sessiz kayıt yapılacak.")
            return False

        cmd.extend([
            "-f", "dshow",
            "-thread_queue_size", "512",
            "-i", f"audio={audio_device}",
        ])
        print(f"[VIDEO] Mikrofon girişi: {audio_device}")
        return True
    
    def get_encoder_info(self) -> str:
        """Kullanılan encoder bilgisi"""
        if not self._encoder:
            return "Yok"
        
        names = {
            "h264_nvenc": "NVIDIA NVENC (GPU)",
            "h264_amf": "AMD AMF (GPU)",
            "h264_qsv": "Intel QuickSync (GPU)",
            "libx264": "CPU x264",
        }
        return names.get(self._encoder, self._encoder)
    
    def start_recording(self, region=None):
        """
        Ekran kaydını başlat
        
        Args:
            region: (x, y, width, height) tuple - None ise tam ekran
        """
        if self.is_recording:
            print("[FFMPEG] Zaten kayıt yapılıyor!")
            return False
        
        if not self.is_available():
            self.error_occurred.emit("FFmpeg bulunamadı! Lütfen FFmpeg'i yükleyin.\nhttps://www.gyan.dev/ffmpeg/builds/")
            return False
        
        try:
            # Dosya adı
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"recording_{timestamp}.{self.format}"
            self.current_output_file = str(self.output_dir / filename)
            
            # FFmpeg komutu
            cmd = self._build_command(region)
            print(f"[FFMPEG] Başlatılıyor: {self.fps} FPS, {self._encoder}")
            print(f"[FFMPEG] Komut: {' '.join(cmd)}")
            
            # FFmpeg başlat
            self.ffmpeg_process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            self.is_recording = True
            self.start_time = time.time()
            self.recording_started.emit()
            
            print(f"[FFMPEG] ✓ Kayıt başladı: {self.current_output_file}")
            return True
            
        except Exception as e:
            self.error_occurred.emit(f"Kayıt başlatılamadı: {e}")
            self.is_recording = False
            return False
    
    def _build_command(self, region=None) -> list:
        """FFmpeg komutunu oluştur"""
        cmd = [self._ffmpeg_path, "-y"]
        
        # Video input - Windows gdigrab
        cmd.extend([
            "-f", "gdigrab",
            "-framerate", str(self.fps),
            "-draw_mouse", "1",
        ])
        
        # Bölge veya tam ekran
        if region:
            x, y, w, h = region
            cmd.extend([
                "-offset_x", str(x),
                "-offset_y", str(y),
                "-video_size", f"{w}x{h}",
            ])
        
        cmd.extend(["-i", "desktop"])
        audio_enabled = self._append_audio_input(cmd)
        
        # Video codec
        cmd.extend(["-c:v", self._encoder])
        
        # Encoder ayarları
        if self._encoder == "h264_nvenc":
            cmd.extend([
                "-preset", "p4",       # Balanced
                "-tune", "ll",         # Low latency
                "-rc", "vbr",
                "-cq", "23",
                "-b:v", f"{self.bitrate}k",
                "-maxrate", f"{self.bitrate * 2}k",
                "-bufsize", f"{self.bitrate * 2}k",
            ])
        elif self._encoder == "h264_amf":
            cmd.extend([
                "-usage", "lowlatency",
                "-quality", "balanced",
                "-b:v", f"{self.bitrate}k",
            ])
        elif self._encoder == "h264_qsv":
            cmd.extend([
                "-preset", "faster",
                "-b:v", f"{self.bitrate}k",
            ])
        else:  # libx264
            cmd.extend([
                "-preset", "ultrafast",
                "-crf", "23",
                "-tune", "zerolatency",
            ])
        
        # Ortak ayarlar
        cmd.extend([
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
        ])

        if audio_enabled:
            cmd.extend([
                "-c:a", "aac",
                "-b:a", "128k",
                "-ar", "48000",
                "-ac", "2",
            ])
        else:
            cmd.extend(["-an"])
        
        # Output
        cmd.append(self.current_output_file)
        
        return cmd
    
    def stop_recording(self) -> str:
        """Kaydı durdur"""
        if not self.is_recording or not self.ffmpeg_process:
            return ""
        
        output_file = self.current_output_file
        
        try:
            # FFmpeg'e quit komutu
            try:
                self.ffmpeg_process.stdin.write(b'q')
                self.ffmpeg_process.stdin.flush()
            except:
                pass
            
            # Bekle (max 5 saniye)
            try:
                self.ffmpeg_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                print("[FFMPEG] Timeout, zorla kapatılıyor...")
                self.ffmpeg_process.terminate()
                try:
                    self.ffmpeg_process.wait(timeout=2)
                except:
                    self.ffmpeg_process.kill()
            
            # Süre hesapla
            duration = time.time() - self.start_time if self.start_time else 0
            print(f"[FFMPEG] ✓ Kayıt durduruldu: {duration:.1f}s")
            
        except Exception as e:
            print(f"[FFMPEG] Durdurma hatası: {e}")
        
        finally:
            self.is_recording = False
            self.ffmpeg_process = None
            self.start_time = None
        
        if output_file and os.path.exists(output_file):
            self.recording_stopped.emit(output_file)
            return output_file
        
        return ""
    
    def get_recording_duration(self) -> float:
        """Mevcut kayıt süresi (saniye)"""
        if self.is_recording and self.start_time:
            return time.time() - self.start_time
        return 0.0
    
    def get_recording_info(self) -> dict:
        """Kayıt bilgileri"""
        return {
            "is_recording": self.is_recording,
            "output_dir": str(self.output_dir),
            "fps": self.fps,
            "encoder": self.get_encoder_info(),
            "format": self.format,
            "current_file": self.current_output_file,
            "duration": self.get_recording_duration(),
            "available": self.is_available()
        }
    
    # === INSTANT REPLAY ===
    
    def start_instant_replay_buffer(self):
        """Arka planda sürekli kayıt (son N saniye buffer)"""
        if self.instant_replay_active or not self.is_available():
            return False
        
        try:
            # Segment dosyası
            segment_pattern = str(self.output_dir / "replay_segment_%03d.mp4")
            
            cmd = [
                self._ffmpeg_path, "-y",
                "-f", "gdigrab",
                "-framerate", str(min(self.fps, 30)),
                "-draw_mouse", "1",
                "-i", "desktop",
            ]
            audio_enabled = self._append_audio_input(cmd)
            cmd.extend(["-c:v", self._encoder])
            
            if self._encoder == "h264_nvenc":
                cmd.extend(["-preset", "p1", "-cq", "28"])
            elif self._encoder == "libx264":
                cmd.extend(["-preset", "ultrafast", "-crf", "28"])
            
            cmd.extend([
                "-pix_fmt", "yuv420p",
            ])

            if audio_enabled:
                cmd.extend([
                    "-c:a", "aac",
                    "-b:a", "128k",
                    "-ar", "48000",
                    "-ac", "2",
                ])
            else:
                cmd.extend(["-an"])

            cmd.extend([
                "-f", "segment",
                "-segment_time", "10",
                "-segment_wrap", str(max(3, self.replay_buffer_seconds // 10)),
                "-reset_timestamps", "1",
                segment_pattern
            ])
            
            self.instant_replay_process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            self.instant_replay_active = True
            print(f"[INSTANT REPLAY] ✓ Buffer başladı ({self.replay_buffer_seconds}s)")
            return True
            
        except Exception as e:
            print(f"[INSTANT REPLAY] Başlatma hatası: {e}")
            return False
    
    def stop_instant_replay_buffer(self):
        """Instant Replay buffer'ı durdur"""
        if not self.instant_replay_active or not self.instant_replay_process:
            return
        
        try:
            self.instant_replay_process.stdin.write(b'q')
            self.instant_replay_process.stdin.flush()
        except:
            pass
        
        try:
            self.instant_replay_process.wait(timeout=3)
        except:
            self.instant_replay_process.kill()
        
        self.instant_replay_active = False
        self.instant_replay_process = None
        print("[INSTANT REPLAY] Buffer durduruldu")
    
    def save_instant_replay(self) -> str:
        """Son N saniyeyi kaydet"""
        if not self.instant_replay_active:
            self.error_occurred.emit("Instant Replay aktif değil!")
            return ""
        
        try:
            # Segment dosyalarını bul
            segment_files = sorted(self.output_dir.glob("replay_segment_*.mp4"))
            if not segment_files:
                self.error_occurred.emit("Replay segmentleri bulunamadı!")
                return ""
            
            segments_needed = max(1, self.replay_buffer_seconds // 10)
            recent_segments = segment_files[-segments_needed:]
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = str(self.output_dir / f"instant_replay_{timestamp}.mp4")
            
            # Concat file
            concat_file = str(self.output_dir / "concat_list.txt")
            with open(concat_file, 'w') as f:
                for seg in recent_segments:
                    f.write(f"file '{seg}'\n")
            
            # FFmpeg concat
            subprocess.run([
                self._ffmpeg_path, "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", concat_file,
                "-c", "copy",
                output_file
            ], creationflags=subprocess.CREATE_NO_WINDOW, timeout=30)
            
            os.remove(concat_file)
            
            print(f"[INSTANT REPLAY] ✓ Kaydedildi: {output_file}")
            self.recording_stopped.emit(output_file)
            return output_file
            
        except Exception as e:
            self.error_occurred.emit(f"Instant Replay hatası: {e}")
            return ""


class RecordingThread(QThread):
    """Kayıt durumunu izleyen arka plan thread'i"""
    
    duration_updated = Signal(float)
    recording_error = Signal(str)
    
    def __init__(self, recorder: AdvancedVideoRecorder):
        super().__init__()
        self.recorder = recorder
        self._running = False
    
    def run(self):
        """Kayıt süresini izle"""
        self._running = True
        
        while self._running and self.recorder.is_recording:
            duration = self.recorder.get_recording_duration()
            self.duration_updated.emit(duration)
            
            if self.recorder.ffmpeg_process:
                poll = self.recorder.ffmpeg_process.poll()
                if poll is not None and poll != 0:
                    self.recording_error.emit("FFmpeg beklenmedik şekilde kapandı!")
                    break
            
            self.msleep(500)
    
    def stop(self):
        """Thread'i durdur"""
        self._running = False
        self.wait(2000)


def get_video_recorder(settings=None, use_advanced: bool = True):
    """Video recorder factory"""
    if use_advanced:
        return AdvancedVideoRecorder(settings)
    return VideoRecorder(settings)


# Test
if __name__ == "__main__":
    recorder = AdvancedVideoRecorder()
    
    print("\n=== FFmpeg Video Recorder Test ===")
    print(f"FFmpeg: {'✓' if recorder._ffmpeg_path else '✗'}")
    print(f"Encoder: {recorder.get_encoder_info()}")
    print(f"Kullanılabilir: {'✓' if recorder.is_available() else '✗'}")
    
    if recorder.is_available():
        print("\n5 saniyelik test kaydı...")
        if recorder.start_recording():
            time.sleep(5)
            output = recorder.stop_recording()
            print(f"✓ Kayıt: {output}")
