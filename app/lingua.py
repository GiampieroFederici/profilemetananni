"""Lingua dell'interfaccia: italiano (predefinito) o inglese (sessione Lingua IT/EN, 18/10/2026).

Il testo italiano resta nel codice ed è anche la chiave del catalogo: _("Avvia l'analisi") dà lo stesso testo con
l'italiano e la traduzione di app/risorse/lingua_en.json con l'inglese. Così con l'italiano non cambia nulla, parola
per parola (tests/test_lingua.py), e chi legge il codice legge ancora la frase vera.
  _(testo, **campi)  traduce e poi riempie i {campi} (str.format); senza campi il testo resta com'è
  N_(testo)          segna un testo da tradurre più tardi (costanti del modulo): restituisce il testo così com'è
I numeri: con l'italiano virgola per i decimali e punto per le migliaia, con l'inglese il contrario (scelta di
18/10). La lingua scelta si ricorda fra un avvio e l'altro (QSettings, come l'ultima cartella delle read).
"""
import json
import re
from pathlib import Path

LINGUE = {"it": "Italiano", "en": "English"}
CATALOGO = Path(__file__).resolve().parent / "risorse" / "lingua_en.json"
_attuale = "it"
_catalogo = {}


def imposta(codice):
    """Cambia la lingua (sconosciuta = italiano). Il catalogo inglese si legge la prima volta che serve."""
    global _attuale, _catalogo
    _attuale = codice if codice in LINGUE else "it"
    if _attuale == "en" and not _catalogo:
        _catalogo = json.loads(CATALOGO.read_text(encoding="utf-8"))


def attuale():
    return _attuale


def _(testo, **campi):
    t = _catalogo.get(testo, testo) if _attuale != "it" else testo
    return t.format(**campi) if campi else t


def N_(testo):
    return testo


# ---------------- numeri ----------------
def decimale():
    return "," if _attuale == "it" else "."


def migliaia():
    return "." if _attuale == "it" else ","


def separatori(testo):
    """Un numero scritto da Python con "," per le migliaia e "." per i decimali, nella lingua scelta."""
    return testo.replace(",", " ").replace(".", ",").replace(" ", ".") if _attuale == "it" else testo


def virgola(testo):
    """Solo il separatore dei decimali (testi già senza migliaia): "0.05" -> "0,05" con l'italiano."""
    return str(testo).replace(".", ",") if _attuale == "it" else str(testo)


def leggi_numero(testo):
    """Il testo di un campo in un numero (float): '3,5' o '3.5'; con l'italiano '1.000.000' e '100.000' (un punto
    seguito da 3 cifre, parte intera da 1 a 999 = migliaia), con l'inglese '1,000,000'. Vuoto -> None; ValueError
    se non è un numero."""
    t = testo.strip().replace(" ", "")
    if not t:
        return None
    if _attuale == "it" or not re.fullmatch(r"\d{1,3}(,\d{3})+(\.\d*)?", t):
        if "," in t:
            t = t.replace(".", "").replace(",", ".")
        elif t.count(".") > 1 or (_attuale == "it" and re.fullmatch(r"[1-9]\d{0,2}\.\d{3}", t)):
            t = t.replace(".", "")
    else:
        t = t.replace(",", "")
    return float(t)


# ---------------- scelta ricordata ----------------
def salvata():
    from PySide6.QtCore import QSettings
    return str(QSettings("ProfileMetaNanni", "app").value("lingua", "it"))


def salva(codice):
    from PySide6.QtCore import QSettings
    QSettings("ProfileMetaNanni", "app").setValue("lingua", codice)


def per_motore():
    """Opzioni per il motore (contratto §1): niente con l'italiano, così i comandi restano quelli di prima."""
    return [] if _attuale == "it" else ["--lingua", _attuale]
