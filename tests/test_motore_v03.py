# -*- coding: utf-8 -*-
"""Contract v0.3 (docs/contratto_motore.md): the engine requests collected by the app pages (S5b, S6), on the real
engine (motore/pmn_motore.py) and on the fake one (installer/finto_motore.py), with the same events.
Criteria fixed before the data, one test (or more) per request 1-11."""
import gzip
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from contratto import PASSI, controlla

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
MOTORE = os.path.join(ROOT, "motore", "pmn_motore.py")
FINTO = os.path.join(ROOT, "installer", "finto_motore.py")
REFERTO = os.path.join(ROOT, "motore", "referto.py")
DATI = os.path.join(ROOT, "installer", "finto")
sys.path.insert(0, os.path.join(ROOT, "motore"))
import pmn_motore  # noqa: E402
import referto  # noqa: E402
import system_one  # noqa: E402
from fssp.validita import numero_it  # noqa: E402

SALSICCIA = {"prodotto": {"temperatura": 5, "sale_fase_acquosa": 3.5, "ph": 6.0, "nitrito": 100}, "giorni": 21}


def vero(tmp_path, *arg):
    env = {**os.environ, "PMN_HOME": str(tmp_path / "pmn_vuota")}
    r = subprocess.run([sys.executable, MOTORE, *arg], capture_output=True, text=True, encoding="utf-8",
                       timeout=120, env=env)
    return controlla(r.stdout, r.returncode, arg[0]), r.returncode


def finto(tmp_path, *arg, velocita="0"):
    """Fake engine with its own TEMP (its lock and logs live there), as the app tests do."""
    env = {**os.environ, "TEMP": str(tmp_path), "TMP": str(tmp_path), "TMPDIR": str(tmp_path)}
    r = subprocess.run([sys.executable, FINTO, *arg, "--velocita", velocita], capture_output=True, text=True,
                       encoding="utf-8", timeout=120, env=env)
    return controlla(r.stdout, r.returncode, arg[0]), r.returncode


def progetto(tmp_path, testo="project_name: prova\n"):
    p = tmp_path / "progetto" / "config.yaml"
    p.parent.mkdir(exist_ok=True)
    p.write_text(testo, encoding="utf-8")
    return p


def read_finte(cartella, nomi, righe=1000):
    cartella.mkdir(exist_ok=True)
    for n in nomi:
        with gzip.open(cartella / n, "wt") as f:
            f.write("@r\nACGT\n+\nIIII\n" * righe)


# ---------------- 1. prodotto -> ospite (system_one, info) ----------------
def test_1_regola_prodotto_ospite():
    p = {x["prodotto"]: x for x in system_one.prodotti()}
    assert list(p)[:4] == ["maiale", "bovino", "pecora", "altro"]               # ordine del menu (D074); poi R9
    assert p["maiale"]["ospiti"] == ["sus_scrofa"] and p["maiale"]["genomi"] == ["Sscrofa11.1"]
    assert p["bovino"]["ospiti"] == ["bos_taurus"] and p["bovino"]["genomi"] == ["ARS-UCD1.2"]
    assert p["pecora"]["ospiti"] == ["ovis_aries"] and p["pecora"]["genomi"] == ["ARS-UI_Ramb_v2.0"]
    assert p["altro"]["ospiti"] == [] and p["altro"]["livello"] == "avviso"
    assert all(x["frase"] and x["perche"] and x["fonte"] and x["livello"] in ("info", "avviso") for x in p.values())
    with open(os.path.join(ROOT, "refs", "hosts.tsv"), encoding="utf-8") as f:   # ospiti che il motore conosce
        noti = f.read()
    assert all(o in noti for x in p.values() for o in x["ospiti"])


def test_1_info_vero_e_finto_danno_la_regola(tmp_path):
    a, _ = vero(tmp_path, "info")
    b, _ = finto(tmp_path, "info")
    assert a[-1]["risultato"]["prodotti"] == b[-1]["risultato"]["prodotti"] == system_one.prodotti()


# ---------------- 2. stima: tempo totale ----------------
def test_2_stima_tempo_totale(tmp_path):
    read_finte(tmp_path / "read", ["C1_R1.fastq.gz", "C1_R2.fastq.gz"])
    cfg = progetto(tmp_path, f"data_source: local\npaths:\n  local_reads_dir: {tmp_path / 'read'}\n")
    for ev, rc in (vero(tmp_path, "stima", "--progetto", str(cfg)), finto(tmp_path, "stima", "--progetto", str(cfg))):
        r = ev[-1]["risultato"]
        assert rc == 0 and r["tempo_totale_s"] == sum(r["tempo_s"].values()) > 0


