# -*- coding: utf-8 -*-
"""F3 (PMN 1.2, 5/11/2026): più veloce senza cambiare i risultati. Proposte e criteri, fissati prima dei dati:
implementazione/decisioni/2026-11-05_F3_proposte_velocita_RAM.md (privata).
- L1: in bin/run.sh prima MetaPhlAn su tutti i campioni, poi Kraken su tutti (la cache del disco di Kraken resta).
- L3: con le fette il .pkl di MetaPhlAn si legge una volta per tutti i campioni (lotto dei profili e dell'alfa), con
  gli stessi argomenti di MetaPhlAn della chiamata singola; il mapout prende il suo nome solo quando è intero.
- L5: la stima del tempo usa le quote d'ospite misurate (anche per i campioni non ancora filtrati).
I test con bash girano nella WSL:  ~/miniforge3/envs/pmn_reports_py/bin/python -m pytest tests/test_f3_velocita.py"""
import gzip
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

RADICE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADICE / "motore"))
import pmn_motore as pm  # noqa: E402

linux = pytest.mark.skipif(os.name == "nt" or not shutil.which("bash"), reason="bin/run.sh: Linux/WSL only")
INDICE = "mpa_vJan25_CHOCOPhlAnSGB_202503"

# --- strumenti finti del motore installato (PMN_ENVS) ---
READ_FASTX = """#!/usr/bin/env bash
printf '@r1__1\\nACGT\\n+\\nIIII\\n'
echo "2 100.0 0" >&2
"""
BOWTIE2 = """#!/usr/bin/env bash
while [ $# -gt 0 ]; do case "$1" in -S) SAM="$2"; shift 2;; -x) X="$2"; shift 2;; *) shift;; esac; done
echo "$X" >> "$TRACCIA/bowtie2.txt"
printf 'r1__1\\t0\\tGeneID:1\\t1\\t42\\t4M\\t*\\t0\\t0\\tACGT\\tIIII\\tAS:i:0\\n' > "$SAM"
"""
# python di pmn_metaphlan (metaphlan_mapout.py): annota gli argomenti e scrive i profili (uno o un lotto)
MPA_PY = """#!/usr/bin/env python3
import sys, os
a = sys.argv[2:]
with open(os.path.join(os.environ["TRACCIA"], "metaphlan.txt"), "a") as f:
    f.write(" ".join(a) + "\\n")
if a[0] == "--lotto":
    for r in open(a[1]):
        m, s, o = r.rstrip("\\n").split("\\t")
        open(o, "w").write("#metaphlan " + m + "\\n")
else:
    open(a[a.index("-o") + 1], "w").write("#metaphlan " + a[0] + "\\n")
"""
MERGE = """#!/usr/bin/env bash
cat "$@"
"""


