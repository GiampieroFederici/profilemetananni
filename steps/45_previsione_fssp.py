#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# steps/45_previsione_fssp.py - sicurezza alimentare: previsione di crescita con i modelli di FSSP
# (motore/fssp, D019, D048-D050). Standard library only.
#
# Ingresso (--ingresso, JSON):
#   {"modalita": "migliorata" | "fssp",                       (predefinita: migliorata)
#    "prodotto": {"temperatura": 5, "sale_fase_acquosa": 3.0  (oppure "aw": 0.98), "ph": 6.2,
#                 "fenoli": 0, "co2": 0, "nitrito": 0, "acidi": {"lattico": 7000, ...}},   (acidi in ppm fase acquosa)
#    "profilo_temperatura": [[T, ore], ...]  (oppure "giorni": 30 a temperatura costante),
#    "lag": false, "gamma": 1.0,
#    "profilo_specie": {"s__Latilactobacillus_sakei": 46.6, ...},   (facoltativo, percentuali)
#    "conte": {"lab_ufc_g": 1e4} oppure {"totale_ufc_g": 1e6},      (facoltativo, D019 opzione A)
#    "scenari_listeria_ufc_g": [1, 100]}                            (predefinito, D019)
# Uscita (--uscita, JSON): previsioni per scenario, avvisi "fuori campo", ponte profilo -> modelli, citazione.
# stdout: un evento JSON "fine" (docs/contratto_motore.md). Codici: 0 ok, 1 ingresso non valido, 4 errore interno.
#
# Uso: 45_previsione_fssp.py --ingresso richiesta.json --uscita risultato.json [--passo-curva-ore 1]
import argparse
import json
import math
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "motore"))
from fssp import CITAZIONE, LAB, LISTERIA, crescita_listeria_lab, crescita_singola  # noqa: E402
from fssp import ponte, validita  # noqa: E402
from fssp.validita import numero_it  # noqa: E402
from fssp.calcolatrici import sale_da_aw  # noqa: E402
from fssp.modelli import ACIDI, Prodotto, condizioni, secondario  # noqa: E402
from lingua import N_, _  # noqa: E402

LIMITI = {"temperatura": (-20.0, 60.0), "sale_fase_acquosa": (0.0, 40.0), "aw": (0.5, 1.0), "ph": (2.0, 10.0),
          "fenoli": (0.0, 1000.0), "co2": (0.0, 100.0), "nitrito": (0.0, 10000.0)}
MAX_GIORNI = 365.0
MAX_TRATTI = 10000


class IngressoNonValido(ValueError):
    pass


def numero(v, nome, lo=None, hi=None):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        raise IngressoNonValido(_("{nome}: serve un numero", nome=_(nome)))
    if (lo is not None and v < lo) or (hi is not None and v > hi):
        raise IngressoNonValido(_("{nome} = {valore}: fuori da {lo}-{hi}", nome=_(nome), valore=numero_it(v),
                                  lo=numero_it(lo), hi=numero_it(hi)))
    return float(v)


def leggi_prodotto(d):
    if not isinstance(d, dict):
        raise IngressoNonValido(_("prodotto: serve un oggetto"))
    noti = set(LIMITI) | {"acidi"}
    extra = set(d) - noti
    if extra:
        raise IngressoNonValido(_("prodotto: campi sconosciuti {campi}", campi=sorted(extra)))
    note = []
    if "aw" in d:
        if "sale_fase_acquosa" in d:
            raise IngressoNonValido(_("prodotto: indica il sale nella fase acquosa oppure l'aw, non entrambi"))
        sale = sale_da_aw(numero(d["aw"], "aw", *LIMITI["aw"]))
        note.append(_("aw {aw} convertita in sale nella fase acquosa {sale} % (calcolatrice di FSSP)",
                      aw=numero_it(d['aw'], 3), sale=numero_it(sale)))
    else:
        sale = numero(d.get("sale_fase_acquosa", 0.0), N_("sale_fase_acquosa"), *LIMITI["sale_fase_acquosa"])
    acidi = d.get("acidi", {})
    if not isinstance(acidi, dict) or set(acidi) - set(ACIDI):
        raise IngressoNonValido(_("acidi: chiavi ammesse {chiavi}", chiavi=list(ACIDI)))
    p = Prodotto(temperatura=numero(d.get("temperatura", 5.0), N_("temperatura"), *LIMITI["temperatura"]),
                 sale_fase_acquosa=sale, ph=numero(d.get("ph", 6.2), "ph", *LIMITI["ph"]),
                 fenoli=numero(d.get("fenoli", 0.0), N_("fenoli"), *LIMITI["fenoli"]),
                 co2=numero(d.get("co2", 0.0), "co2", *LIMITI["co2"]),
                 nitrito=numero(d.get("nitrito", 0.0), N_("nitrito"), *LIMITI["nitrito"]),
                 acidi={a: numero(v, _("acido {a}", a=a), 0.0, 1e6) for a, v in acidi.items()})
    return p, note


