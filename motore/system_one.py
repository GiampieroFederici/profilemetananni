"""System One v0 (D031): regole già misurate che CONSIGLIANO e non calcolano, né cambiano le scelte dell'utente.

Ogni consiglio è {"codice", "livello", "messaggio", "fonte"}: livello "avviso" diventa un evento `avviso`
del contratto, "info" resta solo in risultato.consigli. Ogni soglia ha accanto la sua fonte.
La v1 (S12) sarà un albero addestrato sui casi con risposta nota di L3-L5.
Solo libreria standard.
"""
import csv
import importlib.util
from pathlib import Path

import lingua
from lingua import N_, _

ROOT = Path(__file__).resolve().parent.parent

RAM_STANDARD_GB = 40.0
FONTE_RAM_STANDARD = N_("MetaPhlAn standard: picco 25,5 GB con il catalogo in swap (S2.1, macchina da 30 GB); "
                        "non entra nei 31,4 GB del PC di prova (13/10). Soglia 40 GB come run.sh 'auto' (D051)")
RAM_MINIMA_GB = 7.5
FONTE_RAM_MINIMA = N_("MetaPhlAn a fette provato con WSL a 8 GB (circa 7,7 GB visibili): SF3RAt7 e C03_1, RAM 7,9 GB "
                      "+ swap 1,2 GB (14/10, 'Gira su 16 GB, verificato'). Sotto non è provato")
TEMPO_LUNGO_S = 4 * 3600
FONTE_TEMPO = N_("D023: oltre 4 ore si propone lo screening rapido (PlusPF-8) o il cloud")
MARGINE_SPAZIO = 1.15
FONTE_SPAZIO = N_("stessa regola di steps/05_estimate_size.py: spazio stimato x 1,15 di margine")
FONTE_DB = N_("installazione del motore (installazione.env): database presenti sul disco")
FONTE_TRIAGE = N_("steps/17_triage_report.py: soglie host {host:g} %, {reads:,.0f} frammenti non ospite, "
                  "Q30 {q30:g} % (triage.* del progetto); zona grigia +-20 %")
TRIAGE_ESITO = {"pass": "buono", "review": "da controllare", "exclude": "da rifare"}   # chiavi del contratto §5.3
TRIAGE_PREDEFINITE = {"max_host_pct": 95.0, "min_nonhost_reads": 1_000_000.0, "min_q30_pct": 70.0}
# prodotto -> (ospiti da togliere oltre all'uomo: chiavi di hosts: in config.yaml, frase, perché, livello).
# L'uomo (GRCh38) si toglie sempre. Testi presi dalla pagina Campioni dell'app (S5b), che li mostra così come sono.
_CARNE = N_("Sono la gran parte delle read di un prodotto di carne e non dicono nulla dei taxa del prodotto. "
            "Il DNA umano si toglie sempre.")
PRODOTTI = [
    ("maiale", ["sus_scrofa"], N_("Toglierò il DNA del maiale e quello umano."),
     N_("Sono la gran parte delle read di un salume e non dicono nulla dei taxa del prodotto. Il DNA umano si toglie sempre."),
     "info"),
    ("bovino", ["bos_taurus"], N_("Toglierò il DNA del bovino e quello umano."), _CARNE, "info"),
    ("pecora", ["ovis_aries"], N_("Toglierò il DNA della pecora e quello umano."), _CARNE, "info"),
    ("altro", [], N_("Toglierò solo il DNA umano."),
     N_("Se il prodotto contiene carne di maiale, bovino o pecora, sceglila qui sopra: senza, molte read della carne "
        "finiscono assegnate per errore a qualche taxon."), "avviso"),
]
GENOMI = {"sus_scrofa": "Sscrofa11.1", "bos_taurus": "ARS-UCD1.2", "ovis_aries": "ARS-UI_Ramb_v2.0",
          "grch38": "GRCh38.p14", "vitis_vinifera": "T2T-PN40024 (ASM3070453v1)"}