# ---------------- 3. Bracken -t dal progetto ----------------
@pytest.mark.skipif(os.name == "nt", reason="bin/run.sh: Linux/WSL only")
@pytest.mark.parametrize("scritto, atteso", [("", "10"), ("25", "25")])
def test_3_bracken_t_dal_progetto(tmp_path, scritto, atteso):
    """run.sh --dry-run scrive parameters.tsv: vuoto = profilo del database (10), un valore scritto vince."""
    envs = tmp_path / "envs" / "pmn_reports_py" / "bin"
    envs.mkdir(parents=True)
    os.symlink(sys.executable, envs / "python")     # parse_config.py con PyYAML, come il motore installato
    home = tmp_path / "pmn"
    home.mkdir()
    (home / "installazione.env").write_text(f"PMN_ENVS={tmp_path / 'envs'}\nPMN_TMP={tmp_path / 'tmp'}\n", encoding="utf-8")
    read_finte(tmp_path / "read", ["C1_R1.fastq.gz", "C1_R2.fastq.gz"], righe=1)
    cfg = progetto(tmp_path, f"project_name: prova\ndata_source: local\npaths:\n  work_dir: {tmp_path / 'lavoro'}\n"
                             f"  local_reads_dir: {tmp_path / 'read'}\nprofiling:\n  bracken_min_reads: \"{scritto}\"\n"
                             "motore: {kraken_db: rapido}\n")
    subprocess.run(["bash", os.path.join(ROOT, "bin", "run.sh"), "--config", str(cfg), "--dry-run", "--skip-preflight"],
                   capture_output=True, text=True, timeout=120, cwd=cfg.parent, env={**os.environ, "PMN_HOME": str(home)})
    par = dict(r.split("\t") for r in (tmp_path / "lavoro" / "results" / "parameters.tsv").read_text().splitlines()[1:])
    assert par["bracken_min_reads"] == atteso


@pytest.mark.skipif(os.name == "nt", reason="bin/run.sh: Linux/WSL only")
def test_3_bracken_t_non_valido(tmp_path):
    cfg = progetto(tmp_path, "profiling:\n  bracken_min_reads: tanti\n")
    r = subprocess.run([sys.executable, os.path.join(ROOT, "bin", "lib", "parse_config.py"), str(cfg)],
                       capture_output=True, text=True, timeout=60)
    assert "PMN_KRK_MINREADS=tanti" in r.stdout          # arriva a run.sh, che lo rifiuta con validate_uint
    v = subprocess.run(["bash", "-c", f". {os.path.join(ROOT, 'bin', 'lib', 'validate.sh')} && validate_uint tanti"])
    assert v.returncode != 0


def test_3_referto_dice_se_e_scelto_nel_progetto():
    righe = referto.righe_parametri({"parametri": {"kraken_profile": "rapido", "bracken_min_reads": "25"}})
    fonte = {r[0]: r[3] for r in righe}["Letture minime di Bracken (-t)"]
    assert fonte == "scelto nel progetto (consigliato per 'rapido': 10)"


# ---------------- 4. nomi dei campioni locali ----------------
def test_4_nomi_locali_come_run_sh(tmp_path):
    read_finte(tmp_path / "read", ["A_R1.fastq.gz", "A_R2.fastq.gz", "B_1.fq.gz", "B_2.fq.gz", "C03_1_R1.fastq.gz",
                                   "C03_1_R2.fastq.gz", "D_R1_001.fastq.gz", "D_R2_001.fastq.gz", "solo.fastq.gz",
                                   "orfano_R1.fastq.gz"])
    (tmp_path / "read" / "note.txt").write_text("x", encoding="utf-8")
    nomi = dict(pmn_motore.campioni_locali(tmp_path / "read"))
    assert sorted(nomi) == ["A", "B", "C03_1", "D", "solo"]          # orfano: senza compagna si salta, come run.sh
    assert nomi["C03_1"] == ["C03_1_R1.fastq.gz", "C03_1_R2.fastq.gz"] and nomi["solo"] == ["solo.fastq.gz"]
    cfg = progetto(tmp_path, f"data_source: local\npaths:\n  local_reads_dir: {tmp_path / 'read'}\n")
    ev, rc = vero(tmp_path, "stima", "--progetto", str(cfg))
    assert rc == 0 and sorted(ev[-1]["risultato"]["nomi_campioni"]) == ["A", "B", "C03_1", "D", "solo"]
    assert ev[-1]["risultato"]["campioni"] == 5


