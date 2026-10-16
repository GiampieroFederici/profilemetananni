"""Finto motore di profilemetananni (D032): stessi comandi ed eventi JSON di docs/contratto_motore.md,
tempi accorciati, risultati presi da una corsa vera di SF3RAt7 (installer/finto/). Serve solo a costruire
l'interfaccia (S4-S6): non calcola nulla e non si installa per gli utenti.

Uso: python finto_motore.py <info|installa|verifica|stima|esegui|annulla|sicurezza|referto> [opzioni]
  --progetto FILE   config.yaml del progetto (stima, esegui); i risultati vanno in <sua cartella>/risultati/
  --corsa ID        corsa da fermare (annulla)
  --ingresso FILE   richiesta JSON di sicurezza (calcolo vero di motore/fssp: e' Python puro e istantaneo)
  --velocita N      quante volte piu' veloce del vero (predefinito 60: un'ora diventa un minuto; 0 = senza attese)
  --scenario S      ok (predefinito) | DB_MANCANTE (verifica, esegui) | GIA_IN_CORSO (esegui) |
                    annullata (installa, esegui) | READ_NON_TROVATE (esegui) | TEMPO_LUNGO (stima, esegui) |
                    CAMPIONE_DA_CONTROLLARE (esegui: triage "da controllare", v0.2)

esegui copia in risultati/referto/ il referto vero di SF3RAt7 (installer/finto/referto/); referto lo rifa'
con motore/referto.py (HTML sempre; Excel e PDF se ci sono openpyxl e PySide6, altrimenti REFERTO_PARZIALE).

Senza --scenario si comporta come il vero: un solo esegui alla volta (GIA_IN_CORSO) e annulla ferma davvero
la corsa indicata. Tempi veri misurati su SF3RAt7 (S2.2, S3).
"""
import argparse
import json
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
import system_one  # noqa: E402  (regole vere di System One v0: consigliano, non calcolano)
STATO = Path(tempfile.gettempdir()) / "pmn_finto"
CAMPIONE = "SRR4875279"   # SF3RAt7 (Felino), scaricato da NCBI con il suo codice SRR
COPPIE_DOPO_OSPITE = 1507887
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
}


class Annullata(Exception):
    pass


