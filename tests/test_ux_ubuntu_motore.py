# -*- coding: utf-8 -*-
"""Difetti del motore visti nella prova su un PC con Ubuntu (12-13/11/2026). Ogni test è rosso sul codice di 1eac06e
e verde dopo la correzione. Senza internet e senza bash: gira con l'app su Windows e con la suite del motore.
P14  nel referto, "In breve", i nomi dei taxa non erano in corsivo (nelle tabelle sì).
P16  campione pubblicato da pochi giorni (ENA e NCBI senza le sue read): "Controlla i codici SRR", consiglio sbagliato;
     la stima passava con 0 coppie senza dirlo.
P23  dopo Annulla nel registro restavano "Terminated" e "[FAIL] step failed", che sembrano guasti.
  python -m pytest tests/test_ux_ubuntu_motore.py"""
import argparse
import gzip
import html
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from contratto import controlla
from test_stima_e_nota_kraken import referto_finto
from test_stima_ena_senza_read import NUOVA, Finto, s05, stima  # noqa: F401  (server finti di ENA e NCBI)

RADICE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADICE / "motore"))
import pmn_motore as pm  # noqa: E402
import referto  # noqa: E402

MOTORE = str(RADICE / "motore" / "pmn_motore.py")


# ---------------- P14: "In breve" con i nomi in corsivo ----------------
def test_p14_in_breve_i_nomi_dei_taxa_in_corsivo(tmp_path):
    d = referto_finto(tmp_path)
    breve = referto.html_referto(d).split("<h2>1.")[1].split("<h2>2.")[0]
    s = d["campioni"][0]["sintesi"]
    nomi = [x["nome"] for x in s["metaphlan"]["dominanti"][:3] + s["kraken"]["dominanti"][:3] + s["kraken"]["non_microbi"]]
    assert "Latilactobacillus sakei" in nomi and "Homo sapiens" in nomi
    assert "<i>Latilactobacillus sakei</i>" in breve and "<i>Homo sapiens</i>" in breve
    tondo = re.sub(r"<i>[^<]*</i>", "", breve)                 # quello che resta in tondo
    assert [n for n in nomi if n in tondo] == []
    for metodo in ("metaphlan", "kraken"):                     # stesse parole e stessi numeri: cambia solo il corsivo
        assert "<i>" not in s[metodo]["frase"]
        assert f"<li>{html.escape(s[metodo]['frase'])}</li>" in re.sub(r"</?i>", "", breve)


# ---------------- P16: codice sbagliato, oppure read non ancora negli archivi ----------------
def errore_del_registro(testo):
    """La riga di ERRORI che il motore sceglie per le ultime righe di run.sh (la prima che corrisponde, come _run_sh)."""
    return next(((codice, messaggio, cosa) for regola, codice, messaggio, cosa in pm.ERRORI
                 if re.search(regola, testo)), None)


def test_p16_esegui_distingue_le_read_non_ancora_arrivate(s05, tmp_path, capsys, monkeypatch):  # noqa: F811
    Finto.ncbi = {}
    codice, testo, _cache = stima(s05, tmp_path, capsys, monkeypatch)        # quello che scrive steps/05 dentro run.sh
    assert codice == 4
    trovato = errore_del_registro(testo)
    assert trovato[0] == "READ_NON_DISPONIBILI" and pm.CODICE_USCITA[trovato[0]] == 1
    assert "non ci sono ancora" in trovato[1] and "fra qualche giorno" in trovato[2]
    assert "SRR" not in trovato[2].replace("I codici sono giusti", "")       # non manda a controllare i codici
    sbagliato = tmp_path / "sbagliato"
    sbagliato.mkdir()
    codice, testo, _cache = stima(s05, sbagliato, capsys, monkeypatch, ["SRR9999999"])
    assert codice == 4 and errore_del_registro(testo)[0] == "READ_NON_TROVATE"   # codice sbagliato: come prima


def lancia_stima(s05, tmp_path, righe):  # noqa: F811
    cfg = tmp_path / "config.yaml"
    cfg.write_text(righe, encoding="utf-8")
    env = {**os.environ, "PMN_HOME": str(tmp_path / "vuota"), "PMN_ENA_SEARCH": s05.ENA_SEARCH,
           "PMN_NCBI_API": s05.NCBI_API}
    r = subprocess.run([sys.executable, MOTORE, "stima", "--progetto", str(cfg)], capture_output=True, text=True,
                       encoding="utf-8", timeout=60, env=env)
    return controlla(r.stdout, r.returncode, "stima"), r.returncode


