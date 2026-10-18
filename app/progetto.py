"""Il progetto dell'utente: una cartella con config.yaml (ingresso del motore, contratto §3) e risultati/.

Si scrive e si legge solo con yaml.safe_dump / yaml.safe_load. Il motore valida il contenuto
(CONFIG_NON_VALIDA): qui si controlla solo il nome della cartella.
"""
import os
import re
import tempfile
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
