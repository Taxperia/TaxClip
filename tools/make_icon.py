import sys
from pathlib import Path

def ensure_packages():
    try:
        import cairosvg  # noqa: F401
        from PIL import Image  # noqa: F401
        return True
    except Exception:
        print("Gerekli paketler kuruluyor: cairosvg, pillow ...")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "cairosvg", "pillow"])
        return True

def main():
    ensure_packages()
    import cairosvg
    from PIL import Image

    svg_in = Path("assets/icons/clipboard.svg")
    out_dir = Path("assets/icons")
    out_dir.mkdir(parents=True, exist_ok=True)
    png_out = out_dir / "clipboard_256.png"
    ico_out = out_dir / "clipboard.ico"

    if not svg_in.exists():
        print(f"SVG bulunamadı: {svg_in.resolve()}")
        sys.exit(1)

    print("SVG -> PNG (256x) dönüştürülüyor...")
    cairosvg.svg2png(url=str(svg_in), write_to=str(png_out), output_width=256, output_height=256)

    print("PNG -> ICO dönüştürülüyor (16, 32, 48, 64, 128, 256)...")
    img = Image.open(png_out).convert("RGBA")
    sizes = [(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)]
    img.save(ico_out, sizes=sizes)

    print(f"Tamam: {ico_out.resolve()} üretildi.")

if __name__ == "__main__":
    main()