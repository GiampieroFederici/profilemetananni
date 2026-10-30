"""Il progetto dell'utente: una cartella con config.yaml (ingresso del motore, contratto §3) e risultati/.

Si scrive e si legge solo con yaml.safe_dump / yaml.safe_load. Il motore valida il contenuto
(CONFIG_NON_VALIDA): qui si controlla solo il nome della cartella.
"""
import gzip
import json
import os
import re
import tempfile
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

import yaml
from PySide6.QtCore import QStandardPaths

from app.lingua import _

NOME_VALIDO = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,59}")   # come project_name di config.example.yaml
CODICE_VALIDO = re.compile(r"[SED]RR[0-9]{1,13}")               # come validate_srr (bin/lib/validate.sh)
# coppie di file delle read come le trova il motore (contratto §3, motore/pmn_motore.py campioni_locali)
COPPIE_LOCALI = [("_1.fastq.gz", "_2.fastq.gz"), ("_R1.fastq.gz", "_R2.fastq.gz"),
                 ("_R1_001.fastq.gz", "_R2_001.fastq.gz"), ("_1.fq.gz", "_2.fq.gz"), ("_R1.fq.gz", "_R2.fq.gz")]
NOME_CAMPIONE = re.compile(r"(?![-.])[A-Za-z0-9._-]{1,64}")      # validate_name di bin/lib/validate.sh
PERCORSO_NON_SICURO = re.compile(r"[$`;|&<>!*?]|^-|[\x00-\x1f]")   # rifiutati da validate_path_safe del motore
INDICE_METAPHLAN = "mpa_vJan25_CHOCOPhlAnSGB_202503"             # versione fissata (config.example.yaml)


def cartella_progetti():
    """Documenti\\ProfileMetaNanni (R10: si parte da Documenti)."""
    return Path(QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation)) / "ProfileMetaNanni"


