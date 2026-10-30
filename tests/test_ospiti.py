# -*- coding: utf-8 -*-
"""R8 (incarico OSPITE, 30/10): ospite da togliere personalizzabile, lato motore.
motore/ospiti.py (regole e stima), steps/11_host_index.sh --fasta, bin/run.sh (ospiti_personali, indice riusato in
PMN_HOME/ospiti_utente, origine nel parameters.tsv), motore/pmn_motore.py (tempo dell'indice, citazione).
bowtie2-build e datasets sono finti: la costruzione vera è misurata a mano (RESOCONTO_OSPITE.md).
Gira con la suite del motore:  ~/miniforge3/envs/pmn_reports_py/bin/python -m pytest tests/test_ospiti.py"""
import gzip
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

RADICE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADICE / "motore"))
import ospiti  # noqa: E402

linux = pytest.mark.skipif(os.name == "nt" or not shutil.which("bash"), reason="bash steps: Linux/WSL only")
# bowtie2-build finto: scrive i 6 file dell'indice (come il vero, con il prefisso dato) e annota il FASTA letto
BOWTIE2_BUILD = """#!/bin/sh
[ "$1" = --version ] && { echo "bowtie2-build-s version 2.5.5"; exit 0; }
while [ "$1" = --threads ]; do shift 2; done
echo "$1" >> "${FINTO_LOG:-/dev/null}"
for s in 1 2 3 4 rev.1 rev.2; do echo indice > "$2.$s.bt2"; done
"""


# ---------------- motore/ospiti.py ----------------
def test_nomi_validi_e_non_validi():
    assert ospiti.controlla("olivo", {"accession": "GCF_000000001.1"}) == ("accession", "GCF_000000001.1")
    for nome in ("o", "1olivo", "olivo-capra", "olivo.x", "olìvo", "olivo; rm", "sus_scrofa", "grch38", "a" * 41, None):
        with pytest.raises(ValueError):
            ospiti.controlla(nome, {"accession": "GCF_000000001.1"})


def test_accession_valide_e_non_valide():
    for acc in ("GCF_030704535.1", "GCA_000001405.29"):
        assert ospiti.controlla("vite_x", {"accession": acc})[1] == acc
    for acc in ("GCF_03070453.1", "GCF_030704535", "gcf_030704535.1", "GCX_030704535.1", "GCF_030704535.1; ls",
                "GCF_030704535.1\n", "$(GCF_030704535.1)", 12):
        with pytest.raises(ValueError):
            ospiti.controlla("vite_x", {"accession": acc})
    with pytest.raises(ValueError):   # una sola delle due strade
        ospiti.controlla("vite_x", {"accession": "GCF_030704535.1", "fasta": "/a/b.fa"})
    with pytest.raises(ValueError):
        ospiti.controlla("vite_x", {})


def test_percorsi_fasta():
    assert ospiti.controlla("olivo", {"fasta": "/mnt/c/Users/io/l'olivo/genoma.fna.gz"})[1].endswith("genoma.fna.gz")
    for p in ("/mnt/c/$(touch x)/g.fa", "/mnt/c/`id`/g.fa", "/a/b;c/g.fa", "relativo/g.fa", "/a/../etc/g.fa",
              "/a/g.txt", "/a/g.fa\n", "-/g.fa"):
        with pytest.raises(ValueError):
            ospiti.controlla("olivo", {"fasta": p})


def test_personali_solo_quelli_in_hosts():
    cfg = {"hosts": ["olivo"], "ospiti_personali": {"olivo": {"accession": "GCF_000000001.1"},
                                                    "altro": {"fasta": "/x;y.fa"}}}   # non usato: non si controlla
    assert ospiti.personali(cfg) == {"olivo": ("accession", "GCF_000000001.1")}
    with pytest.raises(ValueError):
        ospiti.personali({"hosts": ["olivo"], "ospiti_personali": ["olivo"]})