def motore(tmp_path, campioni=("S1", "S2"), tool="metaphlan"):
    """Motore installato finto, read senza ospite già pronte (nonhost) e config del progetto. -> (config, env)"""
    envs, lavoro, tr = tmp_path / "envs", tmp_path / "lavoro", tmp_path / "traccia"
    for d in (envs / "pmn_metaphlan" / "bin", envs / "pmn_reports_py" / "bin", tmp_path / "pmn_tmp", tr,
              lavoro / "nonhost", tmp_path / "read", tmp_path / "db_mpa", tmp_path / "krk"):
        d.mkdir(parents=True, exist_ok=True)
    for nome, testo in (("read_fastx.py", READ_FASTX), ("bowtie2", BOWTIE2), ("python", MPA_PY),
                        ("merge_metaphlan_tables.py", MERGE)):
        f = envs / "pmn_metaphlan" / "bin" / nome
        f.write_text(testo, encoding="utf-8")
        f.chmod(0o755)
    (envs / "pmn_reports_py" / "bin" / "python").symlink_to(sys.executable)   # parse_config.py e l'arbitro veri
    home = tmp_path / "home"
    home.mkdir()
    (home / "installazione.env").write_text(
        f"PMN_ENVS={envs}\nPMN_TMP={tmp_path / 'pmn_tmp'}\nPMN_FETTE={tmp_path / 'fette'}\nPMN_MPA_DB={tmp_path / 'db_mpa'}\n"
        f"PMN_KRAKEN_COMPLETO={tmp_path / 'krk'}\n", encoding="utf-8")
    for s in campioni:
        for i in (1, 2):
            dati = gzip.compress(b"@r\nACGT\n+\nIIII\n")
            (tmp_path / "read" / f"{s}_{i}.fastq.gz").write_bytes(dati)
            (lavoro / "nonhost" / f"{s}_nonhost_{i}.fastq.gz").write_bytes(dati)
    cfg = tmp_path / "progetto" / "config.yaml"
    cfg.parent.mkdir()
    cfg.write_text(f"project_name: prova\ndata_source: local\nhosts: [sus_scrofa]\npaths:\n  work_dir: {lavoro}\n"
                   f"  local_reads_dir: {tmp_path / 'read'}\nprofiling:\n  tool: {tool}\n  metaphlan_index: {INDICE}\n"
                   "motore:\n  metaphlan_modo: fette\n  kraken_db: completo\nexecution:\n  threads: 2\n"
                   "analysis:\n  report: false\n  diversity: false\n", encoding="utf-8")
    env = {**os.environ, "PMN_HOME": str(home), "NO_COLOR": "1", "PMN_LANG": "en", "TRACCIA": str(tr)}
    return cfg, env


def run_sh(cfg, env, *extra):
    p = subprocess.run(["bash", str(RADICE / "bin" / "run.sh"), "--config", str(cfg), "--skip-preflight", "--phase", "b",
                        *extra], capture_output=True, text=True, timeout=120, cwd=cfg.parent, env=env)
    return p, p.stdout + p.stderr


def passi(testo, prefisso):
    return [r.split(prefisso, 1)[1].strip() for r in testo.splitlines() if prefisso in r]


@linux
def test_l1_prima_metaphlan_su_tutti_poi_kraken_su_tutti(tmp_path):
    cfg, env = motore(tmp_path, ("S1", "S2", "S3"), tool="both")
    p, testo = run_sh(cfg, env, "--dry-run")
    assert p.returncode == 0, testo
    profilatori = [x for x in passi(testo, "DRY-RUN step:") if x.startswith(("mpa_", "krk_", "profili_mpa"))]
    assert profilatori == ["mpa_S1", "mpa_S2", "mpa_S3", "profili_mpa", "krk_S1", "krk_S2", "krk_S3"]


@linux
def test_l3_pkl_letto_una_volta_per_tutti_i_campioni(tmp_path):
    """Una sola chiamata di MetaPhlAn (un solo .pkl letto) per i profili di tutti i campioni, con gli stessi
    argomenti che la chiamata singola di metaphlan_fette.sh dava a ognuno."""
    cfg, env = motore(tmp_path)
    p, testo = run_sh(cfg, env)
    assert p.returncode == 0, testo
    chiamate = (tmp_path / "traccia" / "metaphlan.txt").read_text().splitlines()
    assert len(chiamate) == 1 and chiamate[0].startswith("--lotto "), chiamate
    mpa = tmp_path / "lavoro" / "metaphlan"
    for s in ("S1", "S2"):
        assert (mpa / f"{s}_profile.txt").read_text() == f"#metaphlan {mpa}/{s}.mapout\n"
        assert (mpa / f"{s}.mapout").read_text().startswith("r1__1\tGeneID:1\n")
    assert len((tmp_path / "traccia" / "bowtie2.txt").read_text().split()) == 12      # 6 fette x 2 campioni
    assert not list(mpa.glob(".*parziale")) and list((tmp_path / "pmn_tmp").iterdir()) == []


