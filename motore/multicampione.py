"""Analisi multicampione (R11, PMN 1.1): diversità alfa e beta fra i campioni di un progetto, con i test scelti dal
disegno scritto dall'utente in metadati.tsv. Uscite in risultati/multicampione/<profiler>/ (docs/metadati.md).

Divisione del lavoro: qui (Python, libreria standard) i metadati, i controlli, il disegno e la scelta dei test, i
testi per il referto; i calcoli statistici e i grafici sono in motore/multicampione.R (ambiente pmn_stats_r: vegan
per PERMANOVA e PERMDISP, permute per le permutazioni ristrette, ggplot2 per i grafici). Si chiama da
motore/referto.py, quindi gira anche con `pmn-motore referto` dopo che l'utente ha compilato metadati.tsv.

Regole fisse: MetaPhlAn e Kraken SEMPRE separati (due cartelle, due tabelle, due serie di grafici, mai una matrice
unica); Kraken solo con i taxa del prodotto sopra la soglia D128, MetaPhlAn senza soglia; un fattore alla volta.
"""
import csv
import json
import os
import shutil
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "motore"))
from lingua import N_, _  # noqa: E402

SEME = 1992            # lo stesso seme del sottocampione di MetaPhlAn (motore/diversita.py)
PERMUTAZIONI = 999
MINIMO = 3             # unità per gruppo sotto cui non si fa nessun test (solo descrittive)
METADATI = "metadati.tsv"
COLONNE = ("sample_id", "group", "subject", "timepoint")
MODELLO = COLONNE + ("covariate",)   # una covariata libera: si riporta, non entra nei test
FATTORI = ("group", "timepoint")
MICROBI = ("batteri", "archei", "funghi")
NOMI = {"metaphlan": "MetaPhlAn", "kraken": "Kraken + Bracken"}
TEST = {"mann_whitney": N_("Mann-Whitney"), "kruskal_dunn": N_("Kruskal-Wallis, poi Dunn a coppie (correzione BH)"),
        "wilcoxon_paired": N_("Wilcoxon per dati appaiati"),
        "friedman": N_("Friedman, poi Wilcoxon appaiato a coppie (correzione BH)"), "none": N_("nessun test")}
EFFETTO = {"r": N_("r di rango (|Z|/radice di n)"), "epsilon2": N_("epsilon quadro (H/(n-1))"),
           "kendall_w": N_("W di Kendall"), "R2": "R²"}
PERMUTA = {"free": N_("libere"), "blocks": N_("ristrette dentro ogni soggetto (misure ripetute)"),
           "subject_mean": N_("dei soggetti (profilo medio di ogni soggetto)")}   # dopo "999 permutazioni"
CITAZIONI = [
    "Anderson MJ (2001) A new method for non-parametric multivariate analysis of variance. Austral Ecology 26:32-46. "
    "doi:10.1111/j.1442-9993.2001.01070.pp.x",
    "Anderson MJ (2006) Distance-based tests for homogeneity of multivariate dispersions. Biometrics 62:245-253. "
    "doi:10.1111/j.1541-0420.2005.00440.x",
    "Anderson MJ, Walsh DCI (2013) PERMANOVA, ANOSIM, and the Mantel test in the face of heterogeneous dispersions. "
    "Ecological Monographs 83:557-574. doi:10.1890/12-2010.1",
    "Martín-Fernández JA, Barceló-Vidal C, Pawlowsky-Glahn V (2003) Dealing with zeros and missing values in "
    "compositional data sets using nonparametric imputation. Mathematical Geology 35:253-278. doi:10.1023/A:1023866030544",
    "Gloor GB et al. (2017) Microbiome datasets are compositional: and this is not optional. Front Microbiol 8:2224. "
    "doi:10.3389/fmicb.2017.02224",
    "Fritz CO, Morris PE, Richler JJ (2012) Effect size estimates: current use, calculations, and interpretation. "
    "J Exp Psychol Gen 141:2-18. doi:10.1037/a0024338",
    "Oksanen J et al. vegan: Community Ecology Package (R package; version in parametri.tsv)",
]


# ---------------- metadati ----------------
def crea_modello(cartella, campioni):
    """metadati.tsv vuoto (solo sample_id compilato) nella cartella del progetto, se manca e ci sono almeno 2
    campioni. Non sovrascrive mai il file dell'utente. True se l'ha scritto."""
    f = Path(cartella) / METADATI
    if len(campioni) < 2 or f.exists():
        return False
    righe = ["\t".join(MODELLO)] + [s + "\t" * (len(MODELLO) - 1) for s in sorted(campioni)]
    f.write_text("\n".join(righe) + "\n", encoding="utf-8")
    return True