def test_stima_dalle_misure():
    """La formula ritrova le misure: maiale 2,47 Gbp 17,6 min e 5,3 GB; uomo 3,14 Gbp 22,5 min e 7,2 GB."""
    maiale, uomo = ospiti.stima(2_472_047_704), ospiti.stima(3_136_819_154)
    assert abs(maiale["secondi"] / 60 - 17.6) < 1.5 and abs(maiale["ram_gb"] - 5.3) < 0.8
    assert abs(uomo["secondi"] / 60 - 22.5) < 1.5 and abs(uomo["ram_gb"] - 7.2) < 0.8
    assert ospiti.stima(10**9, scaricare=True)["secondi"] > ospiti.stima(10**9)["secondi"]


def test_hosts_tsv_ha_la_vite():
    righe = {r.split("\t")[0]: r.split("\t")[1] for r in (RADICE / "refs" / "hosts.tsv").read_text(encoding="utf-8")
             .splitlines() if r.strip() and not r.startswith("#")}
    assert righe["vitis_vinifera"] == "GCF_030704535.1"
    assert righe["sus_scrofa"] == "GCF_000003025.6"   # salumi invariati (D021)


def test_da_costruire(tmp_path):
    cfg = {"hosts": ["sus_scrofa", "vitis_vinifera", "olivo", "grch38"],
           "ospiti_personali": {"olivo": {"fasta": "/non/c/e.fna", "basi": 1_000_000_000}}}
    out = dict(ospiti.da_costruire(cfg, tmp_path))
    assert set(out) == {"vitis_vinifera", "olivo"}             # maiale installato, uomo a parte
    assert out["olivo"] == ospiti.stima(1_000_000_000)["secondi"]
    assert out["vitis_vinifera"] == ospiti.stima(ospiti.BASI["vitis_vinifera"], scaricare=True)["secondi"]
    (tmp_path / "vitis_vinifera").mkdir()
    (tmp_path / "vitis_vinifera" / "vitis_vinifera.1.bt2").write_text("x")
    assert dict(ospiti.da_costruire(cfg, tmp_path)).keys() == {"olivo"}   # già costruito: si riusa


# ---------------- steps/11_host_index.sh ----------------
@pytest.fixture
def finto(tmp_path):
    b = tmp_path / "bin"
    b.mkdir()
    (b / "bowtie2-build").write_text(BOWTIE2_BUILD)
    (b / "datasets").write_text("#!/bin/sh\necho 'datasets: NCBI non raggiungibile' >&2\nexit 1\n")
    for f in b.iterdir():
        f.chmod(0o755)
    log = tmp_path / "letti.txt"
    env = {**os.environ, "PATH": f"{b}:{os.environ['PATH']}", "FINTO_LOG": str(log), "NO_COLOR": "1",
           "TMPDIR": str(tmp_path)}
    return env, log


def indice(env, *arg):
    r = subprocess.run(["bash", str(RADICE / "steps" / "11_host_index.sh"), *arg], capture_output=True, text=True,
                       env=env, timeout=60)
    return r.returncode, r.stdout + r.stderr


def fasta(percorso, seq="ACGT" * 10, gz=False):
    percorso.parent.mkdir(parents=True, exist_ok=True)
    testo = f">chr1 prova\n{seq}\n"
    if gz:
        with gzip.open(percorso, "wt") as g:
            g.write(testo)
    else:
        percorso.write_text(testo)
    return percorso


@linux
def test_11_errori(finto, tmp_path):
    env, _log = finto
    out = tmp_path / "idx"
    g = fasta(tmp_path / "g.fa")
    for arg, atteso in [(["--host", "a b", "--fasta", str(g)], "Invalid host name"),
                        (["--host", "x", "--accession", "GCF_1.1"], "Invalid assembly accession"),
                        (["--host", "x", "--accession", "GCF_000819615.1", "--fasta", str(g)], "not both"),
                        (["--host", "x", "--fasta", str(tmp_path / "manca.fa")], "FASTA file not found"),
                        (["--host", "x", "--fasta", str(tmp_path / "g.txt")], "must end in"),
                        (["--host", "x", "--fasta", str(tmp_path / "$(touch BUCATO).fa")], "Unsafe FASTA path")]:
        codice, testo = indice(env, *arg, "--out", str(out))
        assert codice != 0 and atteso in testo, (arg, testo)
    (tmp_path / "non_fasta.fa").write_text("questo non e' un genoma\n")
    codice, testo = indice(env, "--host", "x", "--fasta", str(tmp_path / "non_fasta.fa"), "--out", str(out))
    assert codice != 0 and "Not a FASTA file" in testo
    assert not (Path.cwd() / "BUCATO").exists() and not (tmp_path / "BUCATO").exists()
    assert not list(out.glob("x.*"))                   # nessun indice a metà


