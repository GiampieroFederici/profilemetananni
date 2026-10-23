"""Crescita nel tempo (modello primario): logistica con effetto Jameson, passi fissi come FSSP.

  dN/dt = mu_max * N * (1 - N/Nmax) * (1 - gamma * N_altro / Nmax_altro)

Il profilo di temperatura e' una lista di (temperatura in C, durata in ore). Come la finestra di FSSP,
ogni tratto si divide in passi da 1 minuto e a ogni passo N <- N * exp(mu * dt).

Modalita':
  "fssp"       fedele a FSSP, difetti compresi (prova F1);
  "migliorata" predefinita nell'app (D048): tempo a 100 volte e a 7 log interpolati e misurati
               da N0 (M1, M2; FSSP misura dal valore dopo il primo passo), lag senza divisione per
               zero (M7), velocita' azzerata quando un fattore supera il limite in un profilo che
               cambia (M11), N0 oltre Nmax rifiutato (M14: in FSSP la crescita esplode).
"""
import math

from .modelli import LAB, LISTERIA, LN2_FSSP, RLT_LISTERIA, condizioni, secondario

MODALITA = ("fssp", "migliorata")


def espandi(profilo, intervallo_min=1.0):
    """Divide ogni tratto (T, ore) in passi di `intervallo_min` minuti (l'ultimo puo' essere piu' corto)."""
    passi = []
    for temperatura, ore in profilo:
        minuti = ore * 60.0
        n = int(math.floor(minuti / intervallo_min))
        if minuti - intervallo_min * n > 0.0001:
            n += 1
        for _ in range(n):
            if minuti > intervallo_min:
                dt = intervallo_min / 60.0
                minuti -= intervallo_min
            else:
                dt = minuti / 60.0
            passi.append((temperatura, dt))
    return passi


def intervallo_esportazione(profilo):
    """Passo (minuti) che FSSP usa solo quando esporta: 30, 60 o 120 a seconda della durata."""
    ore = sum(o for _, o in profilo)
    return 30.0 if ore <= 240.0 else 60.0 if ore <= 960.0 else 120.0


def _exp(x):
    # come Math.Exp di .NET: infinito invece di errore (succede solo con N0 oltre Nmax, dove FSSP esplode)
    try:
        return math.exp(x)
    except OverflowError:
        return math.inf


def _log(n):
    return 0.0 if n == 0.0 else math.log10(n)


def _finestra(aumento, centro):
    # FSSP: tempo "raggiunto" se il valore e' entro +-0,05 da centro (1,95 per 100 volte, 6,95 per 7 log)
    return abs(centro - aumento) < 0.05


def _attraversa(tempi_ore, valori, soglia, t0=0.0, v0=None):
    """Primo istante (giorni) in cui `valori` raggiunge `soglia`, interpolando fra i due passi a cavallo."""
    t_prec, v_prec = t0, v0
    for t, v in zip(tempi_ore, valori):
        if v >= soglia:
            if v_prec is None or v_prec >= soglia or v == v_prec:
                return t / 24.0
            return (t_prec + (soglia - v_prec) / (v - v_prec) * (t - t_prec)) / 24.0
        t_prec, v_prec = t, v
    return None


def _controlla_n0(n0, parametri):
    if not 0.0 <= n0 <= parametri.nmax:
        raise ValueError(f"concentrazione iniziale {n0:g} ufc/g fuori da 0-{parametri.nmax:.3g} "
                         f"(massimo del modello per {parametri.nome})")


def _giorni_lag(mu):
    if mu == 0.0:
        return math.inf
    return RLT_LISTERIA * LN2_FSSP / mu / 24.0


def crescita_singola(prodotto, profilo, n0, parametri=LISTERIA, lag=False, modalita="migliorata",
                     temperatura_iniziale=None):
    """Un solo microrganismo (finestre "Listeria" e "LAB" di FSSP).

    prodotto: modelli.Prodotto; profilo: [(T, ore)]; n0: concentrazione iniziale in ufc/g.
    temperatura_iniziale: temperatura scritta nella casella della finestra (predefinita: la prima del profilo).
    """
    if modalita not in MODALITA:
        raise ValueError(f"modalita' sconosciuta: {modalita}")
    fedele = modalita == "fssp"
    if not fedele:
        _controlla_n0(float(n0), parametri)
    t_iniz = profilo[0][0] if temperatura_iniziale is None else temperatura_iniziale
    iniziale = secondario(parametri, condizioni(prodotto, temperatura=t_iniz))
    mu_stato = 0.0 if iniziale.bloccato else iniziale.mu
    mu_passo = mu_stato
    nmax = parametri.nmax
    n = float(n0)
    frazione_lag = 1.0
    giorni_lag = 0.0
    t = 0.0
    tempi, logs = [], []
    cento_volte = 0.0
    sette_log = None
    for temperatura, dt in espandi(profilo):
        s = secondario(parametri, condizioni(prodotto, temperatura=temperatura))
        if not s.bloccato:
            mu_stato = s.mu
        elif not fedele:
            mu_stato = 0.0   # M11: oltre un limite la crescita si ferma
        if lag:
            giorni_lag = _giorni_lag(mu_stato)
        if lag or fedele:
            # FSSP: con lag spento divide per zero (-inf: cresce subito, M7)
            den = giorni_lag * 24.0
            frazione_lag = -math.inf if den == 0.0 else frazione_lag - dt / den
            cresce = not (frazione_lag >= 0.0)
        else:
            cresce = True
        if cresce:
            n *= _exp(mu_passo * dt)
        t += dt
        tempi.append(t / 24.0)
        logs.append(_log(n))
        if len(logs) > 1 and _finestra(logs[-1] - logs[0], 1.95) and t > cento_volte:
            cento_volte = t
        if len(logs) > 1 and _finestra(logs[-1], 6.95):
            sette_log = t / 24.0
        mu_passo = mu_stato * (1.0 - n / nmax) * (1.0 - 1.0 * (0.0 / 1.0))
    if fedele:
        cento = cento_volte / 24.0 if cento_volte != 0.0 else None
    else:
        ore = [g * 24.0 for g in tempi]
        cento = _attraversa(ore, logs, _log(float(n0)) + 2.0, v0=_log(float(n0)))
        sette_log = _attraversa(ore, logs, 7.0, v0=_log(float(n0)))
    return {"mu": iniziale.mu, "psi": iniziale.psi, "lag_giorni": giorni_lag if lag else 0.0,
            "tempi_giorni": tempi, "log_ufc": logs, "cento_volte_giorni": cento, "sette_log_giorni": sette_log}


