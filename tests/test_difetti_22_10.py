# -*- coding: utf-8 -*-
"""Difetti aperti corretti il 22/10/2026 (estensione della sessione QC).
Ogni test è rosso sul codice di c610320 e verde dopo la correzione.
Gira con la suite del motore:  ~/miniforge3/envs/pmn_reports_py/bin/python -m pytest tests/test_difetti_22_10.py"""
import os
import subprocess
import sys

import pytest

from test_motore_v03 import ROOT, progetto, read_finte

linux = pytest.mark.skipif(os.name == "nt", reason="bin/run.sh: Linux/WSL only")


def parametri(tmp_path, strumento):
    """parameters.tsv scritto da run.sh --dry-run per un progetto con il solo metodo dato."""
    envs = tmp_path / "envs" / "pmn_reports_py" / "bin"
    envs.mkdir(parents=True)
    os.symlink(sys.executable, envs / "python")     # parse_config.py con PyYAML, come il motore installato
    home = tmp_path / "pmn"
    home.mkdir()
    (home / "installazione.env").write_text(f"PMN_ENVS={tmp_path / 'envs'}\nPMN_TMP={tmp_path / 'tmp'}\n", encoding="utf-8")
    read_finte(tmp_path / "read", ["C1_R1.fastq.gz", "C1_R2.fastq.gz"], righe=1)
    cfg = progetto(tmp_path, f"project_name: prova\ndata_source: local\npaths:\n  work_dir: {tmp_path / 'lavoro'}\n"
                             f"  local_reads_dir: {tmp_path / 'read'}\nprofiling:\n  tool: {strumento}\n"
                             "motore: {kraken_db: rapido}\n")
    subprocess.run(["bash", os.path.join(ROOT, "bin", "run.sh"), "--config", str(cfg), "--dry-run", "--skip-preflight"],
                   capture_output=True, text=True, timeout=120, cwd=cfg.parent, env={**os.environ, "PMN_HOME": str(home)})
    righe = (tmp_path / "lavoro" / "results" / "parameters.tsv").read_text().splitlines()[1:]
    return dict(r.split("\t") for r in righe)


KRAKEN = {"kraken_db", "kraken_profile", "kraken_confidence", "bracken_min_reads", "bracken_readlen",
          "abundance_threshold_pct"}


# ---------------- A2: parameters.tsv solo con i parametri dei metodi che girano ----------------
@linux
def test_a2_solo_metaphlan_niente_parametri_di_kraken(tmp_path):
    par = parametri(tmp_path, "metaphlan")
    assert not KRAKEN & set(par), par                       # prima: kraken_* e soglia 0.001 anche senza Kraken
    assert {"metaphlan_mode", "metaphlan_index", "hosts", "filter_human"} <= set(par)