FONTE_OSPITE = N_("D021: gli stessi genomi dell'ospite dei profili pubblicati (maiale Sscrofa11.1, bovino ARS-UCD1.2, "
                  "pecora ARS-UI_Ramb_v2.0); il DNA umano (GRCh38) si toglie sempre. D074: i 4 prodotti dell'app")
# Ambienti nuovi (v1.1, R9): stesse chiavi dei prodotti più "testo" (voce del menu) e "sperimentale" (True finché la
# prova con dati pubblici non è finita e coerente con l'articolo: implementazione/validazione/ambienti/ESITO.md).
# "grch38" fra gli ospiti: l'uomo È l'ospite (run.sh lo toglie con filter_human, nel ciclo degli ospiti lo salta).
# Vite: genoma RefSeq con cloroplasto e mitocondrio (D167, refs/hosts.tsv). Scelte e fonti: docs/ambienti.md.
_TOLGO_VITE = N_("Toglierò il DNA della vite e quello umano.")
AMBIENTI = [
    ("feci_umane", N_("Feci umane (intestino)"), ["grch38"], N_("Toglierò il DNA umano."),
     N_("Nelle feci il DNA umano è di solito poco, ma si toglie sempre: non dice nulla dei taxa e protegge la privacy "
        "della persona. MetaPhlAn e Kraken conoscono bene i taxa dell'intestino umano."), "info", True),
    ("cute", N_("Cute (pelle)"), ["grch38"], N_("Toglierò il DNA umano."),
     N_("Sulla pelle i taxa sono pochi: il DNA umano può essere gran parte delle read e il DNA dei reagenti e del "
        "laboratorio pesa molto. Leggi i taxa rari solo accanto a un controllo negativo (bianco di estrazione)."),
     "avviso", True),
    ("suolo", N_("Suolo o rizosfera (anche del vigneto)"), [],
     N_("Qui non c'è un ospite: toglierò solo il DNA umano, che arriva da chi ha raccolto e lavorato il campione."),
     N_("Nel suolo la gran parte delle specie non ha un genoma di riferimento: MetaPhlAn ne riconosce poche e Kraken "
        "lascia senza nome molte read. Il profilo descrive i taxa noti, non tutta la comunità."), "avviso", True),
    ("vite_mosto", N_("Vite: mosto o vino in fermentazione"), ["vitis_vinifera"], _TOLGO_VITE,
     N_("Nel mosto c'è DNA dell'acino e nessuno dei due database contiene la vite: senza toglierlo, quelle read "
        "finiscono assegnate per errore a qualche taxon. Molti lieviti del mosto (Hanseniaspora, Metschnikowia, "
        "Aureobasidium) non sono in nessuno dei due database: il profilo non li vede."), "avviso", True),
    ("vite_acino", N_("Vite: acino o grappolo"), ["vitis_vinifera"], _TOLGO_VITE,
     N_("Sulla buccia i taxa sono pochi e il DNA della vite può essere la gran parte delle read: servono molte read "
        "per avere un profilo. Il genoma della vite usato contiene anche cloroplasto e mitocondrio, che si tolgono "
        "insieme. Molti lieviti della buccia (Hanseniaspora, Metschnikowia, Aureobasidium) non sono in nessuno dei "
        "due database: il profilo non li vede."), "avviso", True),
    ("vite_foglia", N_("Vite: foglia"), ["vitis_vinifera"], _TOLGO_VITE,
     N_("Nella foglia il DNA della pianta è di solito la gran parte delle read: servono molte read per avere un "
        "profilo. Il genoma della vite usato contiene anche cloroplasto e mitocondrio: si tolgono insieme, "
        "altrimenti le read dei cloroplasti possono sembrare cianobatteri."), "avviso", True),
    ("vite_radice", N_("Vite: radice (superficie o interno)"), ["vitis_vinifera"], _TOLGO_VITE,
     N_("Sulla radice, e ancora di più al suo interno, il DNA della vite è molto: per questo alcuni studi fanno lo "
        "shotgun solo sulla superficie della radice e sul suolo attorno. Per il suolo attorno alla radice scegli "
        "'Suolo o rizosfera'."), "avviso", True),
]
FONTE_AMBIENTI = N_("docs/ambienti.md: ospite, database e limiti di ogni ambiente con le fonti; prova con dati "
                    "pubblici piccoli in implementazione/validazione/ambienti/ESITO.md. 'Sperimentale' finché la "
                    "prova non è finita e coerente con l'articolo")

