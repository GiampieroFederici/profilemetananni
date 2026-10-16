#!/usr/bin/env python3
"""Referto del progetto in risultati/referto/: referto.html, referto.xlsx, referto.pdf (contratto v0.2, D036).

Regole: italiano semplice con i termini tecnici spiegati (D027); MetaPhlAn e Kraken SEMPRE in tabelle e fogli
separati, mai fusi; Kraken mostra solo i microbi (batteri, archei, funghi), con Homo, Leishmania e il resto
segnalati a parte (D023); parametri usati con la fonte (D022); riquadro "Strumenti e database usati" (D036);
virus come opzione sperimentale con postilla (D017, D033); sicurezza alimentare se calcolata (risultati/sicurezza/).

Gira con il Python di pmn_reports_py: libreria standard + openpyxl (Excel) + PySide6/QtGui (PDF, senza schermo:
QTextDocument + QPdfWriter, dallo stesso HTML). Se manca un pezzo, gli altri file si fanno lo stesso e
l'uscita lo dice (il motore lo trasforma nell'avviso REFERTO_PARZIALE).

Uso: referto.py --risultati DIR [--progetto config.yaml]
stdout: una riga JSON {"html", "xlsx", "pdf", "problemi": [...]}. Codici: 0 fatto (anche parziale), 1 risultati mancanti.
"""
import argparse
import csv
import html
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "motore"))
import system_one  # noqa: E402

OSPITI = {"sus_scrofa": "maiale (Sscrofa11.1)", "bos_taurus": "bovino (ARS-UCD1.2)",
          "ovis_aries": "pecora (ARS-UI_Ramb_v2.0)", "grch38": "uomo (GRCh38)", "homo_sapiens": "uomo (GRCh38)"}
MICROBI = ("batteri", "archei", "funghi")
VERSIONI = {"metaphlan": "MetaPhlAn", "database_metaphlan": "Database di MetaPhlAn", "kraken2": "Kraken 2",
            "bracken": "Bracken", "database_kraken": "Database di Kraken", "bowtie2": "Bowtie 2 (ospite, fette)",
            "fastp": "fastp (pulizia delle read)", "samtools": "SAMtools"}
MODELLI = {"listeria": "modello Listeria", "listeria_lab": "modello Listeria + batteri lattici",
           "lab": "modello batteri lattici"}
NOMI_PRODOTTO = {"temperatura": "temperatura {} °C", "sale_fase_acquosa": "sale nella fase acquosa {} %", "aw": "aw {}",
                 "ph": "pH {}", "fenoli": "fenoli del fumo {} ppm", "co2": "CO2 {} %", "nitrito": "nitrito {} ppm"}
POSTILLA_VIRUS = ("Virus: opzione sperimentale, non validata con il database diviso in 6 parti. Nei pareggi fra copie "
                  "virali quasi identiche la scelta puo' cambiare rispetto al MetaPhlAn standard (D017, D033).")
GLOSSARIO = [
    ("Read (lettura)", "un pezzetto di DNA letto dal sequenziatore. Con le coppie (read pairs) ogni frammento e' letto dai due lati."),
    ("Ospite", "l'animale da cui viene il prodotto (es. maiale) e l'uomo: il loro DNA si toglie prima di cercare i microbi."),
    ("Abbondanza relativa", "la percentuale di DNA di una specie rispetto al totale: non e' il numero di cellule vive per grammo."),
    ("MetaPhlAn", "riconosce le specie da geni caratteristici di ognuna (marcatori): preciso sulle specie note."),
    ("Kraken + Bracken", "confronta ogni read con interi genomi di riferimento, poi stima le abbondanze: vede piu' specie, "
                         "anche funghi, ma con piu' rumore. Per questo i due risultati stanno in tabelle separate."),
    ("Soglia di abbondanza", "sotto questa percentuale una specie non si mostra nelle tabelle del referto (resta nell'Excel)."),
]


# ---------------- lettura dei risultati ----------------
def nome_specie(clade):
    return clade.split("|")[-1][3:].replace("_", " ")


