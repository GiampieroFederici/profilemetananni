"""Calcolatrici di FSSP: dagli ingredienti del prodotto agli ingressi dei modelli."""
import math

from .modelli import PESO_MOLECOLARE, PKA, aw_da_sale  # noqa: F401  (aw_da_sale: aw dal sale)

K_CO2_CALCOLATRICE = 247526.8425   # costante delle calcolatrici di FSSP (il modello usa 247521.9567, M4)

# peso molecolare dell'acido e del suo sale, come nelle calcolatrici di FSSP (sale sodico; sorbato: 151,23)
PESI_SALE = {"lattico": (90.08, 112.06), "acetico": (60.05, 80.04), "benzoico": (122.12, 144.11),
             "citrico": (192.13, 258.1), "sorbico": (112.1, 151.23)}


def sale_fase_acquosa(nacl, sostanza_secca):
    """% di sale nella fase acquosa da NaCl (%) e sostanza secca (%) del prodotto."""
    return nacl * 100.0 / (100.0 - sostanza_secca + nacl)


def sale_da_aw(aw):
    """% di sale nella fase acquosa equivalente a una aw (inversa approssimata di aw_da_sale)."""
    return 8.0 - 140.0 * (aw - 0.95) - 405.0 * math.pow(aw - 0.95, 2.0)


def acido_da_sale(sale_percento, acido):
    """% di acido nel prodotto da % del suo sale (es. lattato di sodio -> acido lattico)."""
    pm_acido, pm_sale = PESI_SALE[acido]
    return sale_percento * pm_acido / pm_sale


def sale_da_acido(acido_percento, acido):
    pm_acido, pm_sale = PESI_SALE[acido]
    return acido_percento * pm_sale / pm_acido


def acido_fase_acquosa(acido_nel_prodotto, sostanza_secca):
    """% di acido nella fase acquosa da % nel prodotto e sostanza secca (%)."""
    return acido_nel_prodotto * 100.0 / (100.0 - sostanza_secca + acido_nel_prodotto)


def percento_a_ppm(percento):
    return percento * 10.0 * 1000.0


def ppm_da_non_dissociato(acido, mm_non_dissociato, ph):
    """ppm totali nella fase acquosa che danno quella concentrazione di acido non dissociato (mM)."""
    return mm_non_dissociato * PESO_MOLECOLARE[acido] * (1.0 + math.pow(10.0, ph - PKA[acido]))


def _henry(temperatura):
    tk = temperatura + 273.15
    return K_CO2_CALCOLATRICE / math.exp(-6.8346 + 12817.0 / tk - 3766800.0 / math.pow(tk, 2.0)
                                         + 299700000.0 / math.pow(tk, 3.0))


def co2_fase_acquosa(rapporto_gas_prodotto, temperatura, co2_iniziale):
    """CO2 disciolta all'equilibrio (ppm) in una confezione in atmosfera modificata.

    rapporto_gas_prodotto: volume di gas / volume di prodotto; co2_iniziale: % di CO2 nel gas al confezionamento.
    """
    k = _henry(temperatura)
    a = rapporto_gas_prodotto * 1976.0 + k
    return (a - math.sqrt(math.pow(a, 2.0) - 0.04 * k * rapporto_gas_prodotto * co2_iniziale * 1976.0)) / 2.0


def co2_spazio_di_testa(co2_in_fase_acquosa, temperatura):
    """% di CO2 nello spazio di testa all'equilibrio (l'ingresso "CO2" dei modelli)."""
    return co2_in_fase_acquosa * 100.0 / _henry(temperatura)
