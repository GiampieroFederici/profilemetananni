# -*- coding: utf-8 -*-
"""18/11/2026: filtro dell'ospite in due fasi sul primo genoma (steps/21_hostfilter.sh --prefilter very-fast).

Fase 1: Bowtie2 --very-fast (end-to-end) su tutte le coppie, scrive solo quali coppie hanno le due read non allineate
(la posizione nel file). Fase 2: il comando di ogni passaggio (--very-sensitive-local, regola strict) sulle sole coppie
rimaste, riprese dai file in ingresso con la riga di intestazione intera. Misura del 14/11 su SRR4875279: 167-170 s
contro 370-372 s, nessuna coppia tenuta in più, 3 tolte in più su 2.955.015.

Senza --prefilter il passo lavora come prima (test_ospite_standard.py, non toccato). Read singole, passaggi dopo il
primo e progetti con solo l'uomo restano con un solo passaggio.

Bowtie2 e samtools veri (ambiente pmn_hostfilter) su genomi minuscoli; i test dell'annullamento usano programmi finti.
Rossi sul codice di a61133e (l'argomento --prefilter non esiste), verdi dopo. Nella WSL:
  python -m pytest tests/test_ospite_due_fasi.py -p no:cacheprovider"""
import gzip
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

from test_ospite_standard import (HF, L, RADICE, con_bowtie2, coppie_di_prova, genomi, indice, leggi_gz,  # noqa: F401
                                  linux, rc, scrivi_gz)

from test_ospiti import corsa, installazione_finta

from test_ospiti import corsa, installazione_finta

sys.path.insert(0, str(RADICE / "motore"))
import pmn_motore  # noqa: E402
import referto  # noqa: E402

# Bowtie2 vero dietro una spia: scrive gli argomenti e copia l'R1 non compresso che riceve (quello della fase 2)
SPIA = """#!/bin/bash
echo "$*" >> "$SPIA_ARG"
a=("$@")
for ((j = 0; j < ${#a[@]}; j++)); do
  if [ "${a[j]}" = -1 ]; then case "${a[j+1]}" in *.fastq) cp "${a[j+1]}" "$SPIA_R1" ;; esac; fi
done
exec "$BT2_VERO/bowtie2" "$@"
"""


def lancia(d, r1, r2, indici, *extra, atteso=0):
    """21_hostfilter.sh con Bowtie2 vero dietro la spia -> (cartella delle read senza ospite, registri, processo)."""
    d.mkdir(exist_ok=True)
    spia = d / "spia"
    spia.mkdir(exist_ok=True)
    (spia / "bowtie2").write_text(SPIA, encoding="utf-8")
    (spia / "bowtie2").chmod(0o755)
    (d / "t").mkdir(exist_ok=True)
    a = ["--sample", "S", "--in1", r1]
    if r2:
        a += ["--in2", r2]
    for i in indici:
        a += ["--index", i]
    a += ["--out", d / "nonhost", "--log-dir", d / "log", "--threads", "2", *extra]
    p = subprocess.run(["bash", str(RADICE / "steps" / "21_hostfilter.sh"), *map(str, a)], capture_output=True,
                       text=True, timeout=120,
                       env={**os.environ, "PATH": f"{spia}:{HF}:{os.environ['PATH']}", "NO_COLOR": "1",
                            "PMN_LANG": "en", "TMPDIR": str(d / "t"), "BT2_VERO": str(HF),
                            "SPIA_ARG": str(d / "argomenti.txt"), "SPIA_R1": str(d / "fase2_R1.fastq")})
    assert (p.returncode == 0) == (atteso == 0), p.stdout + p.stderr
    return d / "nonhost", d / "log", p


def coppie_con_locale(g):
    """Le coppie di test_ospite_standard più una che solo la fase 2 toglie: metà read sul maiale, metà no (si allinea
    in modalità locale, non per intero)."""
    coppie, q = coppie_di_prova(g)
    coppie["locale_maiale"] = (g["maiale"][3000:3050] + g["taxon"][4000:4050], rc(g["taxon"][4200:4300]))
    return coppie, q


