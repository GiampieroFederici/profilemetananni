#!/usr/bin/env bash
# installer/windows/prepara_pmn.sh - lanciato da installa_pmn.ps1 come root dentro la WSL "pmn", dalla cartella installer/windows.
# Crea l'utente Linux "pmn" (senza password: nessuna domanda all'utente) e copia nella sua cartella cio' che serve al motore:
# installer/, motore/ e bin/, steps/, refs/ (run.sh, passi della pipeline, tabelle; senza steps/ pmn-motore non parte).
# Imposta la lettura anticipata del disco a 16 KB a ogni avvio di questa WSL (serve solo al motore): Kraken completo
# con --memory-mapping legge pezzi sparsi del database e con gli 8 MB di WSL rilegge 8 MB per ogni pezzo
# (S2.2: ~108 h stimate contro 41 min a 16 KB, risultati identici al byte).
# Si puo' rilanciare: rifa' solo la copia.
set -euo pipefail
id pmn > /dev/null 2>&1 || useradd -m -s /bin/bash pmn
grep -q '^default=pmn' /etc/wsl.conf 2> /dev/null || printf '\n[user]\ndefault=pmn\n' >> /etc/wsl.conf
LA=/usr/local/sbin/pmn_lettura_anticipata.sh
printf '#!/bin/sh\n# profilemetananni: lettura anticipata 16 KB sul disco di questa WSL (installer/windows/prepara_pmn.sh)\necho 16 > "/sys/block/$(basename "$(findmnt -no SOURCE /)")/queue/read_ahead_kb"\n' > "$LA"
chmod 755 "$LA"
if ! grep -q "^command=$LA" /etc/wsl.conf; then
  if grep -q '^\[boot\]' /etc/wsl.conf; then sed -i "/^\[boot\]/a command=$LA" /etc/wsl.conf   # Ubuntu 24.04 ha gia' [boot] systemd=true
  else printf '\n[boot]\ncommand=%s\n' "$LA" >> /etc/wsl.conf; fi
fi
"$LA"   # subito, senza aspettare il prossimo avvio
radice=$(cd ../.. && pwd)
rm -rf /home/pmn/profilemetananni
mkdir -p /home/pmn/profilemetananni
cp -r "$radice/installer" "$radice/motore" "$radice/bin" "$radice/steps" "$radice/refs" /home/pmn/profilemetananni/
find /home/pmn/profilemetananni -name __pycache__ -type d -prune -exec rm -rf {} +
chown -R pmn:pmn /home/pmn/profilemetananni
echo OK
