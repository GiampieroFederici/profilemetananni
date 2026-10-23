"""Prepara dati.js per il prototipo dell'interfaccia (S4): niente numeri inventati.

- eventi: registrati dal finto motore (installer/finto_motore.py, --velocita 0) per ogni comando e scenario;
- risultati: profilo MetaPhlAn e Bracken della corsa vera di SF3RAt7 (installer/finto/), letti con le stesse
  funzioni del referto (motore/referto.py): interfaccia e referto mostrano gli stessi numeri;
- sicurezza alimentare: 3 casi calcolati dal comando `sicurezza` del finto motore (contratto v0.2, motore/fssp).

Uso: python docs/prototipo_interfaccia/costruisci_dati.py   (solo libreria standard, gira anche su Windows)
"""
import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

QUI = Path(__file__).resolve().parent
ROOT = QUI.parent.parent
FINTO = ROOT / "installer" / "finto_motore.py"
DATI = ROOT / "installer" / "finto"


def modulo_referto():
    spec = importlib.util.spec_from_file_location("referto", ROOT / "motore" / "referto.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def eventi(comando, progetto=None, scenario="ok"):
    # esegui a velocita' 60 (un'ora vera = un minuto) perche' eta_s sia vero: tempo vero = eta_s * 60
    velocita = "60" if comando == "esegui" else "0"
    cmd = [sys.executable, str(FINTO), comando, "--velocita", velocita, "--scenario", scenario]
    if progetto:
        cmd += ["--progetto", str(progetto)]
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", check=False)
    righe = [json.loads(r) for r in p.stdout.splitlines() if r.strip()]
    return {"codice_uscita": p.returncode, "eventi": righe}


def profili(referto):
    """MetaPhlAn e Kraken del campione, letti come li legge il referto. Sempre separati."""
    specie, non_class = referto.leggi_metaphlan(DATI / "SRR4875279_profile.txt")
    kraken = referto.leggi_kraken(DATI / "SRR4875279.bracken", DATI / "SRR4875279.k2report")
    return ({"specie": [{"nome": n, "pct": v} for n, v in specie], "non_assegnato_pct": non_class},
            [{k: r[k] for k in ("nome", "categoria", "pct", "pct_microbi")} for r in kraken])


def fssp(casi, profilo):
    """Ogni caso con il comando sicurezza del finto motore: eventi (avvisi FUORI_CAMPO) e risultato."""
    out = {}
    with tempfile.TemporaryDirectory() as t:
        for nome, (titolo, richiesta) in casi.items():
            richiesta = {**richiesta, "profilo_specie": profilo}
            ing = Path(t) / f"{nome}.json"
            ing.write_text(json.dumps(richiesta), encoding="utf-8")
            p = subprocess.run([sys.executable, str(FINTO), "sicurezza", "--ingresso", str(ing), "--velocita", "0"],
                               capture_output=True, text=True, encoding="utf-8", check=False)
            ev = [json.loads(r) for r in p.stdout.splitlines() if r.strip()]
            fine = ev[-1] if ev else {}
            if p.returncode != 0 or fine.get("esito") != "ok":
                raise SystemExit(f"sicurezza, caso {nome}: {p.stdout} {p.stderr}")
            out[nome] = {"titolo": titolo, "richiesta": richiesta, "eventi": ev, "risultato": fine["risultato"]}
    return out


def main():
    with tempfile.TemporaryDirectory() as t:
        progetto = Path(t) / "config.yaml"
        progetto.write_text("project_name: prova\n", encoding="utf-8")
        motore = {"info": eventi("info"), "verifica": eventi("verifica"),
                  "verifica_DB_MANCANTE": eventi("verifica", scenario="DB_MANCANTE"),
                  "installa": eventi("installa"),
                  "stima": eventi("stima", progetto), "stima_TEMPO_LUNGO": eventi("stima", progetto, "TEMPO_LUNGO"),
                  "esegui": eventi("esegui", progetto),
                  "esegui_DB_MANCANTE": eventi("esegui", progetto, "DB_MANCANTE"),
                  "esegui_READ_NON_TROVATE": eventi("esegui", progetto, "READ_NON_TROVATE"),
                  "esegui_annullata": eventi("esegui", progetto, "annullata"),
                  "esegui_GIA_IN_CORSO": eventi("esegui", progetto, "GIA_IN_CORSO")}
    mpa, kraken = profili(modulo_referto())
    profilo = {s["nome"]: s["pct"] for s in mpa["specie"]}
    casi = {
        "salsiccia": ("Salsiccia fresca in frigo (5 °C, 21 giorni), senza conta dei LAB",
                      {"prodotto": {"temperatura": 5, "sale_fase_acquosa": 3.5, "ph": 6.0, "nitrito": 100},
                       "giorni": 21}),
        "salsiccia_lab": ("Stessa salsiccia, con conta dei LAB 10^6 ufc/g",
                          {"prodotto": {"temperatura": 5, "sale_fase_acquosa": 3.5, "ph": 6.0, "nitrito": 100},
                           "giorni": 21, "conte": {"lab_ufc_g": 1e6}}),
        "salame": ("Salame stagionato (aw 0,90, pH 5,2, 15 °C, 60 giorni)",
                   {"prodotto": {"temperatura": 15, "aw": 0.90, "ph": 5.2, "nitrito": 100}, "giorni": 60}),
    }
    dati = {"motore": motore, "risultati": json.loads((DATI / "risultati.json").read_text(encoding="utf-8")),
            "metaphlan": mpa, "kraken": kraken, "fssp": fssp(casi, profilo)}
    (QUI / "dati.js").write_text("// Generato da costruisci_dati.py: non modificare a mano.\nwindow.PMN_DATI = "
                                 + json.dumps(dati, ensure_ascii=False) + ";\n", encoding="utf-8")
    print("dati.js scritto:", {k: len(v["eventi"]) for k, v in motore.items()},
          "specie MetaPhlAn", len(mpa["specie"]), "righe Kraken", len(kraken))


if __name__ == "__main__":
    main()