def scrivi_coppie(d, coppie, q, nome1="{n} 1 length=100", nome2="{n} 2 length=100"):
    d.mkdir(exist_ok=True)
    r1, r2 = d / "R1.fastq.gz", d / "R2.fastq.gz"
    scrivi_gz(r1, [(nome1.format(n=n), a, q) for n, (a, _b) in coppie.items()])
    scrivi_gz(r2, [(nome2.format(n=n), b, q) for n, (_a, b) in coppie.items()])
    return r1, r2


def senza_gz(cartella):
    return [gzip.decompress(f.read_bytes()) for f in sorted(cartella.glob("*.fastq.gz"))]


@linux
@con_bowtie2
def test_due_fasi_stesse_read_di_un_passaggio(tmp_path, genomi):
    """Maiale e uomo finti: le read senza ospite sono identiche al byte a quelle di un solo passaggio; alla fase 2
    arrivano solo le coppie che la fase 1 non ha tolto, con la riga di intestazione intera."""
    coppie, q = coppie_con_locale(genomi)
    r1, r2 = scrivi_coppie(tmp_path / "read", coppie, q)
    idx = [indice(tmp_path / "idx", "sus_scrofa", genomi["maiale"]), indice(tmp_path / "idx", "grch38", genomi["uomo"])]
    uno, _log, _p = lancia(tmp_path / "uno", r1, r2, idx)
    due, log, p = lancia(tmp_path / "due", r1, r2, idx, "--prefilter", "very-fast")
    assert senza_gz(due) == senza_gz(uno) and len(senza_gz(due)) == 2
    assert [n for n, _s, _q in leggi_gz(due / "S_nonhost_1.fastq.gz")] == ["taxon_1", "taxon_2"]
    # tre corse di Bowtie2: fase 1 veloce, fase 2 e uomo con il comando di sempre
    righe = (tmp_path / "due" / "argomenti.txt").read_text().splitlines()
    assert len(righe) == 3
    assert "--very-fast --reorder" in righe[0] and "sensitive" not in righe[0]
    assert all("--very-sensitive-local --reorder" in r and "--very-fast" not in r for r in righe[1:])
    # alla fase 2: le 4 coppie che non si allineano per intero al maiale, nell'ordine del file, intestazione intera
    testa = (tmp_path / "due" / "fase2_R1.fastq").read_text().splitlines()[0::4]
    assert testa == [f"@{n} 1 length=100" for n in ("solo_R1_uomo", "taxon_1", "taxon_2", "locale_maiale")]
    # registri: quello del genoma è la fase 1 (tutte le coppie), la fase 2 ha il suo; un solo conto per genoma
    assert "8 reads; of these:" in (log / "S.sus_scrofa.bowtie2.log").read_text().splitlines()
    assert "4 reads; of these:" in (log / "S.sus_scrofa_fase2.bowtie2.log").read_text().splitlines()
    assert (log / "S.sus_scrofa.coppie.tsv").read_text() == "entrate\ttenute\n8\t3\n"
    assert (log / "S.grch38.coppie.tsv").read_text() == "entrate\ttenute\n3\t2\n"
    assert not (log / "S.grch38_fase2.bowtie2.log").exists()
    assert pmn_motore.coppie_ospite(_lavoro(tmp_path, log)) == {"S": (8, 2)}
    assert "phase 1 of 2 (Bowtie2 --very-fast" in p.stdout and "phase 2 of 2 (Bowtie2 --very-sensitive-local" in p.stdout
    assert list((tmp_path / "due" / "t").iterdir()) == []          # niente file temporanei rimasti


def _lavoro(tmp_path, log):
    """coppie_ospite() legge <lavoro>/hostfilter_logs: i registri della prova sotto quel nome."""
    (tmp_path / "lavoro").mkdir()
    (tmp_path / "lavoro" / "hostfilter_logs").symlink_to(log, target_is_directory=True)
    return tmp_path / "lavoro"