def _testo(f):
    """Il testo del file: UTF-8 (anche con BOM, come lo salva Excel), altrimenti Windows-1252."""
    dati = Path(f).read_bytes()
    try:
        return dati.decode("utf-8-sig")
    except UnicodeDecodeError:
        return dati.decode("cp1252")


def leggi_metadati(f, campioni):
    """({campione: {colonna: valore}} o None, [problemi in parole], [covariate libere]).
    None se il file manca o non si può usare (manca sample_id, separatore sbagliato): allora niente test."""
    f = Path(f)
    if not f.is_file():
        return None, [], []
    righe = [r for r in _testo(f).replace("\r\n", "\n").replace("\r", "\n").split("\n")
             if r.strip() and not r.lstrip().startswith("#")]
    if not righe:
        return None, [_("il file {file} è vuoto", file=METADATI)], []
    testa = [c.strip() for c in righe[0].split("\t")]
    if "sample_id" not in testa:
        if len(testa) == 1 and (";" in testa[0] or "," in testa[0]):
            return None, [_("{file} deve avere le colonne separate da tabulazioni (salvalo come \"Testo delimitato "
                            "da tabulazione\"), non da punto e virgola o virgola", file=METADATI)], []
        return None, [_("in {file} manca la colonna obbligatoria sample_id", file=METADATI)], []
    meta, problemi, doppi = {}, [], []
    for r in righe[1:]:
        celle = [c.strip() for c in r.split("\t")] + [""] * len(testa)
        riga = dict(zip(testa, celle))
        s = riga["sample_id"]
        if not s:
            continue
        if s in meta:
            doppi.append(s)
            continue
        meta[s] = {k: v for k, v in riga.items() if k and k != "sample_id"}
    nomi = set(campioni)
    mancanti = sorted(nomi - set(meta))
    in_piu = sorted(set(meta) - nomi)
    if doppi:
        problemi.append(_("Lo stesso campione compare in più righe: {nomi}. Si usa solo la prima: tieni una riga per "
                          "campione.", nomi=", ".join(sorted(set(doppi)))))
    if mancanti:
        problemi.append(_("Mancano i dati di questi campioni, che restano fuori dai test: {nomi}. Aggiungi una riga "
                          "per ognuno.", nomi=", ".join(mancanti)))
    if in_piu:
        problemi.append(_("Queste righe non corrispondono a nessun campione del progetto e non si usano: {nomi}. "
                          "Controlla che il nome sia scritto come nel progetto.", nomi=", ".join(in_piu)))
    covariate = [c for c in testa if c and c not in COLONNE]
    return meta, problemi + controlla_fattori(meta, campioni), covariate


NOMI_FATTORI = {"group": N_("gruppo"), "timepoint": N_("tempo")}


def controlla_fattori(meta, campioni):
    """Valori vuoti e gruppi troppo piccoli, detti con che cosa fare (R18: chi usa il programma non ha un agente)."""
    problemi = []
    presenti = [s for s in campioni if s in meta]
    for fattore in FATTORI:
        valori = {s: meta[s].get(fattore, "") for s in presenti}
        if not any(valori.values()):
            continue
        cosa = _(NOMI_FATTORI[fattore])
        vuoti = sorted(s for s, v in valori.items() if not v)
        if vuoti:
            problemi.append(_("Questi campioni non hanno il {cosa} e restano fuori dal confronto per {cosa}: {nomi}. "
                              "Scrivi il loro {cosa}, oppure lascialo vuoto per tutti.", cosa=cosa,
                              nomi=", ".join(vuoti)))
        conta = Counter(v for v in valori.values() if v)
        if len(conta) == 1:
            problemi.append(_("Tutti i campioni hanno lo stesso {cosa} ({valore}): per un confronto servono almeno 2 "
                              "valori diversi.", cosa=cosa, valore=next(iter(conta))))
        piccoli = sorted(v for v, n in conta.items() if n < MINIMO)
        if piccoli and len(conta) > 1:
            problemi.append(_("Per un test servono almeno {m} campioni per ogni {cosa}; ne hanno meno: {valori}. "
                              "Aggiungi campioni oppure unisci questi valori a un altro {cosa}: intanto si mostrano "
                              "solo grafici e valori.", m=MINIMO, cosa=cosa,
                              valori=", ".join(f"{v} ({conta[v]})" for v in piccoli)))
    return problemi


