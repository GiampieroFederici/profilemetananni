# -*- coding: utf-8 -*-
"""P16 (prova su Ubuntu, 13/11/2026): un campione pubblicato da pochi giorni. ENA conosce la corsa ma non ha ancora le
sue read (0 read, 0 byte), NCBI le ha già. steps/05 rispondeva "OK, 0 byte" senza chiedere a NCBI, scartava la corsa
con "the runs were not found. Check the SRR list" e teneva la risposta in size_cache.json: il progetto falliva sempre.
Ora per le corse senza read decide NCBI; se nemmeno NCBI le ha lo stato è EMPTY, che si richiede la volta dopo.
Server finti in locale, senza internet:  python -m pytest tests/test_stima_ena_senza_read.py"""
import importlib.util
import json
import os
import sys
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
PIENA, NUOVA = "SRR4875279", "SRR41000001"       # NUOVA: su ENA c'è la scheda, senza read
ENA = {PIENA: ("3240847", "916133132", "251500813;282021285"), NUOVA: ("0", "0", "")}


class Finto(BaseHTTPRequestHandler):
    ncbi = {}            # {corsa: (spots, bases, size_MB)}: quello che NCBI ha in questo momento
    richieste = []       # (percorso, codici chiesti)

    def log_message(self, *a):
        pass

    def do_GET(self):    # lookup_srr: una corsa alla volta
        self.rispondi(urllib.parse.urlparse(self.path).path, urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query))

    def do_POST(self):   # lookup_many: a gruppi
        self.rispondi(self.path, urllib.parse.parse_qs(self.rfile.read(int(self.headers["Content-Length"])).decode()))

    def rispondi(self, percorso, dati):
        chiave = {"/ena": "includeAccessions", "/ena_una": "accession", "/ncbi": "id"}[percorso]
        chiesti = dati[chiave][0].split(",")
        Finto.richieste.append((percorso, chiesti))
        if percorso == "/ncbi":
            righe = "".join(f"<Row><Run>{a}</Run><spots>{Finto.ncbi[a][0]}</spots><bases>{Finto.ncbi[a][1]}</bases>"
                            f"<size_MB>{Finto.ncbi[a][2]}</size_MB></Row>" for a in chiesti if a in Finto.ncbi)
            return self.manda(200, f"<SraRunInfo>{righe}</SraRunInfo>".encode()) if righe else self.manda(400, b"")
        self.manda(200, json.dumps([{"run_accession": a, "read_count": ENA[a][0], "base_count": ENA[a][1],
                                     "fastq_bytes": ENA[a][2]} for a in chiesti if a in ENA]).encode())

    def manda(self, codice, corpo):
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
    m.ENA_SEARCH, m.ENA_API, m.NCBI_API, m.MAX_RETRIES = f"{base}/ena", f"{base}/ena_una", f"{base}/ncbi", 1
    Finto.ncbi, Finto.richieste = {NUOVA: (16400000, 4900000000, 1310)}, []
    yield m
    server.shutdown()
    server.server_close()


def stima(s05, tmp_path, capsys, monkeypatch, codici=(NUOVA,)):
    """main() di steps/05 come lo lancia bin/run.sh: (codice di uscita, quello che scrive, la cache)."""
    (tmp_path / "srr.txt").write_text("".join(f"{c}\n" for c in codici), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["05_estimate_size.py", "--srr-list", str(tmp_path / "srr.txt"), "--out",
                                      str(tmp_path / "size"), "--quota-free", "500"])
    codice = s05.main()
    cache = json.loads((tmp_path / "size" / "size_cache.json").read_text(encoding="utf-8"))
    return codice, capsys.readouterr().out, cache


def test_ena_senza_read_decide_ncbi(s05):
    """ENA conosce la corsa con 0 read: la dimensione è quella di NCBI, che le read le ha."""
    for e in (s05.lookup_many([NUOVA])[0], s05.lookup_srr(NUOVA)):
        assert (e["status"], e["source"]) == ("OK", "NCBI")
        assert (e["read_count"], e["fastq_bytes"]) == (16400000, 1310 * 1_000_000)


