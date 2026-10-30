#!/usr/bin/env bash
# installer/verifica_motore.sh - prova finale dell'installazione (D032, D037):
#   versioni dei programmi chiave, programmi avviabili, mini-campione di regressione (200.000 coppie di SF3RAt7)
#   con MD5 identici a installer/riferimenti.tsv. Esce con 0 solo se e' tutto VERDE.
#   B3-4 (VM 30/10, 8 GB): esce con 3 e la riga MEMORIA_INSUFFICIENTE se memoria + swap di Linux sono sotto 9 GB
#   (picco di MetaPhlAn a fette 8,2 GB, come installa_motore.sh) o se Linux chiude un programma per memoria (137):
#   non e' un motore da reinstallare. PMN_MEMINFO solo per le prove.
# Uso: bash installer/verifica_motore.sh   (PMN_HOME predefinita ~/.pmn)
set -euo pipefail
PMN_HOME=${PMN_HOME:-$HOME/.pmn}
. "$PMN_HOME/installazione.env"
mem_kb=$(awk '/^(MemTotal|SwapTotal):/ {s += $2} END {printf "%.0f\n", s}' "${PMN_MEMINFO:-/proc/meminfo}")
if [ "$mem_kb" -lt $((9 * 1024 * 1024)) ]; then echo "MEMORIA_INSUFFICIENTE memoria + swap $mem_kb kB, servono 9 GB"; exit 3; fi
RIF=$PMN_ROOT/installer/riferimenti.tsv
val() { awk -F'\t' -v k="$1" '$1 == k {print $2}' "$RIF"; }
esito=0
controlla() {  # nome trovato atteso
  if [ -n "$3" ] && [ "$2" = "$3" ]; then echo "OK      $1 = $2"; else echo "DIVERSO $1: atteso '$3', trovato '$2'"; esito=1; fi
}

# versioni installate (dai metadati degli ambienti) e programmi che partono davvero
for k in $(awk -F'\t' '$1 ~ /\// {print $1}' "$RIF"); do
  env=${k%/*}; pkg=${k#*/}
  f=$(ls "$PMN_ENVS/$env/conda-meta/" | grep -m1 "^$pkg-[0-9]" || true)
  v=${f#"$pkg"-}; controlla "$k" "${v%%-*}" "$(val "$k")"
done
for c in pmn_metaphlan/metaphlan pmn_metaphlan/bowtie2 pmn_kraken/kraken2 pmn_trim/fastp pmn_hostfilter/samtools pmn_download/prefetch; do
  if "$PMN_ENVS/${c%/*}/bin/${c#*/}" --version > /dev/null 2>&1; then echo "OK      ${c#*/} si avvia"; else echo "DIVERSO ${c#*/} non si avvia"; esito=1; fi
done

# mini-campione di regressione
O=$PMN_TMP/verifica_$$
rm -rf "$O" "$O.log"
if ! bash "$PMN_ROOT/motore/metaphlan_fette.sh" mini "$PMN_PROVA/mini_SF3RAt7_1.fastq.gz" "$PMN_PROVA/mini_SF3RAt7_2.fastq.gz" "$O" 8 2>&1 | tee "$O.log"; then
  if grep -qE 'exited with value 137|Killed|Out of memory|Cannot allocate memory' "$O.log"; then
    echo "MEMORIA_INSUFFICIENTE Linux ha chiuso un programma per memoria"; rm -rf "$O" "$O.log"; exit 3
  fi
  rm -rf "$O" "$O.log"; echo "DIVERSO mini: MetaPhlAn a fette non ha finito"; echo "ROSSO"; exit 1
fi
rm -f "$O.log"
controlla "mini: mapout (righe ordinate)" "$(sort "$O/mini.mapout" | md5sum | cut -d' ' -f1)" "$(val mini_mapout_ordinato)"
controlla "mini: profilo (senza la riga del comando)" "$(sed 2d "$O/mini_profile.txt" | md5sum | cut -d' ' -f1)" "$(val mini_profilo)"
rm -rf "$O"

if [ "$esito" = 0 ]; then echo "VERDE"; else echo "ROSSO"; fi
exit "$esito"
