# -*- coding: utf-8 -*-
# Test di motore/fssp (D048-D050). I numeri "da FSSP" vengono da FSSP.Models.dll (prova F1,
# implementazione/validazione/F1_fssp/): qui servono da ancora contro le regressioni.
import importlib.util
import json
import math
import os
import subprocess
import sys

import pytest

RADICE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(RADICE, "motore"))

from fssp import calcolatrici, confine, ponte, validita  # noqa: E402
from fssp.crescita import crescita_listeria_lab, crescita_singola, espandi  # noqa: E402
from fssp.modelli import LAB, LISTERIA, Prodotto, aw_da_sale, condizioni, non_dissociato, secondario  # noqa: E402

STEP = os.path.join(RADICE, "steps", "45_previsione_fssp.py")
_spec = importlib.util.spec_from_file_location("previsione_fssp", STEP)
step45 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(step45)

COTTO = Prodotto(temperatura=5.0, sale_fase_acquosa=3.0, ph=6.2, nitrito=60.0, acidi={"lattico": 7000.0})


def test_secondario_listeria_uguale_a_fssp():
    s = secondario(LISTERIA, condizioni(COTTO))
    assert s.mu == pytest.approx(0.015091891023458787, rel=1e-12)   # FSSP.Models.dll
    assert s.psi == pytest.approx(0.45043197205775243, rel=1e-12)
    assert not s.bloccato


def test_conversioni():
    assert aw_da_sale(3.0) == pytest.approx(0.9828072, abs=1e-12)    # FSSP: aw = 0,9828072
    # acido lattico non dissociato a pH 3,86 (= pKa): meta' delle molecole
    assert non_dissociato("lattico", 9008.0, 3.86) == pytest.approx(50.0)


def test_sotto_tmin_bloccato():
    s = secondario(LISTERIA, condizioni(COTTO, temperatura=-3.0))
    assert s.bloccato and s.mu == 0.0 and s.psi is None


def test_psi_oltre_uno_non_cresce_ma_non_bloccato():
    p = COTTO.con(sale_fase_acquosa=8.5, ph=5.8, temperatura=2.0)
    s = secondario(LISTERIA, condizioni(p))
    assert not s.bloccato and s.psi > 1.0 and s.mu == 0.0


def test_espandi_passi_da_un_minuto():
    passi = espandi([(5.0, 1.5), (8.0, 0.0101)])
    assert len(passi) == 90 + 1
    assert passi[0] == (5.0, 1.0 / 60.0)
    assert passi[-1][0] == 8.0 and passi[-1][1] == pytest.approx(0.0101, abs=1e-12)


def test_m11_sotto_tmin_fssp_cresce_migliorata_si_ferma():
    prof = [(5.0, 48.0), (-4.0, 72.0), (5.0, 48.0)]
    f = crescita_singola(COTTO, prof, 10.0, LISTERIA, modalita="fssp")
    m = crescita_singola(COTTO, prof, 10.0, LISTERIA, modalita="migliorata")
    i0, i1 = 48 * 60, (48 + 72) * 60 - 1     # tratto a -4 gradi
    assert f["log_ufc"][i1] > f["log_ufc"][i0]           # difetto di FSSP: cresce sotto Tmin
    assert m["log_ufc"][i1] == pytest.approx(m["log_ufc"][i0])
    assert f["log_ufc"][:i0] == m["log_ufc"][:i0]        # prima del freddo identiche


def test_m1_plateau_fssp_riporta_cento_volte_non_raggiunto():
    # LAB da 10^6,56 a 8,5 al massimo: aumento < 1,94 log, mai 2. FSSP lo conta come "100 volte" (finestra +-0,05)
    p = COTTO.con(temperatura=10.0)
    f = crescita_singola(p, [(10.0, 30 * 24.0)], 10 ** 6.56, LAB, modalita="fssp")
    m = crescita_singola(p, [(10.0, 30 * 24.0)], 10 ** 6.56, LAB, modalita="migliorata")
    assert f["cento_volte_giorni"] is not None
    assert m["cento_volte_giorni"] is None


def test_m1_interpolazione_entro_un_passo():
    f = crescita_singola(COTTO, [(5.0, 40 * 24.0)], 1.0, LISTERIA, modalita="fssp")
    m = crescita_singola(COTTO, [(5.0, 40 * 24.0)], 1.0, LISTERIA, modalita="migliorata")
    assert m["cento_volte_giorni"] == pytest.approx(f["cento_volte_giorni"], abs=2.0 / 1440.0)
    assert f["log_ufc"] == m["log_ufc"]


def test_m14_n0_oltre_nmax_rifiutato_solo_nella_migliorata():
    with pytest.raises(ValueError):
        crescita_listeria_lab(COTTO, [(8.0, 24.0)], 1e9, 1e3, modalita="migliorata")
    crescita_listeria_lab(COTTO, [(8.0, 24.0)], 1e9, 1e3, modalita="fssp")


def test_listeria_lab_jameson():
    prof = [(8.0, 30 * 24.0)]
    senza = crescita_listeria_lab(COTTO, prof, 10.0, 1000.0, gamma=0.0)
    con = crescita_listeria_lab(COTTO, prof, 10.0, 1000.0, gamma=2.0)
    assert max(senza["log_listeria"]) > max(con["log_listeria"])     # i LAB frenano la Listeria
    assert max(con["log_lab"]) == pytest.approx(LAB.log_nmax, abs=0.01)


