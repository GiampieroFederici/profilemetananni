"""Ospiti da togliere (R8, D167): gli ospiti aggiunti dalla persona e il costo dell'indice Bowtie 2.

Un ospite aggiunto sta nel config.yaml del progetto, sotto `ospiti_personali`, e il suo nome in `hosts`:
    hosts: [mio_ospite]
    ospiti_personali:
      mio_ospite: {accession: GCF_000005845.2, basi: 4641652}      # codice dell'assembly NCBI
      altro: {fasta: /mnt/c/Users/io/genoma.fna.gz, basi: 5000000}  # file FASTA come lo vede il motore
`basi` (lunghezza del genoma) serve solo alla stima del tempo. L'indice si costruisce alla prima analisi
(steps/11_host_index.sh) e si riusa: nel motore installato sta in PMN_HOME/ospiti_utente/<nome>/, fuori dalla
cartella del programma, così un aggiornamento non lo perde.

Uso da bin/run.sh:  ospiti.py fonti CONFIG
  una riga per ospite aggiunto che il progetto usa: nome<TAB>accession|fasta<TAB>valore; uscita 1 se non valido.
Solo libreria standard (PyYAML solo per `fonti`, che gira con il python di pmn_reports_py).
"""
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NOME = re.compile(r"[A-Za-z][A-Za-z0-9_]{1,39}")            # nome breve: lettere, numeri, trattino basso
ACCESSION = re.compile(r"GC[AF]_[0-9]{9}\.[0-9]{1,3}")       # più stretta di validate_accession (bin/lib/validate.sh)
ESTENSIONI = (".fa", ".fasta", ".fna", ".fa.gz", ".fasta.gz", ".fna.gz")
# come validate_path_safe di bin/lib/validate.sh: niente $( ` ; | & < > ! * ?, controllo, - o ~ iniziali, /../
PERCORSO_NON_SICURO = re.compile(r"\$\(|[`;|&<>!*?]|^[-~]|[\x00-\x1f\x7f]|(^|/)\.\.(/|$)")
UMANI = {"grch38", "chm13", "homo_sapiens"}                  # l'uomo si toglie con filter_human
INSTALLATI = {"sus_scrofa", "bos_taurus", "ovis_aries", "grch38"}   # indici già nel motore (D021)
BASI = {"vitis_vinifera": 494_873_210}   # GCF_030704535.1, total_sequence_length di NCBI Datasets (30/10)

# Costo dell'indice Bowtie 2 (bowtie2-build 2.5.5, opzioni predefinite, 8 processori), per miliardo di basi.
# Misure: maiale Sscrofa11.1 2,47 Gbp 17 min 36 s di costruzione, RAM 5,3 GB; uomo GRCh38.p14 3,14 Gbp 22 min 30 s,
# 7,2 GB (14/10, S22_logs/ospite_SF3RAt7.log); E. coli K-12 4,6 Mbp 1,7 s, 0,11 GB (30/10, incarico OSPITE).
# Con 16 processori le fette di MetaPhlAn (2,5-3,0 Gbp) hanno preso 13-32 min: i processori contano poco.
MINUTI_PER_GBP = 7.2
RAM_GB_PER_GBP = 2.3
RAM_GB_FISSA = 0.2
INDICE_BYTE_PER_BASE = 1.4      # indice sul disco; il genoma da NCBI passa da TMPDIR (zip + FASTA) e poi si cancella
TEMPORANEO_BYTE_PER_BASE = 1.3
GZ_RAPPORTO = 3.3               # un FASTA .gz è circa 3,3 volte più piccolo (E. coli: 4.641.652 basi, 1.424.030 byte)
DOWNLOAD_BYTE_S = 4.1e6         # come motore/pmn_motore.py (rete di casa, 17/10)
ZIP_BYTE_PER_BASE = 0.31        # pacchetto NCBI (zip del FASTA)


def noti():
    """I nomi di refs/hosts.tsv."""
    with open(ROOT / "refs" / "hosts.tsv", encoding="utf-8") as f:
        return {r.split("\t")[0] for r in f.read().splitlines() if r.strip() and not r.startswith("#")}


