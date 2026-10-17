"""pmn-motore: il motore vero dietro l'interfaccia (docs/contratto_motore.md, D053).

Stessi comandi ed eventi JSON del finto motore (installer/finto_motore.py), ma il lavoro lo fanno i pezzi
già provati: installer/installa_motore.sh (installa), installer/verifica_motore.sh (verifica),
bin/run.sh (esegui). Su stdout solo eventi JSON, uno per riga; i dettagli tecnici vanno nel log.

Uso: pmn-motore <info|installa|verifica|stima|esegui|annulla|sicurezza|referto> [--progetto FILE] [--corsa ID]
                 [--ingresso FILE]
Solo libreria standard: gira anche col python3 di sistema quando il motore non è installato
(e allora lo dice con DB_MANCANTE). Il file del progetto si legge con PyYAML dell'ambiente pmn_reports_py.
"""
import argparse
import csv
import importlib.util
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

import system_one   # stessa cartella (motore/)

VERSIONE = "0.1.0"
ROOT = Path(__file__).resolve().parent.parent
PMN_HOME = Path(os.environ.get("PMN_HOME", Path.home() / ".pmn"))
STATO = PMN_HOME / "stato"
RUN_SH = os.environ.get("PMN_RUN_SH", str(ROOT / "bin" / "run.sh"))   # sostituibile solo nei test
ATTESA_RETE = float(os.environ.get("PMN_ATTESA_RETE", "120"))          # secondi prima di riprovare il download
TENTATIVI_RETE = 3
CODICE_USCITA = {"CONFIG_NON_VALIDA": 1, "READ_NON_TROVATE": 1, "GIA_IN_CORSO": 1, "SPAZIO_INSUFFICIENTE": 1,
                 "DOWNLOAD_FALLITO": 1, "INGRESSO_NON_VALIDO": 1, "DB_MANCANTE": 2, "VERIFICA_ROSSA": 2, "ERRORE_INTERNO": 4}
# regole di stima misurate (S2.2, S3, filone pipeline; L1a 17/10: SF3RAt7 su NVMe con 24 processori, 37 min 39 s)
BYTE_PER_COPPIA = 164.6        # read gz di SF3RAt7: 533.522.098 byte per 3.240.847 coppie (ENA)
DOWNLOAD_BYTE_S = 4.1e6        # 533,5 MB (gz di ENA) scaricati e convertiti in FASTQ in 129 s (rete di casa, 17/10)
PULIZIA_S_PER_M = 5.6          # fastp: 18 s per 3,24 M coppie (17/10)
OSPITE_S_PER_M = 101           # 325 s per 3,21 M coppie dopo fastp (S2.2); 327 s anche con 24 processori (17/10)
OSPITE_QUOTA = 0.53            # coppie tolte con l'ospite: SF3RAt7 (maiale) 3,24 M -> 1,51 M (17/10); bovino e pecora
                               # non misurati (stessa quota); senza ospite (solo uomo) 0, prudente
MPA_S_PER_M, MPA_FISSI_S = 86.2, 230   # per M coppie senza ospite (C03_1, S2.2); fissi: 357 s per 1,51 M (17/10)
KRAKEN_COPPIE_MIN = {"completo": 37000, "rapido": 10_000_000}   # coppie senza ospite al minuto con 8 processori (K2)
KRAKEN_PROC_RIF = 8            # velocità x radice(processori / 8): 63.900 coppie/min con 24 (17/10); fit su 2 misure
ALTRI_S = {"controllo_qualita": 15, "riepilogo": 10, "referto": 10}   # MultiQC 3-16 s, tabelle 4 s, referto 1 s (17/10)
TRIAGE_S = 60                  # triage di un campione (primi 100.000 frammenti, qualità + ospite): non misurato, prudente
# passi di run.sh (etichette di do_step) -> passo del contratto e cosa sta facendo
PASSI = [("download", "scarico le read da NCBI"), ("controllo_qualita", "controllo la qualità delle read"),
         ("pulizia", "tolgo le parti di bassa qualità"), ("ospite", "tolgo le read dell'ospite e dell'uomo"),
         ("metaphlan", "calcolo il profilo delle specie (MetaPhlAn, 6 parti del database)"),
         ("kraken", "classifico le read con Kraken e Bracken"), ("riepilogo", "preparo le tabelle e il riepilogo")]
# passo del contratto -> in parole, per il messaggio di fine dopo un errore (v0.3)
NOMI_PASSI = {"download": "lo scaricamento delle read", "controllo_qualita": "il controllo della qualità",
              "pulizia": "la pulizia delle read", "ospite": "la rimozione del DNA dell'ospite",
              "metaphlan": "il profilo con MetaPhlAn", "kraken": "la classificazione con Kraken e Bracken",
              "riepilogo": "il riepilogo", "referto": "la preparazione del referto", "sicurezza": "la previsione di crescita",
              "verifica": "la verifica del motore"}
# read locali: stesse coppie di for_each_sample in bin/run.sh (nome = file senza il suffisso della prima read)
COPPIE_LOCALI = [("_1.fastq.gz", "_2.fastq.gz"), ("_R1.fastq.gz", "_R2.fastq.gz"), ("_R1_001.fastq.gz", "_R2_001.fastq.gz"),
                 ("_1.fq.gz", "_2.fq.gz"), ("_R1.fq.gz", "_R2.fq.gz")]