def test_a_gruppi_ncbi_solo_per_le_corse_senza_read(s05):
    e = s05.lookup_many([PIENA, NUOVA])
    assert [(x["status"], x["source"]) for x in e] == [("OK", "ENA"), ("OK", "NCBI")]
    assert e[0]["fastq_bytes"] == 251500813 + 282021285            # la corsa con le read resta quella di ENA
    assert Finto.richieste == [("/ena", [PIENA, NUOVA]), ("/ncbi", [NUOVA])]


def test_nemmeno_ncbi_ha_le_read_empty(s05):
    """Né ENA né NCBI hanno le read: EMPTY (la corsa esiste), non "OK con 0 byte" e non NOT_FOUND."""
    for ncbi in ({}, {NUOVA: (0, 0, 0)}):                           # NCBI non la conosce, o la conosce senza read
        Finto.ncbi = ncbi
        assert [s05.lookup_many([NUOVA])[0]["status"], s05.lookup_srr(NUOVA)["status"]] == ["EMPTY", "EMPTY"]
    assert s05.lookup_many(["SRR9999999"])[0]["status"] == "NOT_FOUND"   # un codice che non esiste resta NOT_FOUND


def test_cache_della_1_3_0_e_empty_si_richiedono(s05, tmp_path, capsys, monkeypatch):
    """Il progetto fallito con la 1.3.0 si sblocca senza cancellare nulla; un EMPTY si richiede la volta dopo."""
    (tmp_path / "size").mkdir()
    (tmp_path / "size" / "size_cache.json").write_text(json.dumps({NUOVA: {      # come l'ha scritta la 1.3.0
        "status": "OK", "accession": NUOVA, "fastq_bytes": 0, "read_count": 0, "base_count": 0, "source": "ENA"}}),
        encoding="utf-8")
    codice, testo, cache = stima(s05, tmp_path, capsys, monkeypatch)
    assert codice == 0 and "1 to query, 0 cached" in testo
    assert (cache[NUOVA]["status"], cache[NUOVA]["source"], cache[NUOVA]["fastq_bytes"]) == ("OK", "NCBI", 1310000000)
    assert "Estimated download       : 1.31 GB" in testo
    assert f"{NUOVA}: size taken from NCBI (ENA unavailable, without this run or without its reads)" in testo   # P22
    Finto.ncbi = {}                                                 # un altro progetto, NCBI non ha ancora le read
    altro = tmp_path / "altro"
    altro.mkdir()
    codice, testo, cache = stima(s05, altro, capsys, monkeypatch)
    assert codice == 4 and cache[NUOVA]["status"] == "EMPTY"
    Finto.ncbi = {NUOVA: (16400000, 4900000000, 1310)}              # qualche giorno dopo le read ci sono
    codice, testo, cache = stima(s05, altro, capsys, monkeypatch)
    assert codice == 0 and "1 to query, 0 cached" in testo and cache[NUOVA]["status"] == "OK"
    codice, testo, cache = stima(s05, altro, capsys, monkeypatch)   # una risposta buona resta in cache
    assert codice == 0 and "0 to query, 1 cached" in testo


def test_nessuna_corsa_con_le_read_messaggio_giusto(s05, tmp_path, capsys, monkeypatch):
    """Il log non si contraddice più ("OK 1" e poi "resolved (OK): 0") e non dice di controllare i codici SRR."""
    Finto.ncbi = {}
    codice, testo, _cache = stima(s05, tmp_path, capsys, monkeypatch)
    assert codice == 4
    assert "[1/1] -> OK 0, EMPTY 1, NOT_FOUND 0, ERROR 0" in testo and f"[SKIP] {NUOVA} -> EMPTY" in testo
    fine = [r for r in testo.splitlines() if r.startswith("[FAIL]")]
    assert len(fine) == 1 and "neither ENA nor NCBI has their reads yet" in fine[0]
    assert "runs were not found" in fine[0]                         # un motore di prima lo riconosce ancora
    assert "Check the SRR list" not in testo
    sbagliato = tmp_path / "sbagliato"
    sbagliato.mkdir()
    codice, testo, _cache = stima(s05, sbagliato, capsys, monkeypatch, ["SRR9999999"])
    assert codice == 4 and "the runs were not found. Check the SRR list." in testo      # codice sbagliato: come prima