def controlla(nome, voce):
    """(tipo, valore) di un ospite aggiunto, con tipo "accession" o "fasta"; ValueError se non va."""
    if not isinstance(nome, str) or not NOME.fullmatch(nome):
        raise ValueError(f"invalid host name {nome!r}: 2-40 letters, digits or underscore, starting with a letter")
    if nome in noti() or nome in UMANI:
        raise ValueError(f"invalid host name {nome!r}: already a host of refs/hosts.tsv")
    if not isinstance(voce, dict):
        raise ValueError(f"invalid ospiti_personali entry for {nome!r}")
    acc, fasta = voce.get("accession"), voce.get("fasta")
    if bool(acc) == bool(fasta):
        raise ValueError(f"invalid ospiti_personali entry for {nome!r}: give accession or fasta, one of the two")
    if acc:
        if not isinstance(acc, str) or not ACCESSION.fullmatch(acc):
            raise ValueError(f"invalid accession for host {nome!r}: GCF_ or GCA_, 9 digits, dot, version")
        return "accession", acc
    if not isinstance(fasta, str) or not fasta.startswith("/") or PERCORSO_NON_SICURO.search(fasta):
        raise ValueError(f"unsafe FASTA path for host {nome!r}")
    if not fasta.lower().endswith(ESTENSIONI):
        raise ValueError(f"invalid FASTA file for host {nome!r}: it must end in .fa, .fasta or .fna (also .gz)")
    return "fasta", fasta


def personali(cfg):
    """{nome: (tipo, valore)} degli ospiti aggiunti che il progetto usa (quelli in hosts), controllati."""
    voci = cfg.get("ospiti_personali") or {}
    if not isinstance(voci, dict):
        raise ValueError("invalid ospiti_personali: it must be a mapping name -> {accession | fasta}")
    return {h: controlla(h, voci[h]) for h in cfg.get("hosts") or [] if isinstance(h, str) and h in voci}


def stima(basi, scaricare=False):
    """Costo della costruzione dell'indice: {"secondi", "ram_gb", "disco_gb", "temporaneo_gb"}."""
    gbp = basi / 1e9
    secondi = 60 * MINUTI_PER_GBP * gbp + (basi * ZIP_BYTE_PER_BASE / DOWNLOAD_BYTE_S if scaricare else 0)
    return {"secondi": round(secondi), "ram_gb": round(RAM_GB_FISSA + RAM_GB_PER_GBP * gbp, 1),
            "disco_gb": round(INDICE_BYTE_PER_BASE * basi / 1e9, 1),
            "temporaneo_gb": round(TEMPORANEO_BYTE_PER_BASE * basi / 1e9, 1)}


def basi_del_file(percorso):
    """Basi di un FASTA dalla sua dimensione (un .gz si stima con GZ_RAPPORTO); None se non c'è."""
    try:
        byte = Path(percorso).stat().st_size
    except OSError:
        return None
    return round(byte * GZ_RAPPORTO) if str(percorso).lower().endswith(".gz") else byte


def da_costruire(cfg, cartella):
    """[(nome, secondi)] degli ospiti del progetto il cui indice non c'è ancora in `cartella` (PMN_HOME/ospiti_utente):
    la prima analisi lo costruisce. Gli indici di D021 sono installati; l'uomo è a parte (filter_human)."""
    voci = cfg.get("ospiti_personali") if isinstance(cfg.get("ospiti_personali"), dict) else {}
    out = []
    for h in cfg.get("hosts") or []:
        if not isinstance(h, str) or h in INSTALLATI or h in UMANI or not NOME.fullmatch(h):
            continue
        if any((Path(cartella) / h / f"{h}.1.{e}").is_file() for e in ("bt2", "bt2l")):
            continue
        voce = voci.get(h) if isinstance(voci.get(h), dict) else {}
        basi = voce.get("basi") if isinstance(voce.get("basi"), int) else None
        if basi is None and isinstance(voce.get("fasta"), str):
            basi = basi_del_file(voce["fasta"])
        basi = basi or BASI.get(h, 3_100_000_000)   # sconosciuto: come un genoma di mammifero, prudente
        out.append((h, stima(basi, scaricare=not voce.get("fasta"))["secondi"]))
    return out


def fonti(config):
    import yaml
    with open(config, encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    for nome, (tipo, valore) in personali(cfg if isinstance(cfg, dict) else {}).items():
        print(f"{nome}\t{tipo}\t{valore}")


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] != "fonti":
        sys.exit("usage: ospiti.py fonti CONFIG")
    try:
        fonti(sys.argv[2])
    except (OSError, ValueError) as e:
        sys.exit(f"invalid ospiti_personali in {os.path.basename(sys.argv[2])}: {e}")