def crescita_listeria_lab(prodotto, profilo, n0_listeria, n0_lab, gamma=1.0, lag=False,
                          modalita="migliorata", temperatura_iniziale=None):
    """Listeria e LAB insieme (finestra "Listeria + LAB" di FSSP): i LAB frenano la Listeria (effetto Jameson).

    gamma (0-2) agisce sulla Listeria; per i LAB FSSP usa sempre 1.
    Il lag della Listeria si calcola una volta, alla temperatura iniziale, e si toglie dall'inizio.
    """
    if modalita not in MODALITA:
        raise ValueError(f"modalita' sconosciuta: {modalita}")
    fedele = modalita == "fssp"
    if not fedele:
        _controlla_n0(float(n0_listeria), LISTERIA)
        _controlla_n0(float(n0_lab), LAB)
    t_iniz = profilo[0][0] if temperatura_iniziale is None else temperatura_iniziale
    c0 = condizioni(prodotto, temperatura=t_iniz)
    in_lm, in_lab = secondario(LISTERIA, c0), secondario(LAB, c0)
    mu_lm = 0.0 if in_lm.bloccato else in_lm.mu
    mu_lab = 0.0 if in_lab.bloccato else in_lab.mu
    giorni_lag = _giorni_lag(mu_lm) if lag else 0.0
    ore_lag = giorni_lag * 24.0
    passo_lm, passo_lab = mu_lm, mu_lab
    nmax_lm, nmax_lab = LISTERIA.nmax, LAB.nmax
    n_lm, n_lab = float(n0_listeria), float(n0_lab)
    t = 0.0
    tempi, log_lm, log_lab = [], [], []
    cento_lm = cento_lab = 0.0
    sette_log = None
    for temperatura, dt in espandi(profilo):
        c = condizioni(prodotto, temperatura=temperatura)
        s_lab, s_lm = secondario(LAB, c), secondario(LISTERIA, c)
        if not s_lab.bloccato:
            mu_lab = s_lab.mu
        elif not fedele:
            mu_lab = 0.0
        if not s_lm.bloccato:
            mu_lm = s_lm.mu
        elif not fedele:
            mu_lm = 0.0
        n_lab *= _exp(passo_lab * dt)
        log_lab.append(_log(n_lab))
        if ore_lag == 0.0 or t > ore_lag:
            n_lm *= _exp(passo_lm * dt)
        elif t < ore_lag and t + dt > ore_lag:
            n_lm *= _exp(passo_lm * (t + dt - ore_lag))
        log_lm.append(_log(n_lm))
        t += dt
        tempi.append(t / 24.0)
        if (len(log_lm) > 1 and _finestra(log_lm[-1] - log_lm[0], 1.95) and log_lm[-1] > log_lm[-2]
                and t > cento_lm):
            cento_lm = t
        if len(log_lab) > 1 and _finestra(log_lab[-1] - log_lab[0], 1.95) and t > cento_lab:
            cento_lab = t
        if len(log_lab) > 1 and _finestra(log_lab[-1], 6.95):
            sette_log = t / 24.0
        passo_lab = mu_lab * (1.0 - n_lab / nmax_lab) * (1.0 - 1.0 * (n_lm / nmax_lm))
        passo_lm = mu_lm * (1.0 - n_lm / nmax_lm) * (1.0 - gamma * (n_lab / nmax_lab))
    if fedele:
        c_lm = cento_lm / 24.0 if cento_lm != 0.0 else None
        c_lab = cento_lab / 24.0 if cento_lab != 0.0 else None
    else:
        ore = [g * 24.0 for g in tempi]
        l0_lm, l0_lab = _log(float(n0_listeria)), _log(float(n0_lab))
        c_lm = _attraversa(ore, log_lm, l0_lm + 2.0, v0=l0_lm)
        c_lab = _attraversa(ore, log_lab, l0_lab + 2.0, v0=l0_lab)
        sette_log = _attraversa(ore, log_lab, 7.0, v0=l0_lab)
    return {"mu_listeria": in_lm.mu, "psi_listeria": in_lm.psi, "mu_lab": in_lab.mu, "psi_lab": in_lab.psi,
            "lag_giorni": giorni_lag, "tempi_giorni": tempi, "log_listeria": log_lm, "log_lab": log_lab,
            "cento_volte_listeria_giorni": c_lm, "cento_volte_lab_giorni": c_lab, "sette_log_lab_giorni": sette_log}
