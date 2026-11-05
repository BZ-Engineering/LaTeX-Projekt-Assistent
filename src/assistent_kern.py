"""Logik des LaTeX-Projekt-Assistenten (ohne Oberfläche, damit testbar)."""

from __future__ import annotations

import base64
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable

import vorlagen as V

ZOTERO = "http://127.0.0.1:23119"
GITHUB_API = "https://api.github.com"
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

if sys.platform == "darwin":
    # Per Doppelklick gestartete Mac-Apps kennen den PATH der Shell nicht.
    _extra = ["/Library/TeX/texbin", "/opt/homebrew/bin", "/usr/local/bin", "/usr/bin"]
    os.environ["PATH"] = os.pathsep.join([*_extra, os.environ.get("PATH", "")])

Log = Callable[[str], None]

MONATE = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli",
          "August", "September", "Oktober", "November", "Dezember"]


@dataclass
class Autor:
    name: str
    matrikel: str = ""


@dataclass
class Projekt:
    repo: str                       # Ordner- und Repository-Name
    zielordner: Path                # Elternordner, z. B. Dokumente
    titel: str
    art: str = "Projektbericht"
    autoren: list[Autor] = field(default_factory=list)
    hochschule: str = ""
    studiengang: str = ""
    modul: str = ""
    kurs: str = ""
    betreuer: str = ""
    betreuer_bezeichnung: str = "Dozent"
    abgabe: str = ""
    kapitel: list[str] = field(default_factory=list)
    logo: str = ""                  # Pfad zu einer Logodatei (optional)
    ki_werkzeug: str = "Claude"
    sammlung: str = ""              # Zotero-Sammlung, Standard = repo
    git_name: str = ""
    git_email: str = ""
    github: bool = False            # Repository auf GitHub anlegen?
    github_owner: str = ""          # Benutzer oder Organisation, leer = eigenes Konto
    github_privat: bool = True

    @property
    def ordner(self) -> Path:
        return self.zielordner / self.repo

    @property
    def sammlung_name(self) -> str:
        return self.sammlung.strip() or self.repo


# --------------------------------------------------------------------------
# Hilfsfunktionen für Texte
# --------------------------------------------------------------------------

def tex(s: str) -> str:
    """Maskiert LaTeX-Sonderzeichen in Benutzereingaben."""
    ersatz = {"\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$",
              "#": r"\#", "_": r"\_", "{": r"\{", "}": r"\}",
              "~": r"\textasciitilde{}", "^": r"\textasciicircum{}"}
    return "".join(ersatz.get(c, c) for c in s.strip())


def slug(s: str) -> str:
    s = s.lower()
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        s = s.replace(a, b)
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "kapitel"


def repo_name_gueltig(name: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z0-9._-]+", name)) and name not in (".", "..")


def namen_aufzaehlen(namen: list[str]) -> str:
    if len(namen) <= 1:
        return "".join(namen)
    return ", ".join(namen[:-1]) + " und " + namen[-1]


def kurzname(name: str) -> str:
    """'Erika Mustermann' -> 'E.~Mustermann'"""
    teile = name.split()
    if len(teile) < 2:
        return name
    return " ".join(t[0] + "." for t in teile[:-1]).replace(" ", "~") + "~" + teile[-1]


def datum_lang(eingabe: str) -> str:
    """'21.11.2026' -> '21.~November~2026'; andere Eingaben bleiben, wie sie sind."""
    eingabe = eingabe.strip()
    for fmt in ("%d.%m.%Y", "%Y-%m-%d", "%d.%m.%y"):
        try:
            d = datetime.strptime(eingabe, fmt)
            return f"{d.day}.~{MONATE[d.month - 1]}~{d.year}"
        except ValueError:
            pass
    return tex(eingabe)


