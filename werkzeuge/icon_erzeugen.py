"""Erzeugt das App-Icon (src/icon.png, src/icon.ico, src/icon.icns). Benötigt Pillow."""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ZIEL = Path(__file__).resolve().parent.parent / "src"
N = 1024


def schrift(groesse):
    for name in ("seguisb.ttf", "segoeuib.ttf", "Helvetica.ttc", "DejaVuSans-Bold.ttf", "arialbd.ttf"):
        try:
            return ImageFont.truetype(name, groesse)
        except OSError:
            pass
    return ImageFont.load_default()


def icon() -> Image.Image:
    # Hintergrund: Verlauf Indigo -> Violett, abgerundetes Quadrat
    verlauf = Image.new("RGB", (N, N))
    px = verlauf.load()
    a, b = (79, 70, 229), (124, 58, 237)
    for y in range(N):
        for x in range(N):
            t = (x + y) / (2 * N)
            px[x, y] = tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))
    maske = Image.new("L", (N, N), 0)
    ImageDraw.Draw(maske).rounded_rectangle((0, 0, N - 1, N - 1), radius=230, fill=255)
    bild = Image.new("RGBA", (N, N), (0, 0, 0, 0))
    bild.paste(verlauf, (0, 0), maske)

    d = ImageDraw.Draw(bild)
    # Dokument mit Eselsohr
    l, o, r, u, ecke = 250, 170, 774, 854, 150
    schatten = Image.new("RGBA", (N, N), (0, 0, 0, 0))
    ImageDraw.Draw(schatten).rounded_rectangle((l + 18, o + 30, r + 18, u + 30), radius=40, fill=(20, 10, 60, 90))
    bild = Image.alpha_composite(bild, schatten)
    d = ImageDraw.Draw(bild)
    d.polygon([(l + 40, o), (r - ecke, o), (r, o + ecke), (r, u - 40), (r - 40, u), (l + 40, u), (l, u - 40),
               (l, o + 40)], fill=(255, 255, 255))
    d.pieslice((l, o, l + 80, o + 80), 180, 270, fill=(255, 255, 255))
    d.polygon([(r - ecke, o), (r - ecke, o + ecke), (r, o + ecke)], fill=(214, 212, 250))
    # Textzeilen
    for i, breite in enumerate((0.78, 0.62, 0.70)):
        y = 600 + i * 70
        d.rounded_rectangle((l + 70, y, l + 70 + int((r - l - 140) * breite), y + 26), radius=13,
                            fill=(199, 197, 245))
    # "TeX"
    f = schrift(230)
    d.text(((l + r) / 2, 420), "TeX", font=f, fill=(79, 70, 229), anchor="mm")
    return bild


def main():
    ZIEL.mkdir(exist_ok=True)
    b = icon()
    b.resize((256, 256), Image.LANCZOS).save(ZIEL / "icon.png")
    b.save(ZIEL / "icon.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    b.save(ZIEL / "icon.icns")
    print("Icon erzeugt:", ZIEL)


if __name__ == "__main__":
    main()
