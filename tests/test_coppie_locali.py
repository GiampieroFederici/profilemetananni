# -*- coding: utf-8 -*-
"""VM B4-f (30/10): per le read sul computer la stima calcolava le coppie dalla dimensione dei file (164,6 byte per
coppia, misurati su SF3RAt7). Casuale (read casuali) diventava 12.514 coppie in "Prima di partire", mentre il referto
diceva 20.000 dopo aver tolto l'ospite: le coppie non possono crescere. Ora fino a 64 MB si contano; oltre, i byte per
read si misurano sul file stesso. Il numero entra anche nella stima dei tempi e dello spazio.
Gira con la suite del motore e su Windows."""
import gzip
import random
import sys
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADICE / "motore"))
import pmn_motore as pm  # noqa: E402

CASUALE = RADICE / "tests" / "dati" / "casuale"


def righe(f):
    with gzip.open(f, "rb") as g:
        return sum(pezzo.count(b"\n") for pezzo in iter(lambda: g.read(2 ** 20), b""))


def test_casuale_file_veri():
    file = ["CASUALE_R1.fastq.gz", "CASUALE_R2.fastq.gz"]
    assert pm.campioni_locali(CASUALE) == [("CASUALE", file)]
    vere = righe(CASUALE / file[0]) // 4
    assert vere == 20000 and pm.coppie_locali(CASUALE, file) == vere
    vecchia = round(sum((CASUALE / f).stat().st_size for f in file) / pm.BYTE_PER_COPPIA)
    assert vecchia == 12514                                   # il numero sbagliato visto sulla VM


def test_file_grandi_misura_sul_file(tmp_path, monkeypatch):
    """Oltre la soglia (qui abbassata) i byte per read si misurano sui primi 4 MB del file stesso: entro il 3 %."""
    rnd = random.Random(7)
    with gzip.open(tmp_path / "G_R1.fastq.gz", "wt") as g:
        for i in range(60000):
            s = "".join(rnd.choice("ACGT") for _ in range(150))
            g.write(f"@G.{i}\n{s}\n+\n{'I' * 150}\n")
    (tmp_path / "G_R2.fastq.gz").write_bytes((tmp_path / "G_R1.fastq.gz").read_bytes())
    monkeypatch.setattr(pm, "COPPIE_ESATTE_MAX", 0)
    monkeypatch.setattr(pm, "CAMPIONE_GZ", 2 ** 20)
    stima = pm.coppie_locali(tmp_path, ["G_R1.fastq.gz", "G_R2.fastq.gz"])
    assert abs(stima - 60000) / 60000 < 0.03, stima


def test_gz_rovinato_non_ferma_la_stima(tmp_path):
    (tmp_path / "X_R1.fastq.gz").write_bytes(b"non e' un gzip" * 100)
    (tmp_path / "X_R2.fastq.gz").write_bytes(b"non e' un gzip" * 100)
    assert pm.coppie_locali(tmp_path, ["X_R1.fastq.gz", "X_R2.fastq.gz"]) == round(2800 / pm.BYTE_PER_COPPIA)