@linux
def test_l3_ripresa_profilo_e_mapout_gia_fatti(tmp_path):
    """Corsa ripresa: S1 ha il profilo (niente), S2 il solo mapout (solo il profilo, nel lotto), S3 niente (fette e
    profilo)."""
    cfg, env = motore(tmp_path, ("S1", "S2", "S3"))
    p, testo = run_sh(cfg, env)
    assert p.returncode == 0, testo
    mpa, tr = tmp_path / "lavoro" / "metaphlan", tmp_path / "traccia"
    (mpa / "S2_profile.txt").unlink()
    (mpa / "S3_profile.txt").unlink()
    (mpa / "S3.mapout").unlink()
    for f in tr.iterdir():
        f.unlink()
    p, testo = run_sh(cfg, env)
    assert p.returncode == 0, testo
    assert len((tr / "bowtie2.txt").read_text().split()) == 6                          # solo S3 sulle fette
    lotto = (tr / "metaphlan.txt").read_text().split()
    assert lotto[0] == "--lotto"
    assert [s for s in ("S1", "S2", "S3") if (mpa / f"{s}_profile.txt").is_file()] == ["S1", "S2", "S3"]


ELENCO_FINTO = {
    "metaphlan/__init__.py": "",
    "metaphlan/utils/__init__.py": "",
    "metaphlan/utils/database_controller.py": "class MetaphlanDatabaseController:\n    pass\n",
    # main() finto: usa check_database come MetaPhlAn, annota argomenti e database, lascia gli indici su TaxClade
    "metaphlan/metaphlan.py": """import json, os, sys
from metaphlan.utils.database_controller import MetaphlanDatabaseController
class TaxClade:
    markers2lens = markers2exts = taxa2clades = None
def main():
    c = MetaphlanDatabaseController()
    c.db_dir, c.index = sys.argv[sys.argv.index("--db_dir") + 1], sys.argv[sys.argv.index("--index") + 1]
    assert c.check_database()
    with open(os.environ["TRACCIA"], "a") as f:
        f.write(json.dumps({"argv": sys.argv, "db": id(c.database_pkl), "pulito": TaxClade.markers2lens is None}) + "\\n")
    if "ROTTO" in sys.argv:
        sys.exit(3)
    TaxClade.markers2lens = TaxClade.markers2exts = TaxClade.taxa2clades = {"m": 1}
    open(sys.argv[sys.argv.index("-o") + 1], "w").write("#" + " ".join(sys.argv) + "\\n")
""",
}


def mapout_py(tmp_path, *argomenti):
    import bz2
    import pickle
    for nome, testo in ELENCO_FINTO.items():
        (tmp_path / "finto" / nome).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / "finto" / nome).write_text(testo, encoding="utf-8")
    if not (tmp_path / f"{INDICE}.pkl").exists():
        with bz2.BZ2File(tmp_path / f"{INDICE}.pkl", "w") as f:
            pickle.dump({"markers": {}, "taxonomy": {}, "merged_taxon": {}}, f)
    traccia = tmp_path / "traccia.jsonl"
    traccia.unlink(missing_ok=True)
    p = subprocess.run([sys.executable, str(RADICE / "motore" / "metaphlan_mapout.py"), *argomenti], capture_output=True,
                       text=True, env={**os.environ, "PYTHONPATH": str(tmp_path / "finto"), "TRACCIA": str(traccia)})
    return p, [json.loads(r) for r in traccia.read_text().splitlines()] if traccia.exists() else []


COMUNI = ["--input_type", "mapout", "--nproc", "2", "--db_dir", "{db}", "--index", INDICE, "--offline"]


