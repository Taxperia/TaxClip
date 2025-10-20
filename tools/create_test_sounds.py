"""
Basit test sesleri oluştur
Bu script 5 farklı frekans ve uzunlukta test sesi oluşturur.
"""
import math
import wave
import struct

def generate_beep(filename, frequency=440, duration=0.5, volume=0.5):
    """Basit bir beep sesi oluştur"""
    sample_rate = 44100
    num_samples = int(sample_rate * duration)
    
    # Ses verisi oluştur
    samples = []
    for i in range(num_samples):
        # Sinüs dalgası
        t = float(i) / sample_rate
        value = int(volume * 32767.0 * math.sin(2.0 * math.pi * frequency * t))
        
        # Fade in/out ekle (ilk ve son 0.05 saniye)
        fade_samples = int(0.05 * sample_rate)
        if i < fade_samples:
            value = int(value * (i / fade_samples))
        elif i > num_samples - fade_samples:
            value = int(value * ((num_samples - i) / fade_samples))
        
        samples.append(value)
    
    # WAV dosyasına yaz
    with wave.open(filename, 'w') as wav_file:
        wav_file.setnchannels(1)  # Mono
        wav_file.setsampwidth(2)  # 16-bit
        wav_file.setframerate(sample_rate)
        
        for sample in samples:
            wav_file.writeframes(struct.pack('<h', sample))
    
    print(f"✓ Oluşturuldu: {filename} ({frequency}Hz, {duration}s)")

# Test sesleri oluştur
print("🔊 Test sesleri oluşturuluyor...\n")

generate_beep('assets/sounds/notification1.wav', frequency=800, duration=0.3, volume=0.6)
generate_beep('assets/sounds/notification2.wav', frequency=1000, duration=0.4, volume=0.5)
generate_beep('assets/sounds/notification3.wav', frequency=1200, duration=0.35, volume=0.5)

# Chime - çift ton
def generate_chime(filename):
    sample_rate = 44100
    duration = 0.6
    num_samples = int(sample_rate * duration)
    
    samples = []
    for i in range(num_samples):
        t = float(i) / sample_rate
        # İki frekans karıştır
        value1 = 0.3 * 32767.0 * math.sin(2.0 * math.pi * 800 * t)
        value2 = 0.3 * 32767.0 * math.sin(2.0 * math.pi * 1200 * t)
        value = int(value1 + value2)
        
        # Fade out
        fade_samples = int(0.1 * sample_rate)
        if i > num_samples - fade_samples:
            value = int(value * ((num_samples - i) / fade_samples))
        
        samples.append(value)
    
    with wave.open(filename, 'w') as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        for sample in samples:
            wav_file.writeframes(struct.pack('<h', sample))
    
    print(f"✓ Oluşturuldu: {filename} (800Hz+1200Hz chime)")

generate_chime('assets/sounds/chime.wav')

# Ding - kısa yüksek ton
generate_beep('assets/sounds/ding.wav', frequency=1500, duration=0.2, volume=0.4)

print("\n✅ Tüm test sesleri oluşturuldu!")
print("📁 Konum: assets/sounds/")
print("\n💡 Şimdi uygulamayı başlatıp Settings → Reminders → Ses Dosyası menüsünden seslerden birini seçebilirsiniz.")