def autoren_parsen(text: str) -> list[Autor]:
    """Eine Zeile pro Person: 'Name; Matrikelnummer' (Matrikelnummer optional)."""
    autoren = []
    for zeile in text.splitlines():
        if not zeile.strip():
            continue
        name, _, matrikel = zeile.partition(";")
        autoren.append(Autor(name.strip(), matrikel.strip()))
    return autoren


# --------------------------------------------------------------------------
# Dateien erzeugen
# --------------------------------------------------------------------------

def _ersetze(vorlage: str, **werte: str) -> str:
    for k, v in werte.items():
        vorlage = vorlage.replace(f"<<{k}>>", v)
    return vorlage


def _titelseite(p: Projekt) -> str:
    zeilen: list[tuple[str, str]] = []
    if p.studiengang:
        zeilen.append(("Studiengang", tex(p.studiengang)))
    if p.modul:
        zeilen.append(("Modul", tex(p.modul)))
    if p.kurs:
        zeilen.append(("Kurs", tex(p.kurs)))
    mit_matrikel = [a for a in p.autoren if a.matrikel]
    if len(p.autoren) == 1 and mit_matrikel:
        zeilen.append(("Matrikelnummer", tex(mit_matrikel[0].matrikel)))
    elif mit_matrikel:
        zeilen.append(("Matrikelnummern", ", ".join(
            f"{tex(a.matrikel)} ({kurzname(tex(a.name))})" for a in mit_matrikel)))
    if p.betreuer:
        zeilen.append((tex(p.betreuer_bezeichnung or "Dozent"), tex(p.betreuer)))
    if p.abgabe:
        zeilen.append(("Abgabedatum", datum_lang(p.abgabe)))
    if not zeilen:
        zeilen.append(("Abgabedatum", r"\today"))
    breite = max(len(k) for k, _ in zeilen) + 2
    tabelle = "\n".join(f"    {(k + ':').ljust(breite)}& {v}\\\\" for k, v in zeilen)
    return _ersetze(V.TITELSEITE_TEX, HOCHSCHULE=tex(p.hochschule), ART=tex(p.art),
                    TABELLE=tabelle)


def _erklaerung(p: Projekt) -> str:
    namen = [tex(a.name) for a in p.autoren] or ["Name"]
    if len(namen) == 1:
        return _ersetze(V.ERKLAERUNG_EINZEL, NAME1=namen[0])
    # Unterschriftenfelder paarweise nebeneinander
    bloecke = []
    for i in range(0, len(namen), 2):
        paar = namen[i:i + 2]
        if len(paar) == 2:
            bloecke.append(
                "\\begin{tabular}{@{}p{0.42\\textwidth}@{\\hspace{0.1\\textwidth}}p{0.42\\textwidth}@{}}\n"
                "  \\rule{\\linewidth}{0.4pt} & \\rule{\\linewidth}{0.4pt} \\\\\n"
                f"  Ort, Datum, {paar[0]} & Ort, Datum, {paar[1]} \\\\\n"
                "\\end{tabular}")
        else:
            bloecke.append(
                "\\begin{tabular}{@{}p{0.42\\textwidth}@{}}\n"
                "  \\rule{\\linewidth}{0.4pt} \\\\\n"
                f"  Ort, Datum, {paar[0]} \\\\\n"
                "\\end{tabular}")
    return _ersetze(V.ERKLAERUNG_MEHRERE, UNTERSCHRIFTEN="\n\n\\vspace{1.5cm}\n\\noindent\n".join(bloecke))


