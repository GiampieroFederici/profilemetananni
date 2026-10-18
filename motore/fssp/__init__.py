"""Sicurezza alimentare: modelli di microbiologia previsionale di FSSP riscritti in Python (D019, D048-D050).

Previsioni basate sui modelli del Food Spoilage and Safety Predictor (FSSP), DTU Food
(Mejlholm & Dalgaard 2009, 2013, 2015; Le Marc et al. 2002). Equivalenza con FSSP provata in F1.
"""
from .crescita import MODALITA, crescita_listeria_lab, crescita_singola, espandi
from .modelli import LAB, LISTERIA, Prodotto, condizioni, secondario
from lingua import N_

CITAZIONE = N_("Previsioni basate sui modelli del Food Spoilage and Safety Predictor (FSSP) 4.0, DTU Food "
               "(Mejlholm & Dalgaard 2009, 2013, 2015; Le Marc et al. 2002), riscritti in Python e provati "
               "equivalenti a FSSP (prova F1).")

__all__ = ["CITAZIONE", "LAB", "LISTERIA", "MODALITA", "Prodotto", "condizioni", "crescita_listeria_lab",
           "crescita_singola", "espandi", "secondario"]
