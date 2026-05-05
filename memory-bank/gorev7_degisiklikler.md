# Görev 7: Video Kayıt Sistemi Düzeltmeleri

## Tarih: 2025-01-21

## Tespit Edilen Problemler

### 1. Ayarlar Değişince Güncellenmiyor
- **Problem:** Video recorder settings'i constructor'da bir kez alıyor, sonra değişiklikler uygulanmıyordu
- **Sonuç:** FPS, çözünürlük değişiklikleri etkisizdi

### 2. Instant Replay Çalışmıyor
- **Problem:** Sadece TODO yorum vardı, gerçek implementasyon yoktu
- **Sonuç:** Buton işlevsizdi

### 3. Overlay Mikrofon Göstermiyor
- **Problem:** NVIDIA ShadowPlay'deki gibi mikrofon durumu gösterilmiyordu
- **Sonuç:** Kullanıcı mikrofon kaydının aktif olup olmadığını bilemiyordu

### 4. Overlay Instant Replay Desteği Yok
- **Problem:** Overlay sadece normal kayıt modunu destekliyordu

## Yapılan Düzeltmeler

### 1. video_recorder.py - Settings Reload

```python
def _load_settings(self):
    """Ayarları yükle/yeniden yükle"""
    # ... tüm ayarları yükle
    self.record_mic = settings.get("video_record_mic", False)
    self.microphone_device = settings.get("video_microphone", "default")
    print(f"[VIDEO] Ayarlar yüklendi: {self.fps}FPS, {self.resolution}, Mikrofon: {self.record_mic}")

def reload_settings(self):
    """Ayarları yeniden yükle (settings değiştiğinde çağrılır)"""
    if not self.is_recording:
        self._load_settings()
    else:
        print("[VIDEO] Kayıt sırasında ayarlar değiştirilemez")
```

### 2. Instant Replay Implementasyonu

```python
class InstantReplayThread(QThread):
    """Instant Replay buffer thread'i - Sürekli frame kaydeder"""
    
    def run(self):
        """Buffer kayıt döngüsü"""
        # Circular buffer (deque ile otomatik boyut sınırı)
        self.recorder.replay_buffer = deque(maxlen=max_frames)
        
        while self.running and self.recorder.instant_replay_active:
            # Ekran görüntüsü al ve buffer'a ekle
            screen = self.recorder.ImageGrab.grab()
            frame = self.recorder.np.array(screen)
            self.recorder.replay_buffer.append({
                'frame': frame,
                'timestamp': current_time
            })
```

### 3. recording_overlay.py - Mikrofon ve Instant Replay Desteği

```python
def show_recording(self, mic_enabled: bool = False, is_instant_replay: bool = False):
    """Kayıt overlay'ini göster"""
    self.show_mic = mic_enabled
    self.is_instant_replay = is_instant_replay
    
    # Mikrofon ikonunu göster/gizle
    if mic_enabled:
        self.mic_label.show()
        self.setFixedWidth(160)
    else:
        self.mic_label.hide()
        self.setFixedWidth(120)
    
    # Instant replay modu
    if is_instant_replay:
        self.status_label.setText("⏺ REPLAY")
        self.status_label.setStyleSheet("color: #FFB800;")
```

### 4. video_control_widget_v2.py - Instant Replay Entegrasyonu

```python
def _start_instant_replay(self):
    """Instant Replay arka plan kaydını başlat"""
    if hasattr(self.video_recorder, 'start_instant_replay_buffer'):
        self.video_recorder.start_instant_replay_buffer()
    
    # Overlay göster
    mic_enabled = self.settings.get("video_record_mic", False)
    self.recording_overlay.show_recording(mic_enabled=mic_enabled, is_instant_replay=True)

def save_instant_replay(self):
    """Instant Replay'i kaydet (hotkey ile çağrılabilir)"""
    if self.btn_instant.isChecked():
        filepath = self.video_recorder.save_instant_replay()
```

### 5. app.py - Settings Change Notification

```python
def _apply_runtime_settings(self):
    # ... diğer ayarlar
    
    # Video recorder ayarlarını yeniden yükle
    try:
        if hasattr(self.window, 'video_control_widget') and self.window.video_control_widget:
            self.window.video_control_widget.reload_settings()
    except Exception:
        pass
```

## Yeni Özellikler

### Overlay Durumları
1. **Normal Kayıt:** Kırmızı çerçeve, "● REC" yazısı
2. **Instant Replay:** Altın sarısı çerçeve, "⏺ REPLAY" yazısı
3. **Mikrofon Aktif:** Sağ tarafta yeşil 🎤 ikonu

### Instant Replay Çalışma Mantığı
1. Kullanıcı "Instant Replay" butonuna tıklar
2. Arka planda sürekli frame buffer'ı tutulur (deque ile circular buffer)
3. Buffer boyutu = FPS × Buffer Süresi (ayarlardan)
4. Hotkey ile son N saniye kaydedilebilir

## Bağımlılıklar
- **Temel:** PySide6 (screenshot için)
- **Gelişmiş Kayıt:** opencv-python, Pillow
- **Ses Kaydı:** pyaudiowpatch
- **Ses Birleştirme:** FFmpeg (opsiyonel)

## Test Sonuçları
- ✅ Uygulama hatasız başlatıldı
- ✅ Overlay mikrofon parametresi eklendi
- ✅ Instant Replay thread implementasyonu eklendi
- ⚠️ OpenCV eksik - gelişmiş kayıt pasif (kullanıcı kurmalı)

## Etkilenen Dosyalar
1. `clipstack/video_recorder.py` - reload_settings, instant replay thread
2. `clipstack/ui/recording_overlay.py` - mikrofon, instant replay görünümü
3. `clipstack/ui/video_control_widget_v2.py` - instant replay entegrasyonu
4. `clipstack/app.py` - settings change notification