@linux
def test_11_fasta_con_apostrofo_gz_riuso_e_ricostruzione(finto, tmp_path):
    env, log = finto
    out = tmp_path / "ospiti_utente" / "olivo"
    g = fasta(tmp_path / "l'olivo di Nanni" / "genoma.fna.gz", gz=True)
    codice, testo = indice(env, "--host", "olivo", "--fasta", str(g), "--out", str(out))
    assert codice == 0, testo
    assert sorted(f.name for f in out.iterdir()) == sorted(
        [f"olivo.{s}.bt2" for s in ("1", "2", "3", "4", "rev.1", "rev.2")] + ["olivo.origine.tsv"])
    origine = dict(r.split("\t") for r in (out / "olivo.origine.tsv").read_text().splitlines())
    assert origine["fasta"] == "genoma.fna.gz" and origine["md5"] == hashlib.md5(g.read_bytes()).hexdigest()
    assert origine["bowtie2"] == "2.5.5" and len(origine["date"]) == 10
    assert log.read_text().splitlines() == [str(g)]
    codice, testo = indice(env, "--host", "olivo", "--fasta", str(g), "--out", str(out))   # stesso file: si riusa
    assert codice == 0 and "skip" in testo and len(log.read_text().splitlines()) == 1
    fasta(g, seq="GGGG" * 10, gz=True)                 # stesso nome, altro genoma: si rifà
    codice, testo = indice(env, "--host", "olivo", "--fasta", str(g), "--out", str(out))
    assert codice == 0 and "rebuilding" in testo and len(log.read_text().splitlines()) == 2
    g.unlink()                                         # il FASTA tolto dopo la costruzione: l'indice resta buono
    codice, testo = indice(env, "--host", "olivo", "--fasta", str(g), "--out", str(out))
    assert codice == 0 and "already built is used" in testo


@linux
def test_11_accession_senza_rete_non_lascia_indici(finto, tmp_path):
    env, _log = finto
    codice, testo = indice(env, "--host", "vitis_vinifera", "--accession", "GCF_030704535.1", "--out", str(tmp_path / "i"))
    assert codice != 0 and "datasets download failed" in testo
    assert not list((tmp_path / "i").glob("vitis_vinifera*"))


# ---------------- bin/run.sh ----------------
def installazione_finta(tmp_path):
    """Motore installato finto (come tests/test_revisione_g2.py): maiale e uomo pronti, bowtie2-build finto, fastp
    che fallisce (la corsa si ferma alla prima pulizia, dopo gli indici)."""
    envs, home, pronti = tmp_path / "envs", tmp_path / "pmn", tmp_path / "pronti"
    (envs / "pmn_reports_py" / "bin").mkdir(parents=True)
    os.symlink(sys.executable, envs / "pmn_reports_py" / "bin" / "python")
    for env, nome, testo in [("pmn_trim", "fastp", "#!/bin/sh\nexit 1\n"),
                             ("pmn_hostfilter", "bowtie2-build", BOWTIE2_BUILD)]:
        (envs / env / "bin").mkdir(parents=True, exist_ok=True)
        (envs / env / "bin" / nome).write_text(testo)
        (envs / env / "bin" / nome).chmod(0o755)
    for h in ("sus_scrofa", "homo_sapiens"):
        (pronti / h).mkdir(parents=True)
        (pronti / h / f"{h}.1.bt2").write_text("indice finto")
    home.mkdir()
    (home / "installazione.env").write_text(f"PMN_ENVS={envs}\nPMN_TMP={tmp_path / 'tmp'}\nPMN_OSPITE={pronti}\n")
    return home


