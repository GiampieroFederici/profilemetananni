#!/usr/bin/env bash
# installer/linux/installa_da_internet.sh - installa ProfileMetaNanni su Ubuntu con un solo comando (P5, 12/11).
# Questo file e' il modello: installer/linux/costruisci_pacchetto_linux.py scrive la versione e l'impronta del
# pacchetto nelle due righe VERSIONE e SHA256 qui sotto e lo salva come installa_profilemetananni_linux.sh, il file
# che va nella Release accanto al pacchetto. La persona incolla nel terminale una riga sola:
#   wget -nv -O- https://github.com/GiampieroFederici/profilemetananni/releases/latest/download/installa_profilemetananni_linux.sh | bash
# oppure scarica il file e lancia: bash installa_profilemetananni_linux.sh. Lo script:
#   1. scarica profilemetananni_v<versione>_linux.tar.gz dalla Release, solo HTTPS verso GitHub (curl, oppure wget);
#   2. controlla l'impronta SHA-256 prima di aprirlo: se non torna si ferma e non estrae nulla;
#   3. lo estrae in una cartella temporanea e lancia installer/linux/installa_pmn.sh con gli argomenti ricevuti (per
#      esempio "... | bash -s -- --si"). Se lo script arriva da una pipe, la risposta alla domanda dell'installatore
#      si legge dal terminale (/dev/tty);
#   4. cancella la cartella temporanea: il programma e' gia' stato copiato in PMN_HOME/programma.
# Niente sudo. Tutto il lavoro sta in principale(), chiamata all'ultima riga: uno scarico troncato non esegue nulla.
# Messaggi in italiano se LANG comincia per "it", altrimenti in inglese (come installa_pmn.sh).
set -euo pipefail
umask 022

VERSIONE=@VERSIONE@
SHA256=@SHA256@

case "${LANG:-}" in it*) LINGUA=it ;; *) LINGUA=en ;; esac
declare -A EN=(
  ["ERRORE"]="ERROR"
  ["Questo file è il modello dello script: quello da usare è installa_profilemetananni_linux.sh, nella Release su GitHub."]="This file is the template of the script: the one to use is installa_profilemetananni_linux.sh, in the release on GitHub."
  ["Non lanciare questo comando con sudo: installa tutto nella tua cartella personale, senza permessi di amministratore."]="Do not run this command with sudo: it installs everything in your home folder, without administrator rights."
  ["Prima di scaricare i database l'installazione fa una domanda, ma qui non c'è un terminale per rispondere. Lancia il comando da un terminale, oppure aggiungi --si."]="Before downloading the databases the installation asks a question, but there is no terminal here to answer. Run the command from a terminal, or add --si."
  ["Per scaricare il programma serve curl oppure wget. Lancia questa riga, poi di nuovo lo stesso comando:"]="To download the program, curl or wget is needed. Run this line, then the same command again:"
  ["Scarico ProfileMetaNanni %s per Linux..."]="Downloading ProfileMetaNanni %s for Linux..."
  ["Non riesco a scaricare il programma da GitHub. Controlla la connessione e rilancia lo stesso comando."]="I cannot download the program from GitHub. Check the connection and run the same command again."
  ["Il file scaricato non è quello pubblicato (impronta SHA-256 diversa): non l'ho aperto. Rilancia lo stesso comando; se succede ancora, scarica il pacchetto per Linux dalla pagina della Release su GitHub."]="The downloaded file is not the published one (different SHA-256 checksum): I did not open it. Run the same command again; if it happens again, download the Linux package from the release page on GitHub."
  ["Ho già cancellato io quella cartella temporanea: non devi fare altro."]="I have already deleted that temporary folder: you have nothing else to do."
)
# shellcheck disable=SC2059
T() { local f=$1; shift; if [ "$LINGUA" = en ] && [ -n "${EN[$f]+x}" ]; then f=${EN[$f]}; fi; printf -- "$f" "$@"; }
dice() { printf '[PMN] %s\n' "$(T "$@")"; }
fallisci() { printf '[PMN] %s: %s\n' "$(T 'ERRORE')" "$(T "$@")" >&2; exit 1; }

