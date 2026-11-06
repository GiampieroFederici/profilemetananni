# -*- coding: utf-8 -*-
"""1.2 (6/11, sessione G1 sulle guide): due difetti visti sul campione d'esempio.
1. Stima tarata sul PC libero: l'esempio dura 200-226 s; servono la velocità dell'ospite local, il fisso di Kraken
   (database) e quello di MetaPhlAn col database ridotto. La stima non sta sotto il tempo vero e non lo supera del 30 %.
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
    assert 226 <= stima <= 1.3 * 226, stima               # vero: 200-226 s (6/11, IT e EN, 24 processori, PC libero)


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


def test_v1_fonte_ripetuta_diventa_come_sopra():
    """V1 (VM 6/11): nella tabella dei parametri la stessa fonte lunga stava in tre righe di fila."""
    p = {"kraken_db": "/db/k2_pluspf_20260626", "kraken_profile": "completo", "kraken_confidence": "0.5",
         "bracken_min_reads": "10", "abundance_threshold_pct": "0.1"}
    righe = referto.righe_parametri({"parametri": p})
    fonti = [r[3] for r in righe if r[0].startswith(("Confidenza", "Letture minime", "Soglia di abbondanza"))]
    assert len(fonti) == 3 and len(fonti[0]) > 40 and fonti[1:] == ["come sopra", "come sopra"]


def test_ospite_piu_lento_con_meno_processori():
    """6/11: su un PC con meno processori la rimozione dell'ospite dura di più (Bowtie2 usa tutti i processori). Misurato
    sulle stesse 946.123 coppie: 24 -> 113 s, 8 -> 159 s, 4 -> 271 s. La stima non sta sotto il vero e non lo supera del 30 %
    a 4 processori; a 8 è prudente."""
    import pmn_motore as pm
    camp = [("salume", 1_000_000, 0)]

    def ospite(p):
        return pm.tempi(camp, {"hosts": ["sus_scrofa"], "motore": {"processori": p}, "execution": {"threads": p}})["ospite"]
    assert ospite(8) >= 1.41 * ospite(24) and ospite(4) >= 2.40 * ospite(24) - 1
    assert ospite(4) <= 1.3 * 2.40 * ospite(24) and ospite(8) <= 1.3 * 1.41 * ospite(24)
