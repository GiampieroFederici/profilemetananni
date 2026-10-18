"""Campo di validità dei modelli (M8): avvisa quando una previsione esce dai dati con cui il modello
è stato costruito e validato. Fonte: pagine di aiuto di FSSP 4.0 ("Range of applicability"),
da Mejlholm & Dalgaard (2009, 2013, 2015)."""
import lingua
from lingua import N_, _

# (minimo, massimo); acidi in ppm nella fase acquosa, nitrito in ppm nel prodotto, CO2 in % (spazio di testa)
_LISTERIA = {"temperatura": (2.0, 25.0), "co2": (0.0, 100.0), "sale_fase_acquosa": (0.7, 9.0),
             "ph": (5.6, 7.7), "fenoli": (0.0, 20.0), "nitrito": (0.0, 150.0),
             "acetico": (0.0, 11000.0), "benzoico": (0.0, 1800.0), "citrico": (0.0, 6500.0),
             "diacetato": (0.0, 3800.0), "lattico": (0.0, 60000.0), "sorbico": (0.0, 1300.0)}

CAMPI = {
    "listeria": _LISTERIA,
    "lab": {"temperatura": (0.0, 25.0), "co2": (0.0, 100.0), "sale_fase_acquosa": (0.1, 6.4),
            "ph": (5.3, 7.7), "fenoli": (0.0, 21.2), "nitrito": (0.0, 209.0),
            "acetico": (0.0, 12600.0), "benzoico": (0.0, 1800.0), "citrico": (0.0, 7300.0),
            "diacetato": (0.0, 3000.0), "lattico": (0.0, 67000.0), "sorbico": (0.0, 1600.0)},
    "listeria_lab": dict(_LISTERIA, diacetato=(0.0, 3000.0)),
}

NOMI = {"temperatura": N_("temperatura (°C)"), "co2": "CO2 (%)", "sale_fase_acquosa": N_("sale nella fase acquosa (%)"),
        "ph": "pH", "fenoli": N_("fenoli del fumo (ppm)"), "nitrito": N_("nitrito (ppm)"),
        "acetico": N_("acido acetico (ppm)"), "benzoico": N_("acido benzoico (ppm)"),
        "citrico": N_("acido citrico (ppm)"), "diacetato": N_("diacetato (ppm)"), "lattico": N_("acido lattico (ppm)"),
        "sorbico": N_("acido sorbico (ppm)")}


def numero_it(v, cifre=2):
    """Numero per i testi all'utente, nella lingua scelta (all'italiana: 13.9875 -> "13,99", 60000 -> "60.000",
    5.0 -> "5"; con l'inglese "13.99", "60,000", "5")."""
    testo = lingua.separatori(f"{v:,.{cifre}f}")
    return testo.rstrip("0").rstrip(lingua.decimale()) if lingua.decimale() in testo else testo


def avvisi(modello, prodotto, profilo=None):
    """Lista di avvisi "fuori campo" (vuota se tutto è dentro). modello: listeria | lab | listeria_lab."""
    campo = CAMPI[modello]
    valori = {"co2": prodotto.co2, "sale_fase_acquosa": prodotto.sale_fase_acquosa, "ph": prodotto.ph,
              "fenoli": prodotto.fenoli, "nitrito": prodotto.nitrito}
    valori.update({a: prodotto.acidi.get(a, 0.0) for a in ("acetico", "benzoico", "citrico",
                                                             "diacetato", "lattico", "sorbico")})
    temperature = [t for t, _ in profilo] if profilo else [prodotto.temperatura]
    controlli = [("temperatura", min(temperature)), ("temperatura", max(temperature))]
    controlli += list(valori.items())
    uscita, visti = [], set()
    for fattore, v in controlli:
        lo, hi = campo[fattore]
        if (lo <= v <= hi) or (fattore, v) in visti:
            continue
        visti.add((fattore, v))
        uscita.append({"codice": "FUORI_CAMPO", "fattore": fattore, "valore": v, "campo": [lo, hi],
                       "messaggio": _("{fattore} = {valore}: fuori dal campo del modello ({lo}-{hi}). La previsione "
                                      "è un'estrapolazione: usala con cautela.", fattore=_(NOMI[fattore]),
                                      valore=numero_it(v), lo=numero_it(lo), hi=numero_it(hi))})
    return uscita
