"""Dateivorlagen für neue LaTeX-Projekte.

Platzhalter haben die Form <<NAME>> und werden in assistent_kern.py ersetzt.
"""

MAIN_TEX = r"""\documentclass[
  12pt,
  a4paper,
  oneside,
  parskip=half,
  bibliography=totoc,
  listof=totoc,
  captions=tableheading
]{scrreprt}

% --- Sprache & Schrift -------------------------------------------------
\usepackage[ngerman]{babel}
\usepackage[T1]{fontenc}
\usepackage{lmodern}
\usepackage{microtype}
\usepackage{csquotes}

% --- Layout --------------------------------------------------------------
\usepackage[left=3cm,right=2.5cm,top=2.5cm,bottom=2.5cm,headheight=30pt]{geometry}
\usepackage{setspace}
\onehalfspacing

% --- Mathe, Einheiten, Grafiken -----------------------------------------
\usepackage{amsmath,amssymb}
\usepackage{siunitx}
\sisetup{output-decimal-marker={,}, exponent-product=\cdot, inter-unit-product=\,}
\usepackage{graphicx}
\graphicspath{{bilder/}}
\usepackage{pdfpages}   % ganze PDF-Seiten einbinden (z. B. Schaltplan im Anhang)
\usepackage{booktabs}
\usepackage{tabularx}
\usepackage{pgfplots}
\pgfplotsset{compat=1.18}
\usepackage[european]{circuitikz}

% --- Logo ------------------------------------------------------------------
% \logo[Höhe] setzt bilder/logo.(pdf|png|jpg); fehlt die Datei, erscheint ein Platzhalter
\newcommand{\logo}[1][1cm]{%
  \IfFileExists{bilder/logo.pdf}{\includegraphics[height=#1]{bilder/logo}}{%
  \IfFileExists{bilder/logo.png}{\includegraphics[height=#1]{bilder/logo}}{%
  \IfFileExists{bilder/logo.jpg}{\includegraphics[height=#1]{bilder/logo}}{%
    {\fboxsep=0pt\fbox{\parbox[c][#1][c]{\dimexpr#1*5/2\relax}{\centering\tiny Logo fehlt}}}}}}}

% \bild[Breite]{Name} setzt bilder/Name.(pdf|png|jpg); fehlt die Datei, erscheint ein Platzhalter
\newcommand{\bild}[2][0.8\textwidth]{%
  \IfFileExists{bilder/#2.pdf}{\includegraphics[width=#1]{bilder/#2}}{%
  \IfFileExists{bilder/#2.png}{\includegraphics[width=#1]{bilder/#2}}{%
  \IfFileExists{bilder/#2.jpg}{\includegraphics[width=#1]{bilder/#2}}{%
    \fbox{\parbox[c][4cm][c]{#1}{\centering Platzhalter: bilder/\detokenize{#2}}}}}}}

% --- Kopf- und Fußzeile --------------------------------------------------
\usepackage[headsepline,plainheadsepline]{scrlayer-scrpage} % Linie unter Kopfzeile, auch auf Kapitelanfangsseiten
\clearpairofpagestyles
\automark{chapter}
\ihead*{\headmark}            % links: aktuelles Kapitel
\ohead*{\logo[0.8cm]}         % rechts: Logo (* = auch auf Kapitelanfangsseiten)
\cfoot*{\pagemark}            % unten mittig: Seitenzahl

% --- Abstände der Überschriften -------------------------------------------
% beforeskip: Abstand über der Überschrift, afterskip: Abstand zum folgenden Text
% (\baselineskip = eine Textzeile; parskip=half fügt nach der Überschrift noch eine halbe Zeile hinzu)
\RedeclareSectionCommand[beforeskip=1.5\baselineskip, afterskip=0.1\baselineskip]{chapter}
\RedeclareSectionCommand[beforeskip=1.5\baselineskip, afterskip=0.1\baselineskip]{section}
\RedeclareSectionCommand[beforeskip=1.5\baselineskip, afterskip=0.1\baselineskip]{subsection}

% --- Formelverzeichnis ---------------------------------------------------
% \formel{Beschreibung} innerhalb einer equation-Umgebung trägt die Formel ins Verzeichnis ein
\newcommand*{\listequationsname}{Formelverzeichnis}
\addtotoclist[float]{loe}
\setuptoc{loe}{totoc}
\newcommand*{\listofequations}{\listoftoc[\listequationsname]{loe}}
\DeclareTOCStyleEntry[level=1,indent=1.5em,numwidth=2.3em]{tocline}{equation}
\newcommand*{\formel}[1]{\addxcontentsline{loe}{equation}[\theequation]{#1}}

% --- Verzeichnisse ohne Seitenumbruch --------------------------------------
% \verzeichnis{\listof...} setzt ein Verzeichnis ohne neue Seite; passt es nicht
% mehr vollständig auf die aktuelle Seite, beginnt es auf der nächsten.
\newsavebox{\verzeichnisbox}
\newcommand{\verzeichnis}[1]{%
  \par
  \setbox\verzeichnisbox\vbox{\let\clearpage\relax \phantomsection #1}% Sprungziel für den Link im Inhaltsverzeichnis
  \ifdim\dimexpr\ht\verzeichnisbox+\dp\verzeichnisbox\relax>\dimexpr\pagegoal-\pagetotal\relax
    \clearpage
  \fi
  \unvbox\verzeichnisbox}

% --- Literatur -----------------------------------------------------------
\usepackage[backend=biber,style=ieee]{biblatex}

% Quellenart vor jedem Eintrag, wie im Zotero-Stil "IEEE mit Quellenart" (ieee-quellenart.csl)
\newcommand*{\quellenart}[2]{\ifentrytype{#1}{\def\quellenartlabel{#2}}{}}
\renewbibmacro*{begentry}{%
  \def\quellenartlabel{Sonstige Quelle}%
  \quellenart{online}{Onlinequelle}%
  \quellenart{book}{Buchquelle}%
  \quellenart{inbook}{Buchkapitel}%
  \quellenart{incollection}{Buchkapitel}%
  \quellenart{article}{Wissenschaftlicher Artikel}%
  \quellenart{inproceedings}{Konferenzbeitrag}%
  \quellenart{report}{Bericht / Technische Dokumentation}%
  \quellenart{manual}{Bericht / Technische Dokumentation}%
  \quellenart{standard}{Norm}%
  \quellenart{software}{Software / Repository}%
  \quellenart{thesis}{Abschlussarbeit}%
  \quellenart{video}{Videoquelle}%
  \quellenart{movie}{Videoquelle}%
  % bei Berichten das Zotero-Feld "Typ" verwenden, falls ausgefüllt (z. B. "Datenblatt")
  \ifboolexpr{(test {\ifentrytype{report}} or test {\ifentrytype{manual}})
              and not test {\iffieldundef{type}}}
    {\def\quellenartlabel{\thefield{type}}}{}%
  \printtext{[\quellenartlabel]}\setunit{\addspace}}
\addbibresource{literatur.bib}

% --- Links (zuletzt laden) -----------------------------------------------
\usepackage[hidelinks]{hyperref}

% --- Metadaten -----------------------------------------------------------
\newcommand{\arbeitstitel}{<<TITEL>>}
\newcommand{\autor}{<<AUTOR>>}

\begin{document}

\input{kapitel/00_titelseite}

\pagenumbering{Roman}
\input{kapitel/01_erklaerung}
\tableofcontents
\clearpage
\verzeichnis{\listoffigures}
\verzeichnis{\listoftables}
\verzeichnis{\listofequations}

\clearpage
\pagenumbering{arabic}

<<HAUPTKAPITEL>>

\printbibliography

\appendix
<<ANHANGKAPITEL>>

\end{document}
"""

