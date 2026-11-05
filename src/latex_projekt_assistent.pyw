"""LaTeX-Projekt-Assistent

Legt per geführtem Assistenten eine komplette LaTeX-Ausarbeitung an:
Vorlage, Zotero-Anbindung, VS-Code-Einstellungen, Git und GitHub mit automatischem PDF-Build.

Start: Doppelklick auf diese Datei oder `python3 latex_projekt_assistent.pyw`.
Läuft unter Windows und macOS (Python 3.9+ mit tkinter).

Lizenz: PolyForm Noncommercial 1.0.0 – siehe LICENSE.md
"""

from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

HIER = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
sys.path.insert(0, str(HIER))
import assistent_kern as K  # noqa: E402

VERSION = "1.0"
ANLEITUNG_URL = "https://github.com/BZ-Engineering/LaTeX-Projekt-Assistent#readme"
MAC = sys.platform == "darwin"
WIN = sys.platform == "win32"


def _einstellungsdatei() -> Path:
    if WIN:
        return Path(os.environ.get("APPDATA", Path.home())) / "latex-projekt-assistent.json"
    if MAC:
        return Path.home() / "Library" / "Application Support" / "latex-projekt-assistent.json"
    return Path.home() / ".config" / "latex-projekt-assistent.json"


EINSTELLUNGEN = _einstellungsdatei()

# --------------------------------------------------------------------------- Design
FARBE = {
    "bg": "#F4F6FB", "karte": "#FFFFFF", "rand": "#E2E6EF", "rand_hover": "#C9CFDD",
    "text": "#171C2E", "leise": "#6B7286", "sehr_leise": "#9AA1B4",
    "akzent": "#5B5BD6", "akzent_hover": "#4848C2", "akzent_hell": "#EEEFFE", "akzent_text": "#3F3FB0",
    "seite": "#141A2C", "seite_hover": "#1E2640", "seite_text": "#A3ABC2", "seite_aktiv": "#252E4D",
    "ok": "#1E9E5A", "ok_hell": "#E7F6EE", "fehler": "#D14343", "fehler_hell": "#FCECEC",
    "warn": "#B7791F", "warn_hell": "#FDF5E6",
    "konsole": "#10162A", "konsole_text": "#C9D1E3",
}

if MAC:
    _FAMILIE, _FETT, _MONO, _PLUS = "Helvetica Neue", ("Helvetica Neue", "bold"), "Menlo", 3
else:
    _FAMILIE, _FETT, _MONO, _PLUS = "Segoe UI", ("Segoe UI Semibold", "normal"), "Consolas", 0


def norm(groesse: int):
    return (_FAMILIE, groesse + _PLUS)


def fett(groesse: int):
    return (_FETT[0], groesse + _PLUS, _FETT[1])


def mono(groesse: int):
    return (_MONO, groesse + _PLUS)


SCHRITTE = [
    ("Projekt", "Worum geht es?", "Titel, Art der Arbeit und Speicherort. Der Projektname wird zum "
     "Ordner- und Repository-Namen."),
    ("Personen", "Wer schreibt die Arbeit?", "Alle Verfasserinnen und Verfasser mit Matrikelnummer. "
     "Bei mehreren Personen steht die Erklärung automatisch in der Wir-Form."),
    ("Titelseite", "Angaben für die Titelseite", "Leere Felder werden auf der Titelseite einfach weggelassen."),
    ("Gliederung", "Kapitel festlegen", "Für jedes Kapitel entsteht eine eigene .tex-Datei. "
     "Die Reihenfolge lässt sich mit den Pfeilen ändern."),
    ("Zotero", "Literatur mit Zotero verbinden", "Bei jedem Build holt LaTeX die Quellen aus dieser "
     "Zotero-Sammlung in die Datei literatur.bib."),
    ("GitHub", "Versionierung & automatisches PDF", "Das Projekt wird ein Git-Repository. Auf Wunsch wird "
     "es bei GitHub hochgeladen, wo bei jedem Push automatisch das PDF gebaut wird."),
    ("Erstellen", "Alles bereit?", "Prüfe die Zusammenfassung und lege das Projekt an."),
]

ARTEN = ["Projektbericht", "Studienarbeit", "Seminararbeit", "Laborbericht", "Praxisbericht",
         "Hausarbeit", "Bachelorarbeit", "Masterarbeit"]
BETREUER = ["Dozent", "Dozentin", "Betreuer", "Betreuerin", "Gutachter", "Gutachterin", "Prüfer", "Prüferin"]

STANDARD = {
    "titel": "", "art": "Projektbericht", "repo": "",
    "zielordner": str(Path.home() / "Documents"),
    "autoren": [["", ""]],
    "hochschule": "", "studiengang": "", "modul": "", "kurs": "",
    "betreuer_bezeichnung": "Dozent", "betreuer": "", "abgabe": "", "logo": "",
    "kapitel": ["Einleitung", "Grundlagen", "Umsetzung", "Fazit"],
    "ki_werkzeug": "", "sammlung": "",
    "git_name": "", "git_email": "",
    "github": True, "github_owner": "", "github_privat": True, "vscode": True,
}
GEMERKT = ["art", "zielordner", "autoren", "hochschule", "studiengang", "kurs", "betreuer_bezeichnung",
           "betreuer", "logo", "kapitel", "ki_werkzeug", "git_name", "git_email", "github",
           "github_owner", "github_privat", "vscode"]

DEMO = {
    "titel": "Analyse eines aktiven Tiefpassfilters", "art": "Projektbericht",
    "autoren": [["Erika Mustermann", "1234567"], ["Max Mustermann", "7654321"]],
    "hochschule": "Musterhochschule / Fakultät Technik", "studiengang": "Elektrotechnik",
    "modul": "Schaltungstechnik", "kurs": "ET24A", "betreuer_bezeichnung": "Betreuer",
    "betreuer": "Prof. Dr. Hans Beispiel", "abgabe": "15.03.2027", "logo": "",
    "kapitel": ["Einleitung", "Grundlagen", "Schaltungsentwurf", "Simulation", "Fazit"],
    "ki_werkzeug": "Claude", "git_name": "Erika Mustermann",
    "git_email": "erika.mustermann@example.com", "github": True, "github_owner": "",
    "github_privat": True, "vscode": True,
}