# ---------------- disegno e scelta dei test ----------------
def piano(meta, campioni):
    """[confronti] per i campioni di un profiler, un fattore alla volta (group, poi timepoint).
    Ogni confronto: {"id", "fattore", "disegno", "test_alfa", "permutazioni", "livelli", "unita", "righe": [
    {"sample", "level", "unit", "alpha", "beta"}], "motivo", "solo_descrittive"}.
    Disegni: independent (nessun soggetto ripetuto), between_subjects (soggetti con più campioni, sempre nello stesso
    gruppo: si usa la media del soggetto), paired (2 livelli dentro gli stessi soggetti), repeated (più di 2)."""
    if not meta:
        return []
    out = []
    for fattore in FATTORI:
        liv = {s: meta[s][fattore] for s in campioni if s in meta and meta[s].get(fattore)}
        livelli = sorted(set(liv.values()))
        if len(livelli) < 2:
            continue
        unita = {s: meta[s].get("subject") or f"sample:{s}" for s in liv}   # senza soggetto: il campione è l'unità
        per_unita, conta = defaultdict(set), Counter()
        for s, v in liv.items():
            per_unita[unita[s]].add(v)
            conta[unita[s]] += 1
        ripetuti = any(n > 1 for n in conta.values())
        dentro = any(len(v) > 1 for v in per_unita.values())
        disegno = ("independent" if not ripetuti else "between_subjects" if not dentro
                   else "paired" if len(livelli) == 2 else "repeated")
        if disegno in ("independent", "between_subjects"):
            alfa = set(liv)
            n_alfa = {lv: len({unita[s] for s in liv if liv[s] == lv}) for lv in livelli}
            test = "mann_whitney" if len(livelli) == 2 else "kruskal_dunn"
            permutazioni = "free" if disegno == "independent" else "subject_mean"
            n_beta = n_alfa
        else:
            completi = {u for u, v in per_unita.items() if v == set(livelli) and conta[u] == len(livelli)}
            alfa = {s for s in liv if unita[s] in completi}
            n_alfa = {lv: len(completi) for lv in livelli}
            test = "wilcoxon_paired" if disegno == "paired" else "friedman"
            permutazioni = "blocks"
            n_beta = {lv: sum(1 for s in liv if liv[s] == lv) for lv in livelli}
        pochi_alfa = sorted(lv for lv in livelli if n_alfa[lv] < MINIMO)
        pochi_beta = sorted(lv for lv in livelli if n_beta[lv] < MINIMO)
        motivo = [_motivo(disegno, len(livelli), test, len({unita[s] for s in alfa}))]
        if pochi_alfa:
            test = "none"
            motivo.append(_("Diversità alfa: nessun test, perché servono almeno {m} unità indipendenti per gruppo "
                            "(qui meno di {m} in: {gruppi}); con così pochi dati un valore p non è affidabile, si "
                            "mostrano solo i valori.", m=MINIMO, gruppi=", ".join(pochi_alfa))
                          if disegno in ("independent", "between_subjects") else
                          _("Diversità alfa: nessun test, perché servono almeno {m} soggetti con tutte le condizioni "
                            "(qui {n}); si mostrano solo i valori.", m=MINIMO, n=len({unita[s] for s in alfa})))
        if pochi_beta:
            permutazioni = "none"
            motivo.append(_("Diversità beta: nessuna PERMANOVA, perché servono almeno {m} unità per gruppo (qui meno "
                            "di {m} in: {gruppi}); si mostra solo il grafico.", m=MINIMO, gruppi=", ".join(pochi_beta)))
        righe = [{"sample": s, "level": liv[s], "unit": unita[s], "alpha": int(s in alfa), "beta": 1}
                 for s in sorted(liv)]
        out.append({"id": fattore, "fattore": fattore, "disegno": disegno, "test_alfa": test,
                    "permutazioni": permutazioni, "livelli": livelli, "righe": righe, "motivo": " ".join(motivo),
                    "solo_descrittive": test == "none" and permutazioni == "none"})
    return out


