"""Curve del confine crescita / non crescita della Listeria (grafici 2D di FSSP).

Per un valore fisso di X (temperatura o pH) e per 201 valori di Y da 0 a Y_max, si cerca il valore di Z
per cui psi = psi_obiettivo (di solito 1: sopra la curva la Listeria non cresce).
La ricerca e' quella di FSSP: si avanza a passi, e quando psi supera l'obiettivo si torna indietro
e si dimezza il passo; si parte dall'80 % del punto precedente.
"""
import math
from dataclasses import dataclass

from .modelli import LISTERIA, condizioni, secondario

LIMITE_ITERAZIONI = 1_000_000


@dataclass(frozen=True)
class Combinazione:
    x: str            # "temperatura" o "ph"
    y: str            # variabile sull'asse orizzontale del grafico
    z: str            # variabile cercata
    y_max: float
    passo_iniziale: float
    passo_minimo: float
    z_iniziale: float | None = None   # None = 80 % del punto precedente (0 al primo)
    discesa: bool = False             # True: Z parte alto e scende (temperatura)


# nomi come in FSSP (LmBoundaryCombinations); y_max = costanti della finestra (frmLmBoundary)
COMBINAZIONI = {
    "temperatura_lattico_diacetato": Combinazione("temperatura", "lattico", "diacetato", 35000.0 * 2.5, 500.0, 0.5),
    "ph_lattico_diacetato": Combinazione("ph", "lattico", "diacetato", 35000.0 * 2.5, 500.0, 0.5),
    "ph_sale_fenoli": Combinazione("ph", "sale_fase_acquosa", "fenoli", 8.0, 2.0, 0.01),
    "temperatura_ph_co2": Combinazione("ph", "co2", "temperatura", 100.0, 2.0, 0.01, z_iniziale=13.0, discesa=True),
    "temperatura_benzoico_sorbico": Combinazione("temperatura", "benzoico", "sorbico", 1200.0 * 2.5, 250.0, 0.5),
    "ph_benzoico_sorbico": Combinazione("ph", "benzoico", "sorbico", 1200.0 * 2.5, 250.0, 0.5),
    "temperatura_acetico_citrico": Combinazione("temperatura", "acetico", "citrico", 11000.0 * 2.5, 2500.0, 0.5),
    "ph_acetico_citrico": Combinazione("ph", "acetico", "citrico", 11000.0 * 2.5, 250.0, 0.5),
}


def arrotonda_net(valore, cifre=6):
    """Math.Round(double, cifre) di .NET Framework: scala, arrotonda al pari, riscala."""
    if math.isnan(valore) or abs(valore) >= 1e16:
        return valore
    p = 10.0 ** cifre
    return float(round(valore * p)) / p


def _valuta(prodotto, comb, x, y, z):
    p = prodotto.con(**{comb.x: x, comb.y: y, comb.z: z})
    return secondario(LISTERIA, condizioni(p))


def cerca_z(prodotto, comb, x, y, precedente, psi_obiettivo):
    if comb.z_iniziale is not None:
        z = comb.z_iniziale
    else:
        z = precedente * 0.8 if precedente is not None else 0.0
    verso = -1.0 if comb.discesa else 1.0
    passo = comb.passo_iniziale
    for _ in range(LIMITE_ITERAZIONI):
        s = _valuta(prodotto, comb, x, y, z)
        psi = s.psi
        if passo < comb.passo_minimo and psi is not None and arrotonda_net(psi) < psi_obiettivo:
            z += verso * passo
            continue
        if passo < comb.passo_minimo or s.mu < 0.0 or (psi is not None and arrotonda_net(psi) == psi_obiettivo):
            break
        if psi is None or psi > psi_obiettivo:
            z -= verso * passo
            passo /= 2.0
        z += verso * passo
    else:
        raise RuntimeError("la ricerca del confine non converge")
    return z if comb.discesa else max(z, 0.0)


def curva(prodotto, combinazione, x, psi_obiettivo=1.0, punti=201):
    """Restituisce (valori_y, valori_z) della curva del confine per X = x."""
    comb = COMBINAZIONI[combinazione]
    passo_y = comb.y_max / (punti - 1)
    ys, zs = [0.0] * punti, [0.0] * punti
    y, i, precedente = 0.0, 0, None
    while y < comb.y_max + passo_y:
        if i >= punti:
            raise IndexError("piu' punti del previsto (come FSSP)")
        z = cerca_z(prodotto, comb, x, y, precedente, psi_obiettivo)
        ys[i], zs[i] = y, z
        precedente = z
        y += passo_y
        i += 1
    return ys, zs
