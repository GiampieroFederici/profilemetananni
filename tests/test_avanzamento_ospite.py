# -*- coding: utf-8 -*-
"""13/11/2026 (prova su un portatile con Ubuntu): durante il filtro dell'ospite l'app restava 2 h 24 min senza un
segno. Ora il passo dice a che punto è e il motore lo trasforma in eventi "avanzamento" (docs/contratto_motore.md §4).
- steps/21_hostfilter.sh scrive "[progress] N": quanto Bowtie2 ha già letto del suo ingresso compresso, guardato da
  fuori (/proc), senza mettere nulla nel flusso bowtie2 | samtools.
- motore/pmn_motore.py: da quella riga, percentuale e tempo che manca al ritmo vero del passo.
Rossi sul codice di e574d05, verdi dopo. Il test del passo usa bash e /proc: gira nella WSL o su Linux.
  python -m pytest tests/test_avanzamento_ospite.py"""
import argparse
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

linux = pytest.mark.skipif(os.name == "nt" or not shutil.which("bash") or not Path("/proc/self/fdinfo").is_dir(),
                           reason="steps/21_hostfilter.sh: Linux/WSL only")


# ---------------- motore: "[progress] N" diventa un evento avanzamento ----------------
def test_il_motore_manda_l_avanzamento_dentro_il_filtro_dell_ospite(tmp_path, monkeypatch, capsys):
    stato = tmp_path / "stato"
    stato.mkdir()
    monkeypatch.setattr(pm, "STATO", stato)
    monkeypatch.setattr(pm, "PMN_HOME", tmp_path)
    (tmp_path / "srr.txt").write_text("S1\n", encoding="utf-8")
    progetto = tmp_path / "progetto" / "config.yaml"
    progetto.parent.mkdir()
    m = pm.Motore(argparse.Namespace(comando="esegui", progetto=str(progetto)))
    m.log = tmp_path / "esegui.log"
    orologio = [0.0]
    monkeypatch.setattr(pm.time, "monotonic", lambda: orologio[0])

    class RunLento:
        pid = 4242

        def __init__(self, *a, **k):
            self.stdout = self.righe()

        def righe(self):
            yield "2026-11-13 07:16:23 [INFO] [locale] trim_S1\n"
            orologio[0] = 100
            yield "2026-11-13 07:20:13 [INFO] [locale] hf_S1\n"
            yield "2026-11-13 07:20:13 [INFO] Filtro host di S1: passo 1 (sus_scrofa) ...\n"
            orologio[0] = 100 + 600                    # 10 minuti dopo Bowtie2 ha letto un quarto delle read
            yield "2026-11-13 07:30:13 [INFO] [progress] 25\n"
            orologio[0] = 100 + 1200
            yield "2026-11-13 07:40:13 [INFO] [progress] 50\n"
            yield "2026-11-13 07:40:14 [INFO] [progress] 0\n"       # niente da dire: nessun evento

        def wait(self):
            return 0

    monkeypatch.setattr(pm.subprocess, "Popen", RunLento)
    cfg = {"paths": {"srr_list": str(tmp_path / "srr.txt")}, "hosts": ["sus_scrofa"]}
    m._run_sh(progetto, cfg, stato / "esegui.lock", camp=[("S1", 1_000_000, 0)])
    ospite = [e for e in map(json.loads, capsys.readouterr().out.splitlines())
              if e["tipo"] == "avanzamento" and e["passo"] == "ospite"]
    assert len(ospite) == 3                            # l'inizio del passo, poi i due avanzamenti (prima: solo l'inizio)
    inizio, quarto, meta = ospite
    assert "questo passo è al 25 %" in quarto["messaggio"] and "questo passo è al 50 %" in meta["messaggio"]
    assert quarto["messaggio"].startswith(inizio["messaggio"])      # stesso testo del passo, più il punto dov'è
    dopo = inizio["eta_s"] - inizio["passo_s"]          # i passi che vengono dopo l'ospite, dalla regola di stima
    # un quarto in 600 s: il passo dura 2.400 s, ne mancano 1.800; a metà ne mancano 1.200
    assert (quarto["passo_s"], meta["passo_s"]) == (1800, 1200)
    assert (quarto["eta_s"], meta["eta_s"]) == (1800 + dopo, 1200 + dopo)
    assert inizio["percentuale"] <= quarto["percentuale"] < meta["percentuale"] < 100   # la barra non torna indietro
    for e in (quarto, meta):                           # stessi campi dell'avanzamento di inizio passo (contratto §4)
        assert set(e) == set(inizio) and (e["campione"], e["fatto"], e["totale"]) == ("S1", 1, 1)


# ---------------- passo: Bowtie2 guardato da fuori ----------------
# Bowtie2 finto: il programma che allinea si chiama bowtie2-align-s, tiene aperto R1 ed è arrivato a metà
BOWTIE2 = """#!/bin/bash
while [ $# -gt 0 ]; do case "$1" in -1|-U) R1="$2"; shift 2 ;; *) shift ;; esac; done
echo "100 reads; of these:" >&2
"$(dirname "$0")/bowtie2-align-s" "$R1"
"""
ALLINEA = """#!/bin/bash
exec 3< "$1"
dd of=/dev/null bs=$(( $(stat -c %s "$1") / 2 )) count=1 <&3 2> /dev/null
sleep 1.5
"""
SAMTOOLS = """#!/bin/bash
if [ "$1" = view ]; then cat; exit 0; fi
while [ $# -gt 0 ]; do case "$1" in -1) U1="$2"; shift 2 ;; -2) U2="$2"; shift 2 ;; *) shift ;; esac; done
cat > /dev/null
printf '0123456789' > "$U1"; printf '0123456789' > "$U2"
echo "[M::bam2fq_mainloop] processed 2 reads" >&2
"""


