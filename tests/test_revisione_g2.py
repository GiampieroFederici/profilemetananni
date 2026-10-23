# -*- coding: utf-8 -*-
"""Revisione del 22/10, secondo giro (difetti dei revisori sulle correzioni del primo giro).
Ogni test è rosso sul codice di 7381eda e verde dopo la correzione.
Gira con la suite del motore:  ~/miniforge3/envs/pmn_reports_py/bin/python -m pytest tests/test_revisione_g2.py"""
import gzip
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

RADICE = Path(__file__).resolve().parent.parent
linux = pytest.mark.skipif(os.name == "nt" or not shutil.which("bash"), reason="bin/run.sh: Linux/WSL only")


# ---------------- P01 (D3 di GD1): cartella nonhost personalizzata condivisa da due progetti ----------------
def installazione_finta(tmp_path):
    """Motore installato finto: python vero per parse_config.py, indici degli ospiti già pronti (niente download),
    fastp che fallisce (la corsa si ferma al primo campione da rifilare, nessun programma di analisi parte)."""
    envs, home, ospite = tmp_path / "envs", tmp_path / "pmn", tmp_path / "ospite"
    (envs / "pmn_reports_py" / "bin").mkdir(parents=True)
    os.symlink(sys.executable, envs / "pmn_reports_py" / "bin" / "python")
    (envs / "pmn_trim" / "bin").mkdir(parents=True)
    (envs / "pmn_trim" / "bin" / "fastp").write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
    (envs / "pmn_trim" / "bin" / "fastp").chmod(0o755)
    for h in ("sus_scrofa", "bos_taurus"):
        (ospite / h).mkdir(parents=True)
        (ospite / h / f"{h}.1.bt2").write_text("indice finto", encoding="utf-8")
    home.mkdir()
    (home / "installazione.env").write_text(f"PMN_ENVS={envs}\nPMN_TMP={tmp_path / 'tmp'}\nPMN_OSPITE={ospite}\n",
                                            encoding="utf-8")
    return home


def progetto_custom(tmp_path, nome, campioni, condivisa):
    """Progetto con layout custom: read locali proprie, nonhost nella cartella condivisa."""
    letture = tmp_path / f"{nome}_read"
    letture.mkdir()
    for s in campioni:
        for m in (1, 2):
            with gzip.open(letture / f"{s}_{m}.fastq.gz", "wt") as g:
                g.write(f"@{s}\nACGT\n+\nIIII\n")
    cfg = tmp_path / nome / "config.yaml"
    cfg.parent.mkdir()
    return cfg, letture


def corsa_custom(home, cfg, letture, condivisa, hosts):
    cfg.write_text(f"project_name: {cfg.parent.name}\ndata_source: local\nhosts: {hosts}\nfilter_human: false\n"
                   f"paths:\n  layout: custom\n  work_dir: {cfg.parent / 'lavoro'}\n  local_reads_dir: {letture}\n"
                   f"  nonhost_dir: {condivisa}\nprofiling:\n  tool: metaphlan\n", encoding="utf-8")
    r = subprocess.run(["bash", str(RADICE / "bin" / "run.sh"), "--config", str(cfg), "--skip-preflight"],
                       capture_output=True, text=True, timeout=120, cwd=cfg.parent,
                       env={**os.environ, "PMN_HOME": str(home), "NO_COLOR": "1"})
    testo = r.stdout + r.stderr
    assert r.returncode != 0 and "step failed: trim_" in testo, testo
    return testo


def nonhost_finiti(condivisa, campione, contenuto):
    for m in (1, 2):
        (condivisa / f"{campione}_nonhost_{m}.fastq.gz").write_bytes(contenuto + bytes([m]))


def byte(condivisa, campione):
    return {f.name: f.read_bytes() for f in sorted(condivisa.glob(f"{campione}_nonhost*"))}


@linux
def test_p01_nonhost_condivisa_la_ripresa_non_tocca_i_file_dell_altro_progetto(tmp_path):
    """Due progetti (maiale e bovino) con la stessa cartella nonhost personalizzata: la ripresa di uno, anche coi
    parametri dell'ospite cambiati, cancella solo le uscite dei propri campioni; quelle dell'altro restano identiche."""
    home = installazione_finta(tmp_path)
    condivisa = tmp_path / "nonhost_condivisa"
    condivisa.mkdir()
    a = progetto_custom(tmp_path, "salame", ["A1", "A2"], condivisa)
    b = progetto_custom(tmp_path, "bresaola", ["B1", "B2"], condivisa)
    corsa_custom(home, *a, condivisa, "[sus_scrofa]")      # prime corse: ognuno registra i suoi parametri
    corsa_custom(home, *b, condivisa, "[bos_taurus]")
    nonhost_finiti(condivisa, "A1", b"maiale")              # rimozione dell'ospite finita su A1 e B1
    nonhost_finiti(condivisa, "B1", b"bovino")
    prima_a, prima_b = byte(condivisa, "A1"), byte(condivisa, "B1")
    assert len(prima_a) == len(prima_b) == 2

    corsa_custom(home, *a, condivisa, "[sus_scrofa]")      # ripresa del salame, stessi parametri: nulla si tocca
    assert byte(condivisa, "B1") == prima_b
    assert byte(condivisa, "A1") == prima_a

    testo = corsa_custom(home, *b, condivisa, "[bos_taurus, sus_scrofa]")   # bresaola con altri ospiti
    assert byte(condivisa, "B1") == {}, testo              # si rifanno le sue uscite...
    assert byte(condivisa, "A1") == prima_a                # ...non quelle del salame
    corsa_custom(home, *a, condivisa, "[sus_scrofa]")
    assert byte(condivisa, "A1") == prima_a
    assert not (condivisa / ".parametri").exists()         # il timbro sta nella cartella di lavoro del progetto


# ---------------- P01 (D2 di GD1): barra e tempo restante dopo un cambio di parametri ----------------
def test_p01_gia_fatti_non_conta_le_uscite_che_run_sh_rifa(tmp_path, monkeypatch):
    """Kraken completo già fatto con l'ospite maiale (80 % delle coppie), poi rilancio con l'ospite bovino: run.sh,
    prima del primo passo, cancella profili e log dell'ospite fatti coi parametri vecchi (timbri .parametri) e li
    rifà. Barra e tempo restante non devono dare per fatto Kraken né usare la quota dell'ospite vecchio."""
    from types import SimpleNamespace
    sys.path.insert(0, str(RADICE / "motore"))
    import pmn_motore as pm
    prog = tmp_path / "p"
    lavoro = prog / "w"
    vecchi = [lavoro / "kraken" / "S1.bracken", lavoro / "hostfilter_logs" / "S1.sus_scrofa.bowtie2.log"]
    for f in vecchi:
        f.parent.mkdir(parents=True)
    vecchi[0].write_text("Kraken completo, ospite maiale\n", encoding="utf-8")
    vecchi[1].write_text("1000000 reads; of these:\n  1000000 (100.00%) were paired; of these:\n"
                         "    200000 (20.00%) aligned concordantly 0 times\n", encoding="utf-8")
    (prog / "campioni.txt").write_text("S1\n", encoding="utf-8")
    cfg = {"data_source": "ncbi", "hosts": ["bos_taurus"], "profiling": {"tool": "kraken"},
           "motore": {"kraken_db": "completo"}, "paths": {"work_dir": "./w", "srr_list": str(prog / "campioni.txt")}}

    class RunShFinto:   # come bin/run.sh: il blocco dei timbri gira prima di qualsiasi passo
        pid = 0

        def __init__(self, *a, **k):
            self.stdout = self.righe()

        @staticmethod
        def righe():
            for f in vecchi:
                f.unlink()
            yield "[WARN] Parametri della rimozione dell'ospite cambiati: rifaccio ospite, MetaPhlAn e Kraken\n"
            for e in ("size", "trim_S1", "hf_S1", "multiqc", "krk_S1", "kmatrix"):
                yield f"[INFO] [locale] {e}\n"

        def wait(self):
            return 0
    monkeypatch.setattr(pm.subprocess, "Popen", RunShFinto)
    monkeypatch.setattr(pm, "STATO", tmp_path / "stato")
    (tmp_path / "stato").mkdir()
    m = pm.Motore(SimpleNamespace(comando="esegui", progetto=str(prog / "config.yaml")))
    m.log = tmp_path / "x.log"
    av = []
    monkeypatch.setattr(m, "avanza", lambda passo, *a, **k: av.append({"passo": passo, **k}))
    camp = [("S1", 3_000_000, 0)]
    m._run_sh(prog / "config.yaml", cfg, tmp_path / "stato" / "esegui.lock", camp)
    sec = {e: s for e, _, _, s in pm.piano(camp, cfg)}            # quota dell'ospite ancora da misurare
    assert abs(av[0]["eta_s"] - sum(sec.values())) <= 1            # niente è fatto
    kraken = next(e for e in av if e["passo"] == "kraken")
    assert kraken["passo_s"] == round(sec["krk_S1"])               # Kraken si rifà intero


