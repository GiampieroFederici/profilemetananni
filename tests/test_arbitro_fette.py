# -*- coding: utf-8 -*-
"""Arbitro delle fette a memoria fissa (PMN 1.3, 10/11/2026).

Prima `unisci` teneva in un dizionario tutte le read allineate (circa 350 byte l'una, 0,33 GB per milione). Ora le
fette.tsv arrivano ordinate per nome della read e si leggono insieme, una read alla volta. Stesse read tenute e stessi
marcatori di prima; cambia solo l'ordine delle righe del mapout (per nome della read).
Gira anche su Windows:  python -m pytest tests/test_arbitro_fette.py"""
import random
import sys
from pathlib import Path

import pytest

RADICE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADICE / "motore"))
import arbitro_fette  # noqa: E402
from mapq_bowtie2 import mapq  # noqa: E402


def come_prima(fette):
    """L'arbitro della 1.2 (dizionario di tutte le read): le righe "read<TAB>marker" tenute."""
    best = {}
    for k, righe in enumerate(fette):
        for r, m, a, x, ln, q in righe:
            a, x = int(a), int(x) if x else None
            cur = best.get(r)
            if cur is None:
                best[r] = [a, x, m, int(ln), int(q), k, None]
            elif a > cur[0]:
                best[r] = [a, x, m, int(ln), int(q), k, cur[0] if cur[6] is None else max(cur[0], cur[6])]
            else:
                cur[6] = a if cur[6] is None else max(cur[6], a)
    out = []
    for r, (a, x, m, ln, qbt, _k, other) in best.items():
        cands = [v for v in (x, other) if v is not None]
        q = qbt if len(fette) == 1 else mapq(a, max(cands) if cands else None, ln)
        if arbitro_fette.passa_filtro(m, q):
            out.append(f"{r}\t{m}")
    return out


def fette_finte(n_fette, n_read, seme=1992):
    """Righe come quelle di `compatta`, nell'ordine sparso di Bowtie2 con più processori; molte read in più fette,
    con pareggi di AS fra fette (decide la fetta col numero più basso)."""
    rnd = random.Random(seme)
    fette = []
    for k in range(n_fette):
        righe = []
        for i in rnd.sample(range(n_read), n_read * 2 // 3):
            marker = rnd.choice(["UniRef90_A0A%04d|1__5|SGB%d" % (rnd.randrange(50), k), "GeneID:%d" % k, "VDB|%d" % k])
            a = -rnd.choice([0, 0, 5, 6, 12, 30, 61])
            x = rnd.choice(["", str(a - rnd.choice([0, 3, 20]))])
            righe.append((f"SRR1.{i}__1.150", marker, str(a), x, "150", str(rnd.choice([0, 1, 23, 42]))))
        fette.append(righe)
    return fette


def scrivi(tmp_path, fette, ordinate=True):
    percorsi = []
    for k, righe in enumerate(fette):
        f = tmp_path / f"{k + 1}.tsv"
        with open(f, "w", encoding="utf-8", newline="\n") as t:
            for r in (sorted(righe, key=lambda c: c[0].encode()) if ordinate else righe):
                t.write("\t".join(r) + "\n")
        percorsi.append(str(f))
    (tmp_path / "nreads.txt").write_text("1000 150.0 0\n", encoding="utf-8")
    return percorsi


@pytest.mark.parametrize("n_fette", [1, 2, 6])
def test_stesse_read_e_stessi_marcatori_di_prima(tmp_path, n_fette, capsys):
    fette = fette_finte(n_fette, 3000)
    arbitro_fette.unisci(str(tmp_path / "nreads.txt"), str(tmp_path / "u.mapout"), scrivi(tmp_path, fette))
    righe = (tmp_path / "u.mapout").read_text(encoding="utf-8").split("\n")
    assert righe[-2:] == ["#nreads\t1000", "#avg_read_length\t150.0"]
    atteso = come_prima([sorted(f, key=lambda c: c[0].encode()) for f in fette])
    assert len(atteso) > 500 and sorted(righe[:-2]) == sorted(atteso)
    assert f"tenute dopo il filtro MetaPhlAn: {len(atteso)}" in capsys.readouterr().out


def test_mapout_ordinato_per_nome_della_read(tmp_path):
    """Lo stesso mapout a ogni corsa, qualunque sia l'ordine in cui Bowtie2 ha scritto le read."""
    arbitro_fette.unisci(str(tmp_path / "nreads.txt"), str(tmp_path / "u.mapout"), scrivi(tmp_path, fette_finte(3, 500)))
    nomi = [r.split("\t")[0].encode() for r in (tmp_path / "u.mapout").read_text(encoding="utf-8").split("\n")[:-2]]
    assert nomi == sorted(nomi) and len(nomi) > 100


def test_fetta_non_ordinata_si_ferma(tmp_path):
    """Una fetta.tsv non ordinata darebbe un mapout sbagliato senza un errore: l'arbitro si ferma e lo dice."""
    percorsi = scrivi(tmp_path, fette_finte(2, 500), ordinate=False)
    with pytest.raises(SystemExit) as e:
        arbitro_fette.unisci(str(tmp_path / "nreads.txt"), str(tmp_path / "u.mapout"), percorsi)
    assert "non è ordinato" in str(e.value)