@linux
@con_bowtie2
@pytest.mark.parametrize("nome1, nome2", [("{n}/1", "{n}/2"), ("{n}/1 commento", "{n}/2 commento"), ("{n}", "{n}")])
def test_due_fasi_con_nomi_che_bowtie2_cambia(tmp_path, genomi, nome1, nome2):
    """Bowtie2 toglie /1 e /2 da certi nomi: le coppie si riprendono per posizione, quindi nessuna read si perde."""
    coppie, q = coppie_con_locale(genomi)
    r1, r2 = scrivi_coppie(tmp_path / "read", coppie, q, nome1, nome2)
    idx = [indice(tmp_path / "idx", "sus_scrofa", genomi["maiale"])]
    uno, _log, _p = lancia(tmp_path / "uno", r1, r2, idx)
    due, log, _p = lancia(tmp_path / "due", r1, r2, idx, "--prefilter", "very-fast")
    assert senza_gz(due) == senza_gz(uno)
    assert [s for _n, s, _q in leggi_gz(due / "S_nonhost_1.fastq.gz")] == \
        [coppie[n][0] for n in ("solo_R1_uomo", "taxon_1", "taxon_2")]
    assert (log / "S.sus_scrofa.coppie.tsv").read_text() == "entrate\ttenute\n8\t3\n"


@linux
@con_bowtie2
def test_due_fasi_salva_tutte_le_coppie_tolte(tmp_path, genomi):
    """--host-out: le coppie tolte dalla fase 1 e dalla fase 2 nello stesso file, le due read di ognuna, una volta."""
    coppie, q = coppie_con_locale(genomi)
    r1, r2 = scrivi_coppie(tmp_path / "read", coppie, q)
    idx = [indice(tmp_path / "idx", "sus_scrofa", genomi["maiale"])]
    lancia(tmp_path / "uno", r1, r2, idx, "--host-out", tmp_path / "ospite_uno")
    lancia(tmp_path / "due", r1, r2, idx, "--host-out", tmp_path / "ospite_due", "--prefilter", "very-fast")
    for m in (1, 2):
        tolte = leggi_gz(tmp_path / "ospite_due" / f"S.sus_scrofa_{m}.fastq.gz")
        assert sorted(tolte) == sorted(leggi_gz(tmp_path / "ospite_uno" / f"S.sus_scrofa_{m}.fastq.gz"))
        assert sorted(n for n, _s, _q in tolte) == ["discordante", "entrambe_maiale", "locale_maiale",
                                                    "solo_R1_maiale", "solo_R2_maiale"]
    assert sorted(f.name for f in (tmp_path / "ospite_due").iterdir()) == ["S.sus_scrofa_1.fastq.gz",
                                                                           "S.sus_scrofa_2.fastq.gz"]


@linux
@con_bowtie2
def test_read_singole_restano_con_un_passaggio(tmp_path, genomi):
    """Le due fasi sono misurate solo sulle coppie: con read singole --prefilter non cambia nulla."""
    m, t = genomi["maiale"], genomi["taxon"]
    q = "I" * L
    r = tmp_path / "R.fastq.gz"
    scrivi_gz(r, [("ospite", m[3000:3100], q), ("taxon", t[3000:3100], q), ("ospite_rc", rc(m[100:200]), q)])
    idx = [indice(tmp_path / "idx", "sus_scrofa", m)]
    out, log, _p = lancia(tmp_path / "due", r, None, idx, "--prefilter", "very-fast")
    assert leggi_gz(out / "S_nonhost.fastq.gz") == [("taxon", t[3000:3100], q)]
    righe = (tmp_path / "due" / "argomenti.txt").read_text().splitlines()
    assert len(righe) == 1 and "--very-sensitive-local" in righe[0] and "--very-fast" not in righe[0]
    assert not (log / "S.sus_scrofa_fase2.bowtie2.log").exists()


@linux
@con_bowtie2
def test_prefilter_fuori_elenco_non_arriva_a_bowtie2(tmp_path, genomi):
    """Sulla riga di comando di Bowtie2 va solo una parola dell'elenco: il resto ferma il passo prima."""
    coppie, q = coppie_con_locale(genomi)
    r1, r2 = scrivi_coppie(tmp_path / "read", coppie, q)
    idx = [indice(tmp_path / "idx", "sus_scrofa", genomi["maiale"])]
    for cattivo in ("--very-fast", "very-fast --un-conc /tmp/x", "sensitive", "very-fast;id"):
        _out, _log, p = lancia(tmp_path / "no", r1, r2, idx, "--prefilter", cattivo, atteso=1)
        assert "invalid --prefilter" in p.stdout + p.stderr
    assert not (tmp_path / "no" / "argomenti.txt").exists() and not (tmp_path / "no" / "nonhost").exists()