# ---------------- 5. fonti dei parametri in italiano ----------------
def test_5_fonti_kraken_in_italiano():
    with open(os.path.join(ROOT, "refs", "kraken_profili.tsv"), encoding="utf-8") as f:
        fonti = [r.split("\t")[4] for r in f.read().splitlines() if r and not r.startswith("#")]
    assert len(fonti) == 2
    for fonte in fonti:
        assert not re.search(r"\b(threshold|within|full|quick|not stated|reduced|as completo)\b", fonte), fonte
        assert "soglia" in fonte and re.search(r"\d,\d", fonte)          # parole e numeri all'italiana
    assert "Wright, Comeau & Langille 2023" in fonti[1] and "Edwin et al. 2024" in fonti[1] and "K4" in fonti[0]


# ---------------- 6. dominanti piu' lunghi ----------------
def test_6_dominanti_fino_a_15(tmp_path):
    cfg = progetto(tmp_path)
    ev, rc = finto(tmp_path, "esegui", "--progetto", str(cfg))
    s = ev[-1]["risultato"]["campioni"][0]["sintesi"]
    m, k = s["metaphlan"]["dominanti"], s["kraken"]["dominanti"]
    assert rc == 0 and len(m) == 15 and len(k) == 15                    # 27 specie MetaPhlAn (nessuna soglia) e 48 taxa Kraken sopra la soglia
    assert [x["pct"] for x in m] == sorted((x["pct"] for x in m), reverse=True)
    assert m[0]["nome"] == "Latilactobacillus sakei" and k[0]["nome"] == "Latilactobacillus sakei"
    assert "dominano Latilactobacillus sakei" in s["metaphlan"]["frase"]
    assert s["metaphlan"]["frase"].count("% delle read)") == 3           # la frase ne nomina ancora 3
    # il risultati.json del finto e' quello che il motore calcola oggi dai profili veri
    d = referto.leggi_campione(Path(DATI),{"metaphlan": "SRR4875279_profile.txt",
                                                                   "kraken": "SRR4875279.bracken"})
    assert referto.sintesi(d, 0.005) == s


def test_6_metaphlan_senza_soglia():
    """18/10: la soglia vale solo per Kraken; MetaPhlAn tiene anche la specie allo 0,001 %."""
    d = {"metaphlan": [("Specie a", 60.0), ("Specie b", 0.001)], "non_classificato": 40.0, "kraken": None}
    assert [x["nome"] for x in referto.sintesi(d, 0.005)["metaphlan"]["dominanti"]] == ["Specie a", "Specie b"]


# ---------------- 7. valore finale in ufc/g ----------------
def test_7_finale_in_ufc_g(tmp_path):
    f = tmp_path / "r.json"
    for richiesta in (SALSICCIA, dict(SALSICCIA, conte={"lab_ufc_g": 1e6})):
        f.write_text(json.dumps(richiesta), encoding="utf-8")
        a, _ = vero(tmp_path, "sicurezza", "--ingresso", str(f))
        b, _ = finto(tmp_path, "sicurezza", "--ingresso", str(f))
        assert a[-1]["risultato"]["previsioni"] == b[-1]["risultato"]["previsioni"]
        for p in a[-1]["risultato"]["previsioni"]:
            assert p["finale_listeria_ufc_g"] == float(f"{10 ** p['curva']['log_listeria'][-1]:.2g}")
            if p["modello"] == "listeria_lab":
                assert p["finale_lab_ufc_g"] == float(f"{10 ** p['curva']['log_lab'][-1]:.2g}")
    f.write_text(json.dumps(SALSICCIA), encoding="utf-8")
    ev, _ = vero(tmp_path, "sicurezza", "--ingresso", str(f))
    assert [p["finale_listeria_ufc_g"] for p in ev[-1]["risultato"]["previsioni"]] == [300.0, 30000.0]   # app S6


