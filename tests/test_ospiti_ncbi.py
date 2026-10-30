# -*- coding: utf-8 -*-
"""Difetti della VM (30/10, B2-7a, B2-8a, B2-9a) nella finestra "Aggiungi un ospite".
La domanda a NCBI passa per un server finto su questo computer: risposta valida, codice sconosciuto ({} e 404),
rete assente (porta chiusa), certificato non verificato (HTTPS con un certificato fatto qui). NCBI vero mai.
Gira con l'ambiente dell'app su Windows:  app\\.venv\\Scripts\\python -m pytest tests/test_ospiti_ncbi.py"""
import http.server
import json
import shutil
import socket
import ssl
import subprocess
import sys
import threading
from pathlib import Path

import pytest

pytest.importorskip("pytestqt")
RADICE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADICE))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app import progetto  # noqa: E402
from app.pagine import progetto as pagina  # noqa: E402
from test_app_s5b import ambiente, scritte  # noqa: E402,F401  (progetti e TEMP in tmp_path)

PHIX = {"reports": [{"accession": "GCF_000819615.1", "organism": {"organism_name": "Escherichia phage phiX174"},
                     "assembly_stats": {"total_sequence_length": "5386"}}]}


class Finto(http.server.BaseHTTPRequestHandler):
    """Come NCBI Datasets: 200 con il rapporto, 200 con {} per un codice che non c'è, 404 per un altro."""
    def do_GET(self):
        self.server.richieste.append((self.path, self.headers.get("User-Agent")))
        codice, corpo = {"/v2/genome/accession/GCF_000819615.1/dataset_report": (200, PHIX),
                         "/v2/genome/accession/GCF_999999999.9/dataset_report": (200, {})}.get(
                             self.path, (404, {"error": "not found"}))
        dati = json.dumps(corpo).encode()
        self.send_response(codice)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(dati)))
        self.end_headers()
        self.wfile.write(dati)

    def log_message(self, *a):
        pass


def server(contesto=None):
    s = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Finto)
    s.richieste = []
    if contesto:
        s.socket = contesto.wrap_socket(s.socket, server_side=True)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    return s


@pytest.fixture
def ncbi(monkeypatch):
    s = server()
    monkeypatch.setattr(progetto, "NCBI_DATASETS", f"http://127.0.0.1:{s.server_port}/v2/genome/accession/{{}}"
                                                   "/dataset_report")
    yield s
    s.shutdown()


def porta_chiusa():
    with socket.socket() as so:
        so.bind(("127.0.0.1", 0))
        return so.getsockname()[1]


# ---------------- dimensione_ncbi con la rete di Qt ----------------
def test_valido_sconosciuto_e_404(qapp, ncbi):
    assert progetto.dimensione_ncbi("GCF_000819615.1") == (5386, "Escherichia phage phiX174")
    assert progetto.dimensione_ncbi("GCF_999999999.9") is None          # B2-9a: NCBI risponde 200 con {}
    assert progetto.dimensione_ncbi("GCF_000000404.1") is None          # e 404 per altri codici
    assert ncbi.richieste[0][1] == "ProfileMetaNanni"


def test_codice_non_valido_non_esce(qapp, ncbi):
    assert progetto.dimensione_ncbi("GCF_1/../x") is None and ncbi.richieste == []


def test_rete_assente(qapp, monkeypatch):
    monkeypatch.setattr(progetto, "NCBI_DATASETS", f"http://127.0.0.1:{porta_chiusa()}/{{}}")
    with pytest.raises(progetto.NcbiNonRaggiungibile) as e:
        progetto.dimensione_ncbi("GCF_000819615.1", attesa=5)
    assert e.value.certificato is False


def test_certificato_non_verificato(qapp, monkeypatch, tmp_path):
    """Un HTTPS con un certificato che nessuna radice garantisce: errore di certificato, non di rete."""
    openssl = shutil.which("openssl") or r"C:\Program Files\Git\usr\bin\openssl.exe"
    if not Path(openssl).is_file():
        pytest.skip("openssl non trovato per fare il certificato di prova")
    chiave, cert = tmp_path / "k.pem", tmp_path / "c.pem"
    subprocess.run([openssl, "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-keyout", str(chiave), "-out",
                    str(cert), "-days", "1", "-subj", "/CN=127.0.0.1"], check=True, capture_output=True)
    contesto = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    contesto.load_cert_chain(cert, chiave)
    s = server(contesto)
    monkeypatch.setattr(progetto, "NCBI_DATASETS", f"https://127.0.0.1:{s.server_port}/v2/genome/accession/{{}}"
                                                   "/dataset_report")
    try:
        with pytest.raises(progetto.NcbiNonRaggiungibile) as e:
            progetto.dimensione_ncbi("GCF_000819615.1", attesa=10)
        assert e.value.certificato is True
    finally:
        s.shutdown()