def test_p16_stima_si_ferma_con_il_messaggio_giusto(s05, tmp_path):  # noqa: F811
    Finto.ncbi = {}
    (tmp_path / "srr.txt").write_text(f"{NUOVA}\n", encoding="utf-8")
    ev, codice = lancia_stima(s05, tmp_path, f"paths:\n  srr_list: {tmp_path / 'srr.txt'}\n")
    errore = next(e for e in ev if e["tipo"] == "errore")
    assert codice == 1 and errore["codice"] == "READ_NON_DISPONIBILI"
    assert NUOVA in errore["messaggio"] and "non hanno ancora le sue read" in errore["messaggio"]
    assert "Il codice è giusto" in errore["cosa_fare"] and "fra qualche giorno" in errore["cosa_fare"]


def test_p16_stima_avvisa_se_un_campione_ha_zero_coppie(s05, tmp_path):  # noqa: F811
    read = tmp_path / "read"
    read.mkdir()
    for nome, n in (("PIENO", 1000), ("VUOTO", 0)):
        for m in (1, 2):
            with gzip.open(read / f"{nome}_R{m}.fastq.gz", "wt") as f:
                f.write("@r\nACGT\n+\nIIII\n" * n)
    ev, codice = lancia_stima(s05, tmp_path, f"data_source: local\npaths:\n  local_reads_dir: {read}\n")
    avvisi = [e for e in ev if e["tipo"] == "avviso" and e["codice"] == "READ_NON_DISPONIBILI"]
    assert codice == 0 and ev[-1]["risultato"]["coppie_totali"] == 1000
    assert len(avvisi) == 1 and "VUOTO" in avvisi[0]["messaggio"] and "0 coppie" in avvisi[0]["messaggio"]


# ---------------- P23: Annulla non lascia righe che sembrano guasti ----------------
def test_p23_dopo_annulla_niente_terminated_e_fail_nel_registro(tmp_path, monkeypatch, capsys):
    """run.sh ha una trappola su TERM e non esce: la shell scrive "Terminated" per il passo fermato e run.sh "[FAIL]
    step failed". Il segno <corsa>.annulla c'è da prima del segnale (pmn-motore annulla): da lì in poi sono rumore."""
    stato = tmp_path / "stato"
    stato.mkdir()
    monkeypatch.setattr(pm, "STATO", stato)
    monkeypatch.setattr(pm, "PMN_HOME", tmp_path)
    (tmp_path / "srr.txt").write_text("S1\n", encoding="utf-8")
    progetto = tmp_path / "progetto" / "config.yaml"
    progetto.parent.mkdir()
    m = pm.Motore(argparse.Namespace(comando="esegui", progetto=str(progetto)))
    m.log = tmp_path / "esegui.log"

    class RunFermato:
        pid = 4242

        def __init__(self, *a, **k):
            self.stdout = self.righe()

        def righe(self):
            yield "2026-11-13 07:16:00 [INFO] [locale] trim_S1\n"
            yield "2026-11-13 07:16:00 [INFO] Rifilo S1 con fastp ...\n"
            (stato / f"{m.corsa}.annulla").touch()             # la persona preme Annulla
            yield 'bin/lib/scheduler.sh: line 22: 12345 Terminated              PATH="$PMN_ENVS/$env/bin:$PATH" "$@"\n'
            yield "2026-11-13 07:16:02 [FAIL] step failed: trim_S1\n"

        def wait(self):
            return 1

    monkeypatch.setattr(pm.subprocess, "Popen", RunFermato)
    with pytest.raises(pm.Annullata):
        m._run_sh(progetto, {"paths": {"srr_list": str(tmp_path / "srr.txt")}}, stato / "esegui.lock")
    registro = m.log.read_text(encoding="utf-8")
    assert "Rifilo S1 con fastp" in registro                   # quello di prima dell'annullamento resta
    assert "Terminated" not in registro and "FAIL" not in registro and "failed" not in registro
    assert "annulla" in registro.lower()                       # una riga dice che cosa è successo
