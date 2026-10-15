#!/usr/bin/env bash
# installer/windows/prepara_pmn.sh - lanciato da installa_pmn.ps1 come root dentro la WSL "pmn", dalla cartella installer/windows.
# Crea l'utente Linux "pmn" (senza password: nessuna domanda all'utente) e copia installer/ e motore/ nella sua cartella.
# Si puo' rilanciare: rifa' solo la copia.
set -euo pipefail
id pmn > /dev/null 2>&1 || useradd -m -s /bin/bash pmn
grep -q '^default=pmn' /etc/wsl.conf 2> /dev/null || printf '\n[user]\ndefault=pmn\n' >> /etc/wsl.conf
radice=$(cd ../.. && pwd)
rm -rf /home/pmn/profilemetananni
mkdir -p /home/pmn/profilemetananni
cp -r "$radice/installer" "$radice/motore" /home/pmn/profilemetananni/
rm -rf /home/pmn/profilemetananni/motore/__pycache__
chown -R pmn:pmn /home/pmn/profilemetananni
echo OK