# ---------------- annullamento a metà: programmi finti ----------------
BOWTIE2_LENTO = """#!/bin/bash
echo "400 reads; of these:" >&2
awk 'BEGIN { for (i = 1; i <= 400; i++) print "r" i "\\t" (i % 2 ? 77 : 65) }'
sleep 30
"""
SAMTOOLS_FINTO = """#!/bin/bash
if [ "$1" = view ]; then cat; exit 0; fi
cat > /dev/null
"""


@linux
@pytest.mark.parametrize("fase", [1, 2])
def test_annullamento_non_lascia_file(tmp_path, fase):
    """Fermato come fa il motore (SIGTERM al gruppo) nella fase 1 o nella fase 2: cartella temporanea cancellata,
    nessuna read senza ospite a metà."""
    finti = tmp_path / "finti"
    finti.mkdir()
    # fase 2: la prima corsa di Bowtie2 (fase 1) finisce subito, la seconda resta ferma
    lento = BOWTIE2_LENTO if fase == 1 else BOWTIE2_LENTO.replace(
        "sleep 30", 'case "$*" in *--very-fast*) ;; *) : > "$SEGNO"; sleep 30 ;; esac')
    for nome, testo in (("bowtie2", lento), ("samtools", SAMTOOLS_FINTO)):
        (finti / nome).write_text(testo, encoding="utf-8")
        (finti / nome).chmod(0o755)
    for m in (1, 2):
        with gzip.open(tmp_path / f"r_{m}.fastq.gz", "wt") as g:
            g.write("".join(f"@r{i} {m}\nACGT\n+\nIIII\n" for i in range(1, 401)))
    (tmp_path / "maiale.1.bt2").write_bytes(b"x")
    (tmp_path / "t").mkdir()
    segno = tmp_path / "segno"
    p = subprocess.Popen(["bash", str(RADICE / "steps" / "21_hostfilter.sh"), "--sample", "S1",
                          "--in1", str(tmp_path / "r_1.fastq.gz"), "--in2", str(tmp_path / "r_2.fastq.gz"),
                          "--index", str(tmp_path / "maiale"), "--out", str(tmp_path / "uscita"), "--threads", "1",
                          "--prefilter", "very-fast"],
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, start_new_session=True,
                         env={**os.environ, "PATH": f"{finti}:{os.environ['PATH']}", "PMN_BT2_MM": "no",
                              "TMPDIR": str(tmp_path / "t"), "NO_COLOR": "1", "SEGNO": str(segno)})
    try:
        fine = time.monotonic() + 20
        while time.monotonic() < fine:       # fase 1: l'elenco è aperto; fase 2: Bowtie2 è alla seconda corsa
            if (segno.exists() and list((tmp_path / "t").glob("pmn_hf_S1.*/f1_1.fastq"))) if fase == 2 else \
                    list((tmp_path / "t").glob("pmn_hf_S1.*/f1.n")):
                break
            time.sleep(0.1)
        else:
            pytest.fail("il passo non è arrivato alla fase " + str(fase) + ": " + (p.stdout.read() if p.poll() is not None else ""))
        os.killpg(p.pid, signal.SIGTERM)
        p.wait(timeout=20)
    finally:
        if p.poll() is None:
            os.killpg(p.pid, signal.SIGKILL)
    assert p.returncode != 0
    assert list((tmp_path / "t").iterdir()) == []
    assert not list((tmp_path / "uscita").glob("*.fastq.gz*"))


# ---------------- motore e referto (girano ovunque) ----------------
LOG = ("{n} reads; of these:\n  {n} (100.00%) were paired; of these:\n"
       "    {zero} (50.00%) aligned concordantly 0 times\n    0 (0.00%) aligned concordantly exactly 1 time\n")