def einstellungen_laden(demo: bool = False) -> dict:
    w = json.loads(json.dumps(STANDARD))
    if demo:
        w.update(json.loads(json.dumps(DEMO)))
        return w
    try:
        gespeichert = json.loads(EINSTELLUNGEN.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        gespeichert = {}
    # ältere Version speicherte Personen/Kapitel als Text
    if isinstance(gespeichert.get("autoren"), str):
        gespeichert["autoren"] = [[a.name, a.matrikel] for a in K.autoren_parsen(gespeichert["autoren"])]
    if isinstance(gespeichert.get("kapitel"), str):
        gespeichert["kapitel"] = [z.strip() for z in gespeichert["kapitel"].splitlines() if z.strip()]
    if "github_an" in gespeichert:
        gespeichert["github"] = gespeichert.pop("github_an")
    if "vscode_an" in gespeichert:
        gespeichert["vscode"] = gespeichert.pop("vscode_an")
    w.update({k: v for k, v in gespeichert.items() if k in STANDARD and type(v) is type(STANDARD[k])})
    if not (w["git_name"] or w["git_email"]):
        w["git_name"], w["git_email"] = K.git_identitaet()
    return w


def ordner_oeffnen(pfad: Path) -> None:
    if WIN:
        os.startfile(pfad)  # type: ignore[attr-defined]
    elif MAC:
        subprocess.Popen(["open", str(pfad)])
    else:
        subprocess.Popen(["xdg-open", str(pfad)])


# --------------------------------------------------------------------------- Bausteine
class Knopf(tk.Label):
    """Flacher Button mit Hover-Effekt. art: primaer | sekundaer | leise | link"""

    def __init__(self, master, text, command=None, art="primaer", gross=False, **kw):
        self.art, self.command, self.aktiv = art, command, True
        bg = master.cget("bg")
        stile = {
            "primaer": (FARBE["akzent"], "#FFFFFF", FARBE["akzent_hover"]),
            "sekundaer": (FARBE["karte"], FARBE["text"], FARBE["bg"]),
            "leise": (bg, FARBE["leise"], FARBE["bg"] if bg == FARBE["karte"] else FARBE["seite_hover"]),
            "link": (bg, FARBE["akzent"], bg),
        }
        self.normal, self.fg, self.hover = stile[art]
        super().__init__(master, text=text, bg=self.normal, fg=self.fg, cursor="hand2",
                         font=fett(11 if gross else 10), padx=22 if gross else 16, pady=9 if gross else 6,
                         highlightthickness=1 if art == "sekundaer" else 0,
                         highlightbackground=FARBE["rand"], **kw)
        self.bind("<Enter>", lambda e: self.aktiv and self.configure(bg=self.hover))
        self.bind("<Leave>", lambda e: self.aktiv and self.configure(bg=self.normal))
        self.bind("<Button-1>", self._klick)

    def _klick(self, _):
        if self.aktiv and self.command:
            self.command()

    def setze_aktiv(self, aktiv: bool):
        self.aktiv = aktiv
        if aktiv:
            self.configure(bg=self.normal, fg=self.fg, cursor="hand2")
        else:
            self.configure(bg=FARBE["rand"] if self.art == "primaer" else self.normal,
                           fg=FARBE["sehr_leise"], cursor="arrow")


class Schalter(tk.Frame):
    """Kippschalter mit Beschriftung und optionalem Hinweis."""

    def __init__(self, master, variable: tk.BooleanVar, text: str, hinweis: str = "", command=None, s=1.0):
        super().__init__(master, bg=master.cget("bg"))
        self.var, self.command, self.s = variable, command, s
        b, h = int(40 * s), int(22 * s)
        self.c = tk.Canvas(self, width=b, height=h, bg=self.cget("bg"), highlightthickness=0, cursor="hand2")
        self.c.grid(row=0, column=0, rowspan=2, sticky="n", pady=(2, 0))
        titel = tk.Label(self, text=text, bg=self.cget("bg"), fg=FARBE["text"], font=fett(10), cursor="hand2")
        titel.grid(row=0, column=1, sticky="w", padx=(10, 0))
        if hinweis:
            tk.Label(self, text=hinweis, bg=self.cget("bg"), fg=FARBE["leise"], font=norm(9),
                     justify="left", wraplength=int(560 * s)).grid(row=1, column=1, sticky="w", padx=(10, 0))
        for w in (self.c, titel):
            w.bind("<Button-1>", self._umschalten)
        self.var.trace_add("write", lambda *_: self._zeichnen())
        self._zeichnen()

    def _umschalten(self, _=None):
        self.var.set(not self.var.get())
        if self.command:
            self.command()

    def _zeichnen(self):
        c, s = self.c, self.s
        b, h = int(40 * s), int(22 * s)
        c.delete("all")
        an = bool(self.var.get())
        farbe = FARBE["akzent"] if an else "#CBD1DE"
        r = h / 2
        c.create_oval(0, 0, h, h, fill=farbe, outline=farbe)
        c.create_oval(b - h, 0, b, h, fill=farbe, outline=farbe)
        c.create_rectangle(r, 0, b - r, h, fill=farbe, outline=farbe)
        x = b - r if an else r
        k = r - 3 * s
        c.create_oval(x - k, r - k, x + k, r + k, fill="#FFFFFF", outline="#FFFFFF")


class Eingabe(tk.Frame):
    """Einzeiliges Eingabefeld mit Rahmen, Fokusfarbe und Platzhalter."""

    def __init__(self, master, variable: tk.StringVar, platzhalter: str = "", breite: int = 20, s=1.0):
        super().__init__(master, bg=FARBE["karte"], highlightthickness=1,
                         highlightbackground=FARBE["rand"], highlightcolor=FARBE["rand"])
        self.var, self._s, self._fehler = variable, s, False
        self.entry = tk.Entry(self, textvariable=variable, relief="flat", bd=0, bg=FARBE["karte"],
                              fg=FARBE["text"], insertbackground=FARBE["text"], font=norm(10),
                              width=breite, selectbackground=FARBE["akzent_hell"],
                              selectforeground=FARBE["text"], highlightthickness=0)
        self.entry.pack(fill="x", padx=int(10 * s), pady=int(7 * s))
        self.ph = tk.Label(self, text=platzhalter, bg=FARBE["karte"], fg=FARBE["sehr_leise"],
                           font=norm(10), cursor="xterm")
        self.ph.bind("<Button-1>", lambda e: self.entry.focus_set())
        self.entry.bind("<FocusIn>", lambda e: self._rahmen(True))
        self.entry.bind("<FocusOut>", lambda e: self._rahmen(False))
        variable.trace_add("write", lambda *_: self._platzhalter())
        self._platzhalter()

    def _rahmen(self, fokus: bool):
        farbe = FARBE["fehler"] if self._fehler and not fokus else (FARBE["akzent"] if fokus else FARBE["rand"])
        self.configure(highlightbackground=farbe, highlightcolor=farbe)

    def _platzhalter(self):
        if self.var.get():
            self.ph.place_forget()
        else:
            self.ph.place(x=int(10 * self._s), rely=0.5, anchor="w")

    def fehler(self, an: bool):
        self._fehler = an
        self._rahmen(self.focus_get() is self.entry)


class Scrollbereich(tk.Frame):
    """Senkrecht scrollbarer Bereich; die Leiste erscheint nur, wenn nötig."""

    def __init__(self, master, bg):
        super().__init__(master, bg=bg)
        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0, bd=0)
        self.leiste = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview,
                                    style="Duenn.Vertical.TScrollbar")
        self.innen = tk.Frame(self.canvas, bg=bg)
        self._fenster = self.canvas.create_window(0, 0, window=self.innen, anchor="nw")
        self.canvas.configure(yscrollcommand=self.leiste.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.innen.bind("<Configure>", lambda e: self._anpassen())
        self.canvas.bind("<Configure>", self._canvas_groesse)
        self.bind_all("<MouseWheel>", self._rad, add="+")

    def _canvas_groesse(self, e):
        self.canvas.itemconfigure(self._fenster, width=e.width)
        self._anpassen()

    def _anpassen(self):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        hoehe = max(self.innen.winfo_reqheight(), self.canvas.winfo_height())
        self.canvas.itemconfigure(self._fenster, height=hoehe)
        noetig = self.innen.winfo_reqheight() > self.canvas.winfo_height() + 2
        if noetig and not self.leiste.winfo_ismapped():
            self.leiste.pack(side="right", fill="y")
        elif not noetig and self.leiste.winfo_ismapped():
            self.leiste.pack_forget()
            self.canvas.yview_moveto(0)

    def _rad(self, e):
        if not self.winfo_ismapped() or not self.leiste.winfo_ismapped():
            return
        w = self.winfo_containing(e.x_root, e.y_root)
        while w is not None and w is not self:
            w = w.master
        if w is self:
            schritte = -e.delta if MAC else int(-e.delta / 120)
            self.canvas.yview_scroll(schritte, "units")


class ZeilenListe(tk.Frame):
    """Liste von Eingabezeilen mit Hinzufügen/Entfernen und optional Verschieben."""

    def __init__(self, master, spalten, werte, neu_text, sortierbar=False, s=1.0):
        super().__init__(master, bg=FARBE["karte"])
        self.spalten, self.sortierbar, self.s = spalten, sortierbar, s
        self.zeilen: list[list[tk.StringVar]] = []
        self._eingaben: list[list[Eingabe]] = []
        kopf = tk.Frame(self, bg=FARBE["karte"])
        kopf.pack(fill="x")
        self._spalten_konfigurieren(kopf)
        if sortierbar:
            tk.Label(kopf, text="", bg=FARBE["karte"], font=fett(10), width=3).grid(row=0, column=0)
        for i, (titel, _, _) in enumerate(spalten):
            tk.Label(kopf, text=titel, bg=FARBE["karte"], fg=FARBE["leise"], font=fett(9)).grid(
                row=0, column=i + 1, sticky="w")
        self._platz(kopf)
        self.koerper = tk.Frame(self, bg=FARBE["karte"])
        self.koerper.pack(fill="x", pady=(int(4 * s), 0))
        for zeile in werte or [[""] * len(spalten)]:
            self.zeilen.append(self._vars(zeile))
        Knopf(self, "+  " + neu_text, lambda: self._neue_zeile(fokus=True), art="link").pack(
            anchor="w", pady=(int(6 * s), 0))
        self._neu_zeichnen()

    def _spalten_konfigurieren(self, z):
        for i, (_, gewicht, _) in enumerate(self.spalten):
            z.columnconfigure(i + 1, weight=gewicht, uniform="sp")

    def _platz(self, z):
        """Rechte Spalte für Aktionsknöpfe, damit Kopf und Zeilen gleich breit sind."""
        z.columnconfigure(len(self.spalten) + 1, minsize=int((112 if self.sortierbar else 44) * self.s))

    def _vars(self, werte):
        werte = list(werte or [])
        werte += [""] * (len(self.spalten) - len(werte))
        return [tk.StringVar(value=v) for v in werte]

    def _neue_zeile(self, fokus=False):
        self.zeilen.append(self._vars(None))
        self._neu_zeichnen()
        if fokus:
            self.after(10, lambda: self._eingaben[-1][0].entry.focus_set())

    def _entfernen(self, i):
        if len(self.zeilen) > 1:
            self.zeilen.pop(i)
        else:
            for v in self.zeilen[0]:
                v.set("")
        self._neu_zeichnen()

    def _schieben(self, i, d):
        j = i + d
        if 0 <= j < len(self.zeilen):
            self.zeilen[i], self.zeilen[j] = self.zeilen[j], self.zeilen[i]
            self._neu_zeichnen()

    def _neu_zeichnen(self):
        for w in self.koerper.winfo_children():
            w.destroy()
        self._eingaben = []
        s = self.s
        for i, vars_ in enumerate(self.zeilen):
            z = tk.Frame(self.koerper, bg=FARBE["karte"])
            z.pack(fill="x", pady=int(3 * s))
            self._spalten_konfigurieren(z)
            self._platz(z)
            if self.sortierbar:
                tk.Label(z, text=f"{i + 1:02d}", width=3, bg=FARBE["karte"], fg=FARBE["sehr_leise"],
                         font=fett(10), anchor="w").grid(row=0, column=0, sticky="w")
            reihe = []
            for k, ((_, _, ph), var) in enumerate(zip(self.spalten, vars_)):
                e = Eingabe(z, var, ph, breite=8, s=s)
                e.grid(row=0, column=k + 1, sticky="we", padx=(0, int(8 * s)))
                reihe.append(e)
            self._eingaben.append(reihe)
            aktionen = tk.Frame(z, bg=FARBE["karte"])
            aktionen.grid(row=0, column=len(self.spalten) + 1, sticky="e")
            if self.sortierbar:
                for sym, d in (("∧", -1), ("∨", 1)):
                    Knopf(aktionen, sym, lambda i=i, d=d: self._schieben(i, d), art="leise").pack(side="left")
            Knopf(aktionen, "✕", lambda i=i: self._entfernen(i), art="leise").pack(side="left")

    def werte(self) -> list[list[str]]:
        return [[v.get().strip() for v in z] for z in self.zeilen if any(v.get().strip() for v in z)]


# --------------------------------------------------------------------------- Anwendung
class App(tk.Tk):
    def __init__(self, demo: bool = False) -> None:
        super().__init__()
        self.s = 1.0 if MAC else self.winfo_fpixels("1i") / 96
        s = self.s
        self.title("LaTeX-Projekt-Assistent")
        self.configure(bg=FARBE["bg"])
        b, h = int(1160 * s), int(800 * s)
        b, h = min(b, self.winfo_screenwidth() - 40), min(h, self.winfo_screenheight() - 80)
        self.geometry(f"{b}x{h}+{max(0, (self.winfo_screenwidth() - b) // 2)}+"
                      f"{max(0, (self.winfo_screenheight() - h) // 3)}")
        self.minsize(int(960 * s), int(640 * s))
        try:
            self._fenster_icon = tk.PhotoImage(file=str(HIER / "icon.png"))
            self.iconphoto(True, self._fenster_icon)
            if WIN:
                self.iconbitmap(default=str(HIER / "icon.ico"))
        except tk.TclError:
            pass
        self._stile()

        self.demo = demo
        self.w = einstellungen_laden(demo)
        self.v: dict[str, tk.Variable] = {}
        for k, wert in self.w.items():
            if isinstance(wert, bool):
                self.v[k] = tk.BooleanVar(value=wert)
            elif isinstance(wert, str):
                self.v[k] = tk.StringVar(value=wert)
        self.repo_auto = not self.v["repo"].get()
        self.schritt = 0
        self.laeuft = False
        self._auftraege: queue.Queue = queue.Queue()
        self._pumpe()

        self._aufbau()
        self.v["titel"].trace_add("write", self._repo_vorschlagen)
        self._repo_vorschlagen()
        self.zeige(0)
        self.after(400, self._voraussetzungen)

    # ----------------------------------------------------------------- Threads
    def _ui(self, funktion):
        """Führt eine Funktion im Tk-Hauptthread aus (sicher aus Hintergrund-Threads aufrufbar)."""
        self._auftraege.put(funktion)

    def _pumpe(self):
        try:
            while True:
                self._auftraege.get_nowait()()
        except queue.Empty:
            pass
        self.after(40, self._pumpe)

    # ----------------------------------------------------------------- Stile
    def _stile(self):
        s = self.s
        st = ttk.Style(self)
        st.theme_use("clam")
        st.configure("Duenn.Vertical.TScrollbar", gripcount=0, background="#D3D8E3", troughcolor=FARBE["karte"],
                     bordercolor=FARBE["karte"], lightcolor="#D3D8E3", darkcolor="#D3D8E3", arrowsize=0,
                     relief="flat")
        st.map("Duenn.Vertical.TScrollbar", background=[("active", "#B9C0CF")])
        st.configure("Akzent.Horizontal.TProgressbar", troughcolor=FARBE["rand"], background=FARBE["akzent"],
                     bordercolor=FARBE["rand"], lightcolor=FARBE["akzent"], darkcolor=FARBE["akzent"],
                     thickness=int(6 * s))
        st.configure("Feld.TCombobox", fieldbackground=FARBE["karte"], background=FARBE["karte"],
                     bordercolor=FARBE["rand"], lightcolor=FARBE["karte"], darkcolor=FARBE["karte"],
                     arrowcolor=FARBE["leise"], foreground=FARBE["text"], padding=(int(8 * s), int(6 * s)),
                     relief="flat", arrowsize=int(14 * s))
        st.map("Feld.TCombobox", bordercolor=[("focus", FARBE["akzent"])],
               fieldbackground=[("readonly", FARBE["karte"])], selectbackground=[("!focus", FARBE["karte"])],
               selectforeground=[("!focus", FARBE["text"])])
        self.option_add("*TCombobox*Listbox.font", norm(10))
        self.option_add("*TCombobox*Listbox.selectBackground", FARBE["akzent"])

    # ----------------------------------------------------------------- Grundgerüst
    def _aufbau(self):
        s = self.s
        # Seitenleiste
        seite = tk.Frame(self, bg=FARBE["seite"], width=int(270 * s))
        seite.pack(side="left", fill="y")
        seite.pack_propagate(False)
        kopf = tk.Frame(seite, bg=FARBE["seite"])
        kopf.pack(fill="x", padx=int(24 * s), pady=(int(28 * s), int(30 * s)))
        try:
            self._icon = tk.PhotoImage(file=str(HIER / "icon.png"))
            f = max(1, round(self._icon.width() / (40 * s)))
            self._icon_klein = self._icon.subsample(f, f)
            tk.Label(kopf, image=self._icon_klein, bg=FARBE["seite"]).pack(side="left", padx=(0, int(12 * s)))
        except tk.TclError:
            pass
        txt = tk.Frame(kopf, bg=FARBE["seite"])
        txt.pack(side="left")
        tk.Label(txt, text="LaTeX-Projekt", bg=FARBE["seite"], fg="#FFFFFF", font=fett(13)).pack(anchor="w")
        tk.Label(txt, text="Assistent  ·  v" + VERSION, bg=FARBE["seite"], fg=FARBE["seite_text"],
                 font=norm(9)).pack(anchor="w")

        self.nav = []
        for i, (name, *_rest) in enumerate(SCHRITTE):
            z = tk.Frame(seite, bg=FARBE["seite"], cursor="hand2")
            z.pack(fill="x", padx=int(12 * s), pady=int(1 * s))
            c = tk.Canvas(z, width=int(28 * s), height=int(28 * s), bg=FARBE["seite"], highlightthickness=0)
            c.pack(side="left", padx=(int(12 * s), int(12 * s)), pady=int(8 * s))
            lbl = tk.Label(z, text=name, bg=FARBE["seite"], fg=FARBE["seite_text"], font=fett(10))
            lbl.pack(side="left")
            for w in (z, c, lbl):
                w.bind("<Button-1>", lambda e, i=i: self._springen(i))
                w.bind("<Enter>", lambda e, i=i: self._nav_hover(i, True))
                w.bind("<Leave>", lambda e, i=i: self._nav_hover(i, False))
            self.nav.append((z, c, lbl))

        fuss = tk.Frame(seite, bg=FARBE["seite"])
        fuss.pack(side="bottom", fill="x", padx=int(24 * s), pady=int(22 * s))
        self.status_tools = tk.Label(fuss, text="", bg=FARBE["seite"], fg=FARBE["seite_text"],
                                     font=norm(8), justify="left", anchor="w")
        self.status_tools.pack(fill="x", pady=(0, int(10 * s)))
        lnk = tk.Label(fuss, text="?  Anleitung öffnen", bg=FARBE["seite"], fg="#FFFFFF",
                       font=fett(9), cursor="hand2", anchor="w")
        lnk.pack(fill="x")
        lnk.bind("<Button-1>", lambda e: webbrowser.open(ANLEITUNG_URL))

        # Hauptbereich
        haupt = tk.Frame(self, bg=FARBE["bg"])
        haupt.pack(side="left", fill="both", expand=True)
        rand = int(44 * s)
        oben = tk.Frame(haupt, bg=FARBE["bg"])
        oben.pack(fill="x", padx=rand, pady=(int(34 * s), int(18 * s)))
        self.l_schritt = tk.Label(oben, bg=FARBE["bg"], fg=FARBE["akzent"], font=fett(9))
        self.l_schritt.pack(anchor="w")
        self.l_titel = tk.Label(oben, bg=FARBE["bg"], fg=FARBE["text"], font=fett(20))
        self.l_titel.pack(anchor="w", pady=(int(2 * s), int(4 * s)))
        self.l_text = tk.Label(oben, bg=FARBE["bg"], fg=FARBE["leise"], font=norm(10), justify="left",
                               wraplength=int(760 * s))
        self.l_text.pack(anchor="w")

        unten = tk.Frame(haupt, bg=FARBE["bg"])
        unten.pack(side="bottom", fill="x", padx=rand, pady=(int(14 * s), int(26 * s)))
        self.k_zurueck = Knopf(unten, "←  Zurück", self.zurueck, art="sekundaer")
        self.k_zurueck.pack(side="left")
        self.k_weiter = Knopf(unten, "Weiter  →", self.weiter, art="primaer")
        self.k_weiter.pack(side="right")
        self.l_fehler = tk.Label(unten, text="", bg=FARBE["bg"], fg=FARBE["fehler"], font=norm(9),
                                 justify="right", wraplength=int(520 * s))
        self.l_fehler.pack(side="right", padx=int(16 * s))

        karte_rahmen = tk.Frame(haupt, bg=FARBE["rand"])
        karte_rahmen.pack(fill="both", expand=True, padx=rand)
        self.scroll = Scrollbereich(karte_rahmen, FARBE["karte"])
        self.scroll.pack(fill="both", expand=True, padx=1, pady=1)

        self.seiten = []
        for baue in (self._seite_projekt, self._seite_personen, self._seite_titelseite, self._seite_gliederung,
                     self._seite_zotero, self._seite_github, self._seite_erstellen):
            f = tk.Frame(self.scroll.innen, bg=FARBE["karte"])
            innen = tk.Frame(f, bg=FARBE["karte"])
            innen.pack(fill="both", expand=True, padx=int(34 * s), pady=int(30 * s))
            baue(innen)
            self.seiten.append(f)

    # ----------------------------------------------------------------- Helfer
    def feld(self, master, titel, widget_bauer, hinweis="", row=0, col=0, colspan=1):
        s = self.s
        f = tk.Frame(master, bg=FARBE["karte"])
        f.grid(row=row, column=col, columnspan=colspan, sticky="nwe",
               padx=(0 if col == 0 else int(10 * s), 0 if col + colspan >= 2 else int(10 * s)),
               pady=(0, int(18 * s)))
        tk.Label(f, text=titel, bg=FARBE["karte"], fg=FARBE["text"], font=fett(10)).pack(anchor="w")
        w = widget_bauer(f)
        w.pack(fill="x", pady=(int(6 * s), 0))
        if hinweis:
            tk.Label(f, text=hinweis, bg=FARBE["karte"], fg=FARBE["leise"], font=norm(9), justify="left",
                     anchor="w", wraplength=int((720 if colspan == 2 else 340) * s)).pack(
                anchor="w", fill="x", pady=(int(4 * s), 0))
        return w

    def eingabe(self, key, ph=""):
        return lambda m: Eingabe(m, self.v[key], ph, s=self.s)

    def auswahl(self, key, werte):
        return lambda m: ttk.Combobox(m, textvariable=self.v[key], values=werte, style="Feld.TCombobox",
                                      font=norm(10))

    def raster(self, master):
        g = tk.Frame(master, bg=FARBE["karte"])
        g.pack(fill="x")
        g.columnconfigure(0, weight=1, uniform="r")
        g.columnconfigure(1, weight=1, uniform="r")
        return g

    def infobox(self, master, titel, text, art="info"):
        s = self.s
        bg, fg = {"info": (FARBE["akzent_hell"], FARBE["akzent_text"]),
                  "ok": (FARBE["ok_hell"], FARBE["ok"]),
                  "warn": (FARBE["warn_hell"], FARBE["warn"])}[art]
        box = tk.Frame(master, bg=bg)
        box.pack(fill="x", pady=(int(4 * s), int(8 * s)))
        tk.Frame(box, bg=fg, width=int(3 * s)).pack(side="left", fill="y")
        innen = tk.Frame(box, bg=bg)
        innen.pack(side="left", fill="x", expand=True, padx=int(16 * s), pady=int(12 * s))
        if titel:
            tk.Label(innen, text=titel, bg=bg, fg=fg, font=fett(10)).pack(anchor="w")
        lbl = tk.Label(innen, text=text, bg=bg, fg=FARBE["text"], font=norm(9), justify="left",
                       wraplength=int(700 * s), anchor="w")
        lbl.pack(anchor="w", fill="x", pady=(int(2 * s), 0))
        return lbl

    def ueberschrift(self, master, text, abstand=True):
        tk.Label(master, text=text.upper(), bg=FARBE["karte"], fg=FARBE["sehr_leise"],
                 font=fett(8)).pack(anchor="w", pady=(int(14 * self.s) if abstand else 0, int(10 * self.s)))

    # ----------------------------------------------------------------- Seiten
    def _seite_projekt(self, m):
        g = self.raster(m)
        self.e_titel = self.feld(g, "Titel der Arbeit",
                                 self.eingabe("titel", "z. B. Analyse eines aktiven Tiefpassfilters"),
                                 row=0, col=0, colspan=2)
        self.feld(g, "Art der Arbeit", self.auswahl("art", ARTEN),
                  "Steht auf der Titelseite über dem Titel.", row=1, col=0)
        self.e_repo = self.feld(g, "Projektname", self.eingabe("repo", "wird aus dem Titel vorgeschlagen"),
                                "Ordner- und GitHub-Name: Buchstaben, Ziffern, - und _", row=1, col=1)
        self.e_repo.entry.bind("<Key>", lambda e: setattr(self, "repo_auto", False))

        def ordner(mm):
            f = tk.Frame(mm, bg=FARBE["karte"])
            Eingabe(f, self.v["zielordner"], s=self.s).pack(side="left", fill="x", expand=True)
            Knopf(f, "Durchsuchen…", self._ordner_waehlen, art="sekundaer").pack(
                side="left", padx=(int(8 * self.s), 0))
            return f
        self.feld(g, "Speicherort", ordner, row=2, col=0, colspan=2)
        self.l_pfad = self.infobox(m, "Das Projekt wird angelegt in", "")
        for k in ("repo", "zielordner"):
            self.v[k].trace_add("write", lambda *_: self._pfad_anzeigen())
        self._pfad_anzeigen()

    def _seite_personen(self, m):
        self.liste_personen = ZeilenListe(
            m, [("Name", 3, "Vor- und Nachname"), ("Matrikelnummer", 2, "optional")],
            self.w["autoren"], "Person hinzufügen", s=self.s)
        self.liste_personen.pack(fill="x")
        tk.Frame(m, bg=FARBE["karte"], height=int(16 * self.s)).pack()
        self.infobox(m, "Wofür werden die Angaben verwendet?",
                     "•  Titelseite: Namen und Matrikelnummern\n"
                     "•  Eigenständigkeitserklärung: Ich- bzw. Wir-Form und ein Unterschriftenfeld pro Person\n"
                     "•  Kopfzeile von main.tex (\\autor)")

    def _seite_titelseite(self, m):
        g = self.raster(m)
        self.feld(g, "Hochschule / Fakultät", self.eingabe("hochschule", "z. B. Hochschule XY / Fakultät Technik"),
                  row=0, col=0, colspan=2)
        self.feld(g, "Studiengang", self.eingabe("studiengang", "z. B. Elektrotechnik"), row=1, col=0)
        self.feld(g, "Modul / Fach", self.eingabe("modul", "z. B. Schaltungstechnik"), row=1, col=1)
        self.feld(g, "Kurs", self.eingabe("kurs", "z. B. ET24A"), row=2, col=0)
        self.feld(g, "Abgabedatum", self.eingabe("abgabe", "TT.MM.JJJJ"),
                  "wird als „15. März 2027“ gesetzt", row=2, col=1)
        self.feld(g, "Bezeichnung", self.auswahl("betreuer_bezeichnung", BETREUER), row=3, col=0)
        self.feld(g, "Name der betreuenden Person", self.eingabe("betreuer", "z. B. Prof. Dr. Hans Beispiel"),
                  row=3, col=1)

        def logo(mm):
            f = tk.Frame(mm, bg=FARBE["karte"])
            self.logo_vorschau = tk.Label(f, bg=FARBE["bg"], width=10, height=2, text="kein Logo",
                                          fg=FARBE["sehr_leise"], font=norm(8))
            self.logo_vorschau.pack(side="left", padx=(0, int(10 * self.s)))
            Eingabe(f, self.v["logo"], "PNG, JPG oder PDF – optional", s=self.s).pack(
                side="left", fill="x", expand=True)
            Knopf(f, "Auswählen…", self._logo_waehlen, art="sekundaer").pack(side="left", padx=(int(8 * self.s), 0))
            return f
        self.feld(g, "Logo", logo, "Erscheint auf der Titelseite und rechts in der Kopfzeile. Ohne Logo steht dort "
                  "ein Platzhalter; die Datei kann später als bilder/logo.png abgelegt werden.",
                  row=4, col=0, colspan=2)
        self.v["logo"].trace_add("write", lambda *_: self._logo_anzeigen())
        self._logo_anzeigen()

    def _seite_gliederung(self, m):
        self.liste_kapitel = ZeilenListe(m, [("Kapitel", 1, "Kapitelname")],
                                         [[k] for k in self.w["kapitel"]], "Kapitel hinzufügen",
                                         sortierbar=True, s=self.s)
        self.liste_kapitel.pack(fill="x")
        tk.Frame(m, bg=FARBE["karte"], height=int(14 * self.s)).pack()
        self.infobox(m, "Kommt automatisch dazu",
                     "Titelseite  ·  Eigenständigkeitserklärung  ·  Inhalts-, Abbildungs-, Tabellen- und "
                     "Formelverzeichnis  ·  Literaturverzeichnis  ·  Anhang „Nutzung von KI“  ·  Anhang")
        tk.Frame(m, bg=FARBE["karte"], height=int(10 * self.s)).pack()
        g = self.raster(m)
        self.feld(g, "Verwendetes KI-Werkzeug", self.eingabe("ki_werkzeug", "z. B. Claude, ChatGPT – optional"),
                  "Wird in die Tabelle im Anhang „Nutzung von KI“ eingetragen.", row=0, col=0)

    def _seite_zotero(self, m):
        g = self.raster(m)
        self.e_sammlung = self.feld(g, "Name der Zotero-Sammlung", self.eingabe("sammlung", ""),
                                    "Leer lassen = gleicher Name wie das Projekt (empfohlen).", row=0, col=0)

        def ph(*_):
            self.e_sammlung.ph.configure(text=self.v["repo"].get() or "Projektname")
        self.v["repo"].trace_add("write", ph)
        ph()

        self.ueberschrift(m, "Verbindung")
        self.checks = {}
        liste = tk.Frame(m, bg=FARBE["karte"])
        liste.pack(fill="x")
        for key, text in (("zotero", "Zotero ist gestartet"), ("bbt", "Better BibTeX ist installiert"),
                          ("sammlung", "Sammlung ist vorhanden")):
            z = tk.Frame(liste, bg=FARBE["karte"])
            z.pack(fill="x", pady=int(4 * self.s))
            c = tk.Canvas(z, width=int(22 * self.s), height=int(22 * self.s), bg=FARBE["karte"],
                          highlightthickness=0)
            c.pack(side="left")
            tk.Label(z, text=text, bg=FARBE["karte"], fg=FARBE["text"], font=fett(10)).pack(
                side="left", padx=(int(10 * self.s), 0))
            d = tk.Label(z, text="", bg=FARBE["karte"], fg=FARBE["leise"], font=norm(9))
            d.pack(side="left", padx=(int(10 * self.s), 0))
            self.checks[key] = (c, d)
            self._check_setzen(key, None)
        Knopf(m, "Verbindung prüfen", self._zotero_pruefen, art="sekundaer").pack(
            anchor="w", pady=(int(14 * self.s), int(16 * self.s)))
        self.zotero_hilfe = self.infobox(m, "So legst du die Sammlung an", "")
        self._zotero_hilfe_text()
        self.v["sammlung"].trace_add("write", lambda *_: self._zotero_hilfe_text())
        self.v["repo"].trace_add("write", lambda *_: self._zotero_hilfe_text())

    def _seite_github(self, m):
        self.ueberschrift(m, "Git – wer macht die Änderungen?", abstand=False)
        g = self.raster(m)
        self.feld(g, "Name", self.eingabe("git_name", "Vor- und Nachname"), row=0, col=0)
        self.feld(g, "E-Mail", self.eingabe("git_email", "am besten dieselbe wie bei GitHub"), row=0, col=1)
        self.ueberschrift(m, "GitHub")
        Schalter(m, self.v["github"], "Repository auf GitHub anlegen und hochladen",
                 "Bei jedem Push baut GitHub das PDF und stellt es als Download bereit. "
                 "Ohne diese Option entsteht nur ein lokales Git-Repository.",
                 command=self._github_umschalten, s=self.s).pack(anchor="w", fill="x")
        self.gh_bereich = tk.Frame(m, bg=FARBE["karte"])
        g2 = self.raster(self.gh_bereich)
        self.feld(g2, "Konto oder Organisation", self.eingabe("github_owner", "leer = eigenes Konto"),
                  "Für eine Organisation (z. B. eure Projektgruppe) deren Namen eintragen.", row=0, col=0)
        sf = tk.Frame(g2, bg=FARBE["karte"])
        sf.grid(row=0, column=1, sticky="nw", padx=(int(10 * self.s), 0), pady=(int(30 * self.s), 0))
        Schalter(sf, self.v["github_privat"], "Privat", "Nur du und eingeladene Personen sehen das Repository.",
                 s=self.s).pack(anchor="w")
        z = tk.Frame(self.gh_bereich, bg=FARBE["karte"])
        z.pack(fill="x")
        Knopf(z, "Verbindung testen", self._github_testen, art="sekundaer").pack(side="left")
        self.l_gh = tk.Label(z, text="", bg=FARBE["karte"], fg=FARBE["leise"], font=norm(9),
                             wraplength=int(520 * self.s), justify="left")
        self.l_gh.pack(side="left", padx=int(12 * self.s))
        self._github_umschalten()

    def _seite_erstellen(self, m):
        self.zusammenfassung = tk.Frame(m, bg=FARBE["karte"])
        self.zusammenfassung.pack(fill="x")
        tk.Frame(m, bg=FARBE["rand"], height=1).pack(fill="x", pady=int(14 * self.s))
        z = tk.Frame(m, bg=FARBE["karte"])
        z.pack(fill="x")
        Schalter(z, self.v["vscode"], "Danach in VS Code öffnen", s=self.s).pack(side="left")
        self.k_erstellen = Knopf(z, "Projekt erstellen", self._start, art="primaer", gross=True)
        self.k_erstellen.pack(side="right")
        self.fortschritt = ttk.Progressbar(m, style="Akzent.Horizontal.TProgressbar", mode="determinate",
                                           maximum=100)
        self.fortschritt.pack(fill="x", pady=(int(18 * self.s), int(10 * self.s)))
        self.konsole = tk.Text(m, height=8, bg=FARBE["konsole"], fg=FARBE["konsole_text"], relief="flat",
                               font=mono(9), padx=int(14 * self.s), pady=int(12 * self.s), state="disabled",
                               wrap="word", insertbackground="#FFFFFF", highlightthickness=0)
        self.konsole.pack(fill="both", expand=True)
        for tag, farbe in (("ok", "#4ADE80"), ("fehler", "#F87171"), ("titel", "#FFFFFF"),
                           ("leise", "#7C86A2"), ("warn", "#FBBF24")):
            self.konsole.tag_configure(tag, foreground=farbe)
        self.konsole.tag_configure("titel", font=fett(9))
        self.aktionen = tk.Frame(m, bg=FARBE["karte"])
        self.aktionen.pack(fill="x", pady=(int(12 * self.s), 0))
        self._log("Bereit. Klicke auf „Projekt erstellen“.", "leise")

    # ----------------------------------------------------------------- Navigation
    def zeige(self, i: int):
        self.schritt = i
        for f in self.seiten:
            f.pack_forget()
        self.seiten[i].pack(fill="both", expand=True)
        self.scroll.canvas.yview_moveto(0)
        _, titel, text = SCHRITTE[i]
        self.l_schritt.configure(text=f"SCHRITT {i + 1} VON {len(SCHRITTE)}")
        self.l_titel.configure(text=titel)
        self.l_text.configure(text=text)
        self.l_fehler.configure(text="")
        self.k_zurueck.setze_aktiv(i > 0 and not self.laeuft)
        if i == len(SCHRITTE) - 1:
            self.k_weiter.pack_forget()
            self._zusammenfassung()
        elif not self.k_weiter.winfo_ismapped():
            self.k_weiter.pack(side="right", before=self.l_fehler)
        for j in range(len(self.nav)):
            self._nav_zeichnen(j)
        if i == 4:
            self._zotero_pruefen()
        self.after(50, self.scroll._anpassen)

    def _nav_zeichnen(self, j, hover=False):
        z, c, lbl = self.nav[j]
        aktiv, fertig = j == self.schritt, j < self.schritt
        bg = FARBE["seite_aktiv"] if aktiv else (FARBE["seite_hover"] if hover else FARBE["seite"])
        for w in (z, c, lbl):
            w.configure(bg=bg)
        lbl.configure(fg="#FFFFFF" if aktiv or fertig else FARBE["seite_text"])
        c.delete("all")
        d = int(26 * self.s)
        if aktiv:
            c.create_oval(1, 1, d, d, fill=FARBE["akzent"], outline=FARBE["akzent"])
            c.create_text(d / 2 + 1, d / 2 + 1, text=str(j + 1), fill="#FFFFFF", font=fett(9))
        elif fertig:
            c.create_oval(1, 1, d, d, fill="#2A9D6A", outline="#2A9D6A")
            c.create_text(d / 2 + 1, d / 2 + 1, text="✓", fill="#FFFFFF", font=fett(9))
        else:
            c.create_oval(1, 1, d, d, outline="#3B4566", width=max(1, int(1.5 * self.s)))
            c.create_text(d / 2 + 1, d / 2 + 1, text=str(j + 1), fill=FARBE["seite_text"], font=fett(9))

    def _nav_hover(self, j, an):
        if j != self.schritt:
            self._nav_zeichnen(j, an)

    def _springen(self, i):
        if self.laeuft:
            return
        if i > self.schritt:
            for j in range(self.schritt, i):
                fehler = self._pruefe_schritt(j)
                if fehler:
                    self.zeige(j)
                    self.l_fehler.configure(text=fehler)
                    return
        self.zeige(i)

    def weiter(self):
        fehler = self._pruefe_schritt(self.schritt)
        if fehler:
            self.l_fehler.configure(text=fehler)
            return
        self.zeige(self.schritt + 1)

    def zurueck(self):
        if self.schritt > 0 and not self.laeuft:
            self.zeige(self.schritt - 1)

    def _pruefe_schritt(self, i) -> str:
        if i == 0:
            titel_fehlt = not self.v["titel"].get().strip()
            self.e_titel.fehler(titel_fehlt)
            if titel_fehlt:
                return "Bitte einen Titel eingeben."
            repo_ok = K.repo_name_gueltig(self.v["repo"].get().strip())
            self.e_repo.fehler(not repo_ok)
            if not repo_ok:
                return "Projektname: nur Buchstaben, Ziffern, - und _ (keine Leerzeichen oder Umlaute)."
            ziel = Path(self.v["zielordner"].get().strip() or ".")
            if not ziel.is_dir():
                return f"Speicherort existiert nicht: {ziel}"
            ordner = ziel / self.v["repo"].get().strip()
            if ordner.exists() and any(ordner.iterdir()):
                return f"Den Ordner {ordner} gibt es schon. Bitte einen anderen Projektnamen wählen."
        if i == 1 and not any(z[0] for z in self.liste_personen.werte()):
            return "Bitte mindestens eine Person mit Namen eintragen."
        if i == 2:
            logo = self.v["logo"].get().strip()
            if logo and not Path(logo).is_file():
                return "Die Logodatei wurde nicht gefunden."
        if i == 3 and not self.liste_kapitel.werte():
            return "Bitte mindestens ein Kapitel eintragen."
        if i == 5 and not (self.v["git_name"].get().strip() and self.v["git_email"].get().strip()):
            return "Bitte Name und E-Mail für Git eintragen."
        return ""

    # ----------------------------------------------------------------- Seitenlogik
    def _repo_vorschlagen(self, *_):
        if not self.repo_auto:
            return
        fuell = {"ein", "eine", "eines", "einer", "einem", "der", "die", "das", "des", "dem", "den", "fuer",
                 "und", "von", "mit", "im", "in", "zur", "zum", "auf", "am", "an", "bei", "ueber", "zu"}
        woerter = [w for w in K.slug(self.v["titel"].get()).split("-") if w and w not in fuell]
        self.v["repo"].set("-".join(w.capitalize() for w in woerter[:4]) if self.v["titel"].get().strip() else "")

    def _pfad_anzeigen(self):
        repo = self.v["repo"].get().strip() or "…"
        self.l_pfad.configure(text=str(Path(self.v["zielordner"].get().strip() or ".") / repo))

    def _ordner_waehlen(self):
        d = filedialog.askdirectory(initialdir=self.v["zielordner"].get() or str(Path.home()))
        if d:
            self.v["zielordner"].set(str(Path(d)))

    def _logo_waehlen(self):
        d = filedialog.askopenfilename(filetypes=[("Bilder", "*.png *.jpg *.jpeg *.pdf")])
        if d:
            self.v["logo"].set(str(Path(d)))

    def _logo_anzeigen(self):
        pfad = self.v["logo"].get().strip()
        self._logo_bild = None
        if pfad.lower().endswith(".png") and Path(pfad).is_file():
            try:
                bild = tk.PhotoImage(file=pfad)
                f = max(1, -(-bild.height() // int(40 * self.s)), -(-bild.width() // int(110 * self.s)))
                self._logo_bild = bild.subsample(f, f)
                self.logo_vorschau.configure(image=self._logo_bild, text="", width=0, height=0)
                return
            except tk.TclError:
                pass
        text = Path(pfad).suffix.upper().lstrip(".") if pfad and Path(pfad).is_file() else "kein Logo"
        self.logo_vorschau.configure(image="", text=text, width=10, height=2)

    def _sammlung(self):
        return self.v["sammlung"].get().strip() or self.v["repo"].get().strip()

    def _zotero_hilfe_text(self):
        self.zotero_hilfe.configure(text=(
            "1.  Zotero öffnen\n"
            "2.  Links Rechtsklick auf „Meine Bibliothek“ → „Neue Sammlung…“\n"
            f"3.  Name: {self._sammlung() or '(Projektname)'}\n"
            "4.  Quellen in diese Sammlung ziehen – beim nächsten Build stehen sie in literatur.bib.\n\n"
            "Die Sammlung kann auch später angelegt werden; das Projekt funktioniert trotzdem."))

    def _check_setzen(self, key, ok, detail=""):
        c, d = self.checks[key]
        c.delete("all")
        r = int(20 * self.s)
        if ok is None:
            c.create_oval(1, 1, r, r, outline=FARBE["rand_hover"], width=max(1, int(1.5 * self.s)))
        elif ok == "laeuft":
            c.create_oval(1, 1, r, r, outline=FARBE["akzent"], width=max(1, int(2 * self.s)), dash=(3, 2))
        else:
            farbe = FARBE["ok"] if ok else FARBE["fehler"]
            c.create_oval(1, 1, r, r, fill=farbe, outline=farbe)
            c.create_text(r / 2 + 1, r / 2 + 1, text="✓" if ok else "✕", fill="#FFFFFF", font=fett(8))
        d.configure(text=detail)

    def _zotero_pruefen(self):
        name = self._sammlung()
        for k in self.checks:
            self._check_setzen(k, "laeuft")

        def lauf():
            z = K._http_get(f"{K.ZOTERO}/connector/ping")[0] == 200
            bbt = (K._http_get(f"{K.ZOTERO}/better-bibtex/cayw?probe=true")[0] == 200) if z else None
            sam, detail = None, ""
            if bbt and name:
                sam, msgs = K.zotero_status(name)
                detail = msgs[-1].rsplit("(", 1)[-1].rstrip(").") if sam else "noch nicht angelegt"
            elif bbt:
                detail = "erst Projektname eingeben"

            def anzeigen():
                self._check_setzen("zotero", z, "" if z else "Zotero starten und erneut prüfen")
                self._check_setzen("bbt", bbt, "" if bbt or bbt is None else "Plugin installieren (siehe Anleitung)")
                self._check_setzen("sammlung", sam, detail)
            self._ui(anzeigen)
        threading.Thread(target=lauf, daemon=True).start()

    def _github_umschalten(self):
        if self.v["github"].get():
            self.gh_bereich.pack(fill="x", pady=(int(16 * self.s), 0))
        else:
            self.gh_bereich.pack_forget()
        self.after(50, self.scroll._anpassen)

    def _github_testen(self):
        self.l_gh.configure(text="Verbinde … (beim ersten Mal öffnet sich ggf. der Browser zur Anmeldung)",
                            fg=FARBE["leise"])

        def lauf():
            try:
                login = K.github_login()
                self._ui(lambda: self.l_gh.configure(text=f"✓  Angemeldet als {login}", fg=FARBE["ok"]))
            except Exception as e:  # noqa: BLE001
                meldung = str(e)
                self._ui(lambda: self.l_gh.configure(text=f"✕  {meldung}", fg=FARBE["fehler"]))
        threading.Thread(target=lauf, daemon=True).start()

    def _voraussetzungen(self):
        fehlt = [n for n, ok in (("Git", K.git_vorhanden()), ("latexmk", K.latexmk_vorhanden())) if not ok]
        self.status_tools.configure(
            text=("⚠  Nicht gefunden: " + ", ".join(fehlt) + "\n     siehe Anleitung") if fehlt
            else "●  Git und LaTeX gefunden",
            fg="#FBBF24" if fehlt else "#5FD39A")

    # ----------------------------------------------------------------- Erstellen
    def _werte(self) -> dict:
        w = {k: v.get() for k, v in self.v.items()}
        w["autoren"] = self.liste_personen.werte()
        w["kapitel"] = [z[0] for z in self.liste_kapitel.werte()]
        return w

    def _projekt(self, w: dict) -> K.Projekt:
        return K.Projekt(
            repo=w["repo"].strip(), zielordner=Path(w["zielordner"].strip() or "."), titel=w["titel"].strip(),
            art=w["art"].strip() or "Projektbericht",
            autoren=[K.Autor(a[0], a[1] if len(a) > 1 else "") for a in w["autoren"] if a and a[0]],
            hochschule=w["hochschule"].strip(), studiengang=w["studiengang"].strip(), modul=w["modul"].strip(),
            kurs=w["kurs"].strip(), betreuer=w["betreuer"].strip(),
            betreuer_bezeichnung=w["betreuer_bezeichnung"].strip(), abgabe=w["abgabe"].strip(),
            kapitel=w["kapitel"], logo=w["logo"].strip(), ki_werkzeug=w["ki_werkzeug"].strip(),
            sammlung=w["sammlung"].strip(), git_name=w["git_name"].strip(), git_email=w["git_email"].strip(),
            github=bool(w["github"]), github_owner=w["github_owner"].strip() if w["github"] else "",
            github_privat=bool(w["github_privat"]))

    def _zusammenfassung(self):
        for c in self.zusammenfassung.winfo_children():
            c.destroy()
        p = self._projekt(self._werte())
        gh = ("nein, nur lokal" if not p.github else
              f"{p.github_owner or 'eigenes Konto'} / {p.repo}  ·  {'privat' if p.github_privat else 'öffentlich'}")
        zeilen = [
            ("Titel", p.titel or "–"), ("Art", p.art),
            ("Personen", ", ".join(a.name for a in p.autoren) or "–"),
            ("Kapitel", f"{len(p.kapitel)}  ·  " + ", ".join(p.kapitel)),
            ("Ordner", str(p.ordner)), ("Zotero-Sammlung", p.sammlung_name or "–"), ("GitHub", gh),
        ]
        self.zusammenfassung.columnconfigure(1, weight=1)
        for r, (k, v) in enumerate(zeilen):
            tk.Label(self.zusammenfassung, text=k, bg=FARBE["karte"], fg=FARBE["leise"], font=norm(10),
                     anchor="w").grid(row=r, column=0, sticky="nw", pady=int(3 * self.s), padx=(0, int(24 * self.s)))
            tk.Label(self.zusammenfassung, text=v, bg=FARBE["karte"], fg=FARBE["text"], font=fett(10),
                     anchor="w", justify="left", wraplength=int(600 * self.s)).grid(
                row=r, column=1, sticky="w", pady=int(3 * self.s))

    def _log(self, text, tag=""):
        def tun():
            self.konsole.configure(state="normal")
            self.konsole.insert("end", text + "\n", tag)
            self.konsole.see("end")
            self.konsole.configure(state="disabled")
        self._ui(tun)

    def _fortschritt(self, wert):
        self._ui(lambda: self.fortschritt.configure(value=wert))

    def _start(self):
        if self.laeuft:
            return
        for j in range(len(SCHRITTE) - 1):
            fehler = self._pruefe_schritt(j)
            if fehler:
                self.zeige(j)
                self.l_fehler.configure(text=fehler)
                return
        w = self._werte()
        p = self._projekt(w)
        fehler = K.pruefen(p)
        if fehler:
            messagebox.showerror("Bitte prüfen", "\n\n".join(fehler))
            return
        try:
            if self.demo:
                raise OSError("Demo-Modus speichert nichts")
            EINSTELLUNGEN.parent.mkdir(parents=True, exist_ok=True)
            EINSTELLUNGEN.write_text(json.dumps({k: w[k] for k in GEMERKT}, ensure_ascii=False, indent=2),
                                     encoding="utf-8")
        except OSError:
            pass
        self.laeuft = True
        self.k_erstellen.setze_aktiv(False)
        self.k_zurueck.setze_aktiv(False)
        for c in self.aktionen.winfo_children():
            c.destroy()
        self.konsole.configure(state="normal")
        self.konsole.delete("1.0", "end")
        self.konsole.configure(state="disabled")
        threading.Thread(target=self._erstellen, args=(p, bool(w["vscode"])), daemon=True).start()

    def _erstellen(self, p: K.Projekt, vscode: bool) -> None:
        log = self._log
        ergebnis = {"ordner": p.ordner}
        try:
            log("▸ Dateien anlegen", "titel")
            K.projekt_schreiben(p, lambda t: log(t, "leise"))
            self._fortschritt(30)
            log("▸ Git-Repository anlegen", "titel")
            K.git_init(p, lambda t: log(t, "leise"))
            self._fortschritt(50)
            if p.github:
                log("▸ GitHub (beim ersten Mal öffnet sich ggf. der Browser zur Anmeldung)", "titel")
                ergebnis["url"] = K.github_erstellen(p, lambda t: log(t, "leise"))
            self._fortschritt(85)
            log("▸ Zotero", "titel")
            ok, msgs = K.zotero_status(p.sammlung_name)
            for msg in msgs:
                log("  " + msg, "leise" if ok or msg != msgs[-1] else "warn")
            self._fortschritt(100)
            log("\n✓ Fertig! Das Projekt ist angelegt.", "ok")
            if "url" in ergebnis:
                log("  GitHub baut jetzt das erste PDF (ca. 2–3 Minuten, Reiter „Actions“).", "ok")
            if not ok:
                log(f"  Noch zu tun: in Zotero die Sammlung „{p.sammlung_name}“ anlegen.", "warn")
            if vscode and not K.vscode_oeffnen(p.ordner):
                log("  VS Code wurde nicht gefunden – den Ordner bitte selbst öffnen.", "warn")
            self._ui(lambda: self._fertig(ergebnis))
        except Exception as e:  # noqa: BLE001
            log(f"\n✕ Fehler: {e}", "fehler")
            log("Bereits erstellte Dateien bleiben erhalten. Ordner löschen und erneut versuchen "
                "oder in der Anleitung unter „Probleme lösen“ nachsehen.", "leise")
            self._fortschritt(0)

            def zuruecksetzen():
                self.laeuft = False
                self.k_erstellen.setze_aktiv(True)
                self.k_zurueck.setze_aktiv(True)
            self._ui(zuruecksetzen)

    def _fertig(self, ergebnis):
        self.laeuft = False
        self.k_zurueck.setze_aktiv(True)
        self.k_erstellen.configure(text="✓  Erstellt", bg=FARBE["ok"], fg="#FFFFFF")
        ordner = ergebnis["ordner"]
        Knopf(self.aktionen, "Ordner öffnen", lambda: ordner_oeffnen(ordner), art="sekundaer").pack(side="left")
        Knopf(self.aktionen, "In VS Code öffnen", lambda: K.vscode_oeffnen(ordner), art="sekundaer").pack(
            side="left", padx=int(8 * self.s))
        if ergebnis.get("url"):
            Knopf(self.aktionen, "Repository auf GitHub", lambda: webbrowser.open(ergebnis["url"]),
                  art="sekundaer").pack(side="left")
        Knopf(self.aktionen, "Neues Projekt", self._neu, art="link").pack(side="right")

    def _neu(self):
        self.v["titel"].set("")
        self.v["sammlung"].set("")
        self.repo_auto = True
        self._repo_vorschlagen()
        self.k_erstellen.configure(text="Projekt erstellen")
        self.k_erstellen.setze_aktiv(True)
        self.fortschritt.configure(value=0)
        for c in self.aktionen.winfo_children():
            c.destroy()
        self.zeige(0)


def main():
    if WIN:
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except (AttributeError, OSError):
            pass
    App(demo="--demo" in sys.argv).mainloop()


if __name__ == "__main__":
    main()