def leggi_profilo(r, prodotto):
    if "profilo_temperatura" in r:
        prof = r["profilo_temperatura"]
        if not isinstance(prof, list) or not 0 < len(prof) <= MAX_TRATTI:
            raise IngressoNonValido(_("profilo_temperatura: lista di [temperatura, ore]"))
        out = []
        for i, tratto in enumerate(prof):
            if not isinstance(tratto, list) or len(tratto) != 2:
                raise IngressoNonValido(_("profilo_temperatura[{i}]: serve [temperatura, ore]", i=i))
            out.append((numero(tratto[0], _("temperatura del tratto {n}", n=i + 1), *LIMITI["temperatura"]),
                        numero(tratto[1], _("ore del tratto {n}", n=i + 1), 1e-6, MAX_GIORNI * 24.0)))
    else:
        out = [(prodotto.temperatura, numero(r.get("giorni", 30.0), N_("giorni"), 1e-3, MAX_GIORNI) * 24.0)]
    if sum(o for _t, o in out) > MAX_GIORNI * 24.0:
        raise IngressoNonValido(_("durata totale oltre {giorni} giorni", giorni=f"{MAX_GIORNI:g}"))
    return out


def campiona(tempi, *serie, passo):
    idx = list(range(passo - 1, len(tempi), passo))
    if not idx or idx[-1] != len(tempi) - 1:
        idx.append(len(tempi) - 1)
    return [[round(tempi[i], 6) for i in idx]] + [[round(s[i], 6) for i in idx] for s in serie]


def due_cifre(x):
    """Valore in ufc/g arrotondato a 2 cifre significative (D088): 10^2,48 -> 300."""
    return float(f"{x:.2g}")