_spec = importlib.util.spec_from_file_location("triage_report", ROOT / "steps" / "17_triage_report.py")
_triage = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_triage)


def consiglio(codice, messaggio, fonte, livello="avviso"):
    return {"codice": codice, "livello": livello, "messaggio": messaggio, "fonte": fonte}


def modo(ram_gb, indice_intero, kraken_completo, kraken_rapido):
    """Modalità consigliata dalla RAM e dai database installati: ({"metaphlan", "kraken"}, [consigli])."""
    c = []
    mpa = "standard" if ram_gb >= RAM_STANDARD_GB and indice_intero else "fette"
    c.append(consiglio("MODO_METAPHLAN", _("MetaPhlAn: modalità consigliata '{modo}' ({ram} GB di memoria per il "
                                           "motore).", modo=mpa, ram=lingua.virgola(f"{ram_gb:.1f}")),
                         _(FONTE_RAM_STANDARD), "info"))
    if 0 < ram_gb < RAM_MINIMA_GB:
        c.append(consiglio("RAM_INSUFFICIENTE", _("Il motore vede solo {ram} GB di memoria: l'analisi potrebbe "
                                                  "fermarsi. Chiudi gli altri programmi o usa un PC con almeno 16 GB.",
                                                  ram=lingua.virgola(f"{ram_gb:.1f}")), _(FONTE_RAM_MINIMA)))
    kraken = "rapido" if kraken_rapido and not kraken_completo else "completo"
    if not kraken_completo and not kraken_rapido:
        c.append(consiglio("DB_MANCANTE", _("Manca il database di Kraken."), _(FONTE_DB)))
    elif not kraken_completo:
        c.append(consiglio("DB_MANCANTE", _("Manca il database completo di Kraken: si può usare solo lo screening "
                                            "rapido (PlusPF-8), che perde alcune specie fra 0,1 e 1 %."), _(FONTE_DB)))
    return {"metaphlan": mpa, "kraken": kraken}, c


def prodotti():
    """Regola prodotto -> ospite per l'interfaccia (info.prodotti), nell'ordine del menu:
    [{prodotto, ospiti, genomi, frase, perche, livello, fonte}]; dopo i 4 prodotti di carne (invariati) gli ambienti
    nuovi, con in più {testo, sperimentale}."""
    return ([{"prodotto": p, "ospiti": o, "genomi": [GENOMI[x] for x in o], "frase": _(frase), "perche": _(perche),
              "livello": livello, "fonte": _(FONTE_OSPITE)} for p, o, frase, perche, livello in PRODOTTI]
            + [{"prodotto": p, "testo": _(testo), "ospiti": o, "genomi": [GENOMI[x] for x in o], "frase": _(frase),
                "perche": _(perche), "livello": livello, "fonte": _(FONTE_AMBIENTI), "sperimentale": sperimentale}
               for p, testo, o, frase, perche, livello, sperimentale in AMBIENTI])


def tempo(tempo_s):
    totale = sum(v for v in tempo_s.values() if v)
    if totale <= TEMPO_LUNGO_S:
        return []
    return [consiglio("TEMPO_LUNGO", _("L'analisi richiederà circa {ore} ore. Puoi usare lo screening rapido "
                                       "(PlusPF-8) o il cloud.", ore=round(totale / 3600)), _(FONTE_TEMPO))]


