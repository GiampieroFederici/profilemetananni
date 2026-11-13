#!/usr/bin/env bash
# installer/linux/installa_pmn.sh - installa ProfileMetaNanni su Ubuntu (24.04, x86_64): motore e app, senza sudo.
# Un solo comando, rilanciabile: il motore riprende da dove era (installer/installa_motore.sh), l'ambiente dell'app
# non si rifa' se c'e' gia'.
#   1. controlla Linux a 64 bit e i programmi di sistema che servono al motore: se uno manca dice la riga apt e si ferma
#   2. copia il programma nella cartella fissa PMN_HOME/programma (la cartella scaricata si puo' poi cancellare) e da
#      li' installa il motore: bash installer/installa_motore.sh con gli argomenti ricevuti (--si, --catalogo FILE, ...)
#   3. crea l'ambiente dell'app (pmn_app: Python 3.12 + le versioni di PySide6 e PyYAML di app/requirements.txt) con il
#      micromamba che l'installatore del motore ha messo in PMN_HOME/bin
#   4. prova che l'app si apre senza schermo; se manca una libreria di sistema di Qt dice la riga apt
#   5. scrive il comando ~/.local/bin/profilemetananni e la voce di menu profilemetananni.desktop
# Uso: bash installer/linux/installa_pmn.sh [opzioni di installer/installa_motore.sh]
# Variabili: PMN_HOME (predefinita ~/.pmn). Messaggi in italiano se LANG comincia per "it", altrimenti in inglese.
set -euo pipefail
umask 022   # file 644, cartelle e comandi 755

PMN_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
export PMN_HOME=${PMN_HOME:-$HOME/.pmn}
case "${LANG:-}" in it*) LINGUA=it ;; *) LINGUA=en ;; esac
export PMN_LINGUA=${PMN_LINGUA:-$LINGUA}   # l'installatore del motore parla la stessa lingua

# --- testi per la persona: come in installa_motore.sh, la frase italiana e' la chiave (%s al posto dei valori) ---
declare -A EN=(
  ["ERRORE"]="ERROR"
  ["Non lanciare questo script con sudo: installa tutto nella tua cartella personale, senza permessi di amministratore."]="Do not run this script with sudo: it installs everything in your home folder, without administrator rights."
  ["Serve Linux a 64 bit (x86_64): questo computer è %s %s."]="64-bit Linux (x86_64) is needed: this computer is %s %s."
  ["PMN_HOME deve essere un percorso assoluto, non %s."]="PMN_HOME must be an absolute path, not %s."
  ["Mancano programmi di sistema che servono al motore. Lancia questa riga, poi di nuovo questo script:"]="Some system programs needed by the engine are missing. Run this line, then this script again:"
  ["Installo il motore: programmi e database. Può durare ore; se si interrompe, rilancia questo script e riprende."]="Installing the engine: programs and databases. It can take hours; if it stops, run this script again and it resumes."
  ["Non riesco a copiare il programma in %s. Controlla lo spazio libero e rilancia questo script."]="I cannot copy the program to %s. Check the free space and run this script again."
  ["L'installazione del motore si è fermata (codice %s). Se il motivo non è scritto qui sopra, manda a noi i file della cartella %s."]="The installation of the engine stopped (code %s). If the reason is not written above, send us the files of the folder %s."
  ["Il programma è installato in %s. La cartella da cui hai lanciato l'installazione (%s) non serve più: puoi cancellarla."]="The program is installed in %s. The folder you ran the installation from (%s) is not needed any more: you can delete it."
  ["Non trovo i programmi del motore in %s: rilancia questo script senza --solo-database."]="I cannot find the engine programs in %s: run this script again without --solo-database."
  ["Non trovo le versioni di PySide6 e PyYAML in %s."]="I cannot find the PySide6 and PyYAML versions in %s."
  ["L'ambiente dell'app c'è già (%s)."]="The app environment is already there (%s)."
  ["Preparo l'ambiente dell'app (Python 3.12, %s). Dettagli tecnici in %s"]="Preparing the app environment (Python 3.12, %s). Technical details in %s"
  ["Non riesco a preparare l'ambiente dell'app. Controlla la connessione e rilancia questo script. Dettagli tecnici in %s"]="I cannot prepare the app environment. Check the connection and run this script again. Technical details in %s"
  ["L'app non si apre. Manda a noi il file %s."]="The app does not open. Send us the file %s."
  ["Mancano librerie di sistema per le finestre dell'app. Prima di avviarla lancia questa riga:"]="Some system libraries for the app windows are missing. Before starting it, run this line:"
  ["Librerie mancanti senza un pacchetto che conosco: %s"]="Missing libraries without a package I know: %s"
  ["Non scrivo la voce di menu: il percorso %s ha caratteri che una voce di menu non accetta. Usa il comando qui sotto."]="I do not write the menu entry: the path %s has characters that a menu entry does not accept. Use the command below."
  ["Installazione finita. Avvia ProfileMetaNanni dal menu delle applicazioni, oppure con il comando: %s"]="Installation finished. Start ProfileMetaNanni from the applications menu, or with the command: %s"
)
# shellcheck disable=SC2059
T() { local f=$1; shift; if [ "$LINGUA" = en ] && [ -n "${EN[$f]+x}" ]; then f=${EN[$f]}; fi; printf -- "$f" "$@"; }
dice() { printf '[PMN] %s\n' "$(T "$@")"; }
fallisci() { printf '[PMN] %s: %s\n' "$(T 'ERRORE')" "$(T "$@")" >&2; exit 1; }