def leggi_metaphlan(f):
    """([(specie, %)], % UNCLASSIFIED): righe s__ senza t__, percentuali come le scrive MetaPhlAn."""
    specie, non_class = [], 0.0
    for riga in Path(f).read_text(encoding="utf-8").splitlines():
        c = riga.split("\t")
        if riga.startswith("#") or len(c) < 3:
            continue
        if c[0] == "UNCLASSIFIED":
            non_class = float(c[2])
        elif c[0].split("|")[-1].startswith("s__"):
            specie.append((nome_specie(c[0]), float(c[2])))
    return sorted(specie, key=lambda x: -x[1]), non_class


def categorie_kraken(k2report):
    """{taxid: categoria} dall'albero del report di Kraken (rientro di 2 spazi per livello)."""
    out, pila = {}, []
    for riga in Path(k2report).read_text(encoding="utf-8").splitlines():
        c = riga.split("\t")
        if len(c) < 6:
            continue
        nome, taxid = c[-1], c[-2].strip()
        livello = (len(nome) - len(nome.lstrip(" "))) // 2
        while pila and pila[-1][0] >= livello:
            pila.pop()
        pila.append((livello, taxid))
        antenati = {t for _, t in pila}
        if "10239" in antenati:
            out[taxid] = "virus"
        elif "2" in antenati:
            out[taxid] = "batteri"
        elif "2157" in antenati:
            out[taxid] = "archei"
        elif "2759" in antenati:
            out[taxid] = "funghi" if "4751" in antenati else "altri eucarioti"
        else:
            out[taxid] = "altro"
    return out


def leggi_kraken(bracken, k2report):
    """Specie di Bracken con categoria, % sul totale assegnato e % fra i soli microbi."""
    cat = categorie_kraken(k2report) if Path(k2report).is_file() else {}
    righe = []
    with open(bracken, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f, delimiter="\t"):
            righe.append({"nome": r["name"], "taxid": r["taxonomy_id"], "categoria": cat.get(r["taxonomy_id"], "altro"),
                          "letture": int(r["new_est_reads"]), "pct": float(r["fraction_total_reads"]) * 100.0})
    somma = sum(r["pct"] for r in righe if r["categoria"] in MICROBI)
    for r in righe:
        r["pct_microbi"] = 100.0 * r["pct"] / somma if r["categoria"] in MICROBI and somma else None
    return sorted(righe, key=lambda r: -r["pct"])


def tsv_dict(f):
    out = {}
    if Path(f).is_file():
        for riga in Path(f).read_text(encoding="utf-8").splitlines()[1:]:
            k, _, v = riga.partition("\t")
            out[k] = v
    return out


def profili_kraken():
    out = {}
    for riga in (ROOT / "refs" / "kraken_profili.tsv").read_text(encoding="utf-8").splitlines():
        if riga.strip() and not riga.startswith("#"):
            c = riga.split("\t")
            out[c[0]] = {"confidence": c[1], "min_reads": c[2], "soglia": c[3], "fonte": c[4]}
    return out


