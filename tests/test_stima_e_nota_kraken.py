# -*- coding: utf-8 -*-
"""1.2 (6/11, sessione G1 sulle guide): due difetti visti sul campione d'esempio.
1. La stima diceva "circa 5 minuti" e l'analisi ne durava 6 min 13 s - 6 min 45 s: mancavano i costi fissi (indici
   dell'ospite, database di Kraken) e l'ospite usava la velocità end-to-end. La stima ora non sta sotto il tempo vero.
2. Il referto diceva sempre che mammiferi e virus sono "nella tabella successiva, a parte", anche quando quella
   tabella non c'era (con 0,5 + 0,1 % è il caso normale).
Gira con l'app o con la suite del motore:  python -m pytest tests/test_stima_e_nota_kraken.py"""
import re
import shutil
import sys
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADICE / "motore"))
import referto  # noqa: E402

NOTA_LUNGA = "nella tabella successiva"


def test_stima_dell_esempio_non_sotto_il_tempo_vero():
    import pmn_motore as pm
    camp = [("mini_SF3RAt7", 200_000, 0)]                 # 200.000 coppie, read locali (nessuno scarico)
    cfg = {"hosts": ["sus_scrofa"], "filter_human": True, "motore": {"processori": 24}}
    stima = sum(pm.tempi(camp, cfg).values())
    assert 405 <= stima <= 1.3 * 405, stima               # vero: 373-405 s (6/11, IT e EN, 24 processori)


def referto_finto(tmp_path):
    finto = RADICE / "installer" / "finto"
    r = tmp_path / "risultati"
    for sotto in ("metaphlan", "kraken", "tabelle"):
        (r / sotto).mkdir(parents=True)
    shutil.copy(finto / "SRR4875279_profile.txt", r / "metaphlan")
    for est in ("bracken", "k2report"):
        shutil.copy(finto / f"SRR4875279.{est}", r / "kraken")
    shutil.copy(finto / "risultati.json", r)
    shutil.copy(finto / "parameters.tsv", r / "tabelle")
    return referto.raccogli(r, {})


def sezione_kraken(d):
    return referto.html_referto(d).split("<h2>3.")[1].split("<h2>4.")[0]


def test_nota_solo_se_c_e_la_tabella_a_parte(tmp_path):
    d = referto_finto(tmp_path)
    for c in d["campioni"]:
        c["kraken"] = [r for r in (c["kraken"] or []) if r["categoria"] in referto.MICROBI]
    s = sezione_kraken(d)
    assert NOTA_LUNGA not in s and "Segnalati a parte" not in s
    assert "Solo batteri, archei e funghi." in s


def test_nota_lunga_con_la_tabella_a_parte(tmp_path):
    d = referto_finto(tmp_path)
    c = next(c for c in d["campioni"] if c["kraken"])
    c["kraken"].append({"nome": "Homo sapiens", "categoria": "altro", "pct": 0.2, "pct_microbi": 0.0, "letture": 50,
                        "taxid": 9606})
    s = sezione_kraken(d)
    assert NOTA_LUNGA in s and "Segnalati a parte" in s