# ===================== 1. controlli =====================
[ "$(id -u)" != 0 ] || fallisci 'Non lanciare questo script con sudo: installa tutto nella tua cartella personale, senza permessi di amministratore.'
[ "$(uname -s)" = Linux ] && [ "$(uname -m)" = x86_64 ] \
  || fallisci 'Serve Linux a 64 bit (x86_64): questo computer è %s %s.' "$(uname -s)" "$(uname -m)"
[[ $PMN_HOME = /* ]] || fallisci 'PMN_HOME deve essere un percorso assoluto, non %s.' "$PMN_HOME"
# stesso elenco di installer/installa_motore.sh (tests/test_app_linux.py li confronta), come programma:pacchetto di Ubuntu
PROGRAMMI="curl:curl tar:tar gzip:gzip md5sum:coreutils sha256sum:coreutils awk:gawk df:coreutils ps:procps mkfifo:coreutils"
MANCANO=""
for x in $PROGRAMMI; do
  if ! command -v "${x%%:*}" > /dev/null; then
    case " $MANCANO " in *" ${x##*:} "*) ;; *) MANCANO="$MANCANO ${x##*:}" ;; esac
  fi
done
if [ -n "$MANCANO" ]; then
  dice 'Mancano programmi di sistema che servono al motore. Lancia questa riga, poi di nuovo questo script:'
  printf '    sudo apt install%s\n' "$MANCANO"
  exit 1
fi

# ===================== 2. programma e motore =====================
STIMA=0
for a in "$@"; do if [ "$a" = --stima ]; then STIMA=1; fi; done
# P8 (PC con Ubuntu, 12/11): il comando e la voce di menu puntavano alla cartella scaricata (per esempio sulla
# Scrivania): spostata o cancellata, il programma non partiva piu'. Come su Windows, il programma si copia in una
# cartella fissa (gli stessi file del pacchetto di Windows, piu' l'app) e motore, comando e voce di menu partono da
# li'. Si sostituisce solo se e' cambiato; lanciato da li' (o con --stima) questo script non copia nulla.
FISSA=$PMN_HOME/programma
SCARICATA=""
if [ "$STIMA" = 0 ] && [[ $PMN_ROOT/ != "$FISSA"/* ]] && ! [ "$PMN_ROOT" -ef "$FISSA" ]; then
  SCARICATA=$PMN_ROOT
  rm -rf "$FISSA.nuova" "$FISSA.vecchia"; mkdir -p "$FISSA.nuova"
  tar -C "$PMN_ROOT" --exclude=__pycache__ --exclude=.venv -cf - app bin installer motore refs steps | tar -C "$FISSA.nuova" -xf - \
    || fallisci 'Non riesco a copiare il programma in %s. Controlla lo spazio libero e rilancia questo script.' "$FISSA"
  if [ -d "$FISSA" ] && diff -rq -x __pycache__ "$FISSA" "$FISSA.nuova" > /dev/null; then
    rm -rf "$FISSA.nuova"   # stesso programma: resta com'e'
  else
    # il programma di un motore gia' installato cambia: l'installatore del motore non dira' "non ho cambiato nulla"
    if [ -d "$FISSA" ]; then export PMN_PROGRAMMA_SOSTITUITO=1; mv "$FISSA" "$FISSA.vecchia"; fi
    mv "$FISSA.nuova" "$FISSA"; rm -rf "$FISSA.vecchia"
  fi
  PMN_ROOT=$FISSA
fi
if [ "$STIMA" = 0 ]; then
  dice 'Installo il motore: programmi e database. Può durare ore; se si interrompe, rilancia questo script e riprende.'
fi
r=0; bash "$PMN_ROOT/installer/installa_motore.sh" "$@" || r=$?
if [ "$r" != 0 ]; then
  # P3, P7: con 2 (errore) e 3 (interrotta o annullata) l'installatore del motore ha gia' detto che cosa e' successo e
  # che cosa fare. Prima qui si aggiungeva "Il motore non è ancora installato ... Quando hai risolto, rilancia": falso
  # con un motore gia' installato, senza senso dopo un Ctrl+C. Una riga solo per un arresto senza spiegazione.
  if [ "$r" != 2 ] && [ "$r" != 3 ]; then
    dice "L'installazione del motore si è fermata (codice %s). Se il motivo non è scritto qui sopra, manda a noi i file della cartella %s." "$r" "$PMN_HOME/log"
  fi
  exit "$r"
fi
if [ "$STIMA" = 1 ]; then exit 0; fi   # solo la stima: non si installa nulla

# ===================== 3. ambiente dell'app =====================
# micromamba e gli ambienti stanno dove li ha messi installa_motore.sh: PMN_HOME/bin/micromamba e PMN_ENVS
# (installazione.env, di solito PMN_HOME/mamba/envs). L'ambiente pmn_app sta accanto a quelli del motore.
MM=$PMN_HOME/bin/micromamba
ENVS=$(awk -F= '$1 == "PMN_ENVS" { print $2; exit }' "$PMN_HOME/installazione.env" 2> /dev/null || true)
[[ $ENVS = /* ]] && [ -d "$ENVS" ] && [ -x "$MM" ] \
  || fallisci 'Non trovo i programmi del motore in %s: rilancia questo script senza --solo-database.' "$PMN_HOME"
MAMBA_ROOT_PREFIX=$(dirname "$ENVS"); export MAMBA_ROOT_PREFIX
APP=$ENVS/pmn_app
# -E -s: l'app usa solo i pacchetti del suo ambiente, non PYTHONPATH e non quelli di ~/.local della persona
PY=("$APP/bin/python" -E -s)
REQ=()
while IFS= read -r riga; do REQ+=("$riga"); done \
  < <(tr -d '\r' < "$PMN_ROOT/app/requirements.txt" | grep -E '^(PySide6|PyYAML)==[0-9][0-9A-Za-z.]*$')
[ "${#REQ[@]}" = 2 ] || fallisci 'Non trovo le versioni di PySide6 e PyYAML in %s.' "$PMN_ROOT/app/requirements.txt"
LOG=$PMN_HOME/log/installazione_app_$(date +%Y%m%d_%H%M%S).log
app_pronta() {   # l'ambiente c'e' e ha proprio le versioni chieste
  [ -x "$APP/bin/python" ] && "${PY[@]}" -c 'import sys
from importlib.metadata import version
sys.exit(0 if all(version(r.split("==")[0]) == r.split("==")[1] for r in sys.argv[1:]) else 1)' "${REQ[@]}" 2> /dev/null
}
if app_pronta; then
  dice "L'ambiente dell'app c'è già (%s)." "${REQ[*]}"
else
  dice "Preparo l'ambiente dell'app (Python 3.12, %s). Dettagli tecnici in %s" "${REQ[*]}" "$LOG"
  if [ ! -x "$APP/bin/python" ]; then
    rm -rf "${APP:?}"   # resti di un tentativo interrotto
    "$MM" create -y -q -p "$APP" --override-channels -c conda-forge python=3.12 pip >> "$LOG" 2>&1 \
      || fallisci "Non riesco a preparare l'ambiente dell'app. Controlla la connessione e rilancia questo script. Dettagli tecnici in %s" "$LOG"
    "$MM" clean -a -y >> "$LOG" 2>&1 || true   # la cache dei pacchetti non serve piu'
  fi
  "${PY[@]}" -m pip install --no-input --no-cache-dir --disable-pip-version-check "${REQ[@]}" >> "$LOG" 2>&1 && app_pronta \
    || fallisci "Non riesco a preparare l'ambiente dell'app. Controlla la connessione e rilancia questo script. Dettagli tecnici in %s" "$LOG"
fi

# ===================== 4. l'app si apre? =====================
# Librerie di sistema che Qt chiede per le finestre (X11) e che Ubuntu non sempre ha, come libreria:pacchetto.
# ldd le trova anche senza schermo; poi l'app si apre e si chiude davvero, con lo schermo finto di Qt (offscreen).
LIBRERIE_QT="libxcb-cursor.so.0:libxcb-cursor0 libxkbcommon-x11.so.0:libxkbcommon-x11-0 libxkbcommon.so.0:libxkbcommon0 libEGL.so.1:libegl1 libGL.so.1:libgl1 libfontconfig.so.1:libfontconfig1 libdbus-1.so.3:libdbus-1-3 libX11-xcb.so.1:libx11-xcb1 libxcb-icccm.so.4:libxcb-icccm4 libxcb-image.so.0:libxcb-image0 libxcb-keysyms.so.1:libxcb-keysyms1 libxcb-randr.so.0:libxcb-randr0 libxcb-render-util.so.0:libxcb-render-util0 libxcb-shape.so.0:libxcb-shape0 libxcb-shm.so.0:libxcb-shm0 libxcb-sync.so.1:libxcb-sync1 libxcb-xfixes.so.0:libxcb-xfixes0 libxcb-xkb.so.1:libxcb-xkb1 libxcb-util.so.1:libxcb-util1"
QT=$("${PY[@]}" -c 'import os, PySide6; print(os.path.dirname(PySide6.__file__))' 2>> "$LOG" || true)
PACCHETTI=""; IGNOTE=""
while IFS= read -r so; do
  [[ $so =~ ^lib[A-Za-z0-9_.+-]+$ ]] || continue
  p=""
  for x in $LIBRERIE_QT; do if [ "${x%%:*}" = "$so" ]; then p=${x##*:}; fi; done
  if [ -n "$p" ]; then PACCHETTI="$PACCHETTI $p"; else IGNOTE="$IGNOTE $so"; fi
done < <(ldd "$(find "$QT" -name libqxcb.so -print -quit 2> /dev/null)" 2> /dev/null | awk '/not found/ { print $1 }' | sort -u)
SI_APRE=1
(cd "$PMN_ROOT" && QT_QPA_PLATFORM=offscreen "${PY[@]}" - >> "$LOG" 2>&1 << 'PROVA'
from PySide6.QtWidgets import QApplication
from app import main
from app.finestra import Finestra
app = QApplication([])
main.prepara(app)
f = Finestra(movimento=False)
f.show()
app.processEvents()
f.close()
PROVA
) || SI_APRE=0
if [ "$SI_APRE" = 0 ] && [ -z "$PACCHETTI$IGNOTE" ]; then fallisci "L'app non si apre. Manda a noi il file %s." "$LOG"; fi

# ===================== 5. comando e voce di menu =====================
scrivi() {   # file testo: il file si riscrive solo se cambia
  [ "$(cat "$1" 2> /dev/null || true)" = "$2" ] || printf '%s\n' "$2" > "$1"
}
mkdir -p "$HOME/.local/bin" "$HOME/.local/share/applications"
LANCIATORE=$HOME/.local/bin/profilemetananni
scrivi "$LANCIATORE" "$(printf '#!/usr/bin/env bash\n# scritto da installer/linux/installa_pmn.sh: avvia ProfileMetaNanni\nexport PMN_HOME=%q\ncd %q && exec %q -E -s -m app.main "$@"' "$PMN_HOME" "$PMN_ROOT" "$APP/bin/python")"
chmod 755 "$LANCIATORE"
VOCE=$HOME/.local/share/applications/profilemetananni.desktop
ICONA=$PMN_ROOT/app/risorse/avatar_512.png
if [[ $LANCIATORE$ICONA =~ ^[A-Za-z0-9_./\ -]+$ ]]; then   # solo caratteri che Exec e Icon accettano cosi' come sono
  scrivi "$VOCE" "[Desktop Entry]
Type=Application
Name=ProfileMetaNanni
Comment=Metagenomics of cured meats: from the reads to the taxa
Comment[it]=Metagenomica dei salumi: dalle read ai taxa
Exec=\"$LANCIATORE\"
Icon=$ICONA
Terminal=false
Categories=Science;Biology;
StartupWMClass=ProfileMetaNanni"
  chmod 644 "$VOCE"
else
  dice 'Non scrivo la voce di menu: il percorso %s ha caratteri che una voce di menu non accetta. Usa il comando qui sotto.' "$LANCIATORE, $ICONA"
fi

if [ -n "$PACCHETTI" ]; then
  dice "Mancano librerie di sistema per le finestre dell'app. Prima di avviarla lancia questa riga:"
  printf '    sudo apt install%s\n' "$PACCHETTI"
fi
if [ -n "$IGNOTE" ]; then dice 'Librerie mancanti senza un pacchetto che conosco: %s' "${IGNOTE# }"; fi
if [ -n "$SCARICATA" ]; then
  dice "Il programma è installato in %s. La cartella da cui hai lanciato l'installazione (%s) non serve più: puoi cancellarla." "$PMN_ROOT" "$SCARICATA"
fi
dice 'Installazione finita. Avvia ProfileMetaNanni dal menu delle applicazioni, oppure con il comando: %s' "$LANCIATORE"