def dateien(p: Projekt) -> dict[str, str]:
    """Alle Textdateien des neuen Projekts als {relativer Pfad: Inhalt}."""
    out: dict[str, str] = {}
    haupt = []
    for i, name in enumerate(p.kapitel, start=2):
        datei = f"{i:02d}_{slug(name)}"
        out[f"kapitel/{datei}.tex"] = _ersetze(V.KAPITEL_TEX, NAME=tex(name), LABEL=slug(name))
        haupt.append(f"\\input{{kapitel/{datei}}}")
    n = len(p.kapitel) + 2
    ki, anhang = f"{n:02d}_ki-nutzung", f"{n + 1:02d}_anhang"
    out[f"kapitel/{ki}.tex"] = _ersetze(V.KI_NUTZUNG_TEX, KI_WERKZEUG=tex(p.ki_werkzeug or "KI-Werkzeug"))
    out[f"kapitel/{anhang}.tex"] = V.ANHANG_TEX
    out["kapitel/00_titelseite.tex"] = _titelseite(p)
    out["kapitel/01_erklaerung.tex"] = _erklaerung(p)

    out["main.tex"] = _ersetze(
        V.MAIN_TEX,
        TITEL=tex(p.titel),
        AUTOR=namen_aufzaehlen([tex(a.name) for a in p.autoren]) or "Name",
        HAUPTKAPITEL="\n".join(haupt),
        ANHANGKAPITEL=f"\\input{{kapitel/{ki}}}\n\\input{{kapitel/{anhang}}}")

    sammlung = p.sammlung_name
    out["literatur.bib"] = _ersetze(V.LITERATUR_BIB, SAMMLUNG=sammlung)
    out["latexmkrc"] = _ersetze(V.LATEXMKRC, SAMMLUNG=sammlung,
                                SAMMLUNG_URL=urllib.parse.quote(sammlung))
    out[".gitignore"] = V.GITIGNORE
    out[".github/workflows/build.yml"] = _ersetze(V.BUILD_YML, PDFNAME=p.repo)
    out[".vscode/settings.json"] = V.VSCODE_SETTINGS
    out[".vscode/tasks.json"] = V.VSCODE_TASKS
    out[".vscode/extensions.json"] = V.VSCODE_EXTENSIONS
    out["bilder/.gitkeep"] = ""

    pdflink = ""
    if p.github and p.github_owner:
        url = f"https://github.com/{p.github_owner}/{p.repo}/releases/latest/download/{p.repo}.pdf"
        pdflink = (f"\n**Aktuelles PDF:** [{p.repo}.pdf]({url}) (wird bei jedem Push automatisch "
                   "neu gebaut, siehe *Releases* → *Aktuelles PDF*)\n")
    out["README.md"] = _ersetze(V.README_MD, REPO=p.repo, ART=p.art, TITEL_PLAIN=p.titel,
                                SAMMLUNG=sammlung, PDFNAME=p.repo, PDFLINK=pdflink)
    return out


def pruefen(p: Projekt) -> list[str]:
    fehler = []
    if not repo_name_gueltig(p.repo):
        fehler.append("Projektname: nur Buchstaben, Ziffern, '-', '_' und '.' (keine Leerzeichen/Umlaute).")
    if not p.titel.strip():
        fehler.append("Bitte einen Titel der Arbeit angeben.")
    if not p.autoren:
        fehler.append("Bitte mindestens eine Person angeben.")
    if not p.zielordner.is_dir():
        fehler.append(f"Zielordner existiert nicht: {p.zielordner}")
    elif p.ordner.exists() and any(p.ordner.iterdir()):
        fehler.append(f"Der Ordner {p.ordner} existiert bereits und ist nicht leer.")
    if p.logo and not Path(p.logo).is_file():
        fehler.append(f"Logodatei nicht gefunden: {p.logo}")
    if p.logo and Path(p.logo).suffix.lower() not in (".png", ".jpg", ".jpeg", ".pdf"):
        fehler.append("Logo muss PNG, JPG oder PDF sein.")
    if not (p.git_name and p.git_email):
        fehler.append("Bitte Name und E-Mail für die Git-Commits angeben (Schritt GitHub).")
    if p.github_owner and not re.fullmatch(r"[A-Za-z0-9-]+", p.github_owner):
        fehler.append("GitHub-Konto: nur Buchstaben, Ziffern und '-'.")
    return fehler