# ---------------- testi (B2-8a) ----------------
def test_unita_e_plurali():
    assert progetto.basi_in_parole(5386) == "5.386 basi"
    assert progetto.basi_in_parole(4_641_652) == "4,6 milioni di basi"
    assert progetto.basi_in_parole(2_000_000_000) == "2,0 miliardi di basi"
    assert progetto.durata_in_parole(2) == "meno di un minuto"
    assert progetto.durata_in_parole(70) == "circa 1 minuto"
    assert progetto.durata_in_parole(300) == "circa 5 minuti"
    assert progetto.spazio_in_parole(7e-6) == "meno di 1 MB"
    assert progetto.spazio_in_parole(0.0156) == "16 MB"
    assert progetto.spazio_in_parole(1.27) == "1,3 GB"


# ---------------- finestra ----------------
def finestra(qtbot, codice):
    w = pagina.FinestraOspite(ram_gb=7.6, libero_gb=500)
    qtbot.addWidget(w)
    w.nome.setText("phixncbi")
    w.codice.setText(codice)
    w.controlla()
    return w


def test_finestra_codice_valido_phix(qtbot, ncbi):
    w = finestra(qtbot, "GCF_000819615.1")
    testo = scritte(w)
    assert "Escherichia phage phiX174: circa 5.386 basi." in testo
    assert "meno di un minuto e 200 MB di memoria, più meno di 1 MB sul disco" in testo
    assert "milioni" not in testo and "1 minuti" not in testo and "Non riesco" not in testo
    assert w.pulsante_aggiungi.isEnabled() and w.voce == {"accession": "GCF_000819615.1", "basi": 5386,
                                                          "organismo": "Escherichia phage phiX174"}


def test_finestra_codice_sconosciuto_spento(qtbot, ncbi):
    w = finestra(qtbot, "GCF_999999999.9")
    assert "NCBI non conosce il codice GCF_999999999.9." in scritte(w)
    assert "rete" not in scritte(w) and not w.pulsante_aggiungi.isEnabled() and w.voce is None


def test_finestra_rete_assente_avviso_e_si_aggiunge_senza_basi(qtbot, monkeypatch):
    monkeypatch.setattr(progetto, "NCBI_DATASETS", f"http://127.0.0.1:{porta_chiusa()}/{{}}")
    w = finestra(qtbot, "GCF_000819615.1")
    testo = scritte(w)
    assert "Non riesco a chiedere a NCBI quanto è grande questo genoma." in testo
    assert "Controlla la connessione a internet." in testo and "Puoi aggiungere l'ospite lo stesso" in testo
    assert w.pulsante_aggiungi.isEnabled() and w.voce == {"accession": "GCF_000819615.1"}   # niente basi inventate
    assert w.pulsante_controlla.isEnabled()


def test_finestra_certificato(qtbot, monkeypatch):
    def rifiuta(acc, attesa=15):
        raise progetto.NcbiNonRaggiungibile("SslHandshakeFailedError", certificato=True)
    monkeypatch.setattr(progetto, "dimensione_ncbi", rifiuta)
    w = finestra(qtbot, "GCF_000819615.1")
    assert "Non riesco a verificare il certificato del sito di NCBI." in scritte(w)
    assert "data e l'ora del computer" in scritte(w) and w.pulsante_aggiungi.isEnabled()


def test_finestra_fasta_piccolo(qtbot, tmp_path):
    g = tmp_path / "phix.fa"
    g.write_text(">phix\n" + "ACGT" * 1346 + "A\n")
    w = pagina.FinestraOspite()
    qtbot.addWidget(w)
    w.nome.setText("phixfile")
    w.scelta_file.pulsante.setChecked(True)
    w.usa_file(g)
    w.controlla()
    assert f"Genoma di circa {progetto.basi_in_parole(g.stat().st_size)}." in scritte(w)
    assert "0 milioni" not in scritte(w) and "1 minuti" not in scritte(w)
