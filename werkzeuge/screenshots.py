"""Nimmt die Screenshots für die Anleitung auf (Windows, benötigt Pillow).

Aufruf: python werkzeuge/screenshots.py <Zielordner-für-Testprojekt>
Der Zielordner sollte einen neutralen Pfad haben (z. B. ein per `subst` verbundenes Laufwerk).
"""

import ctypes
import sys
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageGrab

WURZEL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL / "src"))
ctypes.windll.shcore.SetProcessDpiAwareness(1)

import importlib.util  # noqa: E402

spec = importlib.util.spec_from_file_location("app", WURZEL / "src" / "latex_projekt_assistent.pyw")
A = importlib.util.module_from_spec(spec)
spec.loader.exec_module(A)

AUSGABE = WURZEL / "docs" / "bilder"
ZIEL = Path(sys.argv[1])


def demo_logo(pfad: Path):
    b = Image.new("RGBA", (520, 160), (0, 0, 0, 0))
    d = ImageDraw.Draw(b)
    d.rounded_rectangle((0, 20, 120, 140), radius=24, fill=(14, 116, 144))
    d.text((60, 80), "M", font=ImageFont.truetype("seguisb.ttf", 80), fill="white", anchor="mm")
    d.text((140, 55), "Muster", font=ImageFont.truetype("seguisb.ttf", 56), fill=(14, 116, 144), anchor="lm")
    d.text((140, 112), "Hochschule", font=ImageFont.truetype("segoeui.ttf", 44), fill=(60, 70, 90), anchor="lm")
    b.save(pfad)


def foto(app, name):
    app.update()
    time.sleep(0.6)
    app.update()
    x, y = app.winfo_rootx(), app.winfo_rooty()
    w, h = app.winfo_width(), app.winfo_height()
    ImageGrab.grab(bbox=(x, y, x + w, y + h), all_screens=True).save(AUSGABE / f"{name}.png", optimize=True)
    print("  ", name)


def warten(app, bedingung, max_s=60):
    ende = time.time() + max_s
    while time.time() < ende and not bedingung():
        app.update()
        time.sleep(0.1)


def main():
    AUSGABE.mkdir(parents=True, exist_ok=True)
    logo = ZIEL / "musterhochschule-logo.png"
    demo_logo(logo)

    app = A.App(demo=True)
    app.attributes("-topmost", True)
    app.v["zielordner"].set(str(ZIEL))
    app.v["logo"].set(str(logo))
    app.v["vscode"].set(False)
    app.v["github"].set(True)
    app.update()

    namen = ["1-projekt", "2-personen", "3-titelseite", "4-gliederung", "5-zotero", "6-github"]
    for i, name in enumerate(namen):
        app.zeige(i)
        if i == 4:
            time.sleep(1.5)
        foto(app, name)

    # Fehlermeldung zeigen (Beispiel Validierung)
    app.zeige(0)
    alt = app.v["titel"].get()
    app.v["titel"].set("")
    app.weiter()
    foto(app, "0-pruefung")
    app.v["titel"].set(alt)
    app.repo_auto = True
    app._repo_vorschlagen()

    # Zusammenfassung und echtes Erstellen (ohne GitHub, ohne VS Code)
    app.v["github"].set(False)
    app.zeige(6)
    foto(app, "7-zusammenfassung")
    app._start()
    warten(app, lambda: not app.laeuft and app.aktionen.winfo_children())
    foto(app, "8-fertig")
    app.destroy()


if __name__ == "__main__":
    main()
