"""System One v0 (D031): regole già misurate che CONSIGLIANO e non calcolano, né cambiano le scelte dell'utente.

Ogni consiglio è {"codice", "livello", "messaggio", "fonte"}: livello "avviso" diventa un evento `avviso`
del contratto, "info" resta solo in risultato.consigli. Ogni soglia ha accanto la sua fonte.
La v1 (S12) sarà un albero addestrato sui casi con risposta nota di L3-L5.
Solo libreria standard.
"""
import csv
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

RAM_STANDARD_GB = 40.0
FONTE_RAM_STANDARD = ("MetaPhlAn standard: picco 25,5 GB con il catalogo in swap (S2.1, macchina da 30 GB); "
                      "non entra nei 31,4 GB del PC di prova (13/10). Soglia 40 GB come run.sh 'auto' (D051)")
RAM_MINIMA_GB = 7.5
FONTE_RAM_MINIMA = ("MetaPhlAn a fette provato con WSL a 8 GB (circa 7,7 GB visibili): SF3RAt7 e C03_1, RAM 7,9 GB "
                    "+ swap 1,2 GB (14/10, 'Gira su 16 GB, verificatò). Sotto non è provato")
TEMPO_LUNGO_S = 4 * 3600
FONTE_TEMPO = "D023: oltre 4 ore si propone lo screening rapido (PlusPF-8) o il cloud"
MARGINE_SPAZIO = 1.15
FONTE_SPAZIO = "stessa regola di steps/05_estimate_size.py: spazio stimato x 1,15 di margine"
FONTE_DB = "installazione del motore (installazione.env): database presenti sul disco"
FONTE_TRIAGE = ("steps/17_triage_report.py: soglie host {host:g} %, {reads:,.0f} frammenti non ospite, "
                "Q30 {q30:g} % (triage.* del progetto); zona grigia +-20 %")
TRIAGE_ESITO = {"pass": "buono", "review": "da controllare", "exclude": "da rifare"}
TRIAGE_PREDEFINITE = {"max_host_pct": 95.0, "min_nonhost_reads": 1_000_000.0, "min_q30_pct": 70.0}

_spec = importlib.util.spec_from_file_location("triage_report", ROOT / "steps" / "17_triage_report.py")
_triage = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_triage)


def consiglio(codice, messaggio, fonte, livello="avviso"):
    return {"codice": codice, "livello": livello, "messaggio": messaggio, "fonte": fonte}


def modo(ram_gb, indice_intero, kraken_completo, kraken_rapido):
    """Modalità consigliata dalla RAM e dai database installati: ({"metaphlan", "kraken"}, [consigli])."""
    c = []
    mpa = "standard" if ram_gb >= RAM_STANDARD_GB and indice_intero else "fette"
    c.append(consiglio("MODO_METAPHLAN", f"MetaPhlAn: modalità consigliata '{mpa}' "
                       f"({ram_gb:.1f} GB di memoria per il motore).", FONTE_RAM_STANDARD, "info"))
    if 0 < ram_gb < RAM_MINIMA_GB:
        c.append(consiglio("RAM_INSUFFICIENTE", f"Il motore vede solo {ram_gb:.1f} GB di memoria: l'analisi potrebbe "
                           "fermarsi. Chiudi gli altri programmi o usa un PC con almeno 16 GB.", FONTE_RAM_MINIMA))
    kraken = "rapido" if kraken_rapido and not kraken_completo else "completo"
    if not kraken_completo and not kraken_rapido:
        c.append(consiglio("DB_MANCANTE", "Manca il database di Kraken.", FONTE_DB))
    elif not kraken_completo:
        c.append(consiglio("DB_MANCANTE", "Manca il database completo di Kraken: si può usare solo lo screening "
                           "rapido (PlusPF-8), che perde alcune specie fra 0,1 e 1 %.", FONTE_DB))
    return {"metaphlan": mpa, "kraken": kraken}, c


def tempo(tempo_s):
    totale = sum(v for v in tempo_s.values() if v)
    if totale <= TEMPO_LUNGO_S:
        return []
    return [consiglio("TEMPO_LUNGO", f"L'analisi richiederà circa {round(totale / 3600)} ore. Puoi usare lo "
                      "screening rapido (PlusPF-8) o il cloud.", FONTE_TEMPO)]


def spazio(necessario_gb, libero_gb):
    if libero_gb is None or necessario_gb * MARGINE_SPAZIO <= libero_gb:
        return []
    manca = necessario_gb * MARGINE_SPAZIO - libero_gb
    return [consiglio("SPAZIO_INSUFFICIENTE", f"Servono circa {necessario_gb * MARGINE_SPAZIO:.0f} GB liberi, ce ne "
                      f"sono {libero_gb:.0f}: libera almeno {manca:.0f} GB prima di partire.", FONTE_SPAZIO)]


def database(kraken_db, installati):
    """kraken_db scelto nel progetto ('completo' | 'rapido'); installati: {nome: bool} come in info."""
    nome = {"completo": "kraken_pluspf_20260626", "rapido": "kraken_pluspf_08gb_20260626"}.get(kraken_db)
    if nome and not installati.get(nome, False):
        return [consiglio("DB_MANCANTE", f"Il database di Kraken scelto ('{kraken_db}') non è installato.", FONTE_DB)]
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
    fonte = FONTE_TRIAGE.format(host=s["max_host_pct"], reads=s["min_nonhost_reads"], q30=s["min_q30_pct"])
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
                motivi.append("mancano le misure del triage")
            else:   # stesse regole e zona grigia di steps/17: un motivo solo se la regola non e' chiaramente passata
                if _triage.ramp(100.0 - host, 100.0 - s["max_host_pct"]) < 0.75:
                    motivi.append(f"troppo DNA dell'ospite ({host:.0f} %, massimo {s['max_host_pct']:g} %)")
                if _triage.ramp(reads, s["min_nonhost_reads"]) < 0.75:
                    motivi.append(f"poche read dei microbi (circa {reads:,.0f}, minimo {s['min_nonhost_reads']:,.0f})"
                                  .replace(",", "."))
                if _triage.ramp(q30, s["min_q30_pct"]) < 0.75:
                    motivi.append(f"qualità delle read bassa ({q30:.0f} % di basi buone, minimo {s['min_q30_pct']:g} %)")
            esiti.append({"campione": r.get("sample", ""), "esito": esito, "motivi": motivi,
                          "punteggio": float(r["score"]) if r.get("score") else None})
            if esito != "buono":
                codice = "CAMPIONE_DA_RIFARE" if esito == "da rifare" else "CAMPIONE_DA_CONTROLLARE"
                consigli.append(consiglio(codice, f"Campione {r.get('sample', '')}: {esito}"
                                          + (f" ({'; '.join(motivi)})." if motivi else "."), fonte))
    return esiti, consigli
