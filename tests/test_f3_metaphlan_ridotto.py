# -*- coding: utf-8 -*-
"""F3, N1 (di serie dal 5/11): MetaPhlAn 4.2.4 VERO con il database intero e con quello ridotto ai clade del
campione (motore/metaphlan_ridotto.py) deve scrivere lo stesso profilo, byte per byte. Database sintetico piccolo con i
casi delicati: marcatori di una specie con "ext" verso una specie presente (filtro dei marcatori esterni), una specie
esterna senza read, un marcatore il cui clade non segue la regola del nome, un marcatore che il database non ha, un
marcatore di virus (VDB), un mapout senza read. La prova sul .pkl vero (6 Ciauscolo, 5 sottocampioni dell'alfa,
Zymo, un campione senza read, il profilo classico del server di SF3RAt7) è in F3_velocita_RAM: identica al byte. Serve l'ambiente pmn_metaphlan (WSL); senza, il test si salta."""
import bz2
import os
import pickle
import random
import subprocess
import sys
from pathlib import Path

import pytest

RADICE = Path(__file__).resolve().parent.parent
INDICE = "mpa_vJan25_CHOCOPhlAnSGB_202503"
CANDIDATI = [os.environ.get("PMN_MPA_PY", ""), str(Path.home() / "miniforge3/envs/pmn_metaphlan/bin/python"),
             "/home/pmn/.pmn/mamba/envs/pmn_metaphlan/bin/python"]
MPA_PY = next((p for p in CANDIDATI if p and os.path.isfile(p)), None)
pytestmark = pytest.mark.skipif(MPA_PY is None, reason="serve l'ambiente pmn_metaphlan con MetaPhlAn 4.2.4")

GENERI = [("g__Latilactobacillus", "s__Latilactobacillus_sakei", "2767893", "1599"),
          ("g__Staphylococcus", "s__Staphylococcus_xylosus", "1279", "1288"),
          ("g__Staphylococcus", "s__Staphylococcus_equorum", "1279", "246432"),
          ("g__Leuconostoc", "s__Leuconostoc_carnosum", "1243", "1252"),
          ("g__Debaryomyces", "s__Debaryomyces_hansenii", "4958", "4959")]


def database():
    rnd = random.Random(1992)
    taxonomy, markers = {}, {}
    for n, (g, s, gid, sid) in enumerate(GENERI, 1):
        nome = f"k__Bacteria|p__Bacillota|c__Bacilli|o__Lactobacillales|f__F{gid}|{g}|{s}|t__SGB{n}"
        taxonomy[nome] = (f"2|1239|91061|186826|{gid}0|{gid}|{sid}|", 2_000_000 + 10_000 * n)
        for i in range(30):
            ext = ["SGB2"] if n == 1 and i < 10 else (["SGB5"] if n == 3 and i < 5 else [])
            markers[f"UniRef90_M{n}_{i}|1__{n}|SGB{n}"] = {"clade": f"t__SGB{n}", "ext": ext,
                                                          "len": rnd.randint(400, 2000), "taxon": nome}
    markers["EUK_strano_7|nome"] = {"clade": "t__SGB4", "ext": [], "len": 900, "taxon": "x"}   # eccezione alla regola
    sakei = [k for k in taxonomy if "sakei" in k][0].rsplit("|", 1)[0]
    merged = {(sakei, taxonomy[sakei + "|t__SGB1"][0].rstrip("|")): [("s__Latilactobacillus_curvatus", 0.95)]}
    return {"markers": markers, "taxonomy": taxonomy, "merged_taxon": merged}


def mapout(percorso, conteggi, extra=()):
    rnd = random.Random(7)
    righe = []
    for marcatore, n in conteggi.items():
        righe += [f"r{rnd.random():.12f}\t{marcatore}" for _ in range(n)]
    righe += [f"r{rnd.random():.12f}\t{m}" for m in extra]
    percorso.write_text("".join(r + "\n" for r in righe) + "#nreads\t20000\n#avg_read_length\t148.5", encoding="utf-8")


def profilo(tmp_path, m, ridotto):
    out = tmp_path / f"{m.stem}.{'ridotto' if ridotto else 'intero'}.txt"
    env = {**os.environ, "PMN_MPA_RIDOTTO": str(tmp_path / "ridotto.sqlite") if ridotto else "no"}   # no = .pkl intero
    p = subprocess.run([MPA_PY, str(RADICE / "motore" / "metaphlan_mapout.py"), str(m), "--input_type", "mapout",
                        "--nproc", "1", "--db_dir", str(tmp_path / "db"), "--index", INDICE, "--offline",
                        "--sample_id", m.stem, "-o", str(tmp_path / "profilo.txt")],
                       capture_output=True, text=True, env=env, timeout=300)
    assert p.returncode == 0, p.stdout + p.stderr
    os.replace(tmp_path / "profilo.txt", out)
    return out.read_bytes()