def _motivo(disegno, k, test, n_unita):
    """Perché questo test (frase per parametri.tsv e per il referto)."""
    if disegno == "independent":
        return (_("{k} gruppi di campioni indipendenti: test di Mann-Whitney; PERMANOVA con permutazioni libere.", k=k)
                if test == "mann_whitney" else
                _("{k} gruppi di campioni indipendenti: test di Kruskal-Wallis, poi confronti a coppie di Dunn con la "
                  "correzione di Benjamini-Hochberg; PERMANOVA con permutazioni libere.", k=k))
    if disegno == "between_subjects":
        return _("Più campioni dello stesso soggetto, sempre nello stesso gruppo: l'unità indipendente è il soggetto "
                 "({n} soggetti), quindi alfa e beta usano la media di ogni soggetto; poi {test} e PERMANOVA con "
                 "permutazioni dei soggetti.", n=n_unita, test=_(TEST[test]))
    if disegno == "paired":
        return _("2 condizioni misurate sugli stessi soggetti: test di Wilcoxon per dati appaiati sui {n} soggetti che "
                 "le hanno entrambe; PERMANOVA con permutazioni ristrette dentro ogni soggetto.", n=n_unita)
    return _("{k} condizioni misurate sugli stessi soggetti: test di Friedman sui {n} soggetti con dati completi (il "
             "test non ammette dati mancanti), poi Wilcoxon appaiato a coppie con la correzione di Benjamini-Hochberg; "
             "PERMANOVA con permutazioni ristrette dentro ogni soggetto.", k=k, n=n_unita)


# ---------------- matrici (MetaPhlAn e Kraken separati) ----------------
def matrice(campioni, profiler, soglia):
    """{campione: {taxon: abbondanza relativa 0-1}} di UN profiler. MetaPhlAn: tutte le specie (nessuna soglia),
    chiuse a 1. Kraken: solo batteri, archei e funghi con pct >= soglia (D128), letture di Bracken chiuse a 1."""
    out = {}
    for c in campioni:
        if profiler == "metaphlan" and c.get("metaphlan"):
            v = {n: p for n, p in c["metaphlan"] if p > 0}
        elif profiler == "kraken" and c.get("kraken"):
            v = {r["nome"]: r["letture"] for r in c["kraken"] if r["categoria"] in MICROBI and r["pct"] >= soglia
                 and r["letture"] > 0}
        else:
            continue
        tot = sum(v.values())
        if tot > 0:
            out[c["nome"]] = {n: x / tot for n, x in v.items()}
    return out


def _tsv(f, testa, righe):
    with open(f, "w", encoding="utf-8", newline="") as t:
        w = csv.writer(t, delimiter="\t", lineterminator="\n")
        w.writerow(testa)
        w.writerows(righe)


def scrivi_ingressi(cartella, mat, alfa, meta, confronti, profiler, soglia):
    """I file che legge multicampione.R (e che restano come tabelle per l'utente)."""
    campioni = sorted(mat)
    taxa = sorted({t for v in mat.values() for t in v})
    _tsv(cartella / "abundance_relative.tsv", ["taxon"] + campioni,
         [[t] + [f"{mat[s].get(t, 0.0):.10g}" for s in campioni] for t in taxa])
    _tsv(cartella / "alpha_diversity.tsv", ["sample", "reads", "reads_used", "status", "richness", "shannon", "simpson"],
         [[r["campione"], r["letture"], r["letture_usate"],
           {"intero": "full", "pareggiato": "equalized"}.get(r["stato"], "not_equalized"),
           f"{r['ricchezza']:.6g}", f"{r['shannon']:.6g}", f"{r['simpson']:.6g}"] for r in alfa if r["campione"] in mat])
    _tsv(cartella / "metadata_used.tsv", list(COLONNE),
         [[s] + [(meta or {}).get(s, {}).get(c, "") for c in COLONNE[1:]] for s in campioni])
    _tsv(cartella / "comparisons.tsv", ["comparison", "factor", "design", "alpha_test", "permutations"],
         [[c["id"], c["fattore"], c["disegno"], c["test_alfa"], c["permutazioni"]] for c in confronti])
    _tsv(cartella / "design.tsv", ["comparison", "sample", "level", "unit", "alpha", "beta"],
         [[c["id"], r["sample"], r["level"], r["unit"], r["alpha"], r["beta"]] for c in confronti for r in c["righe"]])
    par = [["profiler", NOMI[profiler], "prototype, not for decisions (D115)" if profiler == "kraken" else ""],
           ["samples", len(campioni), ""],
           ["abundance_threshold_pct", f"{soglia:g}" if profiler == "kraken" else "none",
            "Kraken: product taxa (bacteria, archaea, fungi) at or above the threshold (D128); MetaPhlAn: never filtered"],
           ["relative_abundance", "closed to 1 per sample", "MetaPhlAn: species %; Kraken: Bracken reads"],
           ["alpha_diversity", "equal depth (rarefaction)", "motore/diversita.py, as in the report"],
           ["distance_1", "Aitchison", "Euclidean distance on CLR; zeros replaced (multiplicative replacement)"],
           ["distance_2", "Bray-Curtis", "on relative abundances"], ["ordination", "PCoA", ""],
           ["permutations", PERMUTAZIONI, "PERMANOVA (adonis2) and PERMDISP (betadisper), same permutation set"],
           ["seed", SEME, ""], ["min_units_per_group", MINIMO, "below this: descriptive only, no test"],
           ["metadata", METADATI if meta else "none", ""]]
    for c in confronti:
        par.append([f"comparison_{c['id']}", f"{c['disegno']}; alpha: {c['test_alfa']}; beta: {c['permutazioni']}",
                    c["motivo"]])
    _tsv(cartella / "parametri.tsv", ["parameter", "value", "note"], par)