TITELSEITE_TEX = r"""\begin{titlepage}
  \centering
  \logo[2.5cm]\par
  \vspace{1.5cm}
  {\Large <<HOCHSCHULE>>\par}
  \vspace{2cm}
  {\large <<ART>>\par}
  \vspace{1cm}
  {\huge\bfseries \arbeitstitel\par}
  \vspace{2cm}
  {\large \autor\par}
  \vfill
  \begin{tabular}{ll}
<<TABELLE>>
  \end{tabular}
\end{titlepage}
"""

ERKLAERUNG_EINZEL = r"""\chapter*{Eigenständigkeitserklärung}
\label{ch:eigenstaendigkeitserklaerung}

Ich versichere hiermit, dass ich die vorliegende Arbeit zum Thema \textit{\arbeitstitel} selbstständig verfasst und keine anderen als die angegebenen Quellen und Hilfsmittel verwendet habe, dass ich diese Arbeit bei keiner anderen Prüfung mit gleichem oder vergleichbarem Inhalt vorgelegt habe und dass sie bislang nicht veröffentlicht wurde.

Ich habe bei der Erstellung der Arbeit KI-Werkzeuge eingesetzt. Der Einsatz der Werkzeuge ist im Kapitel~\nameref{ch:ki-nutzung} genauer beschrieben.

\vspace{2cm}

\noindent
\begin{tabular}{@{}p{0.42\textwidth}@{}}
  \rule{\linewidth}{0.4pt} \\
  Ort, Datum, <<NAME1>> \\
\end{tabular}
"""

