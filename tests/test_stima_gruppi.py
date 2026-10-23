# -*- coding: utf-8 -*-
"""Fast size estimate for many samples (steps/05 lookup_many): grouped requests to ENA, NCBI as fallback.
Criterion V3 of sessioni/2026-10-16_motore_seconda_parte.md, against local fake servers (no internet)."""
import importlib.util
import json
import os
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
RUNS = {"SRR4875279": (3240847, 916133132, "251500813;282021285", 383),
        "SRR25393919": (34727974, 10304352148, "21025383;2071191476;2073074366", 3361),
        "SRR1000001": (1000, 300000, "5000;6000", 1)}


class Finto(BaseHTTPRequestHandler):
    ena = "ok"          # ok | giu | senza:<acc>
    richieste = []

    def log_message(self, *a):
        pass

    def do_POST(self):
        dati = urllib.parse.parse_qs(self.rfile.read(int(self.headers["Content-Length"])).decode())
        Finto.richieste.append(self.path)
        if self.path == "/ena":
            if Finto.ena == "giu":
                return self.rispondi(500, b"")
            chiesti = dati["includeAccessions"][0].split(",")
            righe = [{"run_accession": a, "read_count": str(RUNS[a][0]), "base_count": str(RUNS[a][1]),
                      "fastq_bytes": RUNS[a][2]} for a in chiesti if a in RUNS and Finto.ena != f"senza:{a}"]
            return self.rispondi(200, json.dumps(righe).encode())
        if self.path == "/ncbi":
            chiesti = dati["id"][0].split(",")
            righe = "".join(f"<Row><Run>{a}</Run><spots>{RUNS[a][0]}</spots><bases>{RUNS[a][1]}</bases>"
                            f"<size_MB>{RUNS[a][3]}</size_MB></Row>" for a in chiesti if a in RUNS)
            if not righe:
                return self.rispondi(400, b"")          # NCBI: nessuno dei codici esiste
            return self.rispondi(200, f"<SraRunInfo>{righe}</SraRunInfo>".encode())
        self.rispondi(404, b"")

    def rispondi(self, codice, corpo):
        self.send_response(codice)
        self.end_headers()
        self.wfile.write(corpo)


@pytest.fixture
def s05():
    server = HTTPServer(("127.0.0.1", 0), Finto)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    spec = importlib.util.spec_from_file_location("s05", os.path.join(ROOT, "steps", "05_estimate_size.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    base = f"http://127.0.0.1:{server.server_port}"
    m.ENA_SEARCH, m.NCBI_API, m.MAX_RETRIES = f"{base}/ena", f"{base}/ncbi", 1
    Finto.ena, Finto.richieste = "ok", []
    yield m
    server.shutdown()


def test_una_richiesta_per_gruppo(s05):
    s05.GROUP = 2
    e = s05.lookup_many(["SRR4875279", "srr25393919", "SRR1000001"])
    assert [x["status"] for x in e] == ["OK"] * 3 and {x["source"] for x in e} == {"ENA"}
    assert e[0]["read_count"] == 3240847 and e[0]["fastq_bytes"] == 251500813 + 282021285
    assert e[1]["accession"] == "SRR25393919"
    assert Finto.richieste == ["/ena", "/ena"]       # 3 codici a gruppi di 2: due richieste, nessuna a NCBI


def test_ena_giu_tutto_da_ncbi(s05):
    Finto.ena = "giu"
    e = s05.lookup_many(["SRR4875279", "SRR25393919"])
    assert [(x["status"], x["source"]) for x in e] == [("OK", "NCBI")] * 2
    assert e[0]["fastq_bytes"] == 383 * 1_000_000 and Finto.richieste == ["/ena", "/ncbi"]


def test_ena_senza_un_codice_solo_quello_a_ncbi(s05):
    Finto.ena = "senza:SRR25393919"
    e = s05.lookup_many(["SRR4875279", "SRR25393919"])
    assert [x["source"] for x in e] == ["ENA", "NCBI"] and Finto.richieste == ["/ena", "/ncbi"]


def test_codice_inesistente_e_non_valido(s05):
    e = s05.lookup_many(["SRR4875279", "SRR9999999", "pippo"])
    assert [x["status"] for x in e] == ["OK", "NOT_FOUND", "INVALID"]


def test_ena_e_ncbi_giu_errore_da_riprovare(s05):
    Finto.ena = "giu"
    s05.NCBI_API = "http://127.0.0.1:9/ncbi"           # porta chiusa: NCBI irraggiungibile
    e = s05.lookup_many(["SRR4875279", "SRR9999999"])
    assert [x["status"] for x in e] == ["ERROR", "ERROR"]


def test_pmn_motore_stima_usa_i_gruppi(s05, tmp_path):
    import subprocess
    import sys
    from contratto import controlla
    (tmp_path / "srr.txt").write_text("SRR4875279\nSRR25393919\n", encoding="utf-8")
    cfg = tmp_path / "config.yaml"
    cfg.write_text(f"paths:\n  srr_list: {tmp_path / 'srr.txt'}\n", encoding="utf-8")
    env = {**os.environ, "PMN_HOME": str(tmp_path / "vuota"), "PMN_ENA_SEARCH": s05.ENA_SEARCH,
           "PMN_NCBI_API": s05.NCBI_API}
    r = subprocess.run([sys.executable, os.path.join(ROOT, "motore", "pmn_motore.py"), "stima", "--progetto", str(cfg)],
                       capture_output=True, text=True, encoding="utf-8", timeout=60, env=env)
    ev = controlla(r.stdout, r.returncode, "stima")
    assert r.returncode == 0 and ev[-1]["risultato"]["coppie_totali"] == 3240847 + 34727974
    assert Finto.richieste == ["/ena"]                   # due campioni, una sola domanda


def test_ena_giu_e_ncbi_non_lo_trova_non_ci_si_fida(s05):
    # come lookup_srr: con ENA giu' un "non esiste" di NCBI diventa ERROR (si riprova la volta dopo)
    Finto.ena = "giu"
    assert [x["status"] for x in s05.lookup_many(["SRR4875279", "SRR9999999"])] == ["OK", "ERROR"]