NOME_VALIDO = re.compile(r"(?![-.])[A-Za-z0-9._-]{1,64}")   # validate_name di bin/lib/validate.sh
ETICHETTE = [(r"size$", "download"), (r"dl_(.+)", "download"), (r"(?:tq|th)_(.+)|triage$|multiqc$", "controllo_qualita"),
             (r"trim_(.+)", "pulizia"), (r"(?:hf|idx)_(.+)", "ospite"), (r"mpa_matrix$", "riepilogo"),
             (r"mpa_(.+)", "metaphlan"), (r"krk_(.+)", "kraken"), (r".+", "riepilogo")]
# righe del log di run.sh e dei suoi passi -> errore per l'utente (codice, messaggio, cosa fare)
ERRORI = [
    (r"ENA and NCBI could not be reached|prefetch failed|fasterq-dump failed", "DOWNLOAD_FALLITO",
     "Non riesco a scaricare le read: i server di ENA e NCBI non rispondono.",
     "Controlla la connessione a internet e riprova fra qualche minuto."),
    (r"Not enough space", "SPAZIO_INSUFFICIENTE", "Lo spazio libero non basta per scaricare le read.",
     "Libera spazio sul disco e riprova."),
    (r"runs were not found|skipping invalid accession|no FASTQ produced", "READ_NON_TROVATE",
     "Non trovo le read di uno o più campioni.", "Controlla i codici SRR o la cartella delle read nel progetto."),
    (r"kraken_db is empty|metaphlan_db|PMN_ENVS missing|No such file or directory.*(?:k2d|bt2|pkl)", "DB_MANCANTE",
     "Manca un database o un programma del motore.", "Apri la pagina Motore e premi Installa."),
    (r"failed to parse config|invalid |unsafe |not found:|is empty", "CONFIG_NON_VALIDA",
     "Il progetto contiene un valore non valido.", "Controlla le impostazioni del progetto."),
]
# verificate su PubMed (VERIFICA_CITAZIONI 15/10: 13/13; Kraken 2, Bracken, Edwin 2024 il 16/10), come README §21
CITAZIONI = {
    "metaphlan": ["Blanco-Míguez et al. 2023, Nat Biotechnol 41(11):1633-1644: MetaPhlAn 4. DOI 10.1038/s41587-023-01688-w",
                  "Database MetaPhlAn mpa_vJan25_CHOCOPhlAnSGB_202503 (le 6 fette sono un derivato del suo indice "
                  "Bowtie2, costruito da profilemetananni)"],
    "kraken": ["Wood et al. 2019, Genome Biol 20:257: Kraken 2. DOI 10.1186/s13059-019-1891-0",
               "Lu et al. 2017, PeerJ Comput Sci 3:e104: Bracken. DOI 10.7717/peerj-cs.104",
               "Indici Kraken2/Bracken {db} di Ben Langmead (genome-idx.s3.amazonaws.com/kraken)",
               "Wright, Comeau & Langille 2023, Microb Genom 9(3):000949: scelta di confidence e database di "
               "Kraken2. DOI 10.1099/mgen.0.000949",
               "Edwin et al. 2024, Environ Microbiome 19:19: soglia di abbondanza 0,005 %. DOI 10.1186/s40793-024-00561-w"],
    "bowtie2": ["Langmead & Salzberg 2012, Nat Methods 9(4):357-359: Bowtie 2. DOI 10.1038/nmeth.1923"],
    "fastp": ["Chen et al. 2018, Bioinformatics 34(17):i884-i890: fastp. DOI 10.1093/bioinformatics/bty560"],
    "sus_scrofa": ["Warr et al. 2020, GigaScience 9(6):giaa051: maiale Sscrofa11.1. DOI 10.1093/gigascience/giaa051"],
    "bos_taurus": ["Rosen et al. 2020, GigaScience 9(3):giaa021: bovino ARS-UCD1.2. DOI 10.1093/gigascience/giaa021"],
    "ovis_aries": ["Davenport et al. 2022, GigaScience 11:giab096: pecora ARS-UI_Ramb_v2.0. DOI 10.1093/gigascience/giab096"],
    "grch38": ["Schneider et al. 2017, Genome Res 27(5):849-864: uomo GRCh38. DOI 10.1101/gr.213611.116"],
}


def processori(cfg):
    """Processori della corsa: execution.threads (quelli che usa run.sh), poi motore.processori, poi 8 come run.sh."""
    for v in (sezione(cfg, "execution").get("threads"), sezione(cfg, "motore").get("processori")):
        try:
            if int(v) > 0:
                return int(v)
        except (TypeError, ValueError):
            pass
    return KRAKEN_PROC_RIF