def corsa(tmp_path, home, extra):
    letture = tmp_path / "read"
    letture.mkdir(exist_ok=True)
    for m in (1, 2):
        with gzip.open(letture / f"C1_{m}.fastq.gz", "wt") as g:
            g.write("@C1\nACGT\n+\nIIII\n")
    cfg = tmp_path / "progetto" / "config.yaml"
    cfg.parent.mkdir(exist_ok=True)
    cfg.write_text(f"project_name: prova\ndata_source: local\nfilter_human: true\npaths:\n  work_dir: "
                   f"{cfg.parent / 'lavoro'}\n  local_reads_dir: {letture}\nprofiling:\n  tool: metaphlan\n{extra}")
    r = subprocess.run(["bash", str(RADICE / "bin" / "run.sh"), "--config", str(cfg), "--skip-preflight"],
                       capture_output=True, text=True, timeout=120, cwd=cfg.parent,
                       env={**os.environ, "PMN_HOME": str(home), "NO_COLOR": "1"})
    return r.stdout + r.stderr, cfg.parent / "lavoro"


@linux
def test_run_ospite_aggiunto_da_fasta(tmp_path):
    """hosts: [olivo] da un FASTA: indice costruito in PMN_HOME/ospiti_utente/olivo, origine nel parameters.tsv,
    il DNA umano dall'indice installato; alla corsa dopo l'indice si riusa."""
    home = installazione_finta(tmp_path)
    g = fasta(tmp_path / "genomi" / "olivo.fa")
    extra = f"hosts: [olivo]\nospiti_personali:\n  olivo: {{fasta: \"{g}\", basi: 40}}\n"
    testo, lavoro = corsa(tmp_path, home, extra)
    assert "step failed: trim_C1" in testo, testo           # gli indici sono a posto, si ferma a fastp
    idx = home / "ospiti_utente" / "olivo"
    assert (idx / "olivo.1.bt2").is_file() and (idx / "olivo.origine.tsv").is_file()
    par = (lavoro / "results" / "parameters.tsv").read_text()
    md5 = hashlib.md5(g.read_bytes()).hexdigest()
    assert "hosts\tolivo\n" in par and f"host_index_olivo\tfile olivo.fa, MD5 {md5}, index of " in par
    assert "host_index_homo_sapiens\tGCF_000001405.40 (installed)" in par
    testo, _lavoro = corsa(tmp_path, home, extra)
    assert "Index for olivo already exists" in testo


@linux
def test_run_ospite_non_valido_si_ferma_prima(tmp_path):
    home = installazione_finta(tmp_path)
    for extra in ["hosts: [olivo]\nospiti_personali:\n  olivo: {fasta: \"/mnt/c/$(touch BUCATO)/g.fa\"}\n",
                  "hosts: [olivo]\nospiti_personali:\n  olivo: {accession: GCF_1}\n",
                  "hosts: [sus_scrofa]\nospiti_personali:\n  sus_scrofa: {accession: GCF_000000001.1}\n"]:
        testo, _lavoro = corsa(tmp_path, home, extra)
        assert "invalid ospiti_personali" in testo and "[locale] trim_" not in testo, testo
    assert not list(tmp_path.rglob("BUCATO"))


@linux
def test_run_salame_invariato(tmp_path):
    """Salame: hosts [sus_scrofa] usa gli indici installati, niente ospiti_utente, timbro dell'ospite come prima."""
    home = installazione_finta(tmp_path)
    testo, lavoro = corsa(tmp_path, home, "hosts: [sus_scrofa]\n")
    assert "step failed: trim_C1" in testo and "idx_" not in testo
    assert not (home / "ospiti_utente").exists()
    assert (lavoro / "nonhost" / ".parametri").read_text().strip() == \
        "hosts=sus_scrofa\nfilter_human=yes\nhost_sensitivity=very-sensitive"