# ---------------- P04 (D1 e D4 di GD1): risultati/ solo coi campioni e i metodi di questa corsa ----------------
FASTP = {"summary": {"before_filtering": {"total_reads": 400, "q30_rate": 0.9, "read1_mean_length": 150,
                                          "read2_mean_length": 150},
                     "after_filtering": {"total_reads": 380, "q30_rate": 0.95, "read1_mean_length": 146,
                                         "read2_mean_length": 144}},
         "duplication": {"rate": 0.07}}


def risultati_finti(tmp_path, monkeypatch, strumento="both", progetto=("SRRA",), lavoro=("SRRA", "SRRA2")):
    """Motore._risultati vero su un pmn_work finto (profili di installer/finto, fastp e FastQC per campione); finti solo
    installazione, versioni e referto. SRRA2 è un campione tolto dal progetto, rimasto in pmn_work."""
    import json
    from types import SimpleNamespace
    sys.path.insert(0, str(RADICE / "motore"))
    import pmn_motore as pm
    monkeypatch.setattr(pm, "installazione", lambda: {})
    monkeypatch.setattr(pm, "versione", lambda *a: None)
    finto = RADICE / "installer" / "finto"
    prog, w = tmp_path / "p", tmp_path / "p" / "w"
    for d in ("metaphlan", "kraken", "results", "trim"):
        (w / d).mkdir(parents=True)
    for nome in lavoro:
        shutil.copy(finto / "SRR4875279_profile.txt", w / "metaphlan" / f"{nome}_profile.txt")
        shutil.copy(finto / "SRR4875279.bracken", w / "kraken" / f"{nome}.bracken")
        shutil.copy(finto / "SRR4875279.k2report", w / "kraken" / f"{nome}.k2report")
        (w / "trim" / f"{nome}_fastp.json").write_text(json.dumps(FASTP), encoding="utf-8")
        for f in (f"{nome}_fastp.html", f"{nome}_1_fastqc.html", f"{nome}_trim_1_fastqc.html"):
            (w / "trim" / f).write_text("report", encoding="utf-8")
    shutil.copy(finto / "parameters.tsv", w / "results" / "parameters.tsv")
    (prog / "campioni.txt").write_text("".join(f"{n}\n" for n in progetto), encoding="utf-8")
    cfg = {"data_source": "ncbi", "paths": {"layout": "managed", "work_dir": "./w", "srr_list": str(prog / "campioni.txt")},
           "profiling": {"tool": strumento}}
    (prog / "config.yaml").write_text(json.dumps(cfg), encoding="utf-8")
    m = pm.Motore(SimpleNamespace(comando="esegui", progetto=str(prog / "config.yaml")))
    m._referto = lambda r, p: {"html": None, "pdf": None, "xlsx": None}
    m.log = tmp_path / "x.log"
    m.log.write_text("", encoding="utf-8")
    return m, prog, cfg


def test_p04_qc_solo_campioni_del_progetto(tmp_path, monkeypatch):
    """Il campione tolto (SRRA2, ancora in pmn_work/trim) non va nella tabella QC di risultati.json (e quindi del
    referto) né in risultati/qc; i suoi report copiati da una corsa vecchia se ne vanno."""
    import json
    m, prog, cfg = risultati_finti(tmp_path, monkeypatch)
    r = prog / "risultati"
    (r / "qc" / "fastqc").mkdir(parents=True)
    (r / "qc" / "SRRA2_fastp.html").write_text("corsa vecchia", encoding="utf-8")
    (r / "qc" / "fastqc" / "SRRA2_1_fastqc.html").write_text("corsa vecchia", encoding="utf-8")
    out = m._risultati(prog / "config.yaml", cfg)
    assert [c["nome"] for c in out["qc"]["campioni"]] == ["SRRA"]
    assert out["qc"]["fastp"] == ["qc/SRRA_fastp.html"]
    assert out["qc"]["fastqc"] == ["qc/fastqc/SRRA_1_fastqc.html", "qc/fastqc/SRRA_trim_1_fastqc.html"]
    assert sorted(f.name for f in (r / "qc").rglob("*.html")) == ["SRRA_1_fastqc.html", "SRRA_fastp.html",
                                                                  "SRRA_trim_1_fastqc.html"]
    indice = json.loads((r / "risultati.json").read_text(encoding="utf-8"))
    assert [c["nome"] for c in indice["qc"]["campioni"]] == ["SRRA"]


def test_p04_risultati_senza_le_uscite_del_metodo_che_non_gira(tmp_path, monkeypatch):
    """Corsa "both", poi solo MetaPhlAn, poi solo Kraken: in risultati/ restano solo profili e tabelle del metodo che
    gira (quelli dell'altro, in pmn_work, sono di una corsa vecchia)."""
    m, prog, cfg = risultati_finti(tmp_path, monkeypatch, lavoro=("SRRA",))
    res, r = prog / "w" / "results", prog / "risultati"
    krk = ["alpha_diversity_kraken.tsv", "kraken_matrix.tsv", "kraken_matrix_taxa.tsv"]
    mpa = ["alpha_diversity_metaphlan.tsv", "metaphlan_matrix.tsv", "metaphlan_merged.tsv"]
    for t in krk + mpa:
        (res / t).write_text("tabella\n", encoding="utf-8")
    (res / "alpha_metaphlan_pari").mkdir()
    shutil.copy(prog / "w" / "metaphlan" / "SRRA_profile.txt", res / "alpha_metaphlan_pari")
    m._risultati(prog / "config.yaml", cfg)
    assert (r / "kraken" / "SRRA.bracken").is_file() and (r / "metaphlan_pari" / "SRRA_profile.txt").is_file()
    assert sorted(f.name for f in (r / "tabelle").iterdir()) == sorted(krk + mpa + ["parameters.tsv"])
    cfg["profiling"]["tool"] = "metaphlan"
    m._risultati(prog / "config.yaml", cfg)
    assert not list((r / "kraken").iterdir())
    assert sorted(f.name for f in (r / "tabelle").iterdir()) == sorted(mpa + ["parameters.tsv"])
    cfg["profiling"]["tool"] = "kraken"
    m._risultati(prog / "config.yaml", cfg)
    assert not list((r / "metaphlan").iterdir()) and not list((r / "metaphlan_pari").iterdir())
    assert sorted(f.name for f in (r / "kraken").iterdir()) == ["SRRA.bracken", "SRRA.k2report"]
    assert sorted(f.name for f in (r / "tabelle").iterdir()) == sorted(krk + ["parameters.tsv"])