def projekt_schreiben(p: Projekt, log: Log) -> None:
    p.ordner.mkdir(parents=True, exist_ok=True)
    for rel, inhalt in dateien(p).items():
        ziel = p.ordner / rel
        ziel.parent.mkdir(parents=True, exist_ok=True)
        ziel.write_text(inhalt, encoding="utf-8", newline="\n")
        log(f"  erstellt: {rel}")
    if p.logo:
        endung = Path(p.logo).suffix.lower().replace(".jpeg", ".jpg")
        shutil.copyfile(p.logo, p.ordner / "bilder" / f"logo{endung}")
        log(f"  kopiert:  bilder/logo{endung}")


# --------------------------------------------------------------------------
# Git und GitHub
# --------------------------------------------------------------------------

def git(args: list[str], cwd: Path, eingabe: str | None = None) -> subprocess.CompletedProcess:
    # GIT_TERMINAL_PROMPT=0: nie im (unsichtbaren) Terminal nach Passwörtern fragen
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
    return subprocess.run(["git", *args], cwd=cwd, input=eingabe, capture_output=True, env=env,
                          text=True, encoding="utf-8", creationflags=_NO_WINDOW, timeout=600)


def _git_ok(args: list[str], cwd: Path, log: Log) -> None:
    r = git(args, cwd)
    if r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} fehlgeschlagen:\n{r.stderr.strip() or r.stdout.strip()}")
    log(f"  git {' '.join(args)}")


def git_init(p: Projekt, log: Log) -> None:
    d = p.ordner
    _git_ok(["init", "-b", "main"], d, log)
    if p.git_name:
        _git_ok(["config", "user.name", p.git_name], d, log)
    if p.git_email:
        _git_ok(["config", "user.email", p.git_email], d, log)
    _git_ok(["add", "-A"], d, log)
    _git_ok(["commit", "-m", "Projekt angelegt (LaTeX-Projekt-Assistent)"], d, log)


def github_token() -> str:
    """Holt das GitHub-Token aus dem Git Credential Manager (öffnet ggf. die Anmeldung im Browser)."""
    for var in ("GH_TOKEN", "GITHUB_TOKEN"):
        if os.environ.get(var):
            return os.environ[var]
    if shutil.which("gh"):
        r = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True,
                           creationflags=_NO_WINDOW)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    r = git(["credential", "fill"], Path.cwd(), eingabe="protocol=https\nhost=github.com\n\n")
    for zeile in r.stdout.splitlines():
        if zeile.startswith("password="):
            return zeile.split("=", 1)[1]
    hinweis = ("Im Terminal einmal 'gh auth login' ausführen" if sys.platform == "darwin"
               else "Git for Windows (mit Git Credential Manager) installieren oder 'gh auth login' ausführen")
    raise RuntimeError(f"Kein GitHub-Login gefunden. {hinweis} – siehe Anleitung, Abschnitt GitHub-Anmeldung.")


def github_login() -> str:
    """Name des angemeldeten GitHub-Kontos (öffnet ggf. die Anmeldung im Browser)."""
    return _api("GET", "/user", github_token())["login"]


