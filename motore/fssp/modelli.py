"""Modelli secondari di FSSP: velocita' massima di crescita (mu_max) e confine crescita / non crescita (psi).

Equazioni: modello "cardinal parameter" esteso di Mejlholm & Dalgaard (2009, Listeria monocytogenes;
2013, Lactobacillus spp. psicrotolleranti) con le interazioni fra fattori di Le Marc et al. (2002).
Parametri e conversioni come in FSSP (Food Spoilage and Safety Predictor, DTU Food), verificati
contro FSSP.Models.dll 1.1.0.21167 nella prova F1 (implementazione/validazione/F1_fssp/).

Unita' (come in FSSP):
  temperatura in gradi C; sale nella fase acquosa in %; acidi organici in ppm (mg/L) nella fase acquosa;
  fenoli (fumo) in ppm; CO2 come % all'equilibrio nello spazio di testa; nitrito in ppm nel prodotto.
Dentro il modello: aw, acidi NON dissociati in mM, CO2 disciolta in ppm.
"""
import math
from dataclasses import dataclass, field, replace

LN2_FSSP = 0.693147181  # costante usata da FSSP per ln 2 (BaseSafety.Ln2)
RLT_LISTERIA = 4.5      # tempo di ritardo relativo della Listeria (BacteriaGrowth)
TREF = 25.0

ACIDI = ("lattico", "acetico", "diacetato", "citrico", "sorbico", "benzoico")
# peso molecolare (g/mol) e pKa usati da FSSP per la frazione non dissociata
PESO_MOLECOLARE = {"lattico": 90.08, "acetico": 60.05, "diacetato": 119.1,
                   "citrico": 192.13, "sorbico": 112.1, "benzoico": 122.12}
PKA = {"lattico": 3.86, "acetico": 4.76, "diacetato": 4.76,
       "citrico": 3.13, "sorbico": 4.76, "benzoico": 4.19}

# costante di FSSP per la CO2 disciolta (Safety.DissolvedCO2); le calcolatrici usano 247526.8425 (M4)
K_CO2_MODELLO = 247521.95669999998


@dataclass(frozen=True)
class Parametri:
    nome: str
    mu_ref: float        # h^-1 a 25 C senza freni
    tmin: float
    ph_min: float
    aw_min: float
    co2_max: float       # ppm disciolta
    fenoli_max: float    # ppm
    nitrito_max: float   # ppm
    mic: dict            # mM non dissociato, per acido
    # termine dell'acido in mu_max: ("lin", n) = (1 - c/MIC)^n ; ("rad", n) = (1 - sqrt(c/MIC))^n
    forma_acidi: dict
    log_nmax: float = 8.5

    @property
    def nmax(self):
        return math.pow(10.0, self.log_nmax)


LISTERIA = Parametri(
    nome="Listeria monocytogenes", mu_ref=0.419, tmin=-2.83, ph_min=4.97, aw_min=0.923,
    co2_max=3140.0, fenoli_max=32.0, nitrito_max=350.0,
    mic={"acetico": 10.3, "benzoico": 0.349, "citrico": 2.119, "diacetato": 4.8, "lattico": 3.79, "sorbico": 1.896},
    forma_acidi={"lattico": ("lin", 1), "acetico": ("rad", 1), "diacetato": ("rad", 1),
                 "citrico": ("lin", 1), "sorbico": ("lin", 1), "benzoico": ("lin", 1)})

LAB = Parametri(
    nome="Lactobacillus spp. psicrotolleranti (LAB)", mu_ref=0.583, tmin=-5.246, ph_min=4.24, aw_min=0.928,
    co2_max=6691.0, fenoli_max=40.28, nitrito_max=2780.0,
    mic={"acetico": 151.3, "benzoico": 1.51, "citrico": 10.3, "diacetato": 33.3, "lattico": 12.0, "sorbico": 12.6},
    forma_acidi={"lattico": ("lin", 1), "acetico": ("rad", 1), "diacetato": ("rad", 1),
                 "citrico": ("lin", 2), "sorbico": ("lin", 2), "benzoico": ("lin", 2)})


