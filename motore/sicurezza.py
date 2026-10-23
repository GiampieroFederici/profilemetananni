"""Comando "sicurezza" del motore: previsioni di FSSP (motore/fssp, D019, D048-D050) con gli eventi del contratto.

Usato tale e quale da pmn_motore.py (motore vero) e da installer/finto_motore.py (finto motore): il calcolo
è Python puro e istantaneo, quindi anche il finto dà i numeri veri. La richiesta è quella di
steps/45_previsione_fssp.py, più "campione" (facoltativo). Se manca "profilo_specie" e c'è un progetto,
il profilo delle specie si legge dal profilo MetaPhlAn in risultati/ (mai sommato a Kraken, D016).
Solo libreria standard.
"""
import importlib.util
import json
import re
from pathlib import Path

import lingua
from lingua import N_, _

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("previsione_fssp", ROOT / "steps" / "45_previsione_fssp.py")
step45 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(step45)

MODELLI = {"listeria": N_("Per il modello della Listeria"),
           "listeria_lab": N_("Per il modello della Listeria con i batteri lattici"),
           "lab": N_("Per il modello dei batteri lattici")}
COSA_FARE = N_("Controlla i dati del prodotto e riprova.")


class Rifiutata(Exception):
    """Richiesta che l'utente può correggere: diventa l'errore INGRESSO_NON_VALIDO (codice di uscita 1)."""


def specie_metaphlan(profilo):
    """({nome: %} delle righe di specie (s__, senza t__), % UNCLASSIFIED) di un profilo MetaPhlAn."""
    out, non_classificato = {}, 0.0
    for riga in Path(profilo).read_text(encoding="utf-8").splitlines():
        c = riga.split("\t")
        if riga.startswith("#") or len(c) < 3:
            continue
        ultimo = c[0].split("|")[-1]
        if ultimo.startswith("s__"):
            out[c[0]] = float(c[2])
        elif c[0] == "UNCLASSIFIED":
            non_classificato = float(c[2])
    return out, non_classificato


def profilo_dal_progetto(risultati, campione):
    """(nome del campione, percorso del profilo MetaPhlAn) dall'indice risultati/risultati.json."""
    try:
        indice = json.loads((risultati / "risultati.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise Rifiutata(_("non trovo i risultati del progetto: prima va fatta l'analisi"))
    con_mpa = {c["nome"]: c["file"]["metaphlan"] for c in indice.get("campioni", []) if c.get("file", {}).get("metaphlan")}
    if campione is None and len(con_mpa) == 1:
        campione = next(iter(con_mpa))
    if campione not in con_mpa:
        raise Rifiutata(_("indica uno dei campioni con il profilo MetaPhlAn: {campioni}",
                          campioni=', '.join(sorted(con_mpa)) or _('nessuno')))
    return campione, risultati / con_mpa[campione]


def comando(evento, ingresso, progetto=None):
    """Esegue la richiesta; evento(tipo, messaggio, **campi) manda gli eventi. Restituisce (risultato, messaggio)."""
    try:
        richiesta = json.loads(Path(ingresso).read_text(encoding="utf-8")) if ingresso else None
    except (OSError, ValueError):
        richiesta = None
    if not isinstance(richiesta, dict):
        raise Rifiutata(_("il file con i dati del prodotto manca o non si legge"))
    richiesta = dict(richiesta)
    campione = richiesta.pop("campione", None)
    if campione is not None and not (isinstance(campione, str) and re.fullmatch(r"[A-Za-z0-9._-]{1,100}", campione)
                                     and campione.strip(".")):
        raise Rifiutata(_("il nome del campione contiene caratteri non ammessi"))
    risultati = Path(progetto).resolve().parent / "risultati" if progetto else None
    profilo_usato = _("indicato nella richiesta") if "profilo_specie" in richiesta else _("nessuno")
    if "profilo_specie" not in richiesta and risultati:
        campione, profilo = profilo_dal_progetto(risultati, campione)
        richiesta["profilo_specie"], non_classificato = specie_metaphlan(profilo)
        profilo_usato = _("MetaPhlAn, campione {campione} (percentuali sul totale delle read, compresa la parte "
                          "non classificata: {pct} %)", campione=campione, pct=lingua.virgola(f'{non_classificato:.1f}'))

    def avanza(i, n, nome):
        evento("avanzamento", _("Scenario {i} di {n}: {nome}", i=i, n=n, nome=nome), passo="sicurezza", campione=campione,
               fatto=i - 1, totale=n, percentuale=round(5 + 90 * (i - 1) / n, 1), eta_s=None)

    evento("avanzamento", _("Preparo gli scenari dal profilo e dai dati del prodotto."), passo="sicurezza",
           campione=campione, fatto=0, totale=1, percentuale=2, eta_s=None)
    try:
        out = step45.esegui(richiesta, 1.0, avanza)
    except step45.IngressoNonValido as e:
        raise Rifiutata(str(e))
    for a in out["avvisi"]:   # M8: fuori dal campo del modello, mostrato com'e'
        evento("avviso", f"{_(MODELLI[a['modello']])}: {a['messaggio']}", codice="FUORI_CAMPO", modello=a["modello"],
               fattore=a["fattore"])
    out.update(campione=campione, profilo_usato=profilo_usato,
               richiesta={k: v for k, v in richiesta.items() if k != "profilo_specie"})
    if risultati:
        cartella = risultati / "sicurezza"
        cartella.mkdir(parents=True, exist_ok=True)
        f = cartella / f"{campione or 'prodotto'}.json"
        f.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
        out["file"] = str(f)
    cresce = [p["scenario"] for p in out["previsioni"] if p["listeria_puo_crescere"]]
    messaggio = (_("Previsione pronta: in questo prodotto la Listeria potrebbe crescere.") if cresce else
                 _("Previsione pronta: in questo prodotto la Listeria non cresce (secondo il modello)."))
    return out, messaggio
