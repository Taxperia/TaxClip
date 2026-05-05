from pathlib import Path
import sys


def ensure_pillow():
    try:
        from PIL import Image  # noqa: F401
        return
    except Exception:
        print("Gerekli paket kuruluyor: pillow ...")
        import subprocess

        subprocess.check_call([sys.executable, "-m", "pip", "install", "pillow"])


def main():
    ensure_pillow()
    from PIL import Image

    png_in = Path("assets/icons/logo.png")
    out_dir = Path("assets/icons")
    out_dir.mkdir(parents=True, exist_ok=True)
    png_out = out_dir / "logo_256.png"
    ico_out = out_dir / "logo.ico"

    if not png_in.exists():
        print(f"PNG bulunamadı: {png_in.resolve()}")
        sys.exit(1)

    print("Logo PNG hazırlanıyor...")
    img = Image.open(png_in).convert("RGBA")
    img.thumbnail((256, 256), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    canvas.alpha_composite(img, ((256 - img.width) // 2, (256 - img.height) // 2))
    canvas.save(png_out)

    print("PNG -> ICO dönüştürülüyor...")
    sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    canvas.save(ico_out, sizes=sizes)

    print(f"Tamam: {ico_out.resolve()} üretildi.")


if __name__ == "__main__":
    main()