@dataclass(frozen=True)
class Prodotto:
    """Caratteristiche del prodotto come le inserisce l'utente (unita' di FSSP)."""
    temperatura: float = 5.0
    sale_fase_acquosa: float = 3.0
    ph: float = 6.2
    fenoli: float = 0.0
    co2: float = 0.0
    nitrito: float = 0.0
    acidi: dict = field(default_factory=dict)   # ppm nella fase acquosa, chiavi in ACIDI

    def con(self, **modifiche):
        acidi = dict(self.acidi)
        for a in ACIDI:
            if a in modifiche:
                acidi[a] = modifiche.pop(a)
        return replace(self, acidi=acidi, **modifiche)


@dataclass(frozen=True)
class Condizioni:
    """Ingressi del modello, gia' convertiti."""
    temperatura: float
    aw: float
    ph: float
    acidi: dict     # mM non dissociato
    fenoli: float
    co2: float      # ppm disciolta
    nitrito: float
    con_nitrito: bool = True


def _radice(x):
    # come Math.Sqrt di .NET: NaN per i negativi (la ricerca del confine puo' passare per valori < 0)
    return math.sqrt(x) if x >= 0.0 else math.nan


def aw_da_sale(sale_fase_acquosa):
    # FSSP (BaseSafety.WaterActivity): aw dal sale nella fase acquosa
    s = sale_fase_acquosa
    return 0.999489 - 0.005179 * s - 0.0001272 * s * s


def non_dissociato(acido, ppm, ph):
    # equazione di Henderson-Hasselbalch: mM non dissociato = (ppm / PM) / (1 + 10^(pH - pKa))
    return ppm / PESO_MOLECOLARE[acido] / (1.0 + math.pow(10.0, ph - PKA[acido]))


def co2_disciolta(co2_percento, temperatura):
    # costante di Henry dipendente dalla temperatura (Safety.DissolvedCO2)
    tk = temperatura + 273.15
    h = math.exp(-6.8346 + 12817.0 / tk - 3766800.0 / math.pow(tk, 2.0) + 299700000.0 / math.pow(tk, 3.0))
    return co2_percento * (K_CO2_MODELLO / h) / 100.0


def condizioni(prodotto, temperatura=None, ph=None):
    """Converte il prodotto negli ingressi del modello. Gli acidi si convertono al pH corrente,
    la CO2 alla temperatura corrente (come FSSP)."""
    t = prodotto.temperatura if temperatura is None else temperatura
    p = prodotto.ph if ph is None else ph
    return Condizioni(
        temperatura=t, aw=aw_da_sale(prodotto.sale_fase_acquosa), ph=p,
        acidi={a: non_dissociato(a, prodotto.acidi.get(a, 0.0), p) for a in ACIDI},
        fenoli=prodotto.fenoli, co2=co2_disciolta(prodotto.co2, t), nitrito=prodotto.nitrito)


@dataclass(frozen=True)
class Secondario:
    mu: float           # h^-1 (0 se un fattore blocca)
    psi: float | None   # None se un fattore e' oltre il limite (FSSP non calcola psi)
    bloccato: bool      # True se un singolo fattore e' oltre il suo limite


def _termine_acido(forma, c, mic):
    tipo, n = forma
    base = 1.0 - (c / mic if tipo == "lin" else _radice(c / mic))
    return base if n == 1 else math.pow(base, float(n))


def _bloccato(par, c):
    # stesso ordine dei controlli di FSSP (BacteriaGrowth.SecondaryGrowth)
    a = c.acidi
    return (c.temperatura <= par.tmin or c.ph <= par.ph_min or c.aw <= par.aw_min
            or a["lattico"] >= par.mic["lattico"] or c.co2 >= par.co2_max or c.fenoli >= par.fenoli_max
            or a["diacetato"] >= par.mic["diacetato"] or c.nitrito >= par.nitrito_max
            or a["acetico"] >= par.mic["acetico"] or a["benzoico"] >= par.mic["benzoico"]
            or a["citrico"] >= par.mic["citrico"] or a["sorbico"] >= par.mic["sorbico"])