ERKLAERUNG_MEHRERE = r"""\chapter*{Eigenständigkeitserklärung}
\label{ch:eigenstaendigkeitserklaerung}

Wir versichern hiermit, dass wir die vorliegende Arbeit zum Thema \textit{\arbeitstitel} selbstständig verfasst und keine anderen als die angegebenen Quellen und Hilfsmittel verwendet haben, dass wir diese Arbeit bei keiner anderen Prüfung mit gleichem oder vergleichbarem Inhalt vorgelegt haben und dass sie bislang nicht veröffentlicht wurde.

Wir haben bei der Erstellung der Arbeit KI-Werkzeuge eingesetzt. Der Einsatz der Werkzeuge ist im Kapitel~\nameref{ch:ki-nutzung} genauer beschrieben.

\vspace{2cm}

\noindent
<<UNTERSCHRIFTEN>>
"""

KAPITEL_TEX = r"""\chapter{<<NAME>>}
\label{ch:<<LABEL>>}

% Text zu <<NAME>>. Quellen mit \cite{schluessel} zitieren
% (in VS Code: Alt+Shift+Z öffnet die Zotero-Suche und fügt \cite{...} ein).
"""

KI_NUTZUNG_TEX = r"""\chapter{Anmerkung zur Nutzung von Künstlicher Intelligenz}
\label{ch:ki-nutzung}

\begin{table}[htbp]
  \centering
  \caption{Übersicht über die verwendeten KI-basierten Werkzeuge}
  \begin{tabularx}{\textwidth}{@{}lX@{}}
    \toprule
    Werkzeug & Beschreibung der Nutzung \\
    \midrule
    <<KI_WERKZEUG>> &
      \textbullet~Korrekturlesen \newline
      \textbullet~Formatierung und Layout der Ausarbeitung \\
    \bottomrule
  \end{tabularx}
\end{table}
"""

ANHANG_TEX = r"""\chapter{Anhang}
\label{ch:anhang}

% Ganze PDF-Seite einbinden (z. B. Schaltplan), mit Eintrag im Abbildungsverzeichnis:
% \includepdf[
%   pages=1,
%   angle=90,      % Inhalt gedreht, die Seite selbst bleibt hochkant
%   scale=0.95,
%   pagecommand={\thispagestyle{empty}},
%   addtolist={1, figure, Beschreibung der Abbildung, fig:anhang1}
% ]{bilder/datei.pdf}
"""

LITERATUR_BIB = """% Diese Datei wird bei jedem Build aus Zotero überschrieben
% (Better BibTeX, Sammlung "<<SAMMLUNG>>", siehe latexmkrc).
"""

LATEXMKRC = """# Literatur vor jedem Build aus Zotero holen (Better BibTeX, Sammlung "<<SAMMLUNG>>").
# Läuft Zotero nicht (oder auf GitHub Actions), bleibt die vorhandene literatur.bib unverändert.
{
  my $url = 'http://127.0.0.1:23119/better-bibtex/export/collection?/1/<<SAMMLUNG_URL>>.biblatex';
  my $tmp = 'literatur.bib.zotero';
  if (system('curl', '-s', '-f', '-m', '5', '-o', $tmp, $url) == 0 && -s $tmp) {
    rename $tmp, 'literatur.bib';
    print "Zotero: literatur.bib aktualisiert\\n";
  } else {
    unlink $tmp;
    print "Zotero: nicht erreichbar oder Sammlung leer, literatur.bib bleibt wie sie ist\\n";
  }
}
"""

