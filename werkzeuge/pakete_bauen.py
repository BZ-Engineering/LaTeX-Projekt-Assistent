"""Baut die Download-Pakete in downloads/.

  python werkzeuge/pakete_bauen.py zip   -> LaTeX-Projekt-Assistent-Python.zip (Windows + macOS, benötigt Python)
  python werkzeuge/pakete_bauen.py exe   -> LaTeX-Projekt-Assistent-Windows.exe (benötigt PyInstaller, nur unter Windows)
  python werkzeuge/pakete_bauen.py app   -> LaTeX-Projekt-Assistent-macOS.zip (benötigt PyInstaller, nur unter macOS)
"""

import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
SRC = WURZEL / "src"
AUS = WURZEL / "downloads"
NAME = "LaTeX-Projekt-Assistent"
QUELLEN = ["latex_projekt_assistent.pyw", "assistent_kern.py", "vorlagen.py", "icon.png", "icon.ico"]

START_MAC = """#!/bin/bash
# Startet den LaTeX-Projekt-Assistenten unter macOS (Doppelklick im Finder).
cd "$(dirname "$0")"
if ! command -v python3 >/dev/null 2>&1; then
  osascript -e 'display alert "Python 3 fehlt" message "Bitte Python von python.org installieren (siehe Anleitung)."'
  exit 1
fi
python3 latex_projekt_assistent.pyw
"""

START_WIN = """@echo off
rem Startet den LaTeX-Projekt-Assistenten unter Windows.
cd /d "%~dp0"
where pyw >nul 2>nul && (start "" pyw latex_projekt_assistent.pyw & exit /b)
where pythonw >nul 2>nul && (start "" pythonw latex_projekt_assistent.pyw & exit /b)
echo Python wurde nicht gefunden. Bitte Python von python.org installieren (siehe Anleitung).
pause
"""

LIESMICH = """LaTeX-Projekt-Assistent (Python-Version)
=========================================

Windows:  Doppelklick auf "Start-Windows.bat"
macOS:    Rechtsklick auf "Start-macOS.command" -> Öffnen (beim ersten Mal), danach Doppelklick

Voraussetzung: Python 3.9 oder neuer von https://www.python.org
Ausführliche Anleitung: https://github.com/BZ-Engineering/LaTeX-Projekt-Assistent#readme

Lizenz: PolyForm Noncommercial 1.0.0 (siehe LICENSE.md) - keine kommerzielle Nutzung.
"""


def _zip_eintrag(z: zipfile.ZipFile, name: str, daten: bytes, ausfuehrbar=False):
    info = zipfile.ZipInfo(f"{NAME}/{name}", date_time=(2026, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 3  # Unix, damit die Rechte unter macOS erhalten bleiben
    info.external_attr = ((0o100755 if ausfuehrbar else 0o100644) << 16)
    z.writestr(info, daten)


def baue_zip():
    ziel = AUS / f"{NAME}-Python.zip"
    with zipfile.ZipFile(ziel, "w") as z:
        for q in QUELLEN:
            _zip_eintrag(z, q, (SRC / q).read_bytes())
        _zip_eintrag(z, "Start-macOS.command", START_MAC.encode(), ausfuehrbar=True)
        _zip_eintrag(z, "Start-Windows.bat", START_WIN.replace("\n", "\r\n").encode())
        _zip_eintrag(z, "LIESMICH.txt", LIESMICH.encode("utf-8"))
        _zip_eintrag(z, "LICENSE.md", (WURZEL / "LICENSE.md").read_bytes())
    print("erstellt:", ziel)


def _pyinstaller(zusatz):
    trenn = ";" if sys.platform == "win32" else ":"
    daten = []
    for q in ("icon.png", "icon.ico"):
        daten += ["--add-data", f"{SRC / q}{trenn}."]
    bau = WURZEL / "build"
    subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--windowed",
                    "--name", NAME, "--paths", str(SRC), "--distpath", str(bau / "dist"),
                    "--workpath", str(bau / "work"), "--specpath", str(bau), *daten, *zusatz,
                    str(SRC / "latex_projekt_assistent.pyw")], check=True)
    return bau / "dist"


def baue_exe():
    dist = _pyinstaller(["--onefile", "--icon", str(SRC / "icon.ico")])
    ziel = AUS / f"{NAME}-Windows.exe"
    shutil.copyfile(dist / f"{NAME}.exe", ziel)
    print("erstellt:", ziel)


def baue_app():
    dist = _pyinstaller(["--icon", str(SRC / "icon.icns"), "--osx-bundle-identifier",
                         "com.bz-engineering.latex-projekt-assistent"])
    ziel = AUS / f"{NAME}-macOS.zip"
    subprocess.run(["ditto", "-c", "-k", "--keepParent", str(dist / f"{NAME}.app"), str(ziel)], check=True)
    print("erstellt:", ziel)


if __name__ == "__main__":
    AUS.mkdir(exist_ok=True)
    for ziel in sys.argv[1:] or ["zip"]:
        {"zip": baue_zip, "exe": baue_exe, "app": baue_app}[ziel]()