def spazio(necessario_gb, libero_gb):
    if libero_gb is None or necessario_gb * MARGINE_SPAZIO <= libero_gb:
        return []
    manca = necessario_gb * MARGINE_SPAZIO - libero_gb
    return [consiglio("SPAZIO_INSUFFICIENTE", _("Servono circa {servono} GB liberi, ce ne sono {liberi}: libera "
                                                "almeno {manca} GB prima di partire.",
                                                servono=f"{necessario_gb * MARGINE_SPAZIO:.0f}",
                                                liberi=f"{libero_gb:.0f}", manca=f"{manca:.0f}"), _(FONTE_SPAZIO))]


def database(kraken_db, installati):
    """kraken_db scelto nel progetto ('completo' | 'rapido'); installati: {nome: bool} come in info."""
    nome = {"completo": "kraken_pluspf_20260626", "rapido": "kraken_pluspf_08gb_20260626"}.get(kraken_db)
    if nome and not installati.get(nome, False):
        return [consiglio("DB_MANCANTE", _("Il database di Kraken scelto ('{db}') non è installato.", db=kraken_db),
                          _(FONTE_DB))]
    return []


def soglie_triage(cfg):
    t = cfg.get("triage") if isinstance(cfg, dict) else None
    t = t if isinstance(t, dict) else {}
    out = {}
    for k, v in TRIAGE_PREDEFINITE.items():
        try:
            out[k] = float(t.get(k, v))
        except (TypeError, ValueError):
            out[k] = v
    return out


def triage(tsv, soglie=None):
    """Esito per campione da triage.tsv (steps/17): [{campione, esito, motivi, punteggio}] e i consigli."""
    s = soglie or dict(TRIAGE_PREDEFINITE)
    fonte = _(FONTE_TRIAGE).format(host=s["max_host_pct"], reads=s["min_nonhost_reads"], q30=s["min_q30_pct"])
    esiti, consigli = [], []
    if not tsv or not Path(tsv).is_file():
        return esiti, consigli
    with open(tsv, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f, delimiter="\t"):
            esito = TRIAGE_ESITO.get(r.get("decision", ""), "da controllare")
            motivi = []
            try:
                host, reads, q30 = float(r["host_pct"]), float(r["est_nonhost_fragments"]), float(r["q30_pct"])
            except (KeyError, ValueError):
                motivi.append(_("mancano le misure del triage"))
            else:   # stesse regole e zona grigia di steps/17: un motivo solo se la regola non e' chiaramente passata
                if _triage.ramp(100.0 - host, 100.0 - s["max_host_pct"]) < 0.75:
                    motivi.append(_("troppo DNA dell'ospite ({host} %, massimo {massimo} %)", host=f"{host:.0f}",
                                    massimo=f"{s['max_host_pct']:g}"))
                if _triage.ramp(reads, s["min_nonhost_reads"]) < 0.75:
                    # il punto delle migliaia solo nei numeri: "circa 900.000, minimo 1.000.000" (R1)
                    motivi.append(_("poche read senza l'ospite (circa {reads}, minimo {minimo})",
                                    reads=lingua.migliaia(f"{reads:,.0f}"),
                                    minimo=lingua.migliaia(f"{s['min_nonhost_reads']:,.0f}")))
                if _triage.ramp(q30, s["min_q30_pct"]) < 0.75:
                    motivi.append(_("qualità delle read bassa ({q30} % di basi buone, minimo {minimo} %)",
                                    q30=f"{q30:.0f}", minimo=f"{s['min_q30_pct']:g}"))
            esiti.append({"campione": r.get("sample", ""), "esito": esito, "motivi": motivi,
                          "punteggio": float(r["score"]) if r.get("score") else None})
            if esito != "buono":
                codice = "CAMPIONE_DA_RIFARE" if esito == "da rifare" else "CAMPIONE_DA_CONTROLLARE"
                consigli.append(consiglio(codice, _("Campione {nome}: {esito}", nome=r.get('sample', ''),
                                                    esito=_(esito))
                                          + (f" ({'; '.join(motivi)})." if motivi else "."), fonte))
    return esiti, consigli