# ---------------- 8. REFERTO_PARZIALE in italiano ----------------
def test_8_referto_parziale_in_italiano(tmp_path):
    p = tmp_path / "SF3RAt7"
    for sotto in ("metaphlan", "kraken", "tabelle"):
        (p / "risultati" / sotto).mkdir(parents=True)
    shutil.copy(os.path.join(DATI, "SRR4875279_profile.txt"), p / "risultati" / "metaphlan")
    for est in ("bracken", "k2report"):
        shutil.copy(os.path.join(DATI, f"SRR4875279.{est}"), p / "risultati" / "kraken")
    shutil.copy(os.path.join(DATI, "parameters.tsv"), p / "risultati" / "tabelle")
    shutil.copy(os.path.join(DATI, "risultati.json"), p / "risultati")
    codice = ("import runpy, sys; sys.modules['openpyxl'] = None; sys.modules['PySide6'] = None; "   # moduli assenti
              f"sys.argv = ['referto.py', '--risultati', {str(p / 'risultati')!r}]; runpy.run_path({REFERTO!r}, run_name='__main__')")
    r = subprocess.run([sys.executable, "-c", codice], capture_output=True, text=True, encoding="utf-8", timeout=120)
    esito = json.loads(r.stdout.strip().splitlines()[-1])
    assert esito["html"] and not esito["xlsx"] and not esito["pdf"]
    assert esito["problemi"] == ["manca l'Excel: nel motore non c'è il modulo che lo scrive (openpyxl)",
                                 "manca il PDF: nel motore non c'è il modulo che lo scrive (PySide6)"]
    assert any("ModuleNotFoundError" in d or "ImportError" in d for d in esito["dettagli"])   # per il log
    testo = referto.avviso_parziale(esito["problemi"], True)
    assert testo.startswith("Il referto non è completo: manca l'Excel") and "si apre lo stesso" in testo
    assert not re.search(r"Error|not created|No module", testo)
    assert "manca la pagina del referto" in referto.avviso_parziale(["il programma del referto non ha risposto"], False)


# ---------------- 9. fine piu' specifico dopo un errore ----------------
def test_9_fine_dice_passo_e_cosa_fare(tmp_path):
    cfg = progetto(tmp_path)
    ev, rc = finto(tmp_path, "esegui", "--progetto", str(cfg), "--scenario", "DB_MANCANTE")
    assert rc == 2 and ev[-1]["risultato"] == {"codice": "DB_MANCANTE", "passo": "kraken"}
    assert ev[-1]["messaggio"] == ("Problema durante la classificazione con Kraken e Bracken. Manca il database di "
                                   "Kraken. Apri la pagina Motore e premi Installa o completa.")
    ev, rc = finto(tmp_path, "esegui", "--progetto", str(tmp_path / "manca.yaml"))
    assert ev[-1]["messaggio"] == "Non trovo il file del progetto. Salva il progetto e riprova."   # prima di un passo
    ev, rc = vero(tmp_path, "verifica")
    assert rc == 2 and ev[-1]["messaggio"] == "Il motore non è ancora installato. Apri la pagina Motore e premi Installa o completa."
    assert set(pmn_motore.NOMI_PASSI) <= PASSI                          # solo passi del contratto


@pytest.mark.skipif(os.name == "nt", reason="run.sh stub: Linux/WSL only")
def test_9_fine_del_motore_vero_durante_un_passo(tmp_path):
    from test_pmn_motore import STUB
    home = tmp_path / "pmn"
    (home / "stato").mkdir(parents=True)
    (home / "installazione.env").write_text(f"PMN_ENVS={tmp_path / 'envs'}\n", encoding="utf-8")
    (tmp_path / "stub.sh").write_text(STUB, encoding="utf-8")
    (tmp_path / "srr.txt").write_text("S1\n", encoding="utf-8")
    cfg = progetto(tmp_path, f"paths:\n  work_dir: {tmp_path / 'lavoro'}\n  srr_list: {tmp_path / 'srr.txt'}\n")
    env = {**os.environ, "PMN_HOME": str(home), "PMN_RUN_SH": str(tmp_path / "stub.sh"), "STUB_MODO": "spazio",
           "PMN_ATTESA_RETE": "0"}
    r = subprocess.run([sys.executable, MOTORE, "esegui", "--progetto", str(cfg)], capture_output=True, text=True,
                       encoding="utf-8", timeout=60, env=env)
    ev = controlla(r.stdout, r.returncode, "esegui")
    assert ev[-1]["risultato"] == {"codice": "SPAZIO_INSUFFICIENTE", "passo": "download"}
    assert ev[-1]["messaggio"] == ("Problema durante lo scaricamento delle read. Lo spazio libero non basta per "
                                   "scaricare le read. Libera spazio sul disco e riprova.")


# ---------------- 10. FSSP: maiuscole e numeri all'italiana ----------------
def test_10_numeri_all_italiana():
    assert [numero_it(v) for v in (13.9875, 60000, 5.0, 0.7, 11000.0, 2.5)] == ["13,99", "60.000", "5", "0,7",
                                                                                 "11.000", "2,5"]