def test_profilo_identico_con_il_database_ridotto(tmp_path):
    (tmp_path / "db").mkdir()
    pkl = tmp_path / "db" / f"{INDICE}.pkl"
    with bz2.BZ2File(pkl, "w") as f:
        pickle.dump(database(), f)
    p = subprocess.run([MPA_PY, str(RADICE / "motore" / "metaphlan_ridotto.py"), "prepara", str(pkl),
                        str(tmp_path / "ridotto.sqlite")], capture_output=True, text=True, timeout=300)
    assert p.returncode == 0 and "eccezioni 1" in p.stdout, p.stdout + p.stderr
    casi = {
        # sakei con molte read; S. xylosus (ext di 10 marcatori di sakei) con read in più di un terzo dei marcatori
        "A": ({**{f"UniRef90_M1_{i}|1__1|SGB1": 5 + i for i in range(30)},
               **{f"UniRef90_M2_{i}|1__2|SGB2": 3 for i in range(15)},
               **{f"UniRef90_M3_{i}|1__3|SGB3": 2 for i in range(0, 30, 3)}, "EUK_strano_7|nome": 4},
              ["UniRef90_NON_NEL_DB|1__9|SGB999", "VDB|virus_1"]),
        "B": ({}, []),                                                  # nessuna read: UNCLASSIFIED
        "C": ({f"UniRef90_M4_{i}|1__4|SGB4": 1 for i in range(0, 30, 2)}, ["EUK_strano_7|nome"]),
        "D": ({f"UniRef90_M2_{i}|1__2|SGB2": 1 for i in range(5)}, []),  # sotto la soglia dei marcatori con read
    }
    for nome, (conteggi, extra) in casi.items():
        m = tmp_path / f"{nome}.mapout"
        mapout(m, conteggi, extra)
        intero, ridotto = profilo(tmp_path, m, False), profilo(tmp_path, m, True)
        assert intero == ridotto, (nome, intero.decode(), ridotto.decode())
    assert b"s__Latilactobacillus_sakei" in profilo(tmp_path, tmp_path / "A.mapout", False)   # il caso A ha specie


def test_database_ridotto_rifiuta_un_pkl_diverso(tmp_path):
    (tmp_path / "db").mkdir()
    pkl = tmp_path / "db" / f"{INDICE}.pkl"
    with bz2.BZ2File(pkl, "w") as f:
        pickle.dump(database(), f)
    subprocess.run([MPA_PY, str(RADICE / "motore" / "metaphlan_ridotto.py"), "prepara", str(pkl),
                    str(tmp_path / "ridotto.sqlite")], check=True, capture_output=True, timeout=300)
    d = database()
    d["markers"].popitem()
    with bz2.BZ2File(pkl, "w") as f:
        pickle.dump(d, f)
    m = tmp_path / "A.mapout"
    mapout(m, {"UniRef90_M1_1|1__1|SGB1": 3})
    p = subprocess.run([MPA_PY, str(RADICE / "motore" / "metaphlan_mapout.py"), str(m), "--input_type", "mapout",
                        "--nproc", "1", "--db_dir", str(tmp_path / "db"), "--index", INDICE, "--offline",
                        "--sample_id", "A", "-o", str(tmp_path / "p.txt")], capture_output=True, text=True,
                       env={**os.environ, "PMN_MPA_RIDOTTO": str(tmp_path / "ridotto.sqlite")}, timeout=300)
    assert p.returncode != 0 and "MD5 diverso" in p.stdout + p.stderr


def test_auto_costruisce_una_volta_e_rifa_se_il_pkl_cambia(tmp_path):
    """Di serie (PMN_MPA_RIDOTTO non dato = auto): il file derivato nasce accanto al .pkl alla prima chiamata, poi si
    riusa; con un altro .pkl si rifà da solo (chi usa PMN non deve fare passi a mano)."""
    (tmp_path / "db").mkdir()
    pkl = tmp_path / "db" / f"{INDICE}.pkl"
    with bz2.BZ2File(pkl, "w") as f:
        pickle.dump(database(), f)
    m = tmp_path / "A.mapout"
    mapout(m, {f"UniRef90_M1_{i}|1__1|SGB1": 3 for i in range(30)})
    derivato = tmp_path / "db" / f"{INDICE}.ridotto.sqlite"

    def chiama():
        p = subprocess.run([MPA_PY, str(RADICE / "motore" / "metaphlan_mapout.py"), str(m), "--input_type", "mapout",
                            "--nproc", "1", "--db_dir", str(tmp_path / "db"), "--index", INDICE, "--offline",
                            "--sample_id", "A", "-o", str(tmp_path / "p.txt")], capture_output=True, text=True,
                           env={k: v for k, v in os.environ.items() if k != "PMN_MPA_RIDOTTO"}, timeout=300)
        assert p.returncode == 0, p.stdout + p.stderr
        return p.stdout
    assert "marcatori 151" in chiama() and derivato.is_file()          # costruito alla prima chiamata
    prima = derivato.stat().st_mtime_ns
    assert "marcatori" not in chiama() and derivato.stat().st_mtime_ns == prima   # riusato
    d = database()
    d["markers"].popitem()
    with bz2.BZ2File(pkl, "w") as f:
        pickle.dump(d, f)
    assert "marcatori 150" in chiama()                                  # .pkl cambiato: rifatto