GITIGNORE = """# LaTeX-Hilfsdateien
*.aux
*.log
*.out
*.toc
*.lof
*.lot
*.loe
*.synctex.gz
*.synctex(busy)
*.fdb_latexmk
*.fls
*.bbl
*.blg
*.bcf
*.run.xml
*.xdv
*.nav
*.snm
*.figlist
*.makefile
*-figure*.pdf

# Erzeugtes PDF (wird von GitHub Actions gebaut)
/main.pdf
/build/
*-SAVE-ERROR
*.zotero
"""

BUILD_YML = """name: PDF bauen

on:
  push:
    branches: [main]
  workflow_dispatch:

permissions:
  contents: write   # nötig, um das Release "aktuell" anzulegen

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v5
      - uses: xu-cheng/latex-action@v3
        with:
          root_file: main.tex
      - uses: actions/upload-artifact@v5
        with:
          name: <<PDFNAME>>-PDF
          path: main.pdf
      - name: PDF als Release "aktuell" veröffentlichen
        env:
          GH_TOKEN: ${{ github.token }}
        run: |
          cp main.pdf <<PDFNAME>>.pdf
          gh release delete aktuell --yes --cleanup-tag || true
          gh release create aktuell <<PDFNAME>>.pdf \\
            --target "$GITHUB_SHA" --latest \\
            --title "Aktuelles PDF" \\
            --notes "Automatisch gebaut aus Commit ${GITHUB_SHA::7}."
      - name: Log bei Fehler hochladen
        if: failure()
        uses: actions/upload-artifact@v5
        with:
          name: LaTeX-Log
          path: |
            main.log
            main.blg
          if-no-files-found: ignore
"""

VSCODE_SETTINGS = """{
  "latex-workshop.latex.recipe.default": "latexmk",
  "latex-workshop.latex.autoBuild.run": "onSave",
  "latex-workshop.latex.autoClean.run": "onSucceeded",
  "latex-workshop.view.pdf.viewer": "tab",
  "git.autofetch": true,
  "git.autofetchPeriod": 60,
  "task.allowAutomaticTasks": "on",
  "git.enableSmartCommit": true,
  "git.postCommitCommand": "sync",
  "files.encoding": "utf8",
  "zotero-citation-picker.port": "http://127.0.0.1:23119/better-bibtex/cayw?format=latex&command=cite",
  "zotero-citation-picker.format": "configured",
  "editor.wordWrap": "wordWrapColumn",
  "editor.wordWrapColumn": 80
}
"""

VSCODE_TASKS = """{
  "version": "2.0.0",
  "tasks": [
    {
      "label": "Neueste Version von GitHub holen",
      "type": "shell",
      "command": "git pull --ff-only",
      "runOptions": { "runOn": "folderOpen" },
      "presentation": { "reveal": "silent", "panel": "shared" },
      "problemMatcher": []
    }
  ]
}
"""

VSCODE_EXTENSIONS = """{
  "recommendations": [
    "james-yu.latex-workshop",
    "mblode.zotero",
    "streetsidesoftware.code-spell-checker-german",
    "github.vscode-github-actions"
  ]
}
"""

README_MD = """# <<REPO>>

<<ART>>: *<<TITEL_PLAIN>>*

- Hauptdatei: `main.tex`, Kapitel liegen in `kapitel/`, Bilder in `bilder/`
- Literatur: `literatur.bib` (biblatex/biber), wird bei jedem Build aus der Zotero-Sammlung *<<SAMMLUNG>>* geholt (Better BibTeX)
- Lokal bauen: `latexmk -pdf main.tex` oder Speichern in VS Code (LaTeX Workshop)
- Bei jedem Push baut GitHub Actions das PDF (Reiter *Actions* → letzter Lauf → Artefakt *<<PDFNAME>>-PDF*)
<<PDFLINK>>"""