def numero(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def raccogli(risultati, cfg):
    """Tutto quello che va nel referto, gia' letto dai file (una sola fonte per HTML, Excel e PDF)."""
    indice = json.loads((risultati / "risultati.json").read_text(encoding="utf-8"))
    par = tsv_dict(risultati / "tabelle" / "parameters.tsv") or {k: str(v) for k, v in indice.get("parametri", {}).items()}
    soglia = numero(par.get("abundance_threshold_pct")) or 0.0
    campioni = []
    for c in indice.get("campioni", []):
        file = c.get("file", {})
        d = {"nome": c["nome"], "coppie": c.get("coppie_dopo_ospite"), "metaphlan": None, "kraken": None}
        if file.get("metaphlan") and (risultati / file["metaphlan"]).is_file():
            d["metaphlan"], d["non_classificato"] = leggi_metaphlan(risultati / file["metaphlan"])
        if file.get("kraken") and (risultati / file["kraken"]).is_file():
            b = risultati / file["kraken"]
            d["kraken"] = leggi_kraken(b, b.with_suffix(".k2report"))
        campioni.append(d)
    triage, _ = system_one.triage(risultati / "tabelle" / "triage.tsv", system_one.soglie_triage(cfg))
    sicurezza = [json.loads(f.read_text(encoding="utf-8")) for f in sorted((risultati / "sicurezza").glob("*.json"))]
    motore = cfg.get("motore") if isinstance(cfg.get("motore"), dict) else {}
    return {"progetto": str(cfg.get("project_name") or risultati.parent.name), "corsa": indice.get("corsa", ""),
            "motore": indice.get("motore", ""), "campioni": campioni, "parametri": par, "soglia": soglia,
            "versioni": indice.get("versioni", {}), "citazioni": list(indice.get("citazioni", [])),
            "triage": triage, "sicurezza": sicurezza, "virus": bool(motore.get("virus", False))}


def righe_parametri(d):
    """[(parametro, valore, cosa vuol dire, fonte)] (D022)."""
    p, prof = d["parametri"], profili_kraken()
    profilo = p.get("kraken_profile", "")
    fonte_k = prof.get(profilo, {}).get("fonte", "")
    out = []
    if p.get("metaphlan_mode"):
        out.append(("Modo di MetaPhlAn", p["metaphlan_mode"],
                    "fette = database diviso in 6 parti per stare in 16 GB; profilo delle specie uguale al modo standard"
                    if p["metaphlan_mode"] == "fette" else "standard = database intero in memoria (oltre 40 GB)",
                    "D016 (prova S2.1: 27 specie su 27 identiche); D051"))
    if p.get("metaphlan_index"):
        out.append(("Database di MetaPhlAn", p["metaphlan_index"], "elenco dei geni marcatori delle specie",
                    "Blanco-Miguez et al. 2023"))
    if p.get("kraken_db"):
        spiega = {"completo": "PlusPF completo: batteri, archei, funghi, protozoi, uomo (consigliato)",
                  "rapido": "PlusPF-8, screening rapido: perde alcune specie fra 0,1 e 1 %"}.get(profilo, "")
        out.append(("Database di Kraken", f"{os.path.basename(p['kraken_db'])} ({profilo})", spiega,
                    "D023 (prova K3); Wright, Comeau & Langille 2023"))

    def da_profilo(chiave_p, chiave_prof, nome, spiega):
        v = p.get(chiave_p)
        if v is None or v == "":
            return
        consigliato = prof.get(profilo, {}).get(chiave_prof)
        fonte = fonte_k if consigliato is not None and numero(consigliato) == numero(v) else \
            f"scelto nel progetto (consigliato per '{profilo}': {consigliato})"
        out.append((nome, v, spiega, fonte))
    da_profilo("kraken_confidence", "confidence", "Confidenza di Kraken (--confidence)",
               "quanto Kraken deve essere sicuro per assegnare una read (0 = accetta tutte)")
    da_profilo("bracken_min_reads", "min_reads", "Letture minime di Bracken (-t)",
               "sotto questo numero di read una specie non si stima")
    da_profilo("abundance_threshold_pct", "soglia", "Soglia di abbondanza (%)",
               "sotto questa percentuale una specie non compare nelle tabelle del referto")
    if p.get("bracken_readlen"):
        out.append(("Lunghezza delle read per Bracken (-r)", p["bracken_readlen"], "lunghezza tipica delle read",
                    "impostazione della pipeline"))
    ospiti = [o for o in p.get("hosts", "").replace(",", " ").split() if o]
    if p.get("filter_human") in ("yes", "true", "True", "1"):
        ospiti.append("grch38")
    if ospiti:
        out.append(("DNA tolto prima dell'analisi (ospite)", ", ".join(OSPITI.get(o, o) for o in ospiti),
                    "genomi di riferimento usati per togliere il DNA dell'ospite e dell'uomo",
                    "D021 (stesse versioni dei profili pubblicati)"))
    return out


def dati_prodotto(richiesta):
    """La richiesta di sicurezza in parole: "pH 5,4, nitrito 60 ppm, ..., 30 giorni a 5 °C"."""
    prod = richiesta.get("prodotto", {})
    num = lambda v: f"{v:g}".replace(".", ",")  # noqa: E731
    parti = [NOMI_PRODOTTO[k].format(num(v)) for k, v in prod.items() if k in NOMI_PRODOTTO]
    parti += [f"acido {a} {num(v)} ppm" for a, v in prod.get("acidi", {}).items()]
    if richiesta.get("profilo_temperatura"):
        parti.append("temperature: " + "; ".join(f"{num(o)} ore a {num(t)} °C" for t, o in richiesta["profilo_temperatura"]))
    else:
        parti.append(f"{num(richiesta.get('giorni', 30))} giorni a {num(prod.get('temperatura', 5))} °C")
    for k, v in richiesta.get("conte", {}).items():
        parti.append(f"{'conta dei batteri lattici' if k == 'lab_ufc_g' else 'conta totale'} {v:g} ufc/g")
    return ", ".join(parti)


# ---------------- HTML (anche base del PDF) ----------------
def e(x):
    return html.escape(str(x))


def pct(v, cifre=2):
    return "" if v is None else f"{v:.{cifre}f}".replace(".", ",")


def tabella(intestazione, righe, allinea_destra=(), larghezze=None):
    larghezze = larghezze or [round(100 / len(intestazione))] * len(intestazione)
    t = ['<table border="1" cellspacing="0" cellpadding="4" width="100%">',
         "<tr>" + "".join(f'<th bgcolor="#dfe8f1" align="left" width="{w}%">{e(h)}</th>'
                          for h, w in zip(intestazione, larghezze)) + "</tr>"]
    for r in righe:
        t.append("<tr>" + "".join(f'<td align="{"right" if i in allinea_destra else "left"}">{c}</td>'
                                  for i, c in enumerate(r)) + "</tr>")
    t.append("</table>")
    return "\n".join(t)


def riquadro(testo, colore="#fff4d6"):
    return f'<table border="0" cellpadding="8" width="100%"><tr><td bgcolor="{colore}">{testo}</td></tr></table>'


def html_referto(d):
    s = d["soglia"]
    h = ["<!DOCTYPE html>", '<html lang="it"><head><meta charset="utf-8">',
         f"<title>Referto {e(d['progetto'])}</title>",
         "<style>body{font-family:'DejaVu Sans',Arial,sans-serif;font-size:10pt;color:#222;max-width:60em;margin:auto}"
         "h1{color:#1f4e79}h2{color:#1f4e79;border-bottom:1px solid #1f4e79;margin-top:1.4em}h3{color:#333}"
         "table{border-collapse:collapse;margin:0.4em 0}td,th{border-color:#999}.piccolo{font-size:8.5pt;color:#555}"
         "</style></head><body>",
         f"<h1>Referto dell'analisi: {e(d['progetto'])}</h1>",
         f"<p>Corsa <b>{e(d['corsa'])}</b> &middot; motore profilemetananni {e(d['motore'])} &middot; "
         f"{len(d['campioni'])} campion{'e' if len(d['campioni']) == 1 else 'i'}</p>",
         riquadro("<b>Come leggere questo referto.</b> Le percentuali dicono quanto DNA di ogni microbo c'e' nel "
                  "campione, non quante cellule vive per grammo. MetaPhlAn e Kraken sono due metodi diversi: i loro "
                  "risultati stanno in tabelle separate e non vanno sommati. In fondo trovi i parametri usati, gli "
                  "strumenti con le versioni e come citarli.", "#e8f1fb")]
    # in breve
    h.append("<h2>1. In breve</h2>")
    esiti = {t["campione"]: t for t in d["triage"]}
    for c in d["campioni"]:
        h.append(f"<h3>Campione {e(c['nome'])}</h3><ul>")
        if c["coppie"]:
            h.append(f"<li>Coppie di read dei microbi (dopo aver tolto l'ospite): <b>{c['coppie']:,}</b></li>".replace(",", "."))
        if c["nome"] in esiti:
            t = esiti[c["nome"]]
            h.append(f"<li>Controllo iniziale (triage): <b>{e(t['esito'])}</b>"
                     + (f" ({e('; '.join(t['motivi']))})" if t["motivi"] else "") + "</li>")
        if c["metaphlan"]:
            top = ", ".join(f"<i>{e(n)}</i> {pct(v, 1)} %" for n, v in c["metaphlan"][:5])
            h.append(f"<li>MetaPhlAn, specie principali: {top}</li>")
        if c["kraken"]:
            micro = [r for r in c["kraken"] if r["categoria"] in MICROBI][:5]
            top = ", ".join(f"<i>{e(r['nome'])}</i> {pct(r['pct_microbi'], 1)} %" for r in micro)
            h.append(f"<li>Kraken, microbi principali (percentuale fra i soli microbi): {top}</li>")
        h.append("</ul>")
    # MetaPhlAn
    h.append("<h2>2. Specie trovate con MetaPhlAn</h2>")
    for c in d["campioni"]:
        if not c["metaphlan"]:
            continue
        somma = sum(v for _, v in c["metaphlan"]) or 1.0
        sopra = [(n, v) for n, v in c["metaphlan"] if v >= s]
        h.append(f"<h3>Campione {e(c['nome'])}</h3>")
        h.append(f'<p class="piccolo">Read non assegnate a specie note (UNCLASSIFIED): {pct(c["non_classificato"], 1)} %. '
                 f"Specie mostrate: {len(sopra)} su {len(c['metaphlan'])} (soglia {pct(s, 3)} %).</p>")
        h.append(tabella(["Specie", "% sul totale delle read", "% fra le specie trovate"],
                         [[f"<i>{e(n)}</i>", pct(v, 3), pct(100 * v / somma, 2)] for n, v in sopra], (1, 2), [50, 25, 25]))
    # Kraken
    h.append("<h2>3. Microbi trovati con Kraken + Bracken</h2>")
    h.append('<p class="piccolo">Solo batteri, archei e funghi. Le read di mammifero rimaste dopo la pulizia, che il '
             "database assegna a <i>Homo sapiens</i> o a <i>Leishmania</i> perche' non contiene il genoma del maiale, "
             "e i virus sono nella tabella successiva, a parte (D023).</p>")
    for c in d["campioni"]:
        if not c["kraken"]:
            continue
        micro = [r for r in c["kraken"] if r["categoria"] in MICROBI]
        sopra = [r for r in micro if r["pct"] >= s]
        h.append(f"<h3>Campione {e(c['nome'])}</h3>")
        h.append(f'<p class="piccolo">Microbi mostrati: {len(sopra)} su {len(micro)} (soglia {pct(s, 3)} %).</p>')
        h.append(tabella(["Specie", "Gruppo", "% fra i soli microbi", "% sul totale assegnato"],
                         [[f"<i>{e(r['nome'])}</i>", e(r["categoria"]), pct(r["pct_microbi"], 2), pct(r["pct"], 3)]
                          for r in sopra], (2, 3), [44, 16, 20, 20]))
        altri = [r for r in c["kraken"] if r["categoria"] not in MICROBI]
        if altri:
            h.append(f"<p><b>Segnalati a parte (non microbi, o non validati)</b>, campione {e(c['nome'])}:</p>")
            h.append(tabella(["Nome", "Gruppo", "% sul totale assegnato", "Letture stimate"],
                             [[f"<i>{e(r['nome'])}</i>", e(r["categoria"]), pct(r["pct"], 3), f"{r['letture']:,}".replace(",", ".")]
                              for r in altri], (2, 3), [46, 18, 18, 18]))
    # virus
    h.append("<h2>4. Virus</h2>")
    h.append(riquadro(e(POSTILLA_VIRUS) + ("<br>Richiesti nel progetto, ma non ancora calcolati da questa versione "
                                             "del motore." if d["virus"] else "<br>Non richiesti in questo progetto.")))
    # sicurezza
    n = 5
    if d["sicurezza"]:
        h.append(f"<h2>{n}. Sicurezza alimentare (previsioni di crescita)</h2>")
        h.append(riquadro("Previsioni da modelli di microbiologia previsionale (FSSP, DTU Food). Il profilo dice chi "
                          "c'e', non quanti per grammo: per la <i>Listeria</i> si calcolano scenari \"e se\" (1 e 100 "
                          "ufc/g). Una previsione non sostituisce le analisi di laboratorio."))
        for r in d["sicurezza"]:
            h.append(f"<h3>{e('Campione ' + r['campione'] if r.get('campione') else 'Prodotto')} "
                     f"(modalita' {e(r.get('modalita', ''))})</h3>")
            if r.get("richiesta"):
                h.append(f'<p class="piccolo">Dati del prodotto: {e(dati_prodotto(r["richiesta"]))}</p>')
            if r.get("profilo_usato"):
                h.append(f'<p class="piccolo">Profilo usato: {e(r["profilo_usato"])}</p>')
            h.append(tabella(["Scenario", "La Listeria puo' crescere?", "Giorni per aumentare di 100 volte",
                              "psi (1 o piu' = non cresce)"],
                             [[e(p["scenario"]), "si'" if p["listeria_puo_crescere"] else "no",
                               pct(p.get("cento_volte_listeria_giorni"), 1) or "non raggiunto",
                               pct(p.get("psi_listeria"), 2) if p.get("psi_listeria") is not None else "oltre un limite"]
                              for p in r["previsioni"]], (2, 3), [34, 18, 24, 24]))
            for a in r.get("avvisi", []):
                h.append(f'<p><b>Attenzione</b> ({e(MODELLI.get(a.get("modello"), "modello"))}): {e(a["messaggio"])}</p>')
            h.append("<ul>" + "".join(f"<li>{e(x)}</li>" for x in r.get("note", [])) + "</ul>")
        n += 1
    # parametri
    h.append(f"<h2>{n}. Parametri usati</h2>")
    h.append(tabella(["Parametro", "Valore", "Cosa vuol dire", "Fonte"],
                     [[e(a), e(b), e(c), f'<span class="piccolo">{e(f)}</span>'] for a, b, c, f in righe_parametri(d)],
                     larghezze=[20, 20, 30, 30]))
    n += 1
    # strumenti
    h.append(f"<h2>{n}. Strumenti e database usati</h2>")
    h.append(tabella(["Strumento o database", "Versione"],
                     [[e(VERSIONI.get(k, k)), e(v)] for k, v in d["versioni"].items() if v], larghezze=[45, 55]))
    citazioni = d["citazioni"] + [r["citazione"] for r in d["sicurezza"][:1]]
    h.append("<p><b>Come citarli:</b></p><ol>" + "".join(f"<li>{e(c)}</li>" for c in citazioni) + "</ol>")
    n += 1
    h.append(f"<h2>{n}. Parole usate</h2><ul>" + "".join(f"<li><b>{e(a)}</b>: {e(b)}</li>" for a, b in GLOSSARIO) + "</ul>")
    h.append("</body></html>")
    return "\n".join(h)


# ---------------- Excel ----------------
def cella(v):
    # niente formule nascoste nei testi (un nome che inizia con = + - @ resta testo)
    return "'" + v if isinstance(v, str) and v[:1] in ("=", "+", "-", "@") else v


def excel(d, percorso):
    from openpyxl import Workbook
    from openpyxl.styles import Font
    wb = Workbook()
    fogli = []

    def foglio(nome, intest, righe):
        ws = wb.create_sheet(nome)
        ws.append(intest)
        for c in ws[1]:
            c.font = Font(bold=True)
        for r in righe:
            ws.append([cella(v) for v in r])
        ws.freeze_panes = "A2"
        for i, h in enumerate(intest):
            ws.column_dimensions[ws.cell(1, i + 1).column_letter].width = max(12, min(60, len(h) + 4))
        fogli.append(nome)
    leggimi = wb.active
    leggimi.title = "Leggimi"
    for r in [[f"Referto dell'analisi: {d['progetto']}"], [f"Corsa {d['corsa']}, motore {d['motore']}"], [],
              ["MetaPhlAn e Kraken sono metodi diversi: stanno in fogli separati e non vanno sommati."],
              ["Le percentuali sono DNA relativo, non cellule vive per grammo."],
              [f"Soglia di abbondanza delle tabelle del referto: {d['soglia']} % (qui ci sono anche le specie sotto soglia)."],
              [POSTILLA_VIRUS]]:
        leggimi.append(r)
    leggimi.column_dimensions["A"].width = 110
    foglio("MetaPhlAn_specie", ["Campione", "Specie", "% sul totale delle read", "% fra le specie trovate", "Sopra soglia"],
           [[c["nome"], n, v, 100 * v / (sum(x for _, x in c["metaphlan"]) or 1), "si" if v >= d["soglia"] else "no"]
            for c in d["campioni"] if c["metaphlan"] for n, v in c["metaphlan"]])
    foglio("Kraken_microbi", ["Campione", "Specie", "Gruppo", "TaxID NCBI", "Letture stimate", "% sul totale assegnato",
                              "% fra i soli microbi", "Sopra soglia"],
           [[c["nome"], r["nome"], r["categoria"], r["taxid"], r["letture"], r["pct"], r["pct_microbi"],
             "si" if r["pct"] >= d["soglia"] else "no"]
            for c in d["campioni"] if c["kraken"] for r in c["kraken"] if r["categoria"] in MICROBI])
    foglio("Kraken_a_parte", ["Campione", "Nome", "Gruppo", "TaxID NCBI", "Letture stimate", "% sul totale assegnato"],
           [[c["nome"], r["nome"], r["categoria"], r["taxid"], r["letture"], r["pct"]]
            for c in d["campioni"] if c["kraken"] for r in c["kraken"] if r["categoria"] not in MICROBI])
    if d["triage"]:
        foglio("Triage", ["Campione", "Esito", "Motivi", "Punteggio"],
               [[t["campione"], t["esito"], "; ".join(t["motivi"]), t["punteggio"]] for t in d["triage"]])
    if d["sicurezza"]:
        foglio("Sicurezza", ["Campione", "Modalita'", "Scenario", "Modello", "Listeria puo' crescere", "psi Listeria",
                             "Giorni per 100 volte (Listeria)", "Giorni per 100 volte (LAB)"],
               [[r.get("campione") or "prodotto", r.get("modalita"), p["scenario"], p["modello"],
                 "si" if p["listeria_puo_crescere"] else "no", p.get("psi_listeria"), p.get("cento_volte_listeria_giorni"),
                 p.get("cento_volte_lab_giorni")] for r in d["sicurezza"] for p in r["previsioni"]])
    foglio("Parametri", ["Parametro", "Valore", "Cosa vuol dire", "Fonte"], righe_parametri(d))
    citazioni = d["citazioni"] + [r["citazione"] for r in d["sicurezza"][:1]]
    foglio("Strumenti_citazioni", ["Strumento o database", "Versione"],
           [[VERSIONI.get(k, k), v] for k, v in d["versioni"].items()] + [[]] +
           [["Citazione", c] for c in citazioni])
    wb.save(percorso)
    return fogli


# ---------------- PDF ----------------
def pdf(testo_html, percorso):
    """PDF dallo stesso HTML con QTextDocument (PySide6 di pmn_reports_py), senza schermo."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QMarginsF
    from PySide6.QtGui import QGuiApplication, QPageLayout, QPageSize, QPdfWriter, QTextDocument
    app = QGuiApplication.instance() or QGuiApplication(["referto"])  # noqa: F841 (serve vivo fino alla fine)
    w = QPdfWriter(str(percorso))
    w.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    w.setPageMargins(QMarginsF(15, 15, 15, 15), QPageLayout.Unit.Millimeter)
    w.setTitle("Referto profilemetananni")
    w.setCreator("profilemetananni")
    doc = QTextDocument()
    doc.setHtml(testo_html)
    doc.print_(w)
    del w
    dati = Path(percorso).read_bytes() if Path(percorso).is_file() else b""
    if dati[:4] != b"%PDF":
        raise RuntimeError("PDF non scritto")
    return len(re.findall(rb"/Type\s*/Page(?!s)", dati))


def main():
    ap = argparse.ArgumentParser(description="Referto HTML + Excel + PDF dei risultati di pmn-motore.")
    ap.add_argument("--risultati", required=True)
    ap.add_argument("--progetto")
    a = ap.parse_args()
    risultati = Path(a.risultati).resolve()
    if not (risultati / "risultati.json").is_file():
        print(json.dumps({"errore": f"manca {risultati / 'risultati.json'}"}, ensure_ascii=False))
        return 1
    cfg = {}
    if a.progetto and Path(a.progetto).is_file():
        try:
            import yaml
            cfg = yaml.safe_load(Path(a.progetto).read_text(encoding="utf-8")) or {}
        except Exception:
            cfg = {}
        cfg = cfg if isinstance(cfg, dict) else {}
    d = raccogli(risultati, cfg)
    cartella = risultati / "referto"
    cartella.mkdir(exist_ok=True)
    testo = html_referto(d)
    uscita = {"html": str(cartella / "referto.html"), "xlsx": None, "pdf": None, "problemi": []}
    (cartella / "referto.html").write_text(testo, encoding="utf-8")
    try:
        excel(d, cartella / "referto.xlsx")
        uscita["xlsx"] = str(cartella / "referto.xlsx")
    except Exception as ex:   # manca openpyxl o il file non si scrive: il resto del referto c'e' lo stesso
        uscita["problemi"].append(f"Excel non creato: {type(ex).__name__}: {ex}")
    try:
        uscita["pagine_pdf"] = pdf(testo, cartella / "referto.pdf")
        uscita["pdf"] = str(cartella / "referto.pdf")
    except Exception as ex:
        uscita["problemi"].append(f"PDF non creato: {type(ex).__name__}: {ex}")
    print(json.dumps(uscita, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