def _mu_senza_interazioni(par, c):
    a, f, m = c.acidi, par.forma_acidi, par.mic
    return (par.mu_ref
            * math.pow((c.temperatura - par.tmin) / (TREF - par.tmin), 2.0)
            * ((c.aw - par.aw_min) / (1.0 - par.aw_min))
            * (1.0 - math.pow(10.0, par.ph_min - c.ph))
            * _termine_acido(f["lattico"], a["lattico"], m["lattico"])
            * _termine_acido(f["acetico"], a["acetico"], m["acetico"])
            * ((par.fenoli_max - c.fenoli) / par.fenoli_max)
            * ((par.co2_max - c.co2) / par.co2_max)
            * _termine_acido(f["diacetato"], a["diacetato"], m["diacetato"])
            * math.pow((par.nitrito_max - c.nitrito) / par.nitrito_max, 2.0)
            * _termine_acido(f["citrico"], a["citrico"], m["citrico"])
            * _termine_acido(f["sorbico"], a["sorbico"], m["sorbico"])
            * _termine_acido(f["benzoico"], a["benzoico"], m["benzoico"]))


def _phi(par, c):
    """Peso di ogni fattore nel confine (Le Marc et al. 2002): 0 = nessun freno, 1 = al limite."""
    a, m = c.acidi, par.mic
    acidi = math.pow(1.0 - (1.0 - _radice(a["lattico"] / m["lattico"]))
                     * (1.0 - _radice(a["diacetato"] / m["diacetato"]))
                     * (1.0 - _radice(a["acetico"] / m["acetico"]))
                     * (1.0 - a["citrico"] / m["citrico"])
                     * (1.0 - a["sorbico"] / m["sorbico"])
                     * (1.0 - a["benzoico"] / m["benzoico"]), 2.0)
    return [
        math.pow(1.0 - (c.temperatura - par.tmin) / (TREF - par.tmin), 2.0),
        math.pow(1.0 - _radice((c.aw - par.aw_min) / (1.0 - par.aw_min)), 2.0),
        math.pow(1.0 - _radice(1.0 - math.pow(10.0, par.ph_min - c.ph)), 2.0),
        acidi,
        math.pow(1.0 - _radice((par.fenoli_max - c.fenoli) / par.fenoli_max), 2.0),
        math.pow(1.0 - _radice((par.co2_max - c.co2) / par.co2_max), 2.0),
        math.pow(1.0 - (par.nitrito_max - c.nitrito) / par.nitrito_max, 2.0) if c.con_nitrito else 0.0,
    ]


def psi(par, c):
    """psi = somma_e phi_e / [2 * prodotto_(j != e) (1 - phi_j)]; psi >= 1 = non cresce."""
    phi = _phi(par, c)
    termini = []
    for e in range(len(phi)):
        den = 1.0
        for j in range(len(phi)):
            if j != e:
                den *= 1.0 - phi[j]
        termini.append(phi[e] / den)
    somma = termini[-1]
    for t in reversed(termini[:-1]):   # stessa sequenza di somme di FSSP
        somma = t + somma
    return somma / 2.0


def xi(valore_psi):
    if valore_psi > 1.0:
        return 0.0
    if valore_psi < 0.5:
        return 1.0
    return (1.0 - valore_psi) * 2.0


def secondario(par, c):
    """mu_max (h^-1) con le interazioni, e psi."""
    if _bloccato(par, c):
        return Secondario(mu=0.0, psi=None, bloccato=True)
    mu = _mu_senza_interazioni(par, c)
    p = psi(par, c)
    return Secondario(mu=mu * xi(p), psi=p, bloccato=False)