# ---------------- R ----------------
def rscript():
    """Rscript dell'ambiente pmn_stats_r: PMN_RSCRIPT, poi l'ambiente accanto a quello di questo Python
    (<envs>/pmn_reports_py/bin/python -> <envs>/pmn_stats_r/bin/Rscript), poi quello nel PATH."""
    for c in (os.environ.get("PMN_RSCRIPT"), Path(sys.executable).parent.parent.parent / "pmn_stats_r" / "bin" / "Rscript",
              shutil.which("Rscript")):
        if c and Path(c).is_file():
            return str(c)
    return None


def _leggi(f):
    if not Path(f).is_file():
        return []
    with open(f, encoding="utf-8", newline="") as t:
        return list(csv.DictReader(t, delimiter="\t"))


# ---------------- tutto il giro ----------------
def esegui(risultati, d):
    """Analisi multicampione del progetto: scrive risultati/multicampione/ e restituisce il riepilogo per il referto
    (lo stesso di riepilogo.json). Con meno di 2 campioni: {"attiva": False}, nessun file."""
    risultati = Path(risultati)
    base = risultati / "multicampione"
    nomi = [c["nome"] for c in d["campioni"]]
    if len(nomi) < 2:
        return {"attiva": False}
    progetto = risultati.parent
    modello = crea_modello(progetto, nomi)
    meta, problemi, covariate = leggi_metadati(progetto / METADATI, nomi)
    if base.exists():
        shutil.rmtree(base)   # solo la cartella che scrive questo programma: niente uscite di una corsa vecchia
    base.mkdir(parents=True)
    r = rscript()
    rie = {"attiva": True, "metadati": {"file": METADATI, "creato_ora": modello, "usati": meta is not None and
                                        any(any(v.get(f) for f in FATTORI) for v in meta.values()),
                                        "problemi": problemi, "covariate": covariate},
           "profiler": {}, "citazioni": CITAZIONI}
    alfa = d.get("diversita", {})
    for profiler in ("metaphlan", "kraken"):
        mat = matrice(d["campioni"], profiler, d.get("soglia", 0.0))
        if len(mat) < 2:
            continue
        cartella = base / profiler
        cartella.mkdir()
        confronti = piano(meta, sorted(mat))
        scrivi_ingressi(cartella, mat, alfa.get(profiler, []), meta, confronti, profiler, d.get("soglia", 0.0))
        p = {"campioni": len(mat), "esclusi": sorted(set(nomi) - set(mat)), "confronti": confronti, "errore": None}
        if r is None:
            p["errore"] = _("Manca R (ambiente pmn_stats_r), quindi niente test né grafici. Apri la pagina Motore e "
                            "premi Controlla il motore.")
        else:
            esito = subprocess.run([r, str(ROOT / "motore" / "multicampione.R"), "--dir", str(cartella), "--seed",
                                    str(SEME), "--permutations", str(PERMUTAZIONI), "--profiler", profiler],
                                   capture_output=True, text=True, encoding="utf-8", errors="replace")
            (cartella / "R_log.txt").write_text(esito.stdout + esito.stderr, encoding="utf-8")
            if esito.returncode != 0:
                p["errore"] = _("Il calcolo statistico non è riuscito. Manda a noi il file {f}.",
                                f=f"risultati/multicampione/{profiler}/R_log.txt")
        p["alfa"] = _leggi(cartella / "alpha_tests.tsv")
        p["coppie"] = _leggi(cartella / "alpha_posthoc.tsv")
        p["beta"] = _leggi(cartella / "beta_tests.tsv")
        p["grafici"] = sorted(f.name for f in cartella.glob("*.png"))
        for c in confronti:
            del c["righe"]   # già in design.tsv: il riepilogo resta piccolo
        rie["profiler"][profiler] = p
    (base / "riepilogo.json").write_text(json.dumps(rie, ensure_ascii=False, indent=1), encoding="utf-8")
    return rie