def piano(camp, cfg, quote=None):
    """[(etichetta di run.sh, passo, gruppo, secondi)] nell'ordine di bin/run.sh: download, triage, pulizia e ospite
    per campione, MultiQC, poi MetaPhlAn e Kraken alternati per campione, riepilogo, referto. MetaPhlAn e Kraken
    contano le coppie senza ospite: quote {campione: quota dell'ospite} dal triage se c'è, se no OSPITE_QUOTA."""
    strumento = sezione(cfg, "profiling").get("tool", "both")
    kraken_db = sezione(cfg, "motore").get("kraken_db") or "completo"
    velocita = KRAKEN_COPPIE_MIN.get(kraken_db, KRAKEN_COPPIE_MIN["completo"]) * (processori(cfg) / KRAKEN_PROC_RIF) ** 0.5
    quota = OSPITE_QUOTA if cfg.get("hosts") else 0.0
    out = [("size", "download", 0, 0)] + [(f"dl_{n}", "download", 0, b / DOWNLOAD_BYTE_S) for n, _, b in camp if b]
    if sezione(cfg, "triage").get("enabled") is True:
        out += [(f"{x}_{n}", "controllo_qualita", 1, TRIAGE_S / 2) for n, _, _ in camp for x in ("tq", "th")]
        out.append(("triage", "controllo_qualita", 1, 0))
    for n, c, _ in camp:
        out += [(f"trim_{n}", "pulizia", 2, c / 1e6 * PULIZIA_S_PER_M), (f"hf_{n}", "ospite", 2, c / 1e6 * OSPITE_S_PER_M)]
    out.append(("multiqc", "controllo_qualita", 3, ALTRI_S["controllo_qualita"]))
    for n, c, _ in camp:
        resto = c * (1 - (quote or {}).get(n, quota))
        if strumento in ("metaphlan", "both"):
            out.append((f"mpa_{n}", "metaphlan", 4, resto / 1e6 * MPA_S_PER_M + MPA_FISSI_S))
        if strumento in ("kraken", "both"):
            out.append((f"krk_{n}", "kraken", 4, resto / velocita * 60))
    return out + [("riepilogo", "riepilogo", 5, ALTRI_S["riepilogo"]), ("referto", "referto", 6, ALTRI_S["referto"])]


def tempi(camp, cfg, quote=None):
    """Secondi previsti per passo del contratto (somma del piano), usati da stima; esegui usa il piano intero."""
    out = dict.fromkeys([p for p, _ in PASSI] + ["referto"], 0)
    for _, passo, _, s in piano(camp, cfg, quote):
        out[passo] += s
    return {p: round(s) for p, s in out.items()}


def quote_triage(lavoro):
    """{campione: quota di frammenti dell'ospite} da results/triage.tsv (steps/17), se il triage c'è stato."""
    f = Path(lavoro) / "results" / "triage.tsv"
    out = {}
    if f.is_file():
        with open(f, encoding="utf-8", newline="") as t:
            for r in csv.DictReader(t, delimiter="\t"):
                try:
                    out[r["sample"]] = min(max(float(r["host_pct"]) / 100, 0.0), 1.0)
                except (KeyError, TypeError, ValueError):
                    pass
    return out


# uscite di run.sh per etichetta (layout managed): se ci sono già, run.sh salta il passo (corsa ripresa)
USCITE = {"dl": ("raw/{}_1.fastq.gz", "raw/{}.fastq.gz"), "mpa": ("metaphlan/{}_profile.txt",),
          "krk": ("kraken/{}.bracken",), **dict.fromkeys(("tq", "th", "trim", "hf"),
                                                         ("nonhost/{}_nonhost_1.fastq.gz", "nonhost/{}_nonhost.fastq.gz"))}


def gia_fatti(lavoro, etichette):
    """Etichette del piano con l'uscita già sul disco: in una corsa ripresa non si contano più."""
    fatti = set()
    for e in etichette:
        tipo, _, nome = e.partition("_")
        for modello in USCITE.get(tipo, ()) if nome else ():
            f = Path(lavoro) / modello.format(nome)
            if f.is_file() and f.stat().st_size > 0:
                fatti.add(e)
    return fatti


class Annullata(Exception):
    pass


class Errore(Exception):
    def __init__(self, codice, messaggio, cosa_fare, passo=None):
        super().__init__(messaggio)
        self.codice, self.messaggio, self.cosa_fare, self.passo = codice, messaggio, cosa_fare, passo


def installazione():
    """Le chiavi di ~/.pmn/installazione.env (lette una per una, mai eseguite), o {} se il motore non c'è."""
    f = PMN_HOME / "installazione.env"
    if not f.is_file():
        return {}
    return dict(r.split("=", 1) for r in f.read_text(encoding="utf-8").splitlines() if "=" in r and not r.startswith("#"))


def serve_installazione():
    env = installazione()
    if not env:
        raise Errore("DB_MANCANTE", "Il motore non è ancora installato.", "Apri la pagina Motore e premi Installa.")
    return env


def versione(envs, ambiente, pacchetto):
    meta = Path(envs) / ambiente / "conda-meta"
    for f in sorted(meta.glob(f"{pacchetto}-[0-9]*.json")) if meta.is_dir() else []:
        return f.name[len(pacchetto) + 1:].split("-")[0]
    return None


def elenco_database(env):
    """[{nome, installato}] dei database del motore, dai segni sul disco (come info)."""
    db = [("metaphlan_fette_vJan25_v1", env.get("PMN_FETTE", ""), "idx6"),
          ("metaphlan_pkl_vJan25", env.get("PMN_MPA_DB", ""), "mpa_vJan25_CHOCOPhlAnSGB_202503.pkl"),
          ("kraken_pluspf_20260626", env.get("PMN_KRAKEN_COMPLETO", ""), "hash.k2d"),
          ("kraken_pluspf_08gb_20260626", env.get("PMN_KRAKEN_RAPIDO", ""), "hash.k2d")]
    database = [{"nome": n, "installato": bool(c) and (Path(c) / segno).exists()} for n, c, segno in db]
    ospite = Path(env.get("PMN_OSPITE", "")) if env.get("PMN_OSPITE") else None
    for o in ("sus_scrofa", "bos_taurus", "ovis_aries", "homo_sapiens"):
        database.append({"nome": f"ospite_{o}",
                         "installato": bool(ospite) and (ospite / o / f"{o}.rev.2.bt2").exists()})
    return database