# ---------------- P29 (GE-1 e GE-2): referto e alfa di Kraken con la stessa % esatta della beta ----------------
def test_p29_referto_usa_le_read_intere_come_la_beta(tmp_path):
    """64 read su 1.405.930 sono lo 0,00455 %: Bracken scrive 0.00005 e leggi_kraken ne faceva lo 0,005 %, sopra la
    soglia rapido. Referto, sintesi, Excel, pct_microbi e alfa (diversita.tabella_kraken) mostravano Listeria
    welshimeri, che la beta (passo 33, --taxa-out) esclude."""
    sys.path.insert(0, str(RADICE / "motore"))
    import diversita
    import referto
    (tmp_path / "S1.bracken").write_text(
        "name\ttaxonomy_id\ttaxonomy_lvl\tkraken_assigned_reads\tadded_reads\tnew_est_reads\tfraction_total_reads\n"
        "Listeria welshimeri\t1643\tS\t64\t0\t64\t0.00005\n"
        "Latilactobacillus sakei\t1599\tS\t1405866\t0\t1405866\t0.99995\n", encoding="utf-8")
    (tmp_path / "S1.k2report").write_text("100.00\t1405930\t0\tR\t1\troot\n"
                                          "100.00\t1405930\t0\tD\t2\t  Bacteria\n"
                                          "0.00\t64\t64\tS\t1643\t    Listeria welshimeri\n"
                                          "100.00\t1405866\t1405866\tS\t1599\t    Latilactobacillus sakei\n",
                                          encoding="utf-8")
    righe = {r["nome"]: r for r in referto.leggi_kraken(tmp_path / "S1.bracken", tmp_path / "S1.k2report")}
    assert righe["Listeria welshimeri"]["pct"] == pytest.approx(64 / 1405930 * 100, rel=1e-9)
    assert righe["Listeria welshimeri"]["pct"] < 0.005                          # sotto la soglia rapido (>=)
    assert sum(r["pct_microbi"] for r in righe.values()) == pytest.approx(100.0)
    alfa = diversita.tabella_kraken({"S1": list(righe.values())}, 0.005, referto.MICROBI)
    assert alfa[0]["letture"] == 1405866 and alfa[0]["ricchezza"] == 1          # solo L. sakei, come nella beta
    pd = pytest.importorskip("pandas")
    r = subprocess.run([sys.executable, str(RADICE / "steps" / "33_kraken_matrix.py"), "--in", str(tmp_path),
                        "--out", str(tmp_path / "m.tsv"), "--taxa-out", str(tmp_path / "t.tsv"),
                        "--threshold-pct", "0.005"], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    beta = pd.read_csv(tmp_path / "t.tsv", sep="\t", index_col=0)["S1"]
    assert set(beta[beta > 0].index) == {n for n, x in righe.items() if x["pct"] >= 0.005}


# ---------------- P38 (secondo giro): singolare e plurale nella conferma di esegui ----------------
def test_p38_riassunto_singolare_e_plurale():
    """Con un campione e un minuto la frase diceva "1 campioni" e "circa 1 minuti"."""
    pytest.importorskip("mcp")
    import importlib.util
    spec = importlib.util.spec_from_file_location("pmn_mcp_server_g2", RADICE / "pmn_mcp" / "server.py")
    s = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(s)
    assert s.riassunto({"esito": "ok", "risultato": {"campioni": 1, "tempo_totale_s": 60, "spazio_gb": 12,
                                                     "spazio_libero_gb": 643}}) == \
        "1 campione, circa 1 minuto, 12 GB di spazio (liberi 643 GB)."
    assert s.riassunto({"esito": "ok", "risultato": {"campioni": 2, "tempo_totale_s": 2280, "spazio_gb": 3.2,
                                                     "spazio_libero_gb": 412.5}}) == \
        "2 campioni, circa 38 minuti, 3,2 GB di spazio (liberi 412,5 GB)."


# ---------------- P19 (secondo giro): l'estensione si guarda sul file che si apre davvero ----------------
def test_p19_estensione_sul_percorso_risolto(tmp_path, monkeypatch):
    """risultati.json nomina "referto/referto.pdf", ma è un collegamento simbolico a un .bat: il nome passava il
    controllo e apri() mandava a ShellExecute il .bat risolto. Su Windows senza il privilegio dei collegamenti
    simbolici il collegamento si imita facendo risolvere dentro() verso il .bat."""
    pytest.importorskip("PySide6")
    sys.path.insert(0, str(RADICE))
    from types import SimpleNamespace
    from app.pagine import risultati
    p = SimpleNamespace(cartella=tmp_path / "prj", risultati=tmp_path / "prj" / "risultati")
    (p.risultati / "referto").mkdir(parents=True)
    bat = p.risultati / "referto" / "x.bat"
    bat.write_text("@echo off\n", encoding="utf-8")
    pdf = p.risultati / "referto" / "referto.pdf"
    try:
        os.symlink(bat, pdf)
    except OSError:
        veri = risultati.dentro
        monkeypatch.setattr(risultati, "dentro",
                            lambda prog, perc: veri(prog, bat if Path(perc).name == "referto.pdf" else perc))
        pdf.write_text("finto", encoding="utf-8")
    (p.risultati / "referto" / "tabelle.xlsx").write_text("x", encoding="utf-8")
    f = risultati.file_referto(p, {"referto": {"pdf": "referto/referto.pdf", "xlsx": "referto/tabelle.xlsx"}})
    assert f["pdf"] is None
    assert f["xlsx"] == (p.risultati / "referto" / "tabelle.xlsx").resolve()


# ---------------- Pagina Motore: l'analisi finisce mentre la pagina è aperta ----------------
def test_motore_si_riaccende_quando_l_analisi_finisce(request, monkeypatch, tmp_path):
    """La barra della pagina Motore si ricalcolava solo in mostrata, _avvia e _finito: se l'analisi finiva mentre
    l'utente era sulla pagina Motore, "Controlla il motore" restava spento finché non si cambiava pagina."""
    pytest.importorskip("pytestqt")
    sys.path.insert(0, str(RADICE))
    from app import finestra, main
    monkeypatch.setenv("PMN_MOTORE", "finto")
    monkeypatch.setenv("PMN_FINTO_OPZIONI", "--velocita 0")
    monkeypatch.setenv("TEMP", str(tmp_path))
    monkeypatch.setenv("TMP", str(tmp_path))
    qtbot, qapp = request.getfixturevalue("qtbot"), request.getfixturevalue("qapp")
    main.prepara(qapp)
    f = finestra.Finestra(movimento=False)
    qtbot.addWidget(f)
    f.show()
    f.fuori.setCurrentIndex(1)
    f.contesto.progetto_in_analisi = "progetto_X"          # come fa la pagina Analisi in corso quando parte
    f.vai("motore")
    assert not f.principale.isEnabled()
    f.pagine["esecuzione"].client.finito.emit(0, {"tipo": "fine", "esito": "ok"})   # l'analisi finisce
    assert f.contesto.progetto_in_analisi is None
    assert f.principale.isEnabled() and f.pagine["motore"].principale_attivo


# ---------------- P41/P02 (secondo giro): ordine di lucchetti e segni di annulla ----------------
def test_finto_installa_ha_il_lucchetto_gia_all_evento_inizio(tmp_path, monkeypatch, capsys):
    """installa_motore.sh scrive installa.lock prima dell'evento inizio: chi legge la corsa dall'evento inizio e
    chiama subito annulla la trova. Il finto lo scriveva dopo, dentro installa()."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("finto_motore_g2", RADICE / "installer" / "finto_motore.py")
    fm = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fm)
    monkeypatch.setattr(fm, "STATO", tmp_path)
    monkeypatch.setattr(sys, "argv", ["finto_motore.py", "installa", "--velocita", "0"])
    visti = []
    monkeypatch.setattr(fm.Motore, "evento", lambda self, tipo, *a, **k: visti.append(
        (tipo, (tmp_path / "installa.lock").exists())))
    assert fm.main() == 0
    assert visti[0] == ("inizio", True)
    assert not (tmp_path / "installa.lock").exists()                    # tolto alla fine, come prima


def test_annulla_crea_il_segno_prima_di_leggere_il_lucchetto(tmp_path, monkeypatch):
    """Gara di P02: annulla leggeva esegui.lock (pgid ancora None), esegui intanto guardava .annulla (non c'era
    ancora), lanciava run.sh e riscriveva il lucchetto col pgid; poi annulla creava .annulla ma, col pgid letto
    prima, non fermava nulla: l'analisi andava fino in fondo. Con il segno creato prima, esegui lo vede sempre."""
    from types import SimpleNamespace
    sys.path.insert(0, str(RADICE / "motore"))
    import pmn_motore as pm
    monkeypatch.setattr(pm, "STATO", tmp_path)
    corsa = "2026-10-22T10-00-00"
    (tmp_path / "esegui.lock").write_text(f'{{"corsa": "{corsa}", "pid": {os.getpid()}, "pgid": null}}',
                                          encoding="utf-8")
    segno_al_momento = []
    leggi = Path.read_text

    def read_text(self, *a, **k):
        if self.name == "esegui.lock":
            segno_al_momento.append((tmp_path / f"{corsa}.annulla").exists())
        return leggi(self, *a, **k)
    monkeypatch.setattr(Path, "read_text", read_text)
    m = pm.Motore(SimpleNamespace(comando="annulla", corsa=corsa))
    m.log = tmp_path / "x.log"
    assert m.annulla()[1] == {"annullata": True}
    assert segno_al_momento == [True]
    # corsa che non c'è, o con un percorso dentro: nessun segno rimasto, niente scritto fuori da STATO
    for altra in ("2026-10-22T11-00-00", "../fuori"):
        m.a.corsa = altra
        assert m.annulla()[1] == {"annullata": False}
    assert {p.name for p in tmp_path.iterdir()} - {"x.log"} == {"esegui.lock", f"{corsa}.annulla"}
    assert not (tmp_path.parent / "fuori.annulla").exists()


# ---------------- P18 (secondo giro): credentials già esistente con permessi larghi ----------------
@pytest.mark.skipif(os.name != "posix", reason="permessi POSIX (0600): Linux/WSL")
def test_p18_credenziale_scritta_solo_dopo_aver_stretto_i_permessi(tmp_path, monkeypatch):
    """os.open con O_CREAT|O_TRUNC non cambia i permessi di un file che c'è già: con un credentials 0644 la chiave
    nuova veniva scritta in un file leggibile da tutti, e solo dopo il chmod lo stringeva."""
    sys.path.insert(0, str(RADICE / "steps"))
    import _biomni_consent as cs
    f = tmp_path / "credentials"
    f.write_text("ALTRA=1\n", encoding="utf-8")
    f.chmod(0o644)
    durante = []
    apri = os.fdopen

    def fdopen(fd, *a, **k):
        durante.append(os.fstat(fd).st_mode & 0o777)
        return apri(fd, *a, **k)
    monkeypatch.setattr(cs.os, "fdopen", fdopen)
    assert cs.store_credential(f, "PMN_CHIAVE", "segreta") == ""
    assert durante == [0o600]
    assert f.stat().st_mode & 0o777 == 0o600
    assert f.read_text(encoding="utf-8") == "ALTRA=1\nPMN_CHIAVE=segreta\n"


# ---------------- P14 (secondo giro): i documenti mostrano la riga wsl.exe dell'app ----------------
def test_p14_documenti_con_la_riga_wsl_senza_shell():
    """app/motore.py lancia wsl.exe con "-e" (senza bash -c); docs/interfaccia_S4.md mostrava ancora "--"."""
    import re
    for doc in ("docs/interfaccia_S4.md", "docs/contratto_motore.md"):
        righe = re.findall(r"`wsl\.exe -d [^`]*`", (RADICE / doc).read_text(encoding="utf-8"))
        assert righe and all(" -e " in r and " -- " not in r for r in righe), (doc, righe)


# ---------------- P15: il finto motore come il contratto (passo referto, risultato di installa) ----------------
def finto(tmp_path, *argomenti):
    sys.path.insert(0, str(RADICE / "tests"))
    from contratto import controlla
    env = {**os.environ, "TEMP": str(tmp_path), "TMP": str(tmp_path)}   # lucchetti del finto solo per questo test
    r = subprocess.run([sys.executable, str(RADICE / "installer" / "finto_motore.py"), *argomenti, "--velocita", "0"],
                       capture_output=True, text=True, encoding="utf-8", env=env, timeout=120)
    return controlla(r.stdout, r.returncode, argomenti[0])


@pytest.mark.parametrize("lingua", ["it", "en"])
def test_p15_esegui_finto_chiude_col_passo_referto(tmp_path, lingua):
    """Il vero manda avanzamento "referto" come ultimo passo di esegui (contratto, v0.2); il finto sommava il tempo
    del referto al riepilogo e non lo mandava mai."""
    cfg = tmp_path / "prog" / "config.yaml"
    cfg.parent.mkdir()
    cfg.write_text("project_name: prog\n", encoding="utf-8")
    ev = finto(tmp_path, "esegui", "--progetto", str(cfg), "--lingua", lingua)
    av = [e for e in ev if e["tipo"] == "avanzamento"]
    assert [e["passo"] for e in av][-2:] == ["riepilogo", "referto"] and av[-1]["campione"] is None
    assert ev[-1]["esito"] == "ok"


def test_p15_installa_finto_con_la_forma_del_contratto(tmp_path):
    """Contratto §2 e installa_motore.sh: {"programmi": 8, "database": [gruppi del catalogo], "verifica": "verde"}."""
    ev = finto(tmp_path, "installa")
    gruppi = [r.split("\t")[0] for r in (RADICE / "installer" / "catalogo.tsv").read_text(encoding="utf-8")
              .splitlines()[1:] if r.strip()]
    assert ev[-1]["risultato"] == {"programmi": 8, "database": list(dict.fromkeys(gruppi)), "verifica": "verde"}


# ---------------- Testi (secondo giro): P27, P30-P37 ----------------
def motore_referto():
    sys.path.insert(0, str(RADICE / "motore"))
    import lingua
    import referto
    lingua.imposta("it")
    return referto, lingua


def test_p33_conte_all_italiana_senza_notazione_esponenziale():
    """Le conte da 10^6 in su uscivano "1e+06 ufc/g" o "2.5e+07 ufc/g", accanto a "pH 5,4"."""
    referto, lingua = motore_referto()
    t = referto.dati_prodotto({"prodotto": {"ph": 5.4}, "giorni": 21, "conte": {"lab_ufc_g": 25000000.0}})
    assert "conta dei batteri lattici 25.000.000 ufc/g" in t and "e+" not in t
    assert "1.234.567 ufc/g" in referto.dati_prodotto({"prodotto": {}, "conte": {"lab_ufc_g": 1234567.0}})
    lingua.imposta("en")
    try:
        assert "1,000,000 ufc/g" in referto.dati_prodotto({"prodotto": {}, "conte": {"lab_ufc_g": 1e6}})
    finally:
        lingua.imposta("it")


def catalogo_en(dove):
    import json
    return json.loads((RADICE / dove / "lingua_en.json").read_text(encoding="utf-8"))


def test_p34_excel_si_con_l_accento(tmp_path):
    """Le colonne sì/no dell'Excel ("Sopra soglia", "Listeria può crescere") scrivevano "si"; HTML e PDF "sì"."""
    openpyxl = pytest.importorskip("openpyxl")
    pytest.importorskip("PySide6.QtGui")
    dati, p = RADICE / "installer" / "finto", tmp_path / "P"
    for sotto in ("metaphlan", "kraken", "tabelle"):
        (p / "risultati" / sotto).mkdir(parents=True)
    shutil.copy(dati / "SRR4875279_profile.txt", p / "risultati" / "metaphlan")
    for est in ("bracken", "k2report"):
        shutil.copy(dati / f"SRR4875279.{est}", p / "risultati" / "kraken")
    for f in ("parameters.tsv", "kraken_matrix.tsv", "metaphlan_merged.tsv"):
        shutil.copy(dati / f, p / "risultati" / "tabelle")
    shutil.copy(dati / "risultati.json", p / "risultati")
    (p / "config.yaml").write_text("project_name: P\n", encoding="utf-8")
    r = subprocess.run([sys.executable, str(RADICE / "motore" / "referto.py"), "--risultati", str(p / "risultati"),
                        "--progetto", str(p / "config.yaml")], capture_output=True, text=True, encoding="utf-8",
                       timeout=120, env={**os.environ, "PMN_LINGUA": "it"})
    assert r.returncode == 0, r.stdout + r.stderr
    v = list(openpyxl.load_workbook(p / "risultati" / "referto" / "referto.xlsx")["Kraken_taxa"].values)[1:]
    col = v[0].index("Sopra soglia")                                    # riga 1: la scritta "prototipo"
    valori = {x[col] for x in v[1:]}
    assert valori and valori <= {"sì", "no"}
    assert "si" not in catalogo_en("motore")                           # chiave rimasta senza usi


def test_p27_p31_limite_kraken_dice_la_base_e_il_database_dei_numeri_k4():
    """P27: la soglia si confronta con la % sulle read assegnate da Bracken (non classificate escluse), non "delle
    read". P31: in una corsa rapida (PlusPF-8, 0,1 e 0,005 %) i numeri di K4 valgono per il PlusPF completo."""
    referto, lingua = motore_referto()
    t = referto.limite_kraken({"soglia": 0.005, "parametri": {"kraken_confidence": "0.1", "kraken_profile": "rapido"}})
    assert "almeno lo 0,005 % delle read assegnate da Bracken (non classificate escluse; confidence 0,1)" in t
    assert "% delle read (confidence" not in t
    assert "Con i valori consigliati (0,5 e 0,1 %)" not in t
    assert "consigliati per il PlusPF completo (confidence 0,5 e soglia 0,1 %)" in t
    assert "da 196 a 64 su 12 campioni" in t and "da 10 a 0" in t
    en = catalogo_en("motore")[referto.LIMITE_KRAKEN]
    assert "of the reads assigned by Bracken" in en and "for the full PlusPF" in en


def test_p30_ancora_non_promette_una_ripresa_da_sola():
    """Non c'è ripresa automatica: si riapre il progetto e si preme Riprendi l'analisi (come dice la conferma)."""
    pytest.importorskip("PySide6")
    sys.path.insert(0, str(RADICE))
    from app.pagine import esecuzione
    assert "alla riaccensione" not in esecuzione.ANCORA and "riparte" not in esecuzione.ANCORA
    assert "quando riapri il progetto, premi Riprendi l'analisi" in esecuzione.ANCORA


def etichette_qt(w):
    from PySide6.QtWidgets import QLabel
    return [x.text() for x in w.findChildren(QLabel)]


@pytest.mark.parametrize("valore, atteso", [(0.0, "Lo <b>0,0 %</b>"), (80.5, "L'<b>80,5 %</b>"),
                                            (11.0, "L'<b>11,0 %</b>"), (1.2, "L'<b>1,2 %</b>"),
                                            (18.0, "Il <b>18,0 %</b>"), (53.7, "Il <b>53,7 %</b>")])
def test_p32_articolo_davanti_alla_quota_non_assegnata(request, valore, atteso):
    """La scheda MetaPhlAn scriveva sempre "Il": "Il 0,0 %", "Il 80,5 %". Il motore dice "Lo 0,0 %", "L'80,5 %"."""
    pytest.importorskip("pytestqt")
    request.getfixturevalue("qapp")
    sys.path.insert(0, str(RADICE))
    from app.pagine.risultati import PaginaRisultati
    pag = PaginaRisultati.__new__(PaginaRisultati)                    # la scheda non usa lo stato della pagina
    w = pag._scheda_metaphlan([{"nome": "S1", "sintesi": {"metaphlan": {
        "specie": 1, "dominanti": [{"nome": "X", "pct": 50.0}], "non_assegnata_pct": valore, "frase": ""}}}])
    assert any(t.startswith(f"Percentuale sul totale delle read del campione. {atteso} non è") for t in etichette_qt(w))


def test_p35_la_soglia_di_abbondanza_e_solo_di_kraken(request):
    """App: "Abbondanza minima mostrata" accanto alla riga MetaPhlAn faceva pensare a una soglia anche lì."""
    pytest.importorskip("pytestqt")
    request.getfixturevalue("qapp")
    sys.path.insert(0, str(RADICE))
    from app.pagine import risultati, scelte
    assert "Vale solo per Kraken: MetaPhlAn non ha soglia" in scelte.FONTE_SOGLIA
    for modulo in (risultati, scelte):
        assert "Abbondanza minima mostrata" not in Path(modulo.__file__).read_text(encoding="utf-8")
    pag = risultati.PaginaRisultati.__new__(risultati.PaginaRisultati)
    t = etichette_qt(pag._scheda_come({"parametri": {"abundance_threshold_pct": "0.1", "kraken_confidence": "0.5"},
                                      "versioni": {"metaphlan": "4.2.4"}}))
    assert t[t.index("0,1 %") - 1] == "Soglia di abbondanza di Kraken"


def test_p36_intestazione_esperti_non_dice_tutto_dalla_letteratura():
    """Con il database completo 0,5 e 0,1 % vengono dalla taratura K4, non dalla letteratura."""
    testo = (RADICE / "app" / "pagine" / "scelte.py").read_text(encoding="utf-8")
    assert "taratura K4" in testo and "viene dalla letteratura" not in testo
    assert "Ogni valore consigliato ha la fonte accanto (letteratura o taratura K4)." in testo


def test_p37_singolare_e_plurale_nelle_schede_della_sicurezza(request):
    """ "Se all'inizio ci fosse 100 ufc/g" e "1 specie del profilo non hanno": il numero decide il verbo."""
    pytest.importorskip("pytestqt")
    request.getfixturevalue("qapp")
    sys.path.insert(0, str(RADICE))
    from app.pagine.sicurezza import PaginaSicurezza
    pag = PaginaSicurezza.__new__(PaginaSicurezza)                     # i due metodi non usano lo stato
    p = {"n0_listeria_ufc_g": 100.0, "listeria_puo_crescere": False,
         "curva": {"giorni": [0, 30], "log_listeria": [2.0, 2.0]}}
    f = pag._scheda(p, False)
    t = " ".join(etichette_qt(f))
    assert "ci fossero 100 ufc/g" in t and "ci fosse 100" not in t
    f1 = pag._scheda(dict(p, n0_listeria_ufc_g=1.0), False)
    assert "ci fosse 1 ufc/g" in " ".join(etichette_qt(f1))
    f2 = pag._ponte({"ponte": {"specie_non_coperte": ["staphylococcus xylosus"], "lab_trovati": []}})
    t = " ".join(etichette_qt(f2))
    assert "1 specie del profilo non ha un modello in FSSP" in t and "non hanno" not in t
    f3 = pag._ponte({"ponte": {"specie_non_coperte": ["a", "b"], "lab_trovati": []}})
    assert "2 specie del profilo non hanno un modello in FSSP" in " ".join(etichette_qt(f3))


# ---------------- P24: il .k2out per read non serve al programma (scelta del 22/10) ----------------
def kraken_finto(tmp_path, **env):
    """32_kraken_bracken.sh con kraken2 e bracken finti: kraken2 scrive i suoi argomenti in argomenti.txt."""
    b = tmp_path / "bin"
    b.mkdir()
    (b / "kraken2").write_text('#!/bin/bash\nprintf "%s\n" "$@" > "$ARGOMENTI"\n'
                               'while [ $# -gt 0 ]; do [ "$1" = --report ] && : > "$2"; shift; done\n', encoding="utf-8")
    (b / "bracken").write_text('#!/bin/bash\nwhile [ $# -gt 0 ]; do [ "$1" = -o ] && echo fatto > "$2"; shift; done\n',
                               encoding="utf-8")
    for p in b.iterdir():
        p.chmod(0o755)
    (tmp_path / "db").mkdir()
    (tmp_path / "r1.fq.gz").write_bytes(gzip.compress(b"@r\nACGT\n+\nIIII\n"))
    argomenti = tmp_path / "argomenti.txt"
    r = subprocess.run(["bash", str(RADICE / "steps" / "32_kraken_bracken.sh"), "--sample", "S1",
                        "--in1", str(tmp_path / "r1.fq.gz"), "--db", str(tmp_path / "db"), "--out", str(tmp_path / "out"),
                        "--confidence", "0.5"], capture_output=True, text=True,
                       env={**os.environ, "PATH": f"{b}:{os.environ['PATH']}", "NO_COLOR": "1", "PMN_LANG": "en",
                            "ARGOMENTI": str(argomenti), **env})
    assert r.returncode == 0, r.stdout + r.stderr
    a = argomenti.read_text(encoding="utf-8").split("\n")
    return a[a.index("--output") + 1]


@linux
def test_p24_kraken_non_scrive_il_k2out(tmp_path):
    assert kraken_finto(tmp_path) == "-"
    assert not (tmp_path / "out" / "S1.k2out").exists()


@linux
def test_p24_k2out_solo_per_le_prove_di_validazione(tmp_path):
    assert kraken_finto(tmp_path, PMN_KEEP_K2OUT="1") == str(tmp_path / "out" / "S1.k2out")


# ---------------- P39: i consigli del motore scrivevano la RAM col punto anche in italiano ("5.8 GB") ----------------
@pytest.mark.parametrize("codice, atteso", [("it", "5,8 GB"), ("en", "5.8 GB")])
def test_p39_ram_con_la_virgola_in_italiano(codice, atteso):
    sys.path.insert(0, str(RADICE / "motore"))
    import lingua
    import system_one
    prima = lingua.attuale()
    lingua.imposta(codice)
    try:
        testi = [c["messaggio"] for c in system_one.modo(5.83, False, True, True)[1]]
    finally:
        lingua.imposta(prima)
    assert len(testi) == 2 and all(atteso in t for t in testi), testi


# ---------------- terzo giro: difetti del revisore cieco del secondo giro (22/10) ----------------
@linux
def test_r1_parentesi_quadre_nel_percorso_non_diventano_un_modello(tmp_path):
    """Cartella nonhost "nonhost[2024]": il modello [2024] trovava anche nonhost2/A1_nonhost_1.fastq.gz (cartella
    sorella) e la cancellava, lasciando il file vero del progetto."""
    home = installazione_finta(tmp_path)
    condivisa, sorella = tmp_path / "nonhost[2024]", tmp_path / "nonhost2"
    condivisa.mkdir()
    sorella.mkdir()
    a = progetto_custom(tmp_path, "salame", ["A1", "A2"], condivisa)   # A2 da rifilare: la corsa finta si ferma lì
    corsa_custom(home, *a, condivisa, "[sus_scrofa]")
    nonhost_finiti(condivisa, "A1", b"maiale")
    nonhost_finiti(sorella, "A1", b"altro")
    prima = byte(sorella, "A1")
    corsa_custom(home, *a, condivisa, "[bos_taurus]")
    assert byte(sorella, "A1") == prima                     # la cartella sorella non si tocca
    assert byte(condivisa, "A1") == {}                      # le uscite del progetto si rifanno


@linux
def test_r1_stesso_campione_in_due_progetti_con_ospiti_diversi(tmp_path):
    """Salame (maiale) e bresaola (bovino) con lo stesso campione A1 nella stessa cartella nonhost: chi trova le read
    filtrate con l'altro ospite le rifà, invece di profilarle dichiarando il proprio ospite (D022)."""
    home = installazione_finta(tmp_path)
    condivisa = tmp_path / "nonhost_condivisa"
    condivisa.mkdir()
    a = progetto_custom(tmp_path, "salame", ["A1", "A2"], condivisa)
    b = progetto_custom(tmp_path, "bresaola", ["A1", "B2"], condivisa)
    corsa_custom(home, *b, condivisa, "[bos_taurus]")
    corsa_custom(home, *a, condivisa, "[sus_scrofa]")       # il timbro di A1 si scrive quando il salame lo rifà
    nonhost_finiti(condivisa, "A1", b"maiale")              # il salame ha finito A1 col maiale
    corsa_custom(home, *a, condivisa, "[sus_scrofa]")
    assert len(byte(condivisa, "A1")) == 2                  # stesso ospite: si tengono
    corsa_custom(home, *b, condivisa, "[bos_taurus]")
    assert byte(condivisa, "A1") == {}                      # filtrate col maiale: la bresaola le rifà
    nonhost_finiti(condivisa, "A1", b"bovino")
    corsa_custom(home, *a, condivisa, "[sus_scrofa]")
    assert byte(condivisa, "A1") == {}                      # e il salame rifà le sue


@linux
def test_r3_fase_b_solo_i_campioni_del_progetto(tmp_path):
    """Con la cartella nonhost condivisa la Fase B profilava anche i campioni dell'altro progetto (ore di analisi)."""
    home = installazione_finta(tmp_path)
    condivisa = tmp_path / "nonhost_condivisa"
    condivisa.mkdir()
    cfg, letture = progetto_custom(tmp_path, "salame", ["A1", "A2"], condivisa)
    corsa_custom(home, cfg, letture, condivisa, "[sus_scrofa]")   # registra i parametri dell'ospite
    nonhost_finiti(condivisa, "A1", b"maiale")
    nonhost_finiti(condivisa, "B1", b"bovino")              # di un altro progetto
    cfg.write_text(cfg.read_text(encoding="utf-8").replace("tool: metaphlan", "tool: kraken"), encoding="utf-8")
    r = subprocess.run(["bash", str(RADICE / "bin" / "run.sh"), "--config", str(cfg), "--skip-preflight", "--dry-run",
                        "--phase", "b"], capture_output=True, text=True, timeout=120, cwd=cfg.parent,
                       env={**os.environ, "PMN_HOME": str(home), "NO_COLOR": "1"})
    testo = r.stdout + r.stderr
    assert "krk_A1" in testo and "krk_B1" not in testo, testo   # a secco Kraken stampa il passo anche senza database


@linux
def test_r3_uscite_dei_campioni_tolti_via_dalla_cartella_di_lavoro(tmp_path):
    """MetaPhlAn e Kraken stanno sempre nella cartella di lavoro del progetto: le uscite dei campioni tolti finivano
    nelle tabelle unite, nella beta e nella profondità del passo 42. Si tolgono solo quelle, coi nomi esatti."""
    mpa, krk = tmp_path / "metaphlan", tmp_path / "kraken"
    mpa.mkdir()
    krk.mkdir()
    for s in ("C1", "C1_bis"):
        for f in (mpa / f"{s}_profile.txt", mpa / f"{s}.mapout", krk / f"{s}.bracken", krk / f"{s}.k2report",
                  krk / f"{s}_bracken_species.k2report"):
            f.write_text(s, encoding="utf-8")
    (mpa / "nreads.txt").write_text("altro", encoding="utf-8")
    comando = '. "$1/bin/lib/common.sh"; pmn_togli_campioni_tolti "$2" "$3" C1'
    r = subprocess.run(["bash", "-c", comando, "x", str(RADICE), str(mpa), str(krk)], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert sorted(f.name for f in mpa.iterdir()) == ["C1.mapout", "C1_profile.txt", "nreads.txt"]
    assert sorted(f.name for f in krk.iterdir()) == ["C1.bracken", "C1.k2report", "C1_bracken_species.k2report"]


def test_r4_i_file_dell_utente_in_risultati_tabelle_restano(tmp_path, monkeypatch):
    """La pulizia di risultati/ fra le corse toglieva ogni *.xlsx e *.tsv di tabelle/, anche quelli salvati lì
    dall'utente: si tolgono solo i nomi che il motore stesso scrive (quelli della cartella results)."""
    m, prog, cfg = risultati_finti(tmp_path, monkeypatch, lavoro=("SRRA",))
    (prog / "w" / "results" / "report_overview.xlsx").write_text("motore", encoding="utf-8")
    m._risultati(prog / "config.yaml", cfg)
    mio = prog / "risultati" / "tabelle" / "report_commentato.xlsx"
    mio.write_text("note dell'utente", encoding="utf-8")
    m._risultati(prog / "config.yaml", cfg)
    assert mio.read_text(encoding="utf-8") == "note dell'utente"


def test_r5_fastqc_col_nome_esatto_del_campione(tmp_path):
    """Il filtro dei report FastQC guardava solo l'inizio del nome: C1_bis (tolto) restava se il progetto ha C1."""
    sys.path.insert(0, str(RADICE / "motore"))
    import pmn_motore as pm
    lavoro, trim, r = tmp_path / "w", tmp_path / "w" / "trim", tmp_path / "risultati"
    trim.mkdir(parents=True)
    for s in ("C1", "C1_bis"):
        for f in (f"{s}_fastp.html", f"{s}_1_fastqc.html", f"{s}_trim_1_fastqc.html"):
            (trim / f).write_text("report", encoding="utf-8")
    qc = pm.controllo_qualita(lavoro, trim, r, {"C1"})
    assert qc["fastqc"] == ["qc/fastqc/C1_1_fastqc.html", "qc/fastqc/C1_trim_1_fastqc.html"]


@linux
def test_r6_profili_pari_dell_altro_progetto_restano(tmp_path):
    """results_dir personalizzata condivisa: il cambio dei parametri di MetaPhlAn di un progetto cancellava tutta
    alpha_metaphlan_pari, anche i profili dell'altro progetto."""
    home = installazione_finta(tmp_path)
    condivisa, risultati = tmp_path / "nonhost_condivisa", tmp_path / "risultati_condivisi"
    condivisa.mkdir()
    (risultati / "alpha_metaphlan_pari").mkdir(parents=True)
    for s in ("A1", "B1"):
        (risultati / "alpha_metaphlan_pari" / f"{s}_profile.txt").write_text(s, encoding="utf-8")
    cfg, letture = progetto_custom(tmp_path, "salame", ["A1"], condivisa)
    cfg.write_text(f"project_name: salame\ndata_source: local\nhosts: [sus_scrofa]\nfilter_human: false\n"
                   f"paths:\n  layout: custom\n  work_dir: {cfg.parent / 'lavoro'}\n  local_reads_dir: {letture}\n"
                   f"  nonhost_dir: {condivisa}\n  results_dir: {risultati}\nprofiling:\n  tool: metaphlan\n",
                   encoding="utf-8")
    subprocess.run(["bash", str(RADICE / "bin" / "run.sh"), "--config", str(cfg), "--skip-preflight", "--phase", "b"],
                   capture_output=True, text=True, timeout=120, cwd=cfg.parent,
                   env={**os.environ, "PMN_HOME": str(home), "NO_COLOR": "1"})
    assert sorted(f.name for f in (risultati / "alpha_metaphlan_pari").iterdir()) == ["B1_profile.txt"]


# ---------------- quarto giro: difetti del revisore cieco del terzo giro (22/10) ----------------
@linux
def test_q1_results_condivisa_toglie_anche_il_sottocampione_mapout(tmp_path):
    """results_dir personalizzata: col profilo pari si toglie anche il suo .mapout, che il passo 42 riuserebbe con i
    parametri vecchi; quelli dell'altro progetto restano."""
    home = installazione_finta(tmp_path)
    condivisa, risultati = tmp_path / "nonhost_condivisa", tmp_path / "risultati_condivisi"
    condivisa.mkdir()
    pari = risultati / "alpha_metaphlan_pari"
    pari.mkdir(parents=True)
    for f in ("A1_profile.txt", "A1.mapout", "B1_profile.txt", "B1.mapout"):
        (pari / f).write_text(f, encoding="utf-8")
    cfg, letture = progetto_custom(tmp_path, "salame", ["A1"], condivisa)
    cfg.write_text(f"project_name: salame\ndata_source: local\nhosts: [sus_scrofa]\nfilter_human: false\n"
                   f"paths:\n  layout: custom\n  work_dir: {cfg.parent / 'lavoro'}\n  local_reads_dir: {letture}\n"
                   f"  nonhost_dir: {condivisa}\n  results_dir: {risultati}\nprofiling:\n  tool: metaphlan\n",
                   encoding="utf-8")
    subprocess.run(["bash", str(RADICE / "bin" / "run.sh"), "--config", str(cfg), "--skip-preflight", "--phase", "b"],
                   capture_output=True, text=True, timeout=120, cwd=cfg.parent,
                   env={**os.environ, "PMN_HOME": str(home), "NO_COLOR": "1"})
    assert sorted(f.name for f in pari.iterdir()) == ["B1.mapout", "B1_profile.txt"]


@linux
def test_q2_read_rifatte_rifanno_anche_i_profili_del_campione(tmp_path):
    """Cartella nonhost condivisa: quando un campione si rifà (read dell'altro ospite, o dati di prima), via anche i
    suoi profili MetaPhlAn e Kraken del progetto, che possono essere stati fatti con le read sbagliate."""
    home = installazione_finta(tmp_path)
    condivisa = tmp_path / "nonhost_condivisa"
    condivisa.mkdir()
    a = progetto_custom(tmp_path, "salame", ["A1", "A2"], condivisa)
    lavoro = a[0].parent / "lavoro"
    for d, f in (("metaphlan", "A1_profile.txt"), ("kraken", "A1.bracken"), ("metaphlan", "A2_profile.txt")):
        (lavoro / d).mkdir(parents=True, exist_ok=True)
        (lavoro / d / f).write_text("profilo vecchio", encoding="utf-8")
    nonhost_finiti(condivisa, "A1", b"read di prima")       # dati di prima dell'aggiornamento: nessun timbro
    corsa_custom(home, *a, condivisa, "[sus_scrofa]")
    assert byte(condivisa, "A1") == {}
    assert not (lavoro / "metaphlan" / "A1_profile.txt").exists() and not (lavoro / "kraken" / "A1.bracken").exists()


@linux
def test_q2_fase_b_non_profila_read_fatte_con_l_altro_ospite(tmp_path):
    """--phase b da sola non passa dai timbri della Fase A: se l'altro progetto ha rifatto le read del campione con
    il suo ospite, il campione non si profila (si dovrebbe rifare la Fase A)."""
    home = installazione_finta(tmp_path)
    condivisa = tmp_path / "nonhost_condivisa"
    condivisa.mkdir()
    a = progetto_custom(tmp_path, "salame", ["A1", "A2"], condivisa)
    b = progetto_custom(tmp_path, "bresaola", ["A1", "B2"], condivisa)
    corsa_custom(home, *a, condivisa, "[sus_scrofa]")
    corsa_custom(home, *b, condivisa, "[bos_taurus]")       # la bresaola rifà A1 col bovino
    nonhost_finiti(condivisa, "A1", b"bovino")
    cfg = a[0]                                              # (il config del salame è quello della sua ultima corsa)
    (tmp_path / "db_mpa").mkdir()                           # un database qualsiasi: la Fase B arriva ai campioni
    testo_cfg = cfg.read_text(encoding="utf-8")
    cfg.write_text(testo_cfg.replace("profiling:\n", f"profiling:\n  metaphlan_db: {tmp_path / 'db_mpa'}\n"),
                   encoding="utf-8")
    r = subprocess.run(["bash", str(RADICE / "bin" / "run.sh"), "--config", str(cfg), "--skip-preflight", "--phase", "b"],
                       capture_output=True, text=True, timeout=120, cwd=cfg.parent,
                       env={**os.environ, "PMN_HOME": str(home), "NO_COLOR": "1", "PMN_LANG": "en"})
    testo = r.stdout + r.stderr
    assert "A1: its host-free reads were made with other host parameters" in testo, testo
    assert "mpa_A1" not in testo, testo


@linux
def test_q3_elenco_incompleto_non_toglie_i_profili(tmp_path):
    """data_source both con la cartella delle read locali non montata: l'elenco ha solo i codici SRR, e i profili dei
    campioni locali sparivano dalla cartella di lavoro. Con l'elenco incompleto non si toglie nulla."""
    home = installazione_finta(tmp_path)
    prog = tmp_path / "salame"
    (prog / "lavoro" / "metaphlan").mkdir(parents=True)
    for s in ("SRR100", "L1"):
        (prog / "lavoro" / "metaphlan" / f"{s}_profile.txt").write_text(s, encoding="utf-8")
    (prog / "srr.txt").write_text("SRR100\n", encoding="utf-8")
    cfg = prog / "config.yaml"
    cfg.write_text(f"project_name: salame\ndata_source: both\nhosts: [sus_scrofa]\nfilter_human: false\n"
                   f"paths:\n  work_dir: {prog / 'lavoro'}\n  srr_list: {prog / 'srr.txt'}\n"
                   f"  local_reads_dir: {tmp_path / 'disco_non_montato'}\nprofiling:\n  tool: metaphlan\n"
                   f"  metaphlan_db: {prog}\n",   # un database qualsiasi: la Fase B arriva ai campioni
                   encoding="utf-8")
    for _ in range(2):   # la prima corsa registra i parametri (timbro assente = si rifà tutto), la seconda riprende
        for s in ("SRR100", "L1"):
            (prog / "lavoro" / "metaphlan" / f"{s}_profile.txt").write_text(s, encoding="utf-8")
        subprocess.run(["bash", str(RADICE / "bin" / "run.sh"), "--config", str(cfg), "--skip-preflight", "--phase", "b"],
                       capture_output=True, text=True, timeout=120, cwd=prog,
                       env={**os.environ, "PMN_HOME": str(home), "NO_COLOR": "1"})
    assert (prog / "lavoro" / "metaphlan" / "L1_profile.txt").is_file()


@linux
def test_q4_raw_condivisa_fase_a_solo_sui_campioni_del_progetto(tmp_path):
    """raw_dir personalizzata condivisa: la Fase A rifilava e filtrava anche le read degli altri progetti (senza il
    loro timbro). Ora solo i campioni dell'elenco."""
    home = installazione_finta(tmp_path)
    prog, raw = tmp_path / "salame", tmp_path / "raw_condivisa"
    prog.mkdir()
    raw.mkdir()
    for s in ("SRR100", "SRR200"):
        for m in (1, 2):
            with gzip.open(raw / f"{s}_{m}.fastq.gz", "wt") as g:
                g.write(f"@{s}\nACGT\n+\nIIII\n")
    (prog / "srr.txt").write_text("SRR100\n", encoding="utf-8")
    cfg = prog / "config.yaml"
    cfg.write_text(f"project_name: salame\ndata_source: ncbi\nhosts: [sus_scrofa]\nfilter_human: false\n"
                   f"paths:\n  layout: custom\n  work_dir: {prog / 'lavoro'}\n  srr_list: {prog / 'srr.txt'}\n"
                   f"  raw_dir: {raw}\nprofiling:\n  tool: metaphlan\n", encoding="utf-8")
    r = subprocess.run(["bash", str(RADICE / "bin" / "run.sh"), "--config", str(cfg), "--skip-preflight", "--dry-run",
                        "--phase", "a"], capture_output=True, text=True, timeout=120, cwd=prog,
                       env={**os.environ, "PMN_HOME": str(home), "NO_COLOR": "1"})
    testo = r.stdout + r.stderr
    assert "trim_SRR100" in testo and "trim_SRR200" not in testo, testo


# ---------------- controllo cieco finale (22/10): elenco dei campioni ----------------
def raw_condivisa(tmp_path, srr_list, triage=False):
    """Progetto ncbi con raw_dir personalizzata che ha SRR100 e SRR200; config e cartella del progetto."""
    prog, raw = tmp_path / "salame", tmp_path / "raw_condivisa"
    prog.mkdir()
    raw.mkdir()
    for s in ("SRR100", "SRR200"):
        for m in (1, 2):
            with gzip.open(raw / f"{s}_{m}.fastq.gz", "wt") as g:
                g.write(f"@{s}\nACGT\n+\nIIII\n")
    (prog / "srr.txt").write_text(srr_list, encoding="utf-8")
    cfg = prog / "config.yaml"
    cfg.write_text(f"project_name: salame\ndata_source: ncbi\nhosts: [sus_scrofa]\nfilter_human: false\n"
                   f"triage:\n  enabled: {'true' if triage else 'false'}\n"
                   f"paths:\n  layout: custom\n  work_dir: {prog / 'lavoro'}\n  srr_list: {prog / 'srr.txt'}\n"
                   f"  raw_dir: {raw}\nprofiling:\n  tool: metaphlan\n", encoding="utf-8")
    return prog, cfg


def a_secco_fase_a(home, prog, cfg):
    r = subprocess.run(["bash", str(RADICE / "bin" / "run.sh"), "--config", str(cfg), "--skip-preflight", "--dry-run",
                        "--phase", "a"], capture_output=True, text=True, timeout=120, cwd=prog,
                       env={**os.environ, "PMN_HOME": str(home), "NO_COLOR": "1"})
    return r.stdout + r.stderr


@linux
def test_f1_srr_list_senza_a_capo_finale(tmp_path):
    """srr_list scritta a mano senza l'a capo finale: l'ultimo SRR si perdeva (e con l'elenco dei campioni del
    progetto non si sarebbe più nemmeno rifilato)."""
    home = installazione_finta(tmp_path)
    testo = a_secco_fase_a(home, *raw_condivisa(tmp_path, "SRR100\nSRR200"))
    assert "trim_SRR100" in testo and "trim_SRR200" in testo, testo


@linux
def test_f2_both_con_la_cartella_locale_vuota_l_elenco_non_e_completo(tmp_path):
    """data_source both e cartella delle read locali vuota (disco non montato su una cartella che esiste): l'elenco
    con i soli SRR non è completo, i profili dei campioni locali restano."""
    home = installazione_finta(tmp_path)
    prog = tmp_path / "salame"
    (prog / "lavoro" / "metaphlan").mkdir(parents=True)
    (tmp_path / "locali_vuota").mkdir()
    (prog / "srr.txt").write_text("SRR100\n", encoding="utf-8")
    cfg = prog / "config.yaml"
    cfg.write_text(f"project_name: salame\ndata_source: both\nhosts: [sus_scrofa]\nfilter_human: false\n"
                   f"paths:\n  work_dir: {prog / 'lavoro'}\n  srr_list: {prog / 'srr.txt'}\n"
                   f"  local_reads_dir: {tmp_path / 'locali_vuota'}\nprofiling:\n  tool: metaphlan\n"
                   f"  metaphlan_db: {prog}\n", encoding="utf-8")
    for _ in range(2):   # la prima corsa registra i parametri, la seconda riprende
        for s in ("SRR100", "L1"):
            (prog / "lavoro" / "metaphlan" / f"{s}_profile.txt").write_text(s, encoding="utf-8")
        subprocess.run(["bash", str(RADICE / "bin" / "run.sh"), "--config", str(cfg), "--skip-preflight", "--phase", "b"],
                       capture_output=True, text=True, timeout=120, cwd=prog,
                       env={**os.environ, "PMN_HOME": str(home), "NO_COLOR": "1"})
    assert (prog / "lavoro" / "metaphlan" / "L1_profile.txt").is_file()


@linux
def test_f3_triage_solo_sui_campioni_del_progetto(tmp_path):
    """raw_dir condivisa col triage acceso: il triage girava anche sulle read degli altri progetti."""
    home = installazione_finta(tmp_path)
    testo = a_secco_fase_a(home, *raw_condivisa(tmp_path, "SRR100\n", triage=True))
    assert "tq_SRR100" in testo and "tq_SRR200" not in testo, testo