class Progetto:
    def __init__(self, cartella):
        self.cartella = Path(cartella)

    @property
    def nome(self):
        return self.cartella.name

    @property
    def config(self):
        return self.cartella / "config.yaml"

    @property
    def risultati(self):
        return self.cartella / "risultati"

    @property
    def segno_analisi(self):
        """B2 (P11): c'è mentre un'analisi gira; se resta (app chiusa, computer spento, analisi fermata o finita male)
        l'analisi è interrotta e si riprende da dove era."""
        return self.cartella / "analisi_avviata.txt"

    @property
    def interrotta(self):
        return self.segno_analisi.is_file()

    @property
    def codici_campioni(self):
        """Elenco dei codici SRR del progetto (paths.srr_list, un codice per riga)."""
        return self.cartella / "campioni.txt"

    def scrivi_codici(self, codici):
        self.cartella.mkdir(parents=True, exist_ok=True)
        self.codici_campioni.write_text("".join(c + "\n" for c in codici), encoding="utf-8")

    def leggi(self):
        if not self.config.is_file():
            return {}
        with open(self.config, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    def scrivi(self, dati):
        """Scrive config.yaml tutto o niente (file temporaneo accanto, poi sostituzione)."""
        self.cartella.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self.cartella, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                yaml.safe_dump(dati, f, allow_unicode=True, sort_keys=False)
            os.replace(tmp, self.config)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise


def nuovo(nome, radice=None):
    """Crea la cartella di un progetto nuovo. Nome: lettere, numeri, punto, trattino, trattino basso."""
    if not NOME_VALIDO.fullmatch(nome or ""):
        raise ValueError(_("Il nome può avere solo lettere senza accenti, numeri, punto, trattino e trattino basso "
                           "(massimo 60), e deve iniziare con una lettera o un numero."))
    cartella = Path(radice or cartella_progetti()) / nome
    if cartella.exists():
        raise FileExistsError(_("Esiste già un progetto che si chiama {nome}.", nome=nome))
    cartella.mkdir(parents=True)
    return Progetto(cartella)


def base(nome):
    """config.yaml di un progetto nuovo: schema di config.example.yaml e blocco `motore` (contratto §3).
    I valori vuoti lasciano al motore il consigliato per il database (refs/kraken_profili.tsv)."""
    return {
        "language": "it",
        "data_source": "ncbi",
        "project_name": nome,
        "hosts": ["sus_scrofa"],
        "filter_human": True,
        "paths": {"layout": "managed", "work_dir": "./pmn_work", "local_reads_dir": "", "srr_list": ""},
        "profiling": {"tool": "both", "metaphlan_index": INDICE_METAPHLAN, "kraken_confidence": "",
                      "bracken_readlen": 150, "abundance_threshold_pct": ""},
        "motore": {"metaphlan_modo": "fette", "kraken_db": "completo", "virus": False, "processori": 8},
        "execution": {"scheduler": "local", "threads": 8},
    }


def codici(testo):
    """Codici dei campioni scritti dall'utente, uno per riga: (validi senza doppioni, righe non riconosciute)."""
    validi, scartati = [], []
    for riga in (testo or "").splitlines():
        c = riga.strip().upper()
        if not c:
            continue
        if CODICE_VALIDO.fullmatch(c):
            if c not in validi:
                validi.append(c)
        else:
            scartati.append(riga.strip())
    return validi, scartati


def campioni_locali(cartella):
    """Campioni di una cartella di .fastq.gz con le regole del motore (contratto §3):
    ([(nome, primo file, secondo file o None)], [file di una coppia senza la sua compagna, che il motore salta])."""
    cartella = Path(cartella)
    file = sorted(f.name for f in cartella.iterdir() if f.is_file())
    out, usati = [], set()
    for s1, s2 in COPPIE_LOCALI:
        for f in file:
            nome = f[:-len(s1)]
            if f.endswith(s1) and nome + s2 in file and NOME_CAMPIONE.fullmatch(nome):
                out.append((nome, cartella / f, cartella / (nome + s2)))
                usati |= {f, nome + s2}
    suffissi = tuple(s for coppia in COPPIE_LOCALI for s in coppia)
    for f in file:
        if f.endswith((".fastq.gz", ".fq.gz")) and not f.endswith(suffissi):
            nome = f.removesuffix(".fastq.gz") if f.endswith(".fastq.gz") else f.removesuffix(".fq.gz")
            if NOME_CAMPIONE.fullmatch(nome):
                out.append((nome, cartella / f, None))
    saltati = [f for f in file if f.endswith(suffissi) and f not in usati]
    return out, saltati


# ---------------- ospiti aggiunti dalla persona (R8) ----------------
# Stesse regole di motore/ospiti.py (il motore le ricontrolla): nome breve, codice dell'assembly NCBI, file FASTA.
NOME_OSPITE = re.compile(r"[A-Za-z][A-Za-z0-9_]{1,39}")
ACCESSION = re.compile(r"GC[AF]_[0-9]{9}\.[0-9]{1,3}")
ESTENSIONI_FASTA = (".fa", ".fasta", ".fna", ".fa.gz", ".fasta.gz", ".fna.gz")
# nomi già usati dal motore (refs/hosts.tsv, che l'app impacchettata non ha: tests/test_ospiti_app.py li confronta)
OSPITI_DEL_MOTORE = {"sus_scrofa", "bos_taurus", "gallus_gallus", "ovis_aries", "grch38", "chm13", "phix",
                     "vitis_vinifera", "homo_sapiens"}
# costo dell'indice Bowtie 2: stesse costanti e fonti di motore/ospiti.py (misure del 14/10 e del 30/10)
MINUTI_PER_GBP, RAM_GB_PER_GBP, RAM_GB_FISSA = 7.2, 2.3, 0.2
INDICE_BYTE_PER_BASE, TEMPORANEO_BYTE_PER_BASE, GZ_RAPPORTO = 1.4, 1.3, 3.3
DOWNLOAD_BYTE_S, ZIP_BYTE_PER_BASE = 4.1e6, 0.31
BASI_GRANDE = 3_100_000_000             # dimensione sconosciuta: come un genoma di mammifero, prudente
NCBI_DATASETS = "https://api.ncbi.nlm.nih.gov/datasets/v2/genome/accession/{}/dataset_report"


def stima_indice(basi, scaricare=False):
    """Costo della costruzione dell'indice: {"minuti", "ram_gb", "disco_gb", "temporaneo_gb"}."""
    gbp = basi / 1e9
    secondi = 60 * MINUTI_PER_GBP * gbp + (basi * ZIP_BYTE_PER_BASE / DOWNLOAD_BYTE_S if scaricare else 0)
    return {"minuti": max(1, round(secondi / 60)), "ram_gb": round(RAM_GB_FISSA + RAM_GB_PER_GBP * gbp, 1),
            "disco_gb": round(INDICE_BYTE_PER_BASE * basi / 1e9, 1),
            "temporaneo_gb": round(TEMPORANEO_BYTE_PER_BASE * basi / 1e9, 1)}


def file_ospiti(radice=None):
    """L'elenco degli ospiti aggiunti: nella cartella dei progetti, fuori da quella del programma (un aggiornamento
    non lo tocca)."""
    return Path(radice or cartella_progetti()) / "ospiti_personali.yaml"


def ospiti_personali(radice=None):
    """{nome: {"accession" o "fasta", "basi", "organismo", "aggiunto"}} degli ospiti aggiunti; voci non valide saltate."""
    f = file_ospiti(radice)
    try:
        dati = yaml.safe_load(f.read_text(encoding="utf-8")) if f.is_file() else {}
    except (OSError, yaml.YAMLError):
        return {}
    return {n: v for n, v in (dati if isinstance(dati, dict) else {}).items() if isinstance(v, dict) and NOME_OSPITE.fullmatch(str(n))
            and (ACCESSION.fullmatch(str(v.get("accession", ""))) or str(v.get("fasta", "")).lower().endswith(ESTENSIONI_FASTA))}


def errore_nome_ospite(nome, radice=None):
    """Il problema del nome breve di un ospite nuovo, o None se va bene."""
    if not NOME_OSPITE.fullmatch(nome or ""):
        return _("Il nome può avere solo lettere senza accenti, numeri e trattino basso (_), da 2 a 40, e deve "
                 "iniziare con una lettera.")
    if nome.lower() in OSPITI_DEL_MOTORE or nome in ospiti_personali(radice):
        return _("Esiste già un ospite che si chiama {nome}: scegli un altro nome.", nome=nome)
    return None


def controlla_fasta(percorso):
    """(basi stimate, None) di un genoma FASTA sul computer, o (None, problema in parole)."""
    p = Path(percorso)
    if not p.name.lower().endswith(ESTENSIONI_FASTA):
        return None, _("Il file deve finire in .fa, .fasta o .fna (anche .gz).")
    if not percorso_sicuro(p):
        return None, _("Il nome di questo file (o di una cartella che lo contiene) ha un carattere che il motore non "
                       "accetta, come ; & ! $: rinominalo e riprova.")
    try:
        with (gzip.open(p, "rb") if p.name.lower().endswith(".gz") else open(p, "rb")) as f:
            inizio = f.read(4096).lstrip()
        byte = p.stat().st_size
    except (OSError, EOFError):
        return None, _("Non riesco a leggere questo file.")
    if not inizio.startswith(b">"):
        return None, _("Questo file non è un genoma in formato FASTA (deve iniziare con il segno >).")
    return round(byte * GZ_RAPPORTO) if p.name.lower().endswith(".gz") else byte, None


def dimensione_ncbi(accession, attesa=15):
    """(basi, organismo) dell'assembly da NCBI Datasets, None se NCBI non lo conosce; OSError se la rete non va."""
    if not ACCESSION.fullmatch(accession or ""):   # solo codici validi entrano nell'indirizzo
        return None
    try:
        with urllib.request.urlopen(NCBI_DATASETS.format(accession), timeout=attesa) as r:
            dati = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code in (400, 404):
            return None
        raise OSError(str(e)) from e
    except ValueError as e:
        raise OSError(str(e)) from e
    for rep in dati.get("reports") or []:
        basi = (rep.get("assembly_stats") or {}).get("total_sequence_length")
        if basi:
            return int(basi), (rep.get("organism") or {}).get("organism_name", "")
    return None


def aggiungi_ospite(nome, voce, radice=None):
    """Aggiunge un ospite all'elenco (scrittura tutto o niente). voce: {"accession" o "fasta", "basi", ...}."""
    problema = errore_nome_ospite(nome, radice)
    if problema:
        raise ValueError(problema)
    elenco = ospiti_personali(radice)
    elenco[nome] = {**voce, "aggiunto": date.today().isoformat()}
    f = file_ospiti(radice)
    f.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=f.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as g:
            yaml.safe_dump(elenco, g, allow_unicode=True, sort_keys=False)
        os.replace(tmp, f)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
    return elenco


def percorso_sicuro(percorso):
    """True se il motore accetta il percorso (niente caratteri che validate_path_safe rifiuta)."""
    return not PERCORSO_NON_SICURO.search(str(percorso))


def elenco(radice=None):
    """I progetti (cartelle con config.yaml), dal più recente."""
    radice = Path(radice or cartella_progetti())
    if not radice.is_dir():
        return []
    trovati = [Progetto(d) for d in radice.iterdir() if (d / "config.yaml").is_file()]
    return sorted(trovati, key=lambda p: p.config.stat().st_mtime, reverse=True)