def test_10_avvisi_e_note_fssp(tmp_path):
    f = tmp_path / "r.json"
    f.write_text(json.dumps({"prodotto": {"temperatura": 15, "aw": 0.9, "ph": 5.4}, "giorni": 30,
                             "profilo_specie": {"s__Leuconostoc_carnosum": 30.0, "s__Latilactobacillus_sakei": 20.0},
                             "conte": {"totale_ufc_g": 1e6}}), encoding="utf-8")
    ev, rc = vero(tmp_path, "sicurezza", "--ingresso", str(f))
    r = ev[-1]["risultato"]
    testi = [a["messaggio"] for a in r["avvisi"]] + r["note"] + [e["messaggio"] for e in ev if e["tipo"] == "avviso"]
    assert rc == 0 and r["avvisi"]
    assert not [t for t in testi if re.search(r"\d\.\d", t)], testi                  # nessun 13.9875
    assert any("sale nella fase acquosa (%) = 13,99" in a["messaggio"] for a in r["avvisi"])
    assert any("Leuconostoc carnosum" in n for n in r["note"])                         # maiuscola nel testo
    assert any("LAB iniziali = 20 %" in n for n in r["note"])
    assert r["ponte"]["lab_trovati"] == ["latilactobacillus sakei"]                    # chiavi invariate
    f.write_text(json.dumps({"prodotto": {"ph": 12.5}, "giorni": 30}), encoding="utf-8")
    ev, rc = vero(tmp_path, "sicurezza", "--ingresso", str(f))
    assert rc == 1 and "ph = 12,5: fuori da 2-10" in ev[-2]["messaggio"]


# ---------------- 11. finto: lucchetto col pid, stima coerente con esegui ----------------
def test_11_lucchetto_rimasto_non_blocca(tmp_path):
    cfg = progetto(tmp_path)
    stato = tmp_path / "pmn_finto"
    stato.mkdir()
    figlio = subprocess.Popen([sys.executable, "-c", "pass"])
    figlio.wait()                                                       # un pid che non c'e' piu'
    for vecchio in (json.dumps({"corsa": "2026-10-16T10-00-00", "pid": figlio.pid}), "2026-10-16T10-00-00"):
        (stato / "esegui.lock").write_text(vecchio, encoding="utf-8")    # nuovo formato, e quello di prima
        ev, rc = finto(tmp_path, "esegui", "--progetto", str(cfg))
        assert rc == 0 and ev[-1]["esito"] == "ok"
        assert not (stato / "esegui.lock").exists()


def test_11_lucchetto_vivo_blocca(tmp_path):
    cfg = progetto(tmp_path)
    stato = tmp_path / "pmn_finto"
    stato.mkdir()
    (stato / "esegui.lock").write_text(json.dumps({"corsa": "x", "pid": os.getpid()}), encoding="utf-8")
    ev, rc = finto(tmp_path, "esegui", "--progetto", str(cfg))
    assert rc == 1 and ev[-2]["codice"] == "GIA_IN_CORSO"
    assert (stato / "esegui.lock").exists()                              # quello di un altro: non si tocca
    ev, _ = finto(tmp_path, "annulla", "--corsa", "x")
    assert ev[-1]["risultato"] == {"annullata": True}


@pytest.mark.parametrize("kraken_db, messaggio", [("completo", "database completo"), ("rapido", "screening rapido")])
def test_11_stima_coerente_con_esegui(tmp_path, kraken_db, messaggio):
    """17/10: il finto usa tempi() del vero (stesse regole, tutti i passi): stima ed esegui danno lo stesso totale."""
    cfg = progetto(tmp_path, f"project_name: prova\nhosts: [sus_scrofa]\nmotore: {{kraken_db: {kraken_db}}}\n")
    stima, _ = finto(tmp_path, "stima", "--progetto", str(cfg))
    t = stima[-1]["risultato"]
    assert t["tempo_s"] == pmn_motore.tempi([("SRR4875279", 3240847, 533522098)],
                                            {"hosts": ["sus_scrofa"], "motore": {"kraken_db": kraken_db}})
    ev, rc = finto(tmp_path, "esegui", "--progetto", str(cfg), velocita="1000000")
    minuti = int(re.search(r"Analisi finita in (\d+) min", ev[-1]["messaggio"]).group(1))
    assert rc == 0 and minuti == round(t["tempo_totale_s"] / 60)
    assert any(messaggio in e["messaggio"] for e in ev if e.get("passo") == "kraken")