CARTELLA=""   # cartella temporanea dello scarico: si cancella sempre, comunque finisca
trap 'if [ -n "$CARTELLA" ]; then rm -rf "$CARTELLA"; fi' EXIT

principale() {
  # versione e impronta entrano nell'indirizzo e nel controllo: solo cifre e punti, solo 64 cifre esadecimali
  [[ $VERSIONE =~ ^[0-9]+\.[0-9]+\.[0-9]+$ && $SHA256 =~ ^[0-9a-f]{64}$ ]] \
    || fallisci 'Questo file è il modello dello script: quello da usare è installa_profilemetananni_linux.sh, nella Release su GitHub.'
  [ "$(id -u)" != 0 ] || fallisci 'Non lanciare questo comando con sudo: installa tutto nella tua cartella personale, senza permessi di amministratore.'

  # Da dove l'installatore legge la risposta a "Procedo con l'installazione? (s/n)". Con "wget ... | bash" l'ingresso
  # di questo script e' la pipe, non la tastiera: all'installatore si passa il terminale. --si e --stima non chiedono.
  local a chiede=1 stima=0 ingresso=""
  for a in "$@"; do
    case "$a" in --si) chiede=0 ;; --stima) chiede=0; stima=1 ;; esac
  done
  if [ ! -t 0 ]; then
    if { : < /dev/tty; } 2> /dev/null; then ingresso=/dev/tty
    elif [ "$chiede" = 0 ]; then ingresso=/dev/null
    else fallisci "Prima di scaricare i database l'installazione fa una domanda, ma qui non c'è un terminale per rispondere. Lancia il comando da un terminale, oppure aggiungi --si."
    fi
  fi

  local nome=profilemetananni_v${VERSIONE}_linux.tar.gz
  local url=https://github.com/GiampieroFederici/profilemetananni/releases/download/v$VERSIONE/$nome
  local scarica
  if command -v curl > /dev/null; then
    scarica=(curl -fsSL --proto '=https' --proto-redir '=https' --retry 3 --connect-timeout 30 -o)
  elif command -v wget > /dev/null; then
    scarica=(wget -q --tries=3 --timeout=30 -O)
  else
    dice 'Per scaricare il programma serve curl oppure wget. Lancia questa riga, poi di nuovo lo stesso comando:'
    printf '    sudo apt install curl\n'
    exit 1
  fi
  CARTELLA=$(mktemp -d "${TMPDIR:-/tmp}/profilemetananni.XXXXXX")
  dice 'Scarico ProfileMetaNanni %s per Linux...' "$VERSIONE"
  "${scarica[@]}" "$CARTELLA/$nome" "$url" \
    || fallisci 'Non riesco a scaricare il programma da GitHub. Controlla la connessione e rilancia lo stesso comando.'
  local trovata resto
  read -r trovata resto < <(sha256sum < "$CARTELLA/$nome") || true
  [ "$trovata" = "$SHA256" ] \
    || fallisci "Il file scaricato non è quello pubblicato (impronta SHA-256 diversa): non l'ho aperto. Rilancia lo stesso comando; se succede ancora, scarica il pacchetto per Linux dalla pagina della Release su GitHub."
  tar -xzf "$CARTELLA/$nome" -C "$CARTELLA" --no-same-owner

  local r=0
  if [ -n "$ingresso" ]; then
    bash "$CARTELLA/profilemetananni/installer/linux/installa_pmn.sh" "$@" < "$ingresso" || r=$?
  else
    bash "$CARTELLA/profilemetananni/installer/linux/installa_pmn.sh" "$@" || r=$?
  fi
  rm -rf "$CARTELLA"; CARTELLA=""
  # installa_pmn.sh ha appena detto che la cartella da cui e' partita si puo' cancellare: e' quella temporanea
  if [ "$r" = 0 ] && [ "$stima" = 0 ]; then dice 'Ho già cancellato io quella cartella temporanea: non devi fare altro.'; fi
  exit "$r"
}

principale "$@"