def esegui(r, passo_curva_ore, avanza=None):
    """avanza(i, n, nome): chiamata prima di ogni scenario (pmn-motore sicurezza la usa per la barra)."""
    if not isinstance(r, dict):
        raise IngressoNonValido(_("la richiesta deve essere un oggetto JSON"))
    modalita = r.get("modalita", "migliorata")
    if modalita not in ("migliorata", "fssp"):
        raise IngressoNonValido(_("modalita: 'migliorata' oppure 'fssp'"))
    prodotto, note = leggi_prodotto(r.get("prodotto"))
    profilo = leggi_profilo(r, prodotto)
    prodotto = prodotto.con(temperatura=profilo[0][0])
    # verdetto "può crescere": psi di ogni tratto, non solo del primo (psi_listeria resta quello iniziale, come FSSP)
    psi_profilo = [secondario(LISTERIA, condizioni(prodotto, temperatura=t)).psi for t, _ore in profilo]
    lag = r.get("lag", False)
    if not isinstance(lag, bool):
        raise IngressoNonValido(_("lag: true o false"))
    gamma = numero(r.get("gamma", 1.0), "gamma", 0.0, 2.0)
    scenari = r.get("scenari_listeria_ufc_g", [1.0, 100.0])
    if not isinstance(scenari, list) or not 0 < len(scenari) <= 10:
        raise IngressoNonValido(_("scenari_listeria_ufc_g: lista di 1-10 concentrazioni"))
    scenari = [numero(v, N_("scenario Listeria"), 0.0, LISTERIA.nmax) for v in scenari]
    specie = r.get("profilo_specie", {})
    if not isinstance(specie, dict):
        raise IngressoNonValido(_("profilo_specie: oggetto nome -> percentuale"))
    specie = {str(k): numero(v, _("percentuale di {specie}", specie=k), 0.0, 100.0) for k, v in specie.items()}
    conte = r.get("conte", {})
    if not isinstance(conte, dict) or set(conte) - {"lab_ufc_g", "totale_ufc_g"}:
        raise IngressoNonValido(_("conte: 'lab_ufc_g' oppure 'totale_ufc_g'"))
    conte = {k: numero(v, k, 0.0, LAB.nmax) for k, v in conte.items()}

    piano = ponte.piano(specie, conte, scenari)
    passo = max(1, int(round(passo_curva_ore * 60.0)))
    previsioni = []
    for i, sc in enumerate(piano["scenari"], 1):
        if avanza:
            avanza(i, len(piano["scenari"]), sc["nome"])
        if sc["n0_lab"] is None:
            o = crescita_singola(prodotto, profilo, sc["n0_listeria"], LISTERIA, lag=lag, modalita=modalita)
            giorni, log_lm = campiona(o["tempi_giorni"], o["log_ufc"], passo=passo)
            prev = {"modello": "listeria", "mu_listeria_h": o["mu"], "psi_listeria": o["psi"],
                    "finale_listeria_ufc_g": due_cifre(10.0 ** o["log_ufc"][-1]),
                    "cento_volte_listeria_giorni": o["cento_volte_giorni"], "curva": {"giorni": giorni,
                                                                                       "log_listeria": log_lm}}
        else:
            o = crescita_listeria_lab(prodotto, profilo, sc["n0_listeria"], sc["n0_lab"], gamma=gamma, lag=lag,
                                      modalita=modalita)
            giorni, log_lm, log_lab = campiona(o["tempi_giorni"], o["log_listeria"], o["log_lab"], passo=passo)
            prev = {"modello": "listeria_lab", "mu_listeria_h": o["mu_listeria"], "psi_listeria": o["psi_listeria"],
                    "mu_lab_h": o["mu_lab"], "psi_lab": o["psi_lab"],
                    "cento_volte_listeria_giorni": o["cento_volte_listeria_giorni"],
                    "cento_volte_lab_giorni": o["cento_volte_lab_giorni"],
                    "sette_log_lab_giorni": o["sette_log_lab_giorni"],
                    "finale_listeria_ufc_g": due_cifre(10.0 ** o["log_listeria"][-1]),
                    "finale_lab_ufc_g": due_cifre(10.0 ** o["log_lab"][-1]),
                    "curva": {"giorni": giorni, "log_listeria": log_lm, "log_lab": log_lab}}
        prev.update({"scenario": sc["nome"], "n0_listeria_ufc_g": sc["n0_listeria"], "n0_lab_ufc_g": sc["n0_lab"],
                     "lag_giorni": o["lag_giorni"],
                     "listeria_puo_crescere": any(p is not None and p < 1.0 for p in psi_profilo)})
        previsioni.append(prev)
    modello_campo = "listeria_lab" if any(p["modello"] == "listeria_lab" for p in previsioni) else "listeria"
    avvisi = [dict(a, modello=modello_campo) for a in validita.avvisi(modello_campo, prodotto, profilo)]
    if piano["lab_trovati"]:
        avvisi += [dict(a, modello="lab") for a in validita.avvisi("lab", prodotto, profilo)]
    return {"modalita": modalita, "citazione": _(CITAZIONE), "note": note + piano["note"], "avvisi": avvisi,
            "ponte": {k: piano[k] for k in ("listeria_trovata", "lab_trovati", "specie_non_coperte")},
            "previsioni": previsioni}


def main():
    ap = argparse.ArgumentParser(description="Previsione di crescita con i modelli di FSSP (motore/fssp).")
    ap.add_argument("--ingresso", required=True)
    ap.add_argument("--uscita", required=True)
    ap.add_argument("--passo-curva-ore", type=float, default=1.0)
    a = ap.parse_args()
    ora = datetime.now().astimezone().isoformat(timespec="seconds")
    try:
        with open(a.ingresso, encoding="utf-8") as fh:
            richiesta = json.load(fh)
        if not 1.0 / 60.0 <= a.passo_curva_ore <= 24.0:
            raise IngressoNonValido("--passo-curva-ore fra 1/60 e 24")
        risultato = esegui(richiesta, a.passo_curva_ore)
    except (IngressoNonValido, json.JSONDecodeError, OSError) as e:
        print(json.dumps({"tipo": "fine", "ora": ora, "esito": "errore", "codice": "INGRESSO_NON_VALIDO",
                          "messaggio": f"Richiesta non valida: {e}", "cosa_fare": "Controlla i dati del prodotto."},
                         ensure_ascii=False))
        return 1
    except Exception as e:  # errore nostro: va segnalato
        print(json.dumps({"tipo": "fine", "ora": ora, "esito": "errore", "codice": "ERRORE_INTERNO",
                          "messaggio": f"Errore interno: {type(e).__name__}"}, ensure_ascii=False))
        return 4
    with open(a.uscita, "w", encoding="utf-8") as fh:
        json.dump(risultato, fh, ensure_ascii=False, indent=1)
    print(json.dumps({"tipo": "fine", "ora": ora, "esito": "ok", "risultato": {"file": a.uscita,
                                                                              "previsioni": len(risultato["previsioni"])}},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
