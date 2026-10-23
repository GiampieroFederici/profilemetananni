"""Finto motore di profilemetananni (D032): stessi comandi ed eventi JSON di docs/contratto_motore.md,
tempi accorciati, risultati presi da una corsa vera di SF3RAt7 (installer/finto/). Serve solo a costruire
l'interfaccia (S4-S6): non calcola nulla e non si installa per gli utenti.

Uso: python finto_motore.py <info|installa|verifica|stima|esegui|annulla|sicurezza|referto> [opzioni]
  --progetto FILE   config.yaml del progetto (stima, esegui); i risultati vanno in <sua cartella>/risultati/
  --corsa ID        corsa da fermare (annulla)
  --ingresso FILE   richiesta JSON di sicurezza (calcolo vero di motore/fssp: è Python puro e istantaneo)
  --velocita N      quante volte più veloce del vero (predefinito 60: un'ora diventa un minuto; 0 = senza attese)
  --scenario S      ok (predefinito) | DB_MANCANTE (verifica, esegui) | GIA_IN_CORSO (esegui) |
                    annullata (installa, esegui) | READ_NON_TROVATE (esegui) | TEMPO_LUNGO (stima, esegui) |
                    CAMPIONE_DA_CONTROLLARE (esegui: triage "da controllare", v0.2)
  --lingua it|en    lingua dei testi (come il vero, contratto §1); con en esegui rifà sintesi e referto in inglese

esegui copia in risultati/referto/ il referto vero di SF3RAt7 (installer/finto/referto/); referto lo rifà
con motore/referto.py (HTML sempre; Excel e PDF se ci sono openpyxl e PySide6, altrimenti REFERTO_PARZIALE).

Senza --scenario si comporta come il vero: un solo esegui alla volta (GIA_IN_CORSO) e annulla ferma davvero
la corsa indicata. Tempi veri misurati su SF3RAt7 (S2.2, S3).
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

DATI = Path(__file__).resolve().parent / "finto"
MOTORE = Path(__file__).resolve().parent.parent / "motore"
sys.path.insert(0, str(MOTORE))
import lingua  # noqa: E402
import system_one  # noqa: E402  (regole vere di System One v0: consigliano, non calcolano)
from lingua import N_, _  # noqa: E402
from pmn_motore import CITAZIONI, ESEMPIO, messaggio_fine, sezione, tempi  # noqa: E402  (stesso testo di fine e stesse regole di stima del vero)
STATO = Path(tempfile.gettempdir()) / "pmn_finto"
CAMPIONE = "SRR4875279"   # SF3RAt7 (Felino), scaricato da NCBI con il suo codice SRR
COPPIE, BYTE = 3240847, 533522098   # SF3RAt7 su ENA: coppie prima dell'ospite e byte delle read gz
COPPIE_LUNGO = 34109943             # C03_1 (scenario TEMPO_LUNGO)
USCITA = {"ok": 0, "annullata": 3}
CODICE_USCITA = {"CONFIG_NON_VALIDA": 1, "READ_NON_TROVATE": 1, "GIA_IN_CORSO": 1, "INGRESSO_NON_VALIDO": 1,
                 "DB_MANCANTE": 2, "ERRORE_INTERNO": 4}
INFO = {
    "motore": "0.1.0", "finto": True, "ram_gb": 15.6, "processori": 8, "spazio_libero_gb": 643,
    "modo_consigliato": {"metaphlan": "fette", "kraken": "completo"},
    "programmi": {"metaphlan": "4.2.4", "bowtie2": "2.5.5", "kraken2": "2.17.2", "bracken": "3.1", "fastp": "1.4.0"},
    "database": [
        {"nome": "metaphlan_fette_vJan25_v1", "installato": True, "gb": 24.5},
        {"nome": "kraken_pluspf_20260626", "installato": True, "gb": 118.6},
        {"nome": "kraken_pluspf_08gb_20260626", "installato": True, "gb": 8.6},
        {"nome": "ospite_maiale_bovino_pecora_uomo", "installato": True, "gb": 15.0},
    ],
    "consigli": system_one.modo(15.6, False, True, True)[1],
    "prodotti": system_one.prodotti(),
    "esempio": {**ESEMPIO, "cartella": "/home/pmn/.pmn/db/prova"},
}


def vivo(pid):
    """Il processo pid c'è ancora? Su Windows con OpenProcess (lì os.kill(pid, 0) manderebbe un Ctrl+C)."""
    if os.name == "nt":
        import ctypes
        k = ctypes.windll.kernel32
        h = k.OpenProcess(0x1000, False, int(pid))   # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return False
        codice = ctypes.c_ulong()
        ok = k.GetExitCodeProcess(h, ctypes.byref(codice))
        k.CloseHandle(h)
        return bool(ok) and codice.value == 259      # STILL_ACTIVE
    try:
        os.kill(int(pid), 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def lucchetto(comando="esegui"):
    """Dati del lucchetto di esegui (o di installa, P41) se la corsa che l'ha messo è viva; un lucchetto rimasto si
    toglie (come il vero)."""
    blocco = STATO / f"{comando}.lock"
    try:
        dati = json.loads(blocco.read_text(encoding="utf-8"))
        if vivo(dati["pid"]):
            return dati
    except FileNotFoundError:
        return None
    except (OSError, ValueError, KeyError, TypeError):
        pass
    blocco.unlink(missing_ok=True)   # rimasto da un esegui chiuso a metà, o nel formato vecchio (solo la corsa)
    return None


def tradotta(citazione):
    """Una citazione di installer/finto/risultati.json (scritta in italiano) nella lingua scelta, come la scrive il
    motore vero (CITAZIONI di motore/pmn_motore.py)."""
    for modelli in CITAZIONI.values():
        for t in modelli:
            for db in (N_("PlusPF-8 del 26/06/2026"), N_("PlusPF del 26/06/2026")):
                if t.format(db=db) == citazione:
                    return _(t).format(db=_(db))
    return citazione


class Annullata(Exception):
    pass


class Motore:
    def __init__(self, a):
        self.a = a
        self.corsa = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
        self.log = STATO / f"{self.corsa}_{a.comando}.log"
        self.passo = None   # ultimo passo annunciato: va nell'evento errore (v0.2)

    def evento(self, tipo, messaggio, **campi):
        riga = {"tipo": tipo, "ora": datetime.now().astimezone().isoformat(timespec="seconds"),
                "messaggio": messaggio, **campi}
        if tipo == "avanzamento":
            self.passo = campi.get("passo")
        print(json.dumps(riga, ensure_ascii=False), flush=True)
        with open(self.log, "a", encoding="utf-8") as f:
            f.write(f"{riga['ora']} {tipo}: {messaggio}\n")

    def attendi(self, secondi_veri):
        """Aspetta il tempo vero diviso per --velocita; intanto guarda se annulla ha chiesto di fermarsi."""
        fine = time.monotonic() + (secondi_veri / self.a.velocita if self.a.velocita > 0 else 0)
        while True:
            if (STATO / f"{self.corsa}.annulla").exists():
                raise Annullata
            resto = fine - time.monotonic()   # letto una volta: fra due letture puo' diventare negativo (B1)
            if resto <= 0:
                return
            time.sleep(min(0.1, resto))

    def errore(self, codice, messaggio, cosa_fare, passo=None):
        passo = passo or self.passo
        self.evento("errore", messaggio, codice=codice, cosa_fare=cosa_fare, passo=passo)
        return "errore", {"codice": codice, "passo": passo}, messaggio_fine(messaggio, cosa_fare, passo)

    def progetto(self):
        p = self.a.progetto
        if not p or not Path(p).is_file():
            return None
        return Path(p).resolve()

    def cfg(self):
        try:
            import yaml
            cfg = yaml.safe_load(Path(self.a.progetto).read_text(encoding="utf-8")) or {}
        except Exception:   # niente PyYAML o file illeggibile: valgono i predefiniti
            cfg = {}
        return cfg if isinstance(cfg, dict) else {}

    def tempi(self, coppie):
        """Secondi per passo con tempi() del motore vero (contratto 5.2), gli stessi per stima ed esegui."""
        return tempi([(CAMPIONE, coppie, BYTE * coppie / COPPIE)], self.cfg())

    # ---------------- comandi ----------------
    def info(self):
        info = {**INFO, "consigli": system_one.modo(15.6, False, True, True)[1], "prodotti": system_one.prodotti(),
                "esempio": {**INFO["esempio"], "frase": _(ESEMPIO["frase"])}}   # testi nella lingua della corsa
        return "ok", info, _("Ecco com'è fatto questo PC e cosa è installato.")

    def installa(self):
        passi = [("controllo", 0, 10, N_("Controllo il PC e lo spazio libero...")),
                 ("programmi", 2, 300, N_("Installo i programmi (8 ambienti)...")),
                 ("database", 22, 3600, N_("Scarico i database e controllo che siano integri...")),
                 ("verifica", 93, 300, N_("Prova finale su un piccolo campione (alcuni minuti)..."))]
        blocco = STATO / "installa.lock"   # P41: come il vero, annulla ferma anche l'installazione (scritto in main)
        try:
            for passo, pct, sec, msg in passi:
                self.evento("avanzamento", _(msg), passo=passo, campione=None, fatto=0, totale=1, percentuale=pct,
                            eta_s=None)
                if self.a.scenario == "annullata" and passo == "database":
                    raise Annullata
                self.attendi(sec)
        finally:
            blocco.unlink(missing_ok=True)
            (STATO / f"{self.corsa}.annulla").unlink(missing_ok=True)
        # P15: la forma del contratto e di installa_motore.sh (i gruppi sono la prima colonna del catalogo)
        righe = (Path(__file__).resolve().parent / "catalogo.tsv").read_text(encoding="utf-8").splitlines()[1:]
        gruppi = list(dict.fromkeys(r.split("\t")[0] for r in righe if r.strip()))
        return "ok", {"programmi": 8, "database": gruppi, "verifica": "verde"}, \
            _("VERDE: il motore è installato e funziona.")

    def verifica(self):
        self.evento("avanzamento", _("Controllo i database e provo un piccolo campione..."), passo="verifica",
                    campione=None, fatto=0, totale=1, percentuale=10, eta_s=None)
        if self.a.scenario == "DB_MANCANTE":
            return self.errore("DB_MANCANTE", _("Manca il database di Kraken."),
                               _("Apri la pagina Motore e premi Installa."))
        self.attendi(300)
        controlli = [{"nome": _(n), "esito": "ok"} for n in
                     (N_("versioni dei programmi"), N_("MD5 dei database"), N_("mini-campione: mapout"),
                      N_("mini-campione: profilo"))]
        return "ok", {"esito": "verde", "controlli": controlli}, _("VERDE: il motore funziona.")

    def stima(self):
        if not self.progetto():
            return self.errore("CONFIG_NON_VALIDA", _("Non trovo il file del progetto."),
                               _("Salva il progetto e riprova."))
        coppie = COPPIE_LUNGO if self.a.scenario == "TEMPO_LUNGO" else COPPIE
        tempo = self.tempi(coppie)
        consigli = system_one.tempo(tempo) + system_one.spazio(12, INFO["spazio_libero_gb"])
        for c in consigli:
            self.evento("avviso", c["messaggio"], codice=c["codice"])
        return "ok", {"campioni": 1, "nomi_campioni": [CAMPIONE], "coppie_totali": coppie, "tempo_s": tempo,
                      "tempo_totale_s": sum(tempo.values()), "spazio_gb": 12,
                      "spazio_libero_gb": INFO["spazio_libero_gb"], "consigli": consigli}, _("Stima pronta.")

    def esegui(self):
        progetto = self.progetto()
        if not progetto:
            return self.errore("CONFIG_NON_VALIDA", _("Non trovo il file del progetto."),
                               _("Salva il progetto e riprova."))
        blocco = STATO / "esegui.lock"
        if self.a.scenario == "GIA_IN_CORSO" or lucchetto():
            return self.errore("GIA_IN_CORSO", _("C'è già un'analisi in corso."),
                               _("Aspetta che finisca, oppure annullala."))
        blocco.write_text(json.dumps({"corsa": self.corsa, "pid": os.getpid()}), encoding="utf-8")
        try:
            return self._esegui(progetto)
        finally:
            blocco.unlink(missing_ok=True)
            (STATO / f"{self.corsa}.annulla").unlink(missing_ok=True)

    def _esegui(self, progetto):
        if self.a.scenario == "TEMPO_LUNGO":
            self.evento("avviso", _("L'analisi richiederà più di 4 ore. Puoi usare lo screening rapido (PlusPF-8) "
                                    "o il cloud."), codice="TEMPO_LUNGO")
        # (passo, secondi veri, messaggi) nell'ordine di run.sh, con gli stessi tempi di stima (v0.3).
        # I dati di installer/finto/ vengono da una corsa con lo screening rapido (PlusPF-8)
        t = self.tempi(COPPIE)
        kraken = (_("classifico le read con Kraken (screening rapido, PlusPF-8)")
                  if sezione(self.cfg(), "motore").get("kraken_db") == "rapido" else
                  _("classifico le read con Kraken (database completo, PlusPF)"))
        piano = [("download", t["download"], [_("scarico le read da NCBI")]),
                 ("pulizia", t["pulizia"], [_("tolgo le parti di bassa qualità")]),
                 ("ospite", t["ospite"], [_("tolgo le read del maiale e dell'uomo")]),
                 ("controllo_qualita", t["controllo_qualita"], [_("controllo la qualità delle read")]),
                 ("metaphlan", t["metaphlan"], [_("allineo sulla parte {n} di 6 del database", n=n) for n in range(1, 7)]
                  + [_("calcolo il profilo delle specie")]),
                 ("kraken", t["kraken"], [kraken, _("stimo le abbondanze con Bracken")]),
                 ("riepilogo", t["riepilogo"], [_("preparo le tabelle e il riepilogo")])]
        totale_s = sum(p[1] for p in piano) + t["referto"]   # il referto è l'ultimo passo, come nel vero (P15)
        fatto_s = 0.0
        for passo, sec, messaggi in piano:
            if passo == "download" and self.a.scenario == "READ_NON_TROVATE":
                return self.errore("READ_NON_TROVATE", _("Non trovo le read del campione {nome} su NCBI.", nome=CAMPIONE),
                                   _("Controlla il codice SRR nel progetto."), passo="download")
            if passo == "kraken" and self.a.scenario == "DB_MANCANTE":
                return self.errore("DB_MANCANTE", _("Manca il database di Kraken."),
                                   _("Apri la pagina Motore e premi Installa."), passo="kraken")
            if passo == "metaphlan" and self.a.scenario == "annullata":
                raise Annullata
            for i, m in enumerate(messaggi):
                rimasti = totale_s - fatto_s
                self.evento("avanzamento", _("Campione {i} di {n}: ", i=1, n=1) + m, passo=passo, campione=CAMPIONE,
                            fatto=i,
                            totale=len(messaggi), percentuale=round(100 * fatto_s / totale_s, 1),
                            eta_s=round(rimasti / self.a.velocita) if self.a.velocita > 0 else 0,
                            passo_s=round(sec / len(messaggi) / self.a.velocita) if self.a.velocita > 0 else 0)
                self.attendi(sec / len(messaggi))
                fatto_s += sec / len(messaggi)
        self.evento("avanzamento", _("Preparo il referto (pagina, PDF ed Excel)..."), passo="referto", campione=None,
                    fatto=0, totale=1, percentuale=max(97, round(100 * fatto_s / totale_s, 1)),
                    eta_s=round(t["referto"] / self.a.velocita) if self.a.velocita > 0 else 0)
        self.attendi(t["referto"])
        return "ok", self._scrivi_risultati(progetto.parent / "risultati", progetto), \
            _("Analisi finita in {min} min (tempo vero, qui accorciato).", min=round(totale_s / 60))

    def _scrivi_risultati(self, cartella, progetto):
        # 22/10: su Windows (senza LongPathsEnabled) un file oltre 260 caratteri non si scrive; con "\\?\" sì. Il motore
        # vero scrive dalla WSL, che non ha questo limite: il finto deve fare lo stesso
        r = Path("\\\\?\\" + str(cartella.resolve())) if os.name == "nt" else cartella
        for sotto in ("metaphlan", "kraken", "tabelle", "log"):
            (r / sotto).mkdir(parents=True, exist_ok=True)
        shutil.copy(DATI / f"{CAMPIONE}_profile.txt", r / "metaphlan")
        for est in ("bracken", "k2report"):
            shutil.copy(DATI / f"{CAMPIONE}.{est}", r / "kraken")
        for f in DATI.glob("*.tsv"):
            shutil.copy(f, r / "tabelle")
        risultati = json.loads((DATI / "risultati.json").read_text(encoding="utf-8"))
        risultati["corsa"] = self.corsa
        italiano = lingua.attuale() == "it"
        if italiano:                      # il referto vero di SF3RAt7, già in italiano
            shutil.copytree(DATI / "referto", r / "referto", dirs_exist_ok=True)
        else:                             # i testi della corsa nella lingua scelta, con le funzioni del motore vero
            import referto
            soglia = float(risultati["parametri"].get("abundance_threshold_pct") or 0)
            for c in risultati["campioni"]:
                c["sintesi"] = referto.sintesi(referto.leggi_campione(r, c["file"]), soglia)
            risultati["citazioni"] = [tradotta(c) for c in risultati["citazioni"]]
        if self.a.scenario == "CAMPIONE_DA_CONTROLLARE":
            motivo = _("poche read senza l'ospite (circa {reads}, minimo {minimo})", reads=lingua.migliaia("900,000"),
                       minimo=lingua.migliaia("1,000,000"))
            risultati["triage"] = [{"campione": CAMPIONE, "esito": "da controllare", "motivi": [motivo], "punteggio": 0.45}]
            c = system_one.consiglio("CAMPIONE_DA_CONTROLLARE", _("Campione {nome}: {esito}", nome=CAMPIONE,
                                                                  esito=_("da controllare")) + f" ({motivo}).",
                                     _("steps/17_triage_report.py (scenario del finto motore)"))
            risultati["consigli"] = [c]
            self.evento("avviso", c["messaggio"], codice=c["codice"])
        (r / "risultati.json").write_text(json.dumps(risultati, ensure_ascii=False, indent=1), encoding="utf-8")
        if not italiano:
            risultati["referto"] = self._referto(r, progetto)
            (r / "risultati.json").write_text(json.dumps(risultati, ensure_ascii=False, indent=1), encoding="utf-8")
        shutil.copy(self.log, r / "log")
        return {"cartella": str(cartella), **risultati}

    def sicurezza(self):
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "motore"))
        import sicurezza
        if self.a.progetto and not self.progetto():
            return self.errore("CONFIG_NON_VALIDA", _("Non trovo il file del progetto."),
                               _("Salva il progetto e riprova."))
        try:
            risultato, messaggio = sicurezza.comando(self.evento, self.a.ingresso, self.a.progetto)
        except sicurezza.Rifiutata as e:
            return self.errore("INGRESSO_NON_VALIDO", _("Dati del prodotto non validi: {errore}.", errore=e),
                               _(sicurezza.COSA_FARE))
        return "ok", risultato, messaggio

    def _referto(self, r, progetto):
        """motore/referto.py sul progetto: {file: percorso relativo o None}, None se la pagina non c'è."""
        p = subprocess.run([sys.executable, str(MOTORE / "referto.py"), "--risultati", str(r), "--progetto", str(progetto)],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        try:
            esito = json.loads(p.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            esito = {}
        if not esito.get("html"):
            return None
        if esito.get("problemi"):
            import referto
            self.evento("avviso", referto.avviso_parziale(esito["problemi"], True), codice="REFERTO_PARZIALE")
        return {k: (f"referto/{Path(esito[k]).name}" if esito.get(k) else None) for k in ("html", "pdf", "xlsx")}

    def referto(self):
        progetto = self.progetto()
        if not progetto:
            return self.errore("CONFIG_NON_VALIDA", _("Non trovo il file del progetto."),
                               _("Salva il progetto e riprova."))
        r = progetto.parent / "risultati"
        if not (r / "risultati.json").is_file():
            return self.errore("CONFIG_NON_VALIDA", _("Questo progetto non ha ancora risultati."),
                               _("Prima avvia l'analisi."))
        self.evento("avanzamento", _("Preparo il referto (pagina, PDF ed Excel)..."), passo="referto", campione=None,
                    fatto=0, totale=1, percentuale=50, eta_s=None)
        file = self._referto(r, progetto)
        if file is None:
            return self.errore("ERRORE_INTERNO", _("Non riesco a preparare il referto."),
                               _("Guarda il file {log}.", log=self.log))
        return "ok", {"cartella": str(r), "referto": file}, _("Referto pronto.")

    def annulla(self):
        for comando, testo in (("esegui", N_("Chiesto di fermare l'analisi.")),
                               ("installa", N_("Chiesto di fermare l'installazione."))):
            dati = lucchetto(comando)
            if dati and dati.get("corsa") == self.a.corsa:
                (STATO / f"{self.a.corsa}.annulla").touch()
                return "ok", {"annullata": True}, _(testo)
        return "ok", {"annullata": False}, _("Nessuna analisi in corso con questo codice.")


def main():
    p = argparse.ArgumentParser(description="Finto motore di profilemetananni (solo per l'interfaccia).")
    p.add_argument("comando", choices=["info", "installa", "verifica", "stima", "esegui", "annulla", "sicurezza",
                                       "referto"])
    p.add_argument("--progetto")
    p.add_argument("--corsa", default="")
    p.add_argument("--ingresso")
    p.add_argument("--velocita", type=float, default=60)
    p.add_argument("--scenario", default="ok", choices=["ok", "DB_MANCANTE", "GIA_IN_CORSO", "annullata",
                                                         "READ_NON_TROVATE", "TEMPO_LUNGO", "CAMPIONE_DA_CONTROLLARE"])
    p.add_argument("--lingua", choices=lingua.LINGUE)
    a = p.parse_args()
    if a.lingua:
        lingua.imposta(a.lingua)
    sys.stdout.reconfigure(encoding="utf-8")   # JSON Lines in UTF-8 anche su Windows (pipe = cp1252)
    STATO.mkdir(exist_ok=True)
    m = Motore(a)
    if a.comando == "installa":   # come installa_motore.sh: il lucchetto c'è già quando esce l'evento inizio
        (STATO / "installa.lock").write_text(json.dumps({"corsa": m.corsa, "pid": os.getpid()}), encoding="utf-8")
    m.evento("inizio", _("Comando {comando} avviato (motore finto).", comando=a.comando), comando=a.comando,
             corsa=m.corsa, log=str(m.log))
    try:
        esito, risultato, messaggio = getattr(m, a.comando)()
        codice = USCITA.get(esito) if esito != "errore" else CODICE_USCITA.get(risultato["codice"], 4)
    except Annullata:
        esito, risultato, messaggio, codice = "annullata", {}, _("Annullata: niente di fatto a metà è rimasto."), 3
    except Exception as e:   # 22/10, come il motore vero: un errore nostro si dice (errore + fine), mai un traceback muto
        with open(m.log, "a", encoding="utf-8") as f:
            f.write(f"ERRORE INTERNO: {e!r}\n")
        esito, risultato, messaggio = m.errore("ERRORE_INTERNO", _("Errore imprevisto del motore."),
                                               _("Manda a noi il file {log}.", log=m.log))
        codice = 4
    m.evento("fine", messaggio, esito=esito, risultato=risultato)
    return codice


if __name__ == "__main__":
    sys.exit(main())