class Motore:
    def __init__(self, a):
        self.a = a
        self.corsa = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
        self.log = STATO / f"{self.corsa}_{a.comando}.log"

    def evento(self, tipo, messaggio, **campi):
        riga = {"tipo": tipo, "ora": datetime.now().astimezone().isoformat(timespec="seconds"),
                "messaggio": messaggio, **campi}
        print(json.dumps(riga, ensure_ascii=False), flush=True)
        with open(self.log, "a", encoding="utf-8") as f:
            f.write(f"{riga['ora']} {tipo}: {messaggio}\n")

    def attendi(self, secondi_veri):
        """Aspetta il tempo vero diviso per --velocita; intanto guarda se annulla ha chiesto di fermarsi."""
        fine = time.monotonic() + (secondi_veri / self.a.velocita if self.a.velocita > 0 else 0)
        while True:
            if (STATO / f"{self.corsa}.annulla").exists():
                raise Annullata
            if time.monotonic() >= fine:
                return
            time.sleep(min(0.1, fine - time.monotonic()))

    def errore(self, codice, messaggio, cosa_fare):
        self.evento("errore", messaggio, codice=codice, cosa_fare=cosa_fare)
        return "errore", {"codice": codice}, "L'operazione non e' andata a buon fine."

    def progetto(self):
        p = self.a.progetto
        if not p or not Path(p).is_file():
            return None
        return Path(p).resolve()

    # ---------------- comandi ----------------
    def info(self):
        return "ok", INFO, "Ecco com'e' fatto questo PC e cosa e' installato."

    def installa(self):
        passi = [("controllo", 0, 10, "Controllo il PC e lo spazio libero..."),
                 ("programmi", 2, 300, "Installo i programmi (8 ambienti)..."),
                 ("database", 22, 3600, "Scarico i database e controllo che siano integri..."),
                 ("verifica", 93, 300, "Prova finale su un piccolo campione (alcuni minuti)...")]
        for passo, pct, sec, msg in passi:
            self.evento("avanzamento", msg, passo=passo, campione=None, fatto=0, totale=1, percentuale=pct, eta_s=None)
            if self.a.scenario == "annullata" and passo == "database":
                raise Annullata
            self.attendi(sec)
        return "ok", {"installati": ["programmi", "metaphlan", "kraken_completo", "kraken_rapido", "ospite", "prova"]}, \
            "VERDE: il motore e' installato e funziona."

    def verifica(self):
        self.evento("avanzamento", "Controllo i database e provo un piccolo campione...", passo="verifica",
                    campione=None, fatto=0, totale=1, percentuale=10, eta_s=None)
        if self.a.scenario == "DB_MANCANTE":
            return self.errore("DB_MANCANTE", "Manca il database di Kraken.", "Apri Impostazioni e premi Installa.")
        self.attendi(300)
        controlli = [{"nome": n, "esito": "ok"} for n in
                     ("versioni dei programmi", "MD5 dei database", "mini-campione: mapout", "mini-campione: profilo")]
        return "ok", {"esito": "verde", "controlli": controlli}, "VERDE: il motore funziona."

    def stima(self):
        if not self.progetto():
            return self.errore("CONFIG_NON_VALIDA", "Non trovo il file del progetto.", "Salva il progetto e riprova.")
        # regole del contratto (5.2): Kraken completo ~37.000 coppie/min; MetaPhlAn a fette 86,2 s per milione + 150 s.
        # Ospite: solo indicativo, in proporzione a SF3RAt7 (325 s per 1,51 M coppie rimaste).
        coppie = 34109943 if self.a.scenario == "TEMPO_LUNGO" else COPPIE_DOPO_OSPITE
        tempo = {"ospite": round(coppie / 1e6 * 216), "metaphlan": round(coppie / 1e6 * 86.2 + 150),
                 "kraken": round(coppie / 37000 * 60)}
        consigli = system_one.tempo(tempo) + system_one.spazio(12, INFO["spazio_libero_gb"])
        for c in consigli:
            self.evento("avviso", c["messaggio"], codice=c["codice"])
        return "ok", {"campioni": 1, "coppie_totali": coppie, "tempo_s": tempo, "spazio_gb": 12,
                      "spazio_libero_gb": INFO["spazio_libero_gb"], "consigli": consigli}, "Stima pronta."

    def esegui(self):
        progetto = self.progetto()
        if not progetto:
            return self.errore("CONFIG_NON_VALIDA", "Non trovo il file del progetto.", "Salva il progetto e riprova.")
        blocco = STATO / "esegui.lock"
        if self.a.scenario == "GIA_IN_CORSO" or blocco.exists():
            return self.errore("GIA_IN_CORSO", "C'e' gia' un'analisi in corso.",
                               "Aspetta che finisca, oppure annullala.")
        blocco.write_text(self.corsa, encoding="utf-8")
        try:
            return self._esegui(progetto)
        finally:
            blocco.unlink(missing_ok=True)
            (STATO / f"{self.corsa}.annulla").unlink(missing_ok=True)

    def _esegui(self, progetto):
        if self.a.scenario == "TEMPO_LUNGO":
            self.evento("avviso", "L'analisi richiedera' piu' di 4 ore. Puoi usare lo screening rapido (PlusPF-8) "
                        "o il cloud.", codice="TEMPO_LUNGO")
        # (passo, secondi veri, messaggi): tempi misurati su SF3RAt7 (S2.2, S3)
        piano = [("download", 240, ["scarico le read da NCBI"]),
                 ("controllo_qualita", 20, ["controllo la qualita' delle read"]),
                 ("pulizia", 60, ["tolgo le parti di bassa qualita'"]),
                 ("ospite", 325, ["tolgo le read del maiale e dell'uomo"]),
                 ("metaphlan", 350, [f"allineo sulla parte {n} di 6 del database" for n in range(1, 7)]
                  + ["calcolo il profilo delle specie"]),
                 ("kraken", 2445, ["classifico le read con Kraken (database completo)"] * 4
                  + ["stimo le abbondanze con Bracken"]),
                 ("riepilogo", 10, ["preparo le tabelle e il riepilogo"])]
        totale_s = sum(p[1] for p in piano)
        fatto_s = 0.0
        for passo, sec, messaggi in piano:
            if passo == "download" and self.a.scenario == "READ_NON_TROVATE":
                return self.errore("READ_NON_TROVATE", f"Non trovo le read del campione {CAMPIONE} su NCBI.",
                                   "Controlla il codice SRR nel progetto.")
            if passo == "kraken" and self.a.scenario == "DB_MANCANTE":
                return self.errore("DB_MANCANTE", "Manca il database di Kraken.", "Apri Impostazioni e premi Installa.")
            if passo == "metaphlan" and self.a.scenario == "annullata":
                raise Annullata
            for i, m in enumerate(messaggi):
                rimasti = totale_s - fatto_s
                self.evento("avanzamento", f"Campione 1 di 1: {m}", passo=passo, campione=CAMPIONE, fatto=i,
                            totale=len(messaggi), percentuale=round(100 * fatto_s / totale_s, 1),
                            eta_s=round(rimasti / self.a.velocita) if self.a.velocita > 0 else 0)
                self.attendi(sec / len(messaggi))
                fatto_s += sec / len(messaggi)
        return "ok", self._scrivi_risultati(progetto.parent / "risultati"),             f"Analisi finita in {round(totale_s / 60)} min (tempo vero, qui accorciato)."

    def _scrivi_risultati(self, r):
        for sotto in ("metaphlan", "kraken", "tabelle", "log"):
            (r / sotto).mkdir(parents=True, exist_ok=True)
        shutil.copy(DATI / f"{CAMPIONE}_profile.txt", r / "metaphlan")
        for est in ("bracken", "k2report"):
            shutil.copy(DATI / f"{CAMPIONE}.{est}", r / "kraken")
        for f in DATI.glob("*.tsv"):
            shutil.copy(f, r / "tabelle")
        shutil.copytree(DATI / "referto", r / "referto", dirs_exist_ok=True)
        risultati = json.loads((DATI / "risultati.json").read_text(encoding="utf-8"))
        risultati["corsa"] = self.corsa
        if self.a.scenario == "CAMPIONE_DA_CONTROLLARE":
            motivo = "poche read dei microbi (circa 900.000, minimo 1.000.000)"
            risultati["triage"] = [{"campione": CAMPIONE, "esito": "da controllare", "motivi": [motivo], "punteggio": 0.45}]
            c = system_one.consiglio("CAMPIONE_DA_CONTROLLARE", f"Campione {CAMPIONE}: da controllare ({motivo}).",
                                     "steps/17_triage_report.py (scenario del finto motore)")
            risultati["consigli"] = [c]
            self.evento("avviso", c["messaggio"], codice=c["codice"])
        (r / "risultati.json").write_text(json.dumps(risultati, ensure_ascii=False, indent=1), encoding="utf-8")
        shutil.copy(self.log, r / "log")
        return {"cartella": str(r), **risultati}

    def sicurezza(self):
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "motore"))
        import sicurezza
        if self.a.progetto and not self.progetto():
            return self.errore("CONFIG_NON_VALIDA", "Non trovo il file del progetto.", "Salva il progetto e riprova.")
        try:
            risultato, messaggio = sicurezza.comando(self.evento, self.a.ingresso, self.a.progetto)
        except sicurezza.Rifiutata as e:
            return self.errore("INGRESSO_NON_VALIDO", f"Dati del prodotto non validi: {e}.", sicurezza.COSA_FARE)
        return "ok", risultato, messaggio

    def referto(self):
        progetto = self.progetto()
        if not progetto:
            return self.errore("CONFIG_NON_VALIDA", "Non trovo il file del progetto.", "Salva il progetto e riprova.")
        r = progetto.parent / "risultati"
        if not (r / "risultati.json").is_file():
            return self.errore("CONFIG_NON_VALIDA", "Questo progetto non ha ancora risultati.", "Prima avvia l'analisi.")
        self.evento("avanzamento", "Preparo il referto (pagina, PDF ed Excel)...", passo="referto", campione=None,
                    fatto=0, totale=1, percentuale=50, eta_s=None)
        p = subprocess.run([sys.executable, str(MOTORE / "referto.py"), "--risultati", str(r), "--progetto", str(progetto)],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        try:
            esito = json.loads(p.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            esito = {}
        if not esito.get("html"):
            return self.errore("ERRORE_INTERNO", "Non riesco a preparare il referto.", f"Guarda il file {self.log}.")
        if esito.get("problemi"):
            self.evento("avviso", "Il referto non e' completo: " + "; ".join(esito["problemi"])[:300],
                        codice="REFERTO_PARZIALE")
        file = {k: (f"referto/{Path(esito[k]).name}" if esito.get(k) else None) for k in ("html", "pdf", "xlsx")}
        return "ok", {"cartella": str(r), "referto": file}, "Referto pronto."

    def annulla(self):
        blocco = STATO / "esegui.lock"
        if blocco.exists() and blocco.read_text(encoding="utf-8") == self.a.corsa:
            (STATO / f"{self.a.corsa}.annulla").touch()
            return "ok", {"annullata": True}, "Chiesto di fermare l'analisi."
        return "ok", {"annullata": False}, "Nessuna analisi in corso con questo codice."


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
    a = p.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")   # JSON Lines in UTF-8 anche su Windows (pipe = cp1252)
    STATO.mkdir(exist_ok=True)
    m = Motore(a)
    m.evento("inizio", f"Comando {a.comando} avviato (motore finto).", comando=a.comando, corsa=m.corsa, log=str(m.log))
    try:
        esito, risultato, messaggio = getattr(m, a.comando)()
        codice = USCITA.get(esito) if esito != "errore" else CODICE_USCITA.get(risultato["codice"], 4)
    except Annullata:
        esito, risultato, messaggio, codice = "annullata", {}, "Annullata: niente di fatto a meta' e' rimasto.", 3
    m.evento("fine", messaggio, esito=esito, risultato=risultato)
    return codice


if __name__ == "__main__":
    sys.exit(main())