# ---------------- motore/pmn_motore.py ----------------
def test_piano_conta_l_indice_da_costruire(tmp_path, monkeypatch):
    import pmn_motore
    monkeypatch.setattr(pmn_motore, "PMN_HOME", tmp_path)
    monkeypatch.setattr(pmn_motore, "installazione", lambda: {"PMN_ENVS": "/x"})
    camp = [("S1", 1_000_000, 0)]
    vite = {"hosts": ["vitis_vinifera"]}
    passi = {e: (p, s) for e, p, _g, s in pmn_motore.piano(camp, vite)}
    assert passi["idx_vitis_vinifera"] == ("ospite", ospiti.stima(ospiti.BASI["vitis_vinifera"], scaricare=True)["secondi"])
    assert "idx_sus_scrofa" not in {e for e, *_r in pmn_motore.piano(camp, {"hosts": ["sus_scrofa"]})}
    # feci (hosts [grch38]): niente quota di ospite animale, MetaPhlAn conta tutte le coppie
    mpa = {e: s for e, _p, _g, s in pmn_motore.piano(camp, {"hosts": ["grch38"]})}["mpa_S1"]
    assert mpa == pytest.approx(1.0 * pmn_motore.MPA_S_PER_M + pmn_motore.MPA_FISSI_S)


def test_etichetta_idx_non_e_un_campione():
    import re

    import pmn_motore
    passo = next((p, re.fullmatch(r, "idx_vitis_vinifera")) for r, p in pmn_motore.ETICHETTE
                 if re.fullmatch(r, "idx_vitis_vinifera"))
    assert passo[0] == "ospite" and passo[1].groups() == ()


@pytest.mark.skipif(os.name == "nt", reason="process groups: Linux/WSL only")
def test_esegui_cita_l_ospite_aggiunto_e_la_vite(tmp_path):
    """Il referto (risultati.citazioni) dice quale genoma è stato tolto: ospite aggiunto con file e MD5, vite con
    la sua fonte (Shi et al. 2023), il DNA umano una volta sola."""
    home = tmp_path / "pmn"
    for d in ("stato", "log"):
        (home / d).mkdir(parents=True)
    (home / "installazione.env").write_text(f"PMN_ENVS={tmp_path / 'envs'}\nPMN_TMP={tmp_path / 'tmp'}\n")
    stub = tmp_path / "run_stub.sh"
    stub.write_text("""#!/usr/bin/env bash
work=$(awk '/work_dir/ {print $2}' "$2")
for l in size dl_S1 idx_olivo trim_S1 hf_S1 multiqc mpa_S1; do echo "[INFO] [locale] $l"; done
mkdir -p "$work/metaphlan" "$work/results"; echo "#mpa" > "$work/metaphlan/S1_profile.txt"
printf 'parameter\\tvalue\\nhosts\\tolivo vitis_vinifera grch38\\nhost_index_olivo\\tfile olivo.fa, MD5 abc, index of 2026-10-30\\n' \\
  > "$work/results/parameters.tsv"
""")
    (tmp_path / "srr.txt").write_text("S1\n")
    cfg = tmp_path / "progetto" / "config.yaml"
    cfg.parent.mkdir()
    cfg.write_text(f"project_name: prova\npaths:\n  work_dir: {tmp_path / 'lavoro'}\n  srr_list: {tmp_path / 'srr.txt'}\n"
                   "profiling: {tool: metaphlan}\nhosts: [olivo, vitis_vinifera, grch38]\n"
                   "ospiti_personali:\n  olivo: {fasta: /mnt/c/g/olivo.fa, basi: 1000}\n")
    r = subprocess.run([sys.executable, str(RADICE / "motore" / "pmn_motore.py"), "esegui", "--progetto", str(cfg)],
                       capture_output=True, text=True, encoding="utf-8", timeout=60,
                       env={**os.environ, "PMN_HOME": str(home), "PMN_RUN_SH": str(stub), "PMN_ATTESA_RETE": "0"})
    eventi = [json.loads(x) for x in r.stdout.splitlines()]
    fine = eventi[-1]
    assert fine["esito"] == "ok", r.stdout + r.stderr
    citazioni = fine["risultato"]["citazioni"]
    assert any("olivo" in c and "MD5 abc" in c for c in citazioni)
    assert any("10.1093/hr/uhad061" in c for c in citazioni)
    assert sum("GRCh38" in c for c in citazioni) == 1
    idx = [e for e in eventi if e["tipo"] == "avanzamento" and "olivo" in e["messaggio"]]
    assert idx and idx[0]["passo"] == "ospite" and idx[0]["campione"] is None
