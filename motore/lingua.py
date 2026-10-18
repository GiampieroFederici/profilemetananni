"""Lingua dei testi del motore per l'utente: italiano (predefinito) o inglese (sessione Lingua IT/EN, 18/10/2026).

Come nell'app (app/lingua.py): il testo italiano resta nel codice ed è la chiave di motore/lingua_en.json.
  _(testo, **campi)  traduce e poi riempie i {campi}; N_(testo) segna un testo da tradurre più tardi
La lingua arriva con `pmn-motore <comando> --lingua en` (contratto §1) oppure dalla variabile PMN_LINGUA, che
imposta() scrive anche per i programmi lanciati dal motore (motore/referto.py). Senza nulla: italiano, come prima.
Numeri: con l'italiano virgola per i decimali e punto per le migliaia, con l'inglese il contrario.
Solo libreria standard.
"""
import json
import os
from pathlib import Path

LINGUE = ("it", "en")
CATALOGO = Path(__file__).resolve().parent / "lingua_en.json"
_attuale = "it"
_catalogo = {}


def imposta(codice):
    global _attuale, _catalogo
    _attuale = codice if codice in LINGUE else "it"
    os.environ["PMN_LINGUA"] = _attuale
    if _attuale == "en" and not _catalogo:
        _catalogo = json.loads(CATALOGO.read_text(encoding="utf-8"))


def attuale():
    return _attuale


def _(testo, **campi):
    t = _catalogo.get(testo, testo) if _attuale != "it" else testo
    return t.format(**campi) if campi else t


def N_(testo):
    return testo


def decimale():
    return "," if _attuale == "it" else "."


def separatori(testo):
    """Un numero scritto da Python con "," per le migliaia e "." per i decimali, nella lingua scelta."""
    return testo.replace(",", " ").replace(".", ",").replace(" ", ".") if _attuale == "it" else testo


def virgola(testo):
    """Solo il separatore dei decimali: "0.05" -> "0,05" con l'italiano."""
    return str(testo).replace(".", ",") if _attuale == "it" else str(testo)


def migliaia(testo):
    """Solo il separatore delle migliaia (numeri interi scritti con "{:,}"): "1,507,887" -> "1.507.887"."""
    return str(testo).replace(",", ".") if _attuale == "it" else str(testo)


imposta(os.environ.get("PMN_LINGUA", "it"))