def test_a3_beta_di_kraken_solo_taxa_del_prodotto(tmp_path):
    """La beta di Kraken (41_diversity.R) leggeva kraken_matrix.tsv con Homo, Leishmania e virus. Ora il passo 33
    scrive anche kraken_matrix_taxa.tsv: batteri, archei e funghi alla soglia o sopra (% sul totale assegnato), gli
    stessi taxa del profilo di Kraken nel referto (D023, D128)."""
    pd = pytest.importorskip("pandas")
    import shutil
    sys.path.insert(0, os.path.join(ROOT, "motore"))
    import referto
    dati = os.path.join(ROOT, "installer", "finto")
    for est in ("bracken", "k2report"):
        shutil.copy(os.path.join(dati, f"SRR4875279.{est}"), tmp_path)
    r = subprocess.run([sys.executable, os.path.join(ROOT, "steps", "33_kraken_matrix.py"), "--in", str(tmp_path),
                        "--out", str(tmp_path / "m.tsv"), "--taxa-out", str(tmp_path / "t.tsv"), "--threshold-pct", "0.005"],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    tutti = pd.read_csv(tmp_path / "m.tsv", sep="\t", index_col=0)["SRR4875279"]
    taxa = pd.read_csv(tmp_path / "t.tsv", sep="\t", index_col=0)["SRR4875279"]
    assert {"Homo sapiens", "Leishmania mexicana"} <= set(tutti.index)              # la matrice intera resta com'era
    assert not {"Homo sapiens", "Leishmania mexicana"} & set(taxa.index)
    attesi = {x["nome"] for x in referto.leggi_kraken(tmp_path / "SRR4875279.bracken", tmp_path / "SRR4875279.k2report")
              if x["categoria"] in referto.MICROBI and x["pct"] >= 0.005}
    assert set(taxa[taxa > 0].index) == attesi and len(attesi) == 48                # i 48 taxa del referto
    assert taxa["Latilactobacillus sakei"] == pytest.approx(tutti["Latilactobacillus sakei"])   # % sul totale assegnato


@linux
@pytest.mark.parametrize("strumento", ["kraken", "both"])
def test_a2_con_kraken_i_suoi_parametri_restano(tmp_path, strumento):
    par = parametri(tmp_path, strumento)
    assert KRAKEN <= set(par) and par["abundance_threshold_pct"] == "0.005"    # profilo rapido
    assert ("metaphlan_mode" in par) is (strumento == "both")


# ---------------- B4: numeri della tabella "Parametri" all'italiana ----------------
def test_b4_parametri_con_la_virgola():
    """Il referto italiano scriveva "0.1" e "0.005" nella colonna Valore (e la soglia nel foglio Leggimi)."""
    sys.path.insert(0, os.path.join(ROOT, "motore"))
    import referto
    par = referto.tsv_dict(os.path.join(ROOT, "installer", "finto", "parameters.tsv"))
    valori = {nome: v for nome, v, _, _ in referto.righe_parametri({"parametri": par})}
    assert valori["Confidenza di Kraken (--confidence)"] == "0,1"
    assert valori["Soglia di abbondanza di Kraken (%)"] == "0,005"
    fonti = [f for _, _, _, f in referto.righe_parametri({"parametri": {**par, "kraken_confidence": "0.25"}})]
    assert "scelto nel progetto (consigliato per 'rapido': 0,1)" in fonti


# ---------------- C6-C10: installer/installa_motore.sh e messaggi di run.sh ----------------
INSTALLA = os.path.join(ROOT, "installer", "installa_motore.sh")


def stima(home, catalogo):
    import json
    env = {**os.environ, "PMN_HOME": str(home)}
    env.pop("PMN_URL_PACCHETTI", None)
    r = subprocess.run(["bash", INSTALLA, "--json", "--stima", "--catalogo", str(catalogo), "--specchio", "http://127.0.0.1:9"],
                       capture_output=True, text=True, encoding="utf-8", env=env, timeout=120)
    return [json.loads(x) for x in r.stdout.splitlines()], r.returncode


@pytest.fixture
def su_disco():
    """Sul disco, non in /tmp: la WSL tiene /tmp in RAM (~6 GB), meno dei 16 GB per i programmi (test_installa_eventi)."""
    import shutil
    import tempfile
    from pathlib import Path
    d = Path(tempfile.mkdtemp(prefix="pmn_test_", dir=Path.home()))
    yield d
    shutil.rmtree(d, ignore_errors=True)


@linux
def test_c6_programmi_gia_installati_niente_16_gb(su_disco):
    """Lo spazio dei programmi (16 GB) si contava anche con tutti gli ambienti già installati."""
    import glob
    from test_installa_eventi import catalogo
    home, c = catalogo(su_disco)
    ev, rc = stima(home, c)
    assert rc == 0 and ev[-1]["risultato"]["spazio_necessario_gb"] == 14.9      # 16e9 byte = 14,9 GB di Esplora file
    for lock in glob.glob(os.path.join(ROOT, "installer", "lock", "*.txt")):   # ambienti uguali ai file di blocco
        meta = home / "mamba" / "envs" / os.path.basename(lock)[:-4] / "conda-meta"
        meta.mkdir(parents=True)
        for r in open(lock, encoding="utf-8"):
            if r.startswith("https://"):
                nome = r.strip().rsplit("/", 1)[1].split("#")[0].replace(".conda", "").replace(".tar.bz2", "")
                (meta / f"{nome}.json").write_text("{}", encoding="utf-8")
    ev, rc = stima(home, c)
    assert rc == 0 and ev[-1]["risultato"]["spazio_necessario_gb"] == 0.0


def test_c7_misura_della_rete_con_un_limite_di_tempo():
    misura = [r for r in open(INSTALLA, encoding="utf-8") if "speed_download" in r]
    assert len(misura) == 1 and "--max-time" in misura[0]


@linux
def test_c8_gb_come_esplora_file():
    testo = open(INSTALLA, encoding="utf-8").read()
    assert "b/1e9" not in testo and '"$b" 1e9' not in testo
    righe = "\n".join(r for r in testo.splitlines() if r.startswith(("GIB=", "GB()", "num()")))
    out = subprocess.run(["bash", "-c", f"LINGUA=it\n{righe}\nGB 1073741824; echo; num 1610612736 $GIB 1"],
                         capture_output=True, text=True).stdout.split()
    assert out == ["1", "1,5"]


@linux
def test_c9_fine_dopo_un_errore_ha_il_passo(tmp_path):
    import json
    r = subprocess.run(["bash", INSTALLA, "--json", "--stima", "--catalogo", str(tmp_path / "manca.tsv")],
                       capture_output=True, text=True, encoding="utf-8", env={**os.environ, "PMN_HOME": str(tmp_path / "h")})
    ev = [json.loads(x) for x in r.stdout.splitlines()]
    assert ev[-2]["tipo"] == "errore" and ev[-2]["passo"] == "controllo"
    assert ev[-1]["risultato"] == {"codice": "CONFIG_NON_VALIDA", "passo": "controllo"}


def test_c10_accenti_veri_nei_messaggi_di_run_sh():
    import re
    righe = [r for r in open(os.path.join(ROOT, "bin", "run.sh"), encoding="utf-8") if not r.lstrip().startswith("#")]
    assert not [r for r in righe if re.search(r"\b(e|piu|gia|puo|velocita|cosi)'(?=[\s.,:;)!?])", r)]


# ---------------- D11: finto motore con percorsi oltre 260 caratteri (Windows) ----------------
@pytest.mark.skipif(os.name != "nt", reason="limite di 260 caratteri: solo Windows")
@pytest.mark.parametrize("lingua", ["it", "en"])
def test_d11_finto_motore_con_percorsi_lunghi(tmp_path, lingua):
    """Cartella del progetto di 225 caratteri: risultati/kraken/SRR4875279.k2report ne ha 262. Prima: traceback a
    finto_motore.py:268 e nessun evento "fine"; ora la corsa finisce e i file ci sono."""
    import shutil
    from contratto import controlla
    base = tmp_path.resolve()
    p = base / ("a" * 60) / ("b" * (225 - len(str(base)) - 62))
    p.mkdir(parents=True)
    cfg = p / "config.yaml"
    cfg.write_text("project_name: prova\n", encoding="utf-8")
    try:
        r = subprocess.run([sys.executable, os.path.join(ROOT, "installer", "finto_motore.py"), "esegui", "--progetto",
                            str(cfg), "--velocita", "0", "--lingua", lingua], capture_output=True, text=True,
                           encoding="utf-8", timeout=120)
        ev = controlla(r.stdout, r.returncode, "esegui")
        assert r.returncode == 0 and ev[-1]["esito"] == "ok", r.stdout[-500:] + r.stderr[-1500:]
        assert ev[-1]["risultato"]["cartella"] == str(p / "risultati")
        lungo = "\\\\?\\" +str(p / "risultati" / "kraken" / "SRR4875279.k2report")
        assert len(lungo) > 264 and os.path.isfile(lungo)
        assert os.path.isfile("\\\\?\\" +str(p / "risultati" / "referto" / "referto.html"))
    finally:
        shutil.rmtree("\\\\?\\" +str(base / ("a" * 60)), ignore_errors=True)


# ---------------- D12: .gitattributes copre il referto del finto motore ----------------
def test_d12_referto_del_finto_sempre_lf():
    """Con core.autocrlf=true (Windows) referto.html usciva con CRLF: test_r7 lo confronta al byte con uno nuovo (LF)."""
    r = subprocess.run(["git", "check-attr", "eol", "text", "--", "installer/finto/referto/referto.html",
                        "installer/finto/referto/referto.xlsx"], capture_output=True, text=True, cwd=ROOT)
    if r.returncode != 0:
        pytest.skip("git non legge questo repository da qui (worktree aperto dalla WSL)")
    assert "referto.html: eol: lf" in r.stdout
    assert "referto.xlsx: text: unset" in r.stdout