def test_lag_ritarda_la_listeria():
    prof = [(5.0, 30 * 24.0)]
    a = crescita_listeria_lab(COTTO, prof, 1.0, 100.0, lag=False)
    b = crescita_listeria_lab(COTTO, prof, 1.0, 100.0, lag=True)
    assert b["lag_giorni"] == pytest.approx(4.5 * 0.693147181 / a["mu_listeria"] / 24.0)
    assert b["log_listeria"][-1] < a["log_listeria"][-1]


def test_confine_201_punti_e_psi_sul_confine():
    ys, zs = confine.curva(COTTO, "ph_lattico_diacetato", 6.0)
    assert len(ys) == len(zs) == 201 and ys[0] == 0.0
    assert zs[0] > 0.0
    s = secondario(LISTERIA, condizioni(COTTO.con(ph=6.0, lattico=ys[0], diacetato=zs[0])))
    assert s.psi == pytest.approx(1.0, abs=0.01)


def test_arrotonda_net_al_pari():
    assert confine.arrotonda_net(1.23456749) == 1.234567
    assert math.isnan(confine.arrotonda_net(math.nan))


def test_calcolatrici():
    assert calcolatrici.sale_fase_acquosa(2.0, 40.0) == pytest.approx(2.0 * 100.0 / 62.0)
    assert calcolatrici.sale_da_aw(0.95) == pytest.approx(8.0)
    assert calcolatrici.acido_da_sale(112.06, "lattico") == pytest.approx(90.08)
    w = calcolatrici.co2_fase_acquosa(2.0, 4.0, 40.0)
    assert 0.0 < calcolatrici.co2_spazio_di_testa(w, 4.0) < 40.0     # parte della CO2 si scioglie nel prodotto


def test_validita():
    cotto = Prodotto(temperatura=4.0, sale_fase_acquosa=2.8, ph=6.2, nitrito=100.0, acidi={"lattico": 5000.0})
    assert validita.avvisi("listeria", cotto) == []
    salame = cotto.con(sale_fase_acquosa=14.0, ph=5.0, temperatura=15.0)
    fattori = {a["fattore"] for a in validita.avvisi("listeria", salame)}
    assert fattori == {"sale_fase_acquosa", "ph"}
    assert {a["fattore"] for a in validita.avvisi("lab", cotto, [(4.0, 10.0), (-1.0, 5.0)])} == {"temperatura"}


def test_ponte_nomi_e_caso_peggiore():
    assert ponte.normalizza("k__Bacteria|p__Bacillota|s__Listeria_monocytogenes") == "listeria monocytogenes"
    piano = ponte.piano({"s__Listeria_monocytogenes": 0.2}, {}, [1.0, 100.0])
    assert piano["listeria_trovata"] and [s["n0_lab"] for s in piano["scenari"]] == [None, None]
    assert any("caso peggiore" in n for n in piano["note"])


def test_ponte_conta_totale():
    piano = ponte.piano({"s__Latilactobacillus_sakei": 40.0, "s__Staphylococcus_xylosus": 60.0},
                        {"totale_ufc_g": 1e6}, [1.0])
    assert piano["scenari"][0]["n0_lab"] == pytest.approx(4e5)
    assert "staphylococcus xylosus" in piano["specie_non_coperte"]


def _corri(tmp_path, richiesta):
    ing, usc = tmp_path / "r.json", tmp_path / "u.json"
    ing.write_text(json.dumps(richiesta), encoding="utf-8")
    p = subprocess.run([sys.executable, STEP, "--ingresso", str(ing), "--uscita", str(usc)],
                       capture_output=True, text=True, encoding="utf-8")
    evento = json.loads(p.stdout.strip().splitlines()[-1])
    return p.returncode, evento, (json.loads(usc.read_text(encoding="utf-8")) if usc.exists() else None)


def test_comando_json(tmp_path):
    codice, evento, ris = _corri(tmp_path, {
        "prodotto": {"sale_fase_acquosa": 2.8, "ph": 6.2, "nitrito": 100, "acidi": {"lattico": 5000}},
        "profilo_temperatura": [[4, 240], [12, 48]], "conte": {"lab_ufc_g": 100}})
    assert codice == 0 and evento["esito"] == "ok"
    assert [p["modello"] for p in ris["previsioni"]] == ["listeria_lab", "listeria_lab"]
    assert ris["previsioni"][0]["curva"]["giorni"][-1] == pytest.approx(12.0)
    assert "FSSP" in ris["citazione"]


@pytest.mark.parametrize("prodotto", [{"sale_fase_acquosa": 3, "aw": 0.97}, {"ph": "6"}, {"ph": 99},
                                      {"acidi": {"cloridrico": 1}}, {"zucchero": 1}])
def test_comando_rifiuta_ingressi_non_validi(tmp_path, prodotto):
    codice, evento, ris = _corri(tmp_path, {"prodotto": prodotto})
    assert codice == 1 and evento["codice"] == "INGRESSO_NON_VALIDO" and ris is None


def test_step45_aw_convertita():
    r = step45.esegui({"prodotto": {"aw": 0.97, "ph": 6.0}, "giorni": 1}, 1.0)
    assert any("aw" in n for n in r["note"])


def test_ponte_lab_non_adatti():
    piano = ponte.piano({"s__Leuconostoc_carnosum": 5.0, "s__Latilactobacillus_curvatus": 20.0},
                        {"lab_ufc_g": 1e3}, [1.0])
    assert piano["lab_trovati"] == ["latilactobacillus curvatus"]
    assert any("non è adatto" in n and "Leuconostoc carnosum" in n for n in piano["note"])