def _api(methode: str, pfad: str, token: str, daten: dict | None = None) -> dict:
    req = urllib.request.Request(
        GITHUB_API + pfad, method=methode,
        data=json.dumps(daten).encode() if daten is not None else None,
        headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
                 "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "latex-projekt-assistent"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as e:
        text = e.read().decode(errors="replace")
        try:
            meldung = json.loads(text)
            text = meldung.get("message", text) + "".join(
                f"\n  - {f.get('message', f)}" for f in meldung.get("errors", []))
        except ValueError:
            pass
        raise RuntimeError(f"GitHub {e.code}: {text}") from None


def github_erstellen(p: Projekt, log: Log) -> str:
    token = github_token()
    login = _api("GET", "/user", token)["login"]
    log(f"  angemeldet bei GitHub als {login}")
    if not p.github_owner:
        p.github_owner = login
    daten = {"name": p.repo, "private": p.github_privat, "description": p.titel[:300],
             "has_wiki": False}
    if p.github_owner.lower() == login.lower():
        repo = _api("POST", "/user/repos", token, daten)
    else:
        repo = _api("POST", f"/orgs/{p.github_owner}/repos", token, daten)
    log(f"  Repository angelegt: {repo['html_url']}")
    _git_ok(["remote", "add", "origin", repo["clone_url"]], p.ordner, log)
    # Erster Push mit demselben Token (über Umgebungsvariablen, nicht sichtbar in der Befehlszeile),
    # damit er auch ohne eingerichteten Credential-Helper funktioniert (z. B. macOS).
    basis = base64.b64encode(f"x-access-token:{token}".encode()).decode()
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_CONFIG_COUNT": "1",
           "GIT_CONFIG_KEY_0": "http.https://github.com/.extraheader",
           "GIT_CONFIG_VALUE_0": f"AUTHORIZATION: basic {basis}"}
    r = subprocess.run(["git", "push", "-u", "origin", "main"], cwd=p.ordner, env=env, capture_output=True,
                       text=True, encoding="utf-8", creationflags=_NO_WINDOW, timeout=600)
    if r.returncode != 0:
        raise RuntimeError("git push fehlgeschlagen: " + r.stderr.strip())
    log("  git push -u origin main")
    return repo["html_url"]


# --------------------------------------------------------------------------
# Zotero
# --------------------------------------------------------------------------

def _http_get(url: str, timeout: float = 3) -> tuple[int, str]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.status, r.read().decode(errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode(errors="replace")
    except (urllib.error.URLError, OSError):
        return 0, ""


def zotero_status(sammlung: str) -> tuple[bool, list[str]]:
    """Gibt (alles_ok, Meldungen) zurück."""
    code, _ = _http_get(f"{ZOTERO}/connector/ping")
    if code != 200:
        return False, ["Zotero läuft nicht (oder ist noch nicht gestartet). Zotero öffnen und erneut prüfen."]
    msgs = ["Zotero läuft."]
    code, text = _http_get(f"{ZOTERO}/better-bibtex/cayw?probe=true")
    if code != 200:
        return False, msgs + ["Better BibTeX ist nicht installiert: Zotero → Werkzeuge → Plugins → "
                              "zotero-better-bibtex.xpi installieren."]
    msgs.append("Better BibTeX ist installiert.")
    url = f"{ZOTERO}/better-bibtex/export/collection?/1/{urllib.parse.quote(sammlung)}.biblatex"
    code, text = _http_get(url, timeout=10)
    if code == 200:
        anzahl = len(re.findall(r"^@\w+\{", text, flags=re.M))
        msgs.append(f"Sammlung \"{sammlung}\" gefunden ({anzahl} Einträge).")
        return True, msgs
    return False, msgs + [f"Sammlung \"{sammlung}\" gibt es noch nicht. In Zotero: Rechtsklick auf "
                          f"\"Meine Bibliothek\" → \"Neue Sammlung…\" → Name: {sammlung}"]


def vscode_oeffnen(ordner: Path) -> bool:
    code = shutil.which("code")
    if code:
        subprocess.Popen([code, str(ordner)], creationflags=_NO_WINDOW, shell=code.lower().endswith(".cmd"))
        return True
    if sys.platform == "darwin" and Path("/Applications/Visual Studio Code.app").exists():
        subprocess.Popen(["open", "-a", "Visual Studio Code", str(ordner)])
        return True
    return False


def git_identitaet() -> tuple[str, str]:
    """Global eingestellter Git-Name und -E-Mail (falls vorhanden)."""
    werte = []
    for key in ("user.name", "user.email"):
        try:
            r = git(["config", "--global", key], Path.home())
            werte.append(r.stdout.strip() if r.returncode == 0 else "")
        except OSError:
            werte.append("")
    return werte[0], werte[1]


def git_vorhanden() -> bool:
    return shutil.which("git") is not None


def latexmk_vorhanden() -> bool:
    return shutil.which("latexmk") is not None