@linux
def test_il_passo_dice_a_che_punto_e_bowtie2(tmp_path):
    finti = tmp_path / "finti"
    finti.mkdir()
    for nome, testo in (("bowtie2", BOWTIE2), ("bowtie2-align-s", ALLINEA), ("samtools", SAMTOOLS)):
        (finti / nome).write_text(testo, encoding="utf-8")
        (finti / nome).chmod(0o755)
    for nome in ("r_1.fastq.gz", "r_2.fastq.gz"):
        (tmp_path / nome).write_bytes(b"x" * 1000)
    for indice in ("maiale", "uomo"):
        (tmp_path / f"{indice}.1.bt2").write_bytes(b"x")
    env = {**os.environ, "PATH": f"{finti}:{os.environ['PATH']}", "PMN_AVANZAMENTO_S": "0.3", "PMN_BT2_MM": "no",
           "TMPDIR": str(tmp_path), "NO_COLOR": "1"}
    p = subprocess.run(["bash", str(RADICE / "steps" / "21_hostfilter.sh"), "--sample", "S1",
                        "--in1", str(tmp_path / "r_1.fastq.gz"), "--in2", str(tmp_path / "r_2.fastq.gz"),
                        "--index", str(tmp_path / "maiale"), "--index", str(tmp_path / "uomo"),
                        "--out", str(tmp_path / "uscita"), "--threads", "1"],
                       capture_output=True, text=True, timeout=60, env=env)
    assert p.returncode == 0, p.stdout + p.stderr
    righe = [r.split("[progress] ")[1] for r in p.stdout.splitlines() if "[progress] " in r]
    # primo passaggio: metà di R1 letta, l'uscita non c'è ancora -> 50 % del passo intero; secondo passaggio (sulle
    # read rimaste, 10 byte, che pesano un decimo): (10 x 1.000 + 5) su (10 x 1.000 + 10) -> 99
    assert set(righe) == {"50", "99"} and righe == sorted(righe), p.stdout
    assert (tmp_path / "uscita" / "S1_nonhost_1.fastq.gz").read_bytes() == b"0123456789"
    assert "Terminated" not in p.stderr                 # chiudere il controllo non lascia righe che sembrano guasti


# ---------------- passo in due fasi (18/11/2026): l'avanzamento attraversa fase 1, fase 2 e passaggio dopo ----------------
# Bowtie2 finto: 40.000 coppie, una su quattro con le due read non allineate (flag 77), poi tiene aperto R1 a metà
BOWTIE2_COPPIE = """#!/bin/bash
while [ $# -gt 0 ]; do case "$1" in -1|-U) R1="$2"; shift 2 ;; *) shift ;; esac; done
echo "40000 reads; of these:" >&2
awk 'BEGIN { for (i = 1; i <= 40000; i++) print "r" i "\\t" (i % 4 ? 65 : 77) }'
"$(dirname "$0")/bowtie2-align-s" "$R1"
"""


@linux
def test_l_avanzamento_attraversa_le_due_fasi(tmp_path):
    import gzip
    finti = tmp_path / "finti"
    finti.mkdir()
    for nome, testo in (("bowtie2", BOWTIE2_COPPIE), ("bowtie2-align-s", ALLINEA), ("samtools", SAMTOOLS)):
        (finti / nome).write_text(testo, encoding="utf-8")
        (finti / nome).chmod(0o755)
    for m in (1, 2):
        with gzip.open(tmp_path / f"r_{m}.fastq.gz", "wt") as g:
            g.write("".join(f"@r{i} {m}\nACGT\n+\nIIII\n" for i in range(1, 40001)))
    for indice in ("maiale", "uomo"):
        (tmp_path / f"{indice}.1.bt2").write_bytes(b"x")
    env = {**os.environ, "PATH": f"{finti}:{os.environ['PATH']}", "PMN_AVANZAMENTO_S": "0.3", "PMN_BT2_MM": "no",
           "TMPDIR": str(tmp_path), "NO_COLOR": "1"}
    p = subprocess.run(["bash", str(RADICE / "steps" / "21_hostfilter.sh"), "--sample", "S1",
                        "--in1", str(tmp_path / "r_1.fastq.gz"), "--in2", str(tmp_path / "r_2.fastq.gz"),
                        "--index", str(tmp_path / "maiale"), "--index", str(tmp_path / "uomo"),
                        "--out", str(tmp_path / "uscita"), "--log-dir", str(tmp_path / "log"), "--threads", "1",
                        "--prefilter", "very-fast"],
                       capture_output=True, text=True, timeout=60, env=env)
    assert p.returncode == 0, p.stdout + p.stderr
    righe = [r.split("[progress] ")[1] for r in p.stdout.splitlines() if "[progress] " in r]
    # Pesi: fase 1 = 3, fase 2 = 4, passaggio dopo = 1, per le stesse coppie. Un quarto delle coppie passa alla fase 2.
    # fase 1 a metà di R1: 3 x 0,5 su (3 + (4 + 1) x 0,25) -> 35
    # fase 2 a metà del suo ingresso (l'uscita non c'è ancora): (3 + 4 x 0,25 x 0,5) su (3 + 4 x 0,25) -> 87
    # uomo (10 byte, pesa 1): quasi tutto fatto -> 99
    assert set(righe) == {"35", "87", "99"} and righe == sorted(righe), p.stdout
    assert (tmp_path / "uscita" / "S1_nonhost_1.fastq.gz").read_bytes() == b"0123456789"
    assert (tmp_path / "log" / "S1.maiale.coppie.tsv").read_text() == "entrate\ttenute\n40000\t1\n"
    assert (tmp_path / "log" / "S1.maiale_fase2.bowtie2.log").is_file()
    assert "Terminated" not in p.stderr