def test_l3_lotto_stessi_argomenti_della_chiamata_singola(tmp_path):
    comuni = [x.format(db=tmp_path) for x in COMUNI]
    singoli = []
    for s in ("A", "B"):
        p, t = mapout_py(tmp_path, f"/m/{s}.mapout", *comuni, "--sample_id", s, "-o", str(tmp_path / f"{s}_uno.txt"))
        assert p.returncode == 0, p.stderr
        singoli.append(t[0]["argv"])
    (tmp_path / "elenco.tsv").write_text("".join(f"/m/{s}.mapout\t{s}\t{tmp_path / f'{s}_uno.txt'}\n" for s in "AB"))
    p, t = mapout_py(tmp_path, "--lotto", str(tmp_path / "elenco.tsv"), *comuni)
    assert p.returncode == 0, p.stderr
    assert [x["argv"] for x in t] == singoli                      # riga del comando del profilo uguale
    assert len({x["db"] for x in t}) == 1                          # stesso database: letto una volta
    assert all(x["pulito"] for x in t)                             # indici del campione prima tolti da TaxClade


def test_l3_lotto_si_ferma_al_primo_errore(tmp_path):
    comuni = [x.format(db=tmp_path) for x in COMUNI]
    (tmp_path / "elenco.tsv").write_text(
        "".join(f"/m/{s}.mapout\t{s}\t{tmp_path / f'{s}.txt'}\n" for s in ("A", "ROTTO", "C")))
    p, t = mapout_py(tmp_path, "--lotto", str(tmp_path / "elenco.tsv"), *comuni)
    assert p.returncode == 3 and len(t) == 2
    assert (tmp_path / "A.txt").is_file() and not (tmp_path / "C.txt").exists()


# --- L5: stima del tempo con le quote d'ospite misurate ---
CFG = {"hosts": ["sus_scrofa"], "profiling": {"tool": "both"}, "motore": {"kraken_db": "completo"}}


def test_l5_campioni_non_misurati_prendono_la_media_delle_quote_misurate():
    camp = [("A", 1_000_000, 0), ("B", 1_000_000, 0)]
    sec = {e: s for e, _, _, s in pm.piano(camp, CFG, {"A": 0.9})}       # A filtrato: 90 % di ospite
    assert sec["krk_B"] == pytest.approx(sec["krk_A"])                    # B: 90 %, non il 53 % fisso
    senza = {e: s for e, _, _, s in pm.piano(camp, CFG)}
    assert senza["krk_B"] == pytest.approx(senza["krk_A"])
    assert sec["krk_A"] == pytest.approx(senza["krk_A"] * 0.1 / (1 - pm.OSPITE_QUOTA))


def test_l5_stima_usa_le_quote_di_una_corsa_precedente(tmp_path):
    """Progetto già analizzato una volta (log dell'ospite in pmn_work): la stima usa la quota misurata (90 %)."""
    read = tmp_path / "read"
    read.mkdir()
    for i in (1, 2):
        with gzip.open(read / f"A_R{i}.fastq.gz", "wt") as f:
            f.write("@r\nACGT\n+\nIIII\n" * 1_000_000)   # 1 M di coppie: Kraken stimato in minuti, non in secondi
    cfg = tmp_path / "progetto" / "config.yaml"
    cfg.parent.mkdir()
    cfg.write_text(f"data_source: local\nhosts: [sus_scrofa]\npaths:\n  local_reads_dir: {read}\n", encoding="utf-8")

    def kraken():
        r = subprocess.run([sys.executable, str(RADICE / "motore" / "pmn_motore.py"), "stima", "--progetto", str(cfg)],
                           capture_output=True, text=True, encoding="utf-8", timeout=120,
                           env={**os.environ, "PMN_HOME": str(tmp_path / "pmn_vuota")})
        assert r.returncode == 0, r.stdout + r.stderr
        return json.loads(r.stdout.strip().splitlines()[-1])["risultato"]["tempo_s"]["kraken"]
    prima = kraken()
    log = cfg.parent / "pmn_work" / "hostfilter_logs"
    log.mkdir(parents=True)
    (log / "A.sus_scrofa.bowtie2.log").write_text(
        "1000 reads; of these:\n  1000 (100.00%) were paired; of these:\n    100 (10.00%) aligned concordantly 0 times\n")
    assert kraken() == pytest.approx(prima * 0.1 / (1 - pm.OSPITE_QUOTA), abs=1)


