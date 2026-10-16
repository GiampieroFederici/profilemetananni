"""Prepara dati.js per il prototipo dell'interfaccia (S4): niente numeri inventati.

- eventi: registrati dal finto motore (installer/finto_motore.py, --velocita 0) per ogni comando e scenario;
- risultati: profilo MetaPhlAn e Bracken della corsa vera di SF3RAt7 (installer/finto/);
- sicurezza alimentare: 3 casi calcolati con steps/45_previsione_fssp.py (motore/fssp).

Uso: python docs/prototipo_interfaccia/costruisci_dati.py   (solo libreria standard, gira anche su Windows)
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

QUI = Path(__file__).resolve().parent
ROOT = QUI.parent.parent
FINTO = ROOT / "installer" / "finto_motore.py"
DATI = ROOT / "installer" / "finto"


def eventi(comando, progetto=None, scenario="ok"):
    # esegui a velocita' 60 (un'ora vera = un minuto) perche' eta_s sia vero: tempo vero = eta_s * 60
    velocita = "60" if comando == "esegui" else "0"
    cmd = [sys.executable, str(FINTO), comando, "--velocita", velocita, "--scenario", scenario]
    if progetto:
        cmd += ["--progetto", str(progetto)]
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", check=False)
    righe = [json.loads(r) for r in p.stdout.splitlines() if r.strip()]
    return {"codice_uscita": p.returncode, "eventi": righe}


def metaphlan():
    specie, non_assegnato = [], None
    # colonne: clade_name, NCBI_tax_id, relative_abundance, additional_species
    for r in (DATI / "SRR4875279_profile.txt").read_text(encoding="utf-8").splitlines():
        if r.startswith("#"):
            continue
        clade, _, pct = r.split("\t")[:3]
        livelli = clade.split("|")
        if clade == "UNCLASSIFIED":
            non_assegnato = float(pct)
        elif livelli[-1].startswith("s__"):
            specie.append({"nome": livelli[-1][3:].replace("_", " "),
                           "genere": next((x[3:] for x in livelli if x.startswith("g__")), ""),
                           "regno": livelli[0][3:], "pct": float(pct)})
    specie.sort(key=lambda s: -s["pct"])
    return {"specie": specie, "non_assegnato_pct": non_assegnato}


def bracken():
    righe = (DATI / "SRR4875279.bracken").read_text(encoding="utf-8").splitlines()[1:]
    out = [{"nome": c[0], "read": int(c[5]), "pct": round(100 * float(c[6]), 3)}
           for c in (r.split("\t") for r in righe)]
    return sorted(out, key=lambda s: -s["read"])


def fssp(casi, profilo):
    out = {}
    with tempfile.TemporaryDirectory() as t:
        for nome, (titolo, richiesta) in casi.items():
            richiesta = {**richiesta, "profilo_specie": profilo}
            ing, usc = Path(t) / f"{nome}_in.json", Path(t) / f"{nome}_out.json"
            ing.write_text(json.dumps(richiesta), encoding="utf-8")
            p = subprocess.run([sys.executable, str(ROOT / "steps" / "45_previsione_fssp.py"), "--ingresso", str(ing),
                                "--uscita", str(usc), "--passo-curva-ore", "12"],
                               capture_output=True, text=True, encoding="utf-8", check=False)
            if p.returncode != 0:
                raise SystemExit(f"FSSP caso {nome}: {p.stdout} {p.stderr}")
            out[nome] = {"titolo": titolo, "richiesta": richiesta,
                         "risultato": json.loads(usc.read_text(encoding="utf-8"))}
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
    mpa = metaphlan()
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
            "metaphlan": mpa, "bracken": bracken(), "fssp": fssp(casi, profilo)}
    (QUI / "dati.js").write_text("// Generato da costruisci_dati.py: non modificare a mano.\nwindow.PMN_DATI = "
                                 + json.dumps(dati, ensure_ascii=False) + ";\n", encoding="utf-8")
    print("dati.js scritto:", {k: len(v["eventi"]) for k, v in motore.items()},
          "specie MetaPhlAn", len(mpa["specie"]), "Bracken", len(dati["bracken"]))


if __name__ == "__main__":
    main()