def test_il_motore_conta_una_volta_il_genoma_in_due_fasi(tmp_path):
    """Due registri di Bowtie2 per il primo genoma: le coppie entrate sono quelle della fase 1, le rimaste quelle del
    file coppie.tsv; la fase 2 non diventa un altro campione e non si conta due volte."""
    h = tmp_path / "hostfilter_logs"
    h.mkdir()
    (h / "S1.sus_scrofa.bowtie2.log").write_text(LOG.format(n=1900000, zero=760000))
    (h / "S1.sus_scrofa_fase2.bowtie2.log").write_text(LOG.format(n=700000, zero=520000))
    (h / "S1.sus_scrofa.coppie.tsv").write_text("entrate\ttenute\n1900000\t500000\n")
    assert pmn_motore.coppie_ospite(tmp_path) == {"S1": (1900000, 500000)}
    (h / "S1.homo_sapiens.bowtie2.log").write_text(LOG.format(n=500000, zero=480000))
    (h / "S1.homo_sapiens.coppie.tsv").write_text("entrate\ttenute\n500000\t450000\n")
    assert pmn_motore.coppie_ospite(tmp_path) == {"S1": (1900000, 450000)}
    assert pmn_motore.quote_ospite(tmp_path) == {"S1": pytest.approx(1 - 450000 / 1900000)}


PARAMETRI = {"hosts": "sus_scrofa", "filter_human": "yes", "host_sensitivity": "very-sensitive-local",
             "host_pairs": "strict", "trim": "fastp cut_right 4:20, length_required 70"}


def test_il_referto_dice_le_due_fasi():
    righe = {r[0]: r for r in referto.righe_parametri({"parametri": {**PARAMETRI, "host_prefilter": "very-fast"}})}
    fasi = righe["Filtro dell'ospite in due fasi"]
    assert fasi[1] == "Bowtie2 very-fast, Bowtie2 very-sensitive-local"
    assert "end-to-end" in fasi[2] and "riga di intestazione intera" in fasi[2] and "read singole" in fasi[2]
    assert "SRR4875279" in fasi[3]
    assert righe["Come si toglie l'ospite"][1] == "Bowtie2 very-sensitive-local, strict"      # la regola non cambia
    # progetto fatto con un solo passaggio (riga assente): il referto resta com'era
    assert "Filtro dell'ospite in due fasi" not in [r[0] for r in referto.righe_parametri({"parametri": PARAMETRI})]


def test_run_sh_chiede_le_due_fasi_solo_dove_sono_misurate():
    """bin/run.sh: host_prefilter nel timbro, in parameters.tsv e sulla riga del passo, solo con un ospite del
    prodotto come primo genoma e l'impostazione predefinita."""
    testo = (RADICE / "bin" / "run.sh").read_text(encoding="utf-8")
    regola = testo[testo.index('HOST_PREFILTER=""'):testo.index("validate_yesno \"$PMN_KEEP_TRIMMED\"")]
    assert '[ "$PMN_HOST_PRESET" = very-sensitive-local ]' in regola and "grch38|chm13) ;;" in regola
    assert "printf '\\nhost_prefilter=%s' \"$HOST_PREFILTER\"" in testo                       # timbro
    blocco = testo[testo.index("printf 'parameter\\tvalue\\n'"):testo.index('} > "$RES_DIR/parameters.tsv"')]
    assert "printf 'host_prefilter\\t%s\\n' \"$HOST_PREFILTER\"" in blocco
    assert '[ -n "$HOST_PREFILTER" ] && a+=(--prefilter "$HOST_PREFILTER")' in testo



@linux
@pytest.mark.parametrize("extra, attesa", [("hosts: [sus_scrofa]\n", True), ("hosts: []\n", False),
                                           ("hosts: [sus_scrofa]\nhost_sensitivity: very-sensitive\n", False)])
def test_timbro_con_le_due_fasi_solo_dove_si_usano(tmp_path, extra, attesa):
    """Il timbro dell'ospite ha host_prefilter solo se le due fasi si usano davvero: un progetto con solo l'uomo o con
    very-sensitive resta con il timbro di prima (e non si rifà)."""
    home = installazione_finta(tmp_path)
    _testo, lavoro = corsa(tmp_path, home, extra)
    timbro = (lavoro / "nonhost" / ".parametri").read_text()
    assert ("\nhost_prefilter=very-fast" in timbro) == attesa, timbro
    assert "host_pairs=strict\n" in timbro