def leggi_progetto(percorso):
    if not percorso or not Path(percorso).is_file():
        raise Errore("CONFIG_NON_VALIDA", "Non trovo il file del progetto.", "Salva il progetto e riprova.")
    try:
        import yaml
        cfg = yaml.safe_load(Path(percorso).read_text(encoding="utf-8")) or {}
    except Exception:
        raise Errore("CONFIG_NON_VALIDA", "Il file del progetto non si legge.", "Salva di nuovo il progetto e riprova.")
    if not isinstance(cfg, dict):
        raise Errore("CONFIG_NON_VALIDA", "Il file del progetto non si legge.", "Salva di nuovo il progetto e riprova.")
    return cfg


def sezione(cfg, nome):
    v = cfg.get(nome) or {}
    return v if isinstance(v, dict) else {}


def campioni_locali(cartella):
    """[(nome, [file])] delle read in una cartella, con le regole di bin/run.sh: "C1_R1.fastq.gz" + "C1_R2.fastq.gz"
    = campione "C1" (anche _1/_2, _R1_001/_R2_001, .fq.gz); un file senza la sua coppia si salta, come in run.sh;
    gli altri .fastq.gz/.fq.gz sono campioni a lettura singola."""
    file = sorted(f.name for f in Path(cartella).iterdir() if f.is_file())
    out = []
    for s1, s2 in COPPIE_LOCALI:
        for f in file:
            nome = f[:-len(s1)]
            if f.endswith(s1) and nome + s2 in file and NOME_VALIDO.fullmatch(nome):
                out.append((nome, [f, nome + s2]))
    suffissi = tuple(s for coppia in COPPIE_LOCALI for s in coppia)
    for f in file:
        if f.endswith((".fastq.gz", ".fq.gz")) and not f.endswith(suffissi):
            nome = f[:-len(".fastq.gz")] if f.endswith(".fastq.gz") else f[:-len(".fq.gz")]
            if NOME_VALIDO.fullmatch(nome):
                out.append((nome, [f]))
    return out


def messaggio_fine(messaggio, cosa_fare, passo):
    """Testo dell'evento fine dopo un errore (v0.3): quale passo, che cosa è successo, che cosa fare."""
    dove = f"Problema durante {NOMI_PASSI[passo]}. " if passo in NOMI_PASSI else ""
    return f"{dove}{messaggio} {cosa_fare}".strip()


class Motore:
    def __init__(self, a):
        self.a = a
        self.corsa = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
        cartella = PMN_HOME / "log" if (PMN_HOME / "log").is_dir() else Path(tempfile.gettempdir())
        self.log = cartella / f"pmn_{self.corsa}_{a.comando}.log"
        self.passo = None   # ultimo passo annunciato: va nell'evento errore (v0.2)
        self.ultimo_pct, self.eta_referto = 97, None   # dove parte il referto (esegui li aggiorna)

    def evento(self, tipo, messaggio, **campi):
        riga = {"tipo": tipo, "ora": datetime.now().astimezone().isoformat(timespec="seconds"),
                "messaggio": messaggio, **campi}
        if tipo == "avanzamento":
            self.passo = campi.get("passo")
        print(json.dumps(riga, ensure_ascii=False), flush=True)
        self.scrivi(f"{tipo}: {messaggio}")

    def scrivi(self, testo):
        with open(self.log, "a", encoding="utf-8") as f:
            f.write(f"{datetime.now():%H:%M:%S} {testo}\n")

    def consigli(self, elenco):
        """System One v0: i consigli di livello "avviso" diventano eventi; tutti restano nel risultato."""
        for c in elenco:
            if c["livello"] == "avviso":
                self.evento("avviso", c["messaggio"], codice=c["codice"])
        return elenco

    def avanza(self, passo, messaggio, pct, campione=None, fatto=0, totale=1, eta_s=None):
        self.evento("avanzamento", messaggio, passo=passo, campione=campione, fatto=fatto, totale=totale,
                    percentuale=round(max(0, min(100, pct)), 1), eta_s=eta_s)

    # ---------------- info ----------------
    def info(self):
        env = installazione()
        ram = 0.0
        if Path("/proc/meminfo").is_file():
            for r in Path("/proc/meminfo").read_text().splitlines():
                if r.startswith("MemTotal:"):
                    ram = int(r.split()[1]) / 1024 / 1024
        base = PMN_HOME if PMN_HOME.exists() else Path.home()
        e = env.get("PMN_ENVS", "")
        programmi = {p: versione(e, a, p) for a, p in [("pmn_metaphlan", "metaphlan"), ("pmn_metaphlan", "bowtie2"),
                     ("pmn_kraken", "kraken2"), ("pmn_kraken", "bracken"), ("pmn_trim", "fastp")]} if e else {}
        database = elenco_database(env)
        mpa_db = env.get("PMN_MPA_DB", "")
        indice_intero = bool(mpa_db) and (Path(mpa_db) / "mpa_vJan25_CHOCOPhlAnSGB_202503.1.bt2l").exists()
        modo, consigli = system_one.modo(ram, indice_intero, database[2]["installato"], database[3]["installato"])
        return "ok", {"motore": VERSIONE, "ram_gb": round(ram, 1), "processori": os.cpu_count(),
                      "spazio_libero_gb": round(shutil.disk_usage(base).free / 1e9),
                      "modo_consigliato": modo, "consigli": self.consigli(consigli),
                      "programmi": programmi, "database": database, "prodotti": system_one.prodotti()}, \
            "Ecco com'è fatto questo PC e cosa è installato."

    # ---------------- verifica ----------------
    def verifica(self):
        serve_installazione()
        self.avanza("verifica", "Controllo i programmi e provo un piccolo campione (alcuni minuti)...", 5)
        controlli, n = [], 0
        p = subprocess.Popen(["bash", str(ROOT / "installer" / "verifica_motore.sh")], stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace",
                             env={**os.environ, "PMN_HOME": str(PMN_HOME)})
        for riga in p.stdout:
            self.scrivi(riga.rstrip())
            m = re.match(r"(OK|DIVERSO)\s+(.*)", riga)
            if m:
                controlli.append({"nome": m.group(2).strip(), "esito": "ok" if m.group(1) == "OK" else "diverso"})
                n += 1
                self.avanza("verifica", f"Controllo {n}: {m.group(2).strip()[:60]}", 5 + 90 * n / 16)
        if p.wait() != 0:
            raise Errore("VERIFICA_ROSSA", "ROSSO: la prova del motore non ha dato il risultato atteso.",
                         f"Manda a noi il file {self.log}.")
        return "ok", {"esito": "verde", "controlli": controlli}, "VERDE: il motore funziona."

    # ---------------- stima ----------------
    def campioni(self, cfg):
        """[(nome, coppie, byte da scaricare)] secondo il progetto; per NCBI dimensioni da ENA o NCBI (steps/05)."""
        paths, fonte = sezione(cfg, "paths"), cfg.get("data_source", "ncbi")
        out = []
        if fonte in ("ncbi", "both"):
            lista = Path(str(paths.get("srr_list") or ""))
            if not lista.is_file():
                raise Errore("CONFIG_NON_VALIDA", "Non trovo l'elenco dei codici SRR.", "Controlla il progetto.")
            spec = importlib.util.spec_from_file_location("stima_dimensione", ROOT / "steps" / "05_estimate_size.py")
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            codici = [r.split()[0] for r in lista.read_text(encoding="utf-8").splitlines() if r.strip() and not r.startswith("#")]
            esiti = mod.lookup_many(codici)   # richieste a gruppi (ENA, poi NCBI)
            if esiti and all(e["status"] == "ERROR" for e in esiti):
                raise Errore("DOWNLOAD_FALLITO", "I server di ENA e NCBI non rispondono: non posso stimare il download.",
                             "Controlla la connessione e riprova fra qualche minuto.")
            for e in esiti:
                if e["status"] != "OK":
                    raise Errore("READ_NON_TROVATE", f"Non trovo il campione {e['accession']} su ENA né su NCBI.",
                                 "Controlla il codice SRR nel progetto.")
                out.append((e["accession"], e["read_count"], e["fastq_bytes"]))
        if fonte in ("local", "both"):
            cartella = Path(str(paths.get("local_reads_dir") or ""))
            if not cartella.is_dir():
                raise Errore("READ_NON_TROVATE", "Non trovo la cartella delle read.", "Controlla il progetto.")
            for nome, file in campioni_locali(cartella):   # nomi come in run.sh: "C1", non "C1_R1" (v0.3)
                byte = sum((cartella / f).stat().st_size for f in file)
                out.append((nome, round(byte / BYTE_PER_COPPIA), 0))
        if not out:
            raise Errore("READ_NON_TROVATE", "Il progetto non contiene campioni.", "Aggiungi le read al progetto.")
        return out

    def stima(self):
        cfg = leggi_progetto(self.a.progetto)
        camp = self.campioni(cfg)
        coppie = sum(c for _, c, _ in camp)
        strumento = sezione(cfg, "profiling").get("tool", "both")
        kraken_db = sezione(cfg, "motore").get("kraken_db") or "completo"
        lavoro = Path(self.a.progetto).resolve().parent / str(sezione(cfg, "paths").get("work_dir") or "./pmn_work")
        tempo = tempi(camp, cfg, quote_triage(lavoro))
        scaricare = sum(b for _, _, b in camp)
        spazio_gb = round(max(scaricare, coppie * BYTE_PER_COPPIA) * 6 / 1e9, 1)
        while not lavoro.exists() and lavoro != lavoro.parent:   # lo spazio del disco dove andra' il lavoro
            lavoro = lavoro.parent
        libero = round(shutil.disk_usage(lavoro).free / 1e9, 1)
        env = installazione()
        consigli = system_one.tempo(tempo) + system_one.spazio(spazio_gb, libero)
        if env and strumento in ("kraken", "both"):
            consigli += system_one.database(kraken_db, {d["nome"]: d["installato"] for d in elenco_database(env)})
        return "ok", {"campioni": len(camp), "nomi_campioni": [n for n, _, _ in camp], "coppie_totali": coppie,
                      "tempo_s": tempo, "tempo_totale_s": sum(tempo.values()), "spazio_gb": spazio_gb,
                      "spazio_libero_gb": libero, "consigli": self.consigli(consigli)}, \
            f"Stima pronta per {processori(cfg)} processori (dipende anche dalla rete e dalla quantità di DNA dell'ospite)."

    # ---------------- esegui ----------------
    def esegui(self):
        serve_installazione()
        progetto = Path(self.a.progetto).resolve() if self.a.progetto else None
        cfg = leggi_progetto(progetto)
        blocco = STATO / "esegui.lock"
        STATO.mkdir(parents=True, exist_ok=True)
        if blocco.exists():
            try:
                vecchio = json.loads(blocco.read_text(encoding="utf-8"))
                os.kill(vecchio["pid"], 0)
                raise Errore("GIA_IN_CORSO", "C'è già un'analisi in corso.", "Aspetta che finisca, oppure annullala.")
            except (ProcessLookupError, ValueError, KeyError):
                blocco.unlink(missing_ok=True)   # rimasto da una corsa interrotta
        blocco.write_text(json.dumps({"corsa": self.corsa, "pid": os.getpid(), "pgid": None}), encoding="utf-8")
        try:   # tempo stimato (D027) con le regole di stima; senza dimensioni (rete giu', read non trovate) resta null
            camp = self.campioni(cfg)
        except (Errore, OSError, ValueError):
            camp = None
        try:
            for tentativo in range(1, TENTATIVI_RETE + 1):
                try:
                    self._run_sh(progetto, cfg, blocco, camp)
                    break
                except Errore as e:
                    if e.codice != "DOWNLOAD_FALLITO" or tentativo == TENTATIVI_RETE:
                        raise
                    self.evento("avviso", f"I server di ENA e NCBI non rispondono: riprovo fra {round(ATTESA_RETE)} "
                                f"secondi (tentativo {tentativo + 1} di {TENTATIVI_RETE}).", codice="RETE_INTERROTTA")
                    fine = time.monotonic() + ATTESA_RETE
                    while time.monotonic() < fine:
                        if (STATO / f"{self.corsa}.annulla").exists():
                            raise Annullata
                        time.sleep(min(1, fine - time.monotonic()))
            return "ok", self._risultati(progetto, cfg), "Analisi finita."
        finally:
            blocco.unlink(missing_ok=True)
            (STATO / f"{self.corsa}.annulla").unlink(missing_ok=True)

    def _run_sh(self, progetto, cfg, blocco, camp=None):
        n = max(1, len(self._nomi(cfg)))
        lavoro = progetto.parent / str(sezione(cfg, "paths").get("work_dir") or "./pmn_work")
        # senza dimensioni (rete giu') la barra va lo stesso, con campioni grandi come SF3RAt7; il tempo resta null
        campioni = camp or [(x, 3_240_847, 0) for x in self._nomi(cfg)]
        unita = piano(campioni, cfg, quote_triage(lavoro))
        secondi, gruppo = {e: s for e, _, _, s in unita}, {e: g for e, _, g, _ in unita}
        totale = sum(secondi.values()) or 1
        fatti = gia_fatti(lavoro, secondi)   # corsa ripresa: i passi già finiti non si contano
        triage_letto = False

        def eta(etichetta, passo):
            """(percentuale, secondi che restano): questo passo intero + quelli non ancora partiti. Un passo di
            un gruppo prima di questo che non è partito, run.sh l'ha saltato."""
            chiave = etichetta if etichetta in secondi else "riepilogo" if passo == "riepilogo" else None
            if chiave:
                fatti.update(e for e in secondi if gruppo[e] < gruppo[chiave])
            resta = (secondi[chiave] if chiave and chiave not in fatti else 0) + \
                sum(s for e, s in secondi.items() if e not in fatti and e != chiave)
            if chiave:
                fatti.add(chiave)
            return 100 * (totale - resta) / totale, round(resta) if camp else None
        visti, ultimo = {}, 0.0
        p = subprocess.Popen(["bash", RUN_SH, "--config", str(progetto), "--skip-preflight"], cwd=progetto.parent,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                             errors="replace", env={**os.environ, "PMN_HOME": str(PMN_HOME), "NO_COLOR": "1"},
                             start_new_session=True)
        blocco.write_text(json.dumps({"corsa": self.corsa, "pid": os.getpid(), "pgid": p.pid}), encoding="utf-8")
        coda = []
        for riga in p.stdout:
            riga = riga.rstrip()
            self.scrivi(riga)
            coda = (coda + [riga])[-40:]
            m = re.search(r"\[(?:local|locale)\] (\S+)", riga)
            if not m:
                continue
            for regola, passo in ETICHETTE:
                mm = re.fullmatch(regola, m.group(1))
                if mm:
                    campione = next((g for g in mm.groups() if g), None) if mm.groups() else None
                    i = visti.setdefault(passo, set())
                    if campione:
                        i.add(campione)
                    fatto = len(i)
                    if not triage_letto and gruppo.get(m.group(1), 0) >= 2:   # triage finito: quote misurate
                        triage_letto = True
                        secondi.update((e, s) for e, _, _, s in piano(campioni, cfg, quote_triage(lavoro)))
                        totale = sum(secondi.values()) or 1
                    pct, resta = eta(m.group(1), passo)
                    pct = ultimo = max(ultimo, pct)   # la barra non torna mai indietro
                    testo = dict(PASSI)[passo]
                    chi = f"Campione {min(fatto, n)} di {n}: " if campione else ""
                    self.avanza(passo, f"{chi}{testo}", pct, campione=campione, fatto=fatto, totale=n, eta_s=resta)
                    break
        self.ultimo_pct, self.eta_referto = ultimo, secondi["referto"] if camp else None
        codice = p.wait()
        if (STATO / f"{self.corsa}.annulla").exists():
            raise Annullata
        if codice != 0:
            testo = "\n".join(coda)
            for regola, cod, msg, cosa in ERRORI:
                if re.search(regola, testo):
                    raise Errore(cod, msg, cosa)
            raise Errore("ERRORE_INTERNO", "L'analisi si è fermata per un errore imprevisto.",
                         f"Manda a noi il file {self.log}.")

    @staticmethod
    def _nomi(cfg):
        paths, fonte, nomi = sezione(cfg, "paths"), cfg.get("data_source", "ncbi"), []
        lista = Path(str(paths.get("srr_list") or ""))
        if fonte in ("ncbi", "both") and lista.is_file():
            nomi += [r.split()[0] for r in lista.read_text(encoding="utf-8").splitlines() if r.strip() and not r.startswith("#")]
        cartella = Path(str(paths.get("local_reads_dir") or ""))
        if fonte in ("local", "both") and cartella.is_dir():
            nomi += [n for n, _ in campioni_locali(cartella)]
        return nomi

    def _risultati(self, progetto, cfg):
        """Cartella <progetto>/risultati/ come nel contratto (5.3), copiando dai percorsi di run.sh."""
        paths = sezione(cfg, "paths")
        lavoro = (progetto.parent / str(paths.get("work_dir") or "./pmn_work")).resolve()
        res = Path(paths["results_dir"]) if paths.get("layout") == "custom" and paths.get("results_dir") else lavoro / "results"
        r = progetto.parent / "risultati"
        for sotto in ("metaphlan", "kraken", "tabelle", "log"):
            (r / sotto).mkdir(parents=True, exist_ok=True)
        campioni = {}
        for f in sorted((lavoro / "metaphlan").glob("*_profile.txt")):
            shutil.copy(f, r / "metaphlan")
            campioni.setdefault(f.name[:-len("_profile.txt")], {})["metaphlan"] = f"metaphlan/{f.name}"
        for f in sorted((lavoro / "kraken").glob("*.bracken")) + sorted((lavoro / "kraken").glob("*.k2report")):
            shutil.copy(f, r / "kraken")
            if f.suffix == ".bracken":
                campioni.setdefault(f.stem, {})["kraken"] = f"kraken/{f.name}"
        for f in sorted(res.glob("*.tsv")) + sorted(res.glob("*.xlsx")):
            shutil.copy(f, r / "tabelle")
        parametri = {}
        if (res / "parameters.tsv").is_file():
            for riga in (res / "parameters.tsv").read_text(encoding="utf-8").splitlines()[1:]:
                k, _, v = riga.partition("\t")
                parametri[k] = v
        ospiti = list(cfg.get("hosts") or []) + (["grch38"] if cfg.get("filter_human", True) else [])
        strumento = sezione(cfg, "profiling").get("tool", "both")
        kraken_db = os.path.basename(parametri.get("kraken_db", "").rstrip("/"))
        nome_db = "PlusPF-8 del 26/06/2026" if "08gb" in kraken_db else "PlusPF del 26/06/2026"
        citazioni = [c.format(db=nome_db) for k in ["metaphlan", "kraken", "bowtie2", "fastp", *ospiti] if k in CITAZIONI
                     and not (k == "metaphlan" and strumento == "kraken") and not (k == "kraken" and strumento == "metaphlan")
                     for c in CITAZIONI[k]]
        env = installazione()
        e = env.get("PMN_ENVS", "")
        triage, consigli = system_one.triage(r / "tabelle" / "triage.tsv", system_one.soglie_triage(cfg))
        elenco = []
        for nome, file in sorted(campioni.items()):
            coppie = None
            rep = lavoro / "kraken" / f"{nome}.k2report"
            if rep.is_file():   # righe "unclassified" + "root" del report = coppie dopo l'ospite
                coppie = sum(int(c.split("\t")[1]) for c in rep.read_text(encoding="utf-8").splitlines()
                             if c.split("\t")[-1].strip() in ("unclassified", "root"))
            elenco.append({"nome": nome, "esito": "ok", "coppie_dopo_ospite": coppie, "file": file})
        import referto   # stessa cartella; qui serve solo la libreria standard
        try:
            soglia = float(parametri.get("abundance_threshold_pct") or 0)
        except ValueError:
            soglia = 0.0
        for c in elenco:   # sintesi pronta per l'interfaccia (v0.2): mostra, non calcola (D006)
            c["sintesi"] = referto.sintesi(referto.leggi_campione(r, c["file"]), soglia)
        versioni = {"metaphlan": versione(e, "pmn_metaphlan", "metaphlan"), "database_metaphlan": parametri.get("metaphlan_index"),
                    "kraken2": versione(e, "pmn_kraken", "kraken2"), "bracken": versione(e, "pmn_kraken", "bracken"),
                    "database_kraken": kraken_db or None, "bowtie2": versione(e, "pmn_metaphlan", "bowtie2"),
                    "fastp": versione(e, "pmn_trim", "fastp")}
        risultati = {"motore": VERSIONE, "corsa": self.corsa, "campioni": elenco, "parametri": parametri,
                     "versioni": {k: v for k, v in versioni.items() if v}, "citazioni": citazioni,
                     "triage": triage, "consigli": self.consigli(consigli)}
        (r / "risultati.json").write_text(json.dumps(risultati, ensure_ascii=False, indent=1), encoding="utf-8")
        risultati["referto"] = self._referto(r, progetto)
        (r / "risultati.json").write_text(json.dumps(risultati, ensure_ascii=False, indent=1), encoding="utf-8")
        shutil.copy(self.log, r / "log")
        return {"cartella": str(r), **risultati}

    def _referto(self, r, progetto):
        """risultati/referto/ (HTML + Excel + PDF) con motore/referto.py; {file: percorso relativo o null}."""
        self.avanza("referto", "Preparo il referto (pagina, PDF ed Excel)...", max(97, self.ultimo_pct),
                    eta_s=self.eta_referto)
        p = subprocess.run([sys.executable, str(ROOT / "motore" / "referto.py"), "--risultati", str(r),
                            *(["--progetto", str(progetto)] if progetto else [])],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        self.scrivi(p.stdout.strip() + p.stderr.strip())
        try:
            esito = json.loads(p.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            esito = {"problemi": ["il programma del referto non ha risposto"]}
        if esito.get("problemi") or not esito.get("html"):
            import referto
            self.evento("avviso", referto.avviso_parziale(esito.get("problemi") or [], bool(esito.get("html"))),
                        codice="REFERTO_PARZIALE")
        return {k: (f"referto/{Path(esito[k]).name}" if esito.get(k) else None) for k in ("html", "pdf", "xlsx")}

    # ---------------- referto (v0.2) ----------------
    def referto(self):
        """Rifà il referto di un progetto già analizzato (per esempio dopo un calcolo di sicurezza)."""
        progetto = Path(self.a.progetto).resolve() if self.a.progetto else None
        leggi_progetto(progetto)
        r = progetto.parent / "risultati"
        if not (r / "risultati.json").is_file():
            raise Errore("CONFIG_NON_VALIDA", "Questo progetto non ha ancora risultati.", "Prima avvia l'analisi.")
        file = self._referto(r, progetto)
        if not file["html"]:
            raise Errore("ERRORE_INTERNO", "Non riesco a preparare il referto.", f"Manda a noi il file {self.log}.")
        return "ok", {"cartella": str(r), "referto": file}, "Referto pronto."

    # ---------------- sicurezza (FSSP, v0.2) ----------------
    def sicurezza(self):
        import sicurezza
        if self.a.progetto and not Path(self.a.progetto).is_file():
            raise Errore("CONFIG_NON_VALIDA", "Non trovo il file del progetto.", "Salva il progetto e riprova.")
        try:
            risultato, messaggio = sicurezza.comando(self.evento, self.a.ingresso, self.a.progetto)
        except sicurezza.Rifiutata as e:
            raise Errore("INGRESSO_NON_VALIDO", f"Dati del prodotto non validi: {e}.", sicurezza.COSA_FARE)
        return "ok", risultato, messaggio

    # ---------------- annulla ----------------
    def annulla(self):
        blocco = STATO / "esegui.lock"
        try:
            dati = json.loads(blocco.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            dati = {}
        if not dati or dati.get("corsa") != self.a.corsa:
            return "ok", {"annullata": False}, "Nessuna analisi in corso con questo codice."
        (STATO / f"{self.a.corsa}.annulla").touch()
        if dati.get("pgid"):
            for segnale, attesa in ((signal.SIGTERM, 10), (signal.SIGKILL, 5)):
                try:
                    os.killpg(dati["pgid"], segnale)
                except ProcessLookupError:
                    break
                fine = time.monotonic() + attesa
                while time.monotonic() < fine:
                    try:
                        os.killpg(dati["pgid"], 0)
                    except ProcessLookupError:
                        break
                    time.sleep(0.2)
                else:
                    continue
                break
        return "ok", {"annullata": True}, "Ho fermato l'analisi."


def main():
    p = argparse.ArgumentParser(description="Motore di profilemetananni (eventi JSON, docs/contratto_motore.md).")
    p.add_argument("comando", choices=["info", "installa", "verifica", "stima", "esegui", "annulla", "sicurezza",
                                       "referto"])
    p.add_argument("--progetto")
    p.add_argument("--corsa", default="")
    p.add_argument("--ingresso", help="sicurezza: richiesta JSON (prodotto, temperature, conte)")
    a = p.parse_args()
    if a.comando == "installa":   # l'installatore parla gia' da solo il contratto (eventi propri, dall'inizio alla fine)
        os.execvp("bash", ["bash", str(ROOT / "installer" / "installa_motore.sh"), "--json", "--si"])
    sys.stdout.reconfigure(encoding="utf-8")
    m = Motore(a)
    m.evento("inizio", f"Comando {a.comando} avviato.", comando=a.comando, corsa=m.corsa, log=str(m.log))
    try:
        esito, risultato, messaggio = getattr(m, a.comando)()
        codice = 0
    except Errore as e:
        passo = e.passo or m.passo
        m.evento("errore", e.messaggio, codice=e.codice, cosa_fare=e.cosa_fare, passo=passo)
        esito, risultato, codice = "errore", {"codice": e.codice, "passo": passo}, CODICE_USCITA.get(e.codice, 4)
        messaggio = messaggio_fine(e.messaggio, e.cosa_fare, passo)
    except Annullata:
        esito, risultato, messaggio, codice = "annullata", {}, "Annullata: i passi finiti restano, quelli a metà si rifanno.", 3
    except Exception as e:   # errore nostro: lo si dice, e il dettaglio va nel log
        m.scrivi(f"ERRORE INTERNO: {e!r}")
        cosa_fare = f"Manda a noi il file {m.log}."
        m.evento("errore", "Errore imprevisto del motore.", codice="ERRORE_INTERNO", cosa_fare=cosa_fare, passo=m.passo)
        esito, risultato, codice = "errore", {"codice": "ERRORE_INTERNO", "passo": m.passo}, 4
        messaggio = messaggio_fine("Errore imprevisto del motore.", cosa_fare, m.passo)
    m.evento("fine", messaggio, esito=esito, risultato=risultato)
    return codice


if __name__ == "__main__":
    sys.exit(main())
