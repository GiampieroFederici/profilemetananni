# -*- coding: utf-8 -*-
"""R12 (pulsante Aggiorna) e D168 (numero di versione nello zip). Gira con l'ambiente dell'app su Windows:
  app\\.venv\\Scripts\\python -m pytest tests/test_aggiorna.py
1. app/aggiorna.py contro una Release finta servita da un server locale (versione uguale, più nuova, più vecchia, rete
   assente, JSON rotto, limite di richieste, asset mancante, digest e dimensione sbagliati, zip non compatibile).
2. La pagina "I miei progetti": pulsanti spenti mentre il motore lavora, novità come testo semplice, niente scarico
   senza il Sì, con il Sì scarica, controlla, estrae e lancia lo script.
3. installer/windows/aggiorna_pmn.ps1: sintassi col parser di PowerShell e il suo percorso con la WSL finta (funzioni
   sostituite dopo ". aggiorna_pmn.ps1"): app sostituita e ripristinabile, dati dell'utente (cartella finta) intatti.
Niente rete vera, niente WSL vera, niente registro: tutto in cartelle temporanee."""
import hashlib
import http.server
import io
import json
import os
import subprocess
import sys
import threading
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

RADICE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADICE))
PS1 = RADICE / "installer" / "windows" / "aggiorna_pmn.ps1"

from app import aggiorna  # noqa: E402


# ---------------- Release finta ----------------
def zip_pacchetto(con_script=True, extra=None):
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        z.writestr("profilemetananni/VERSIONE.txt", "profilemetananni 9.0.0\ncommit abc1234\n")
        z.writestr("profilemetananni/app_windows/ProfileMetaNanni/ProfileMetaNanni.exe", b"nuova")
        if con_script:
            z.writestr("profilemetananni/installer/windows/aggiorna_pmn.ps1", "# finto")
        for nome, dati in (extra or {}).items():
            z.writestr(nome, dati)
    return b.getvalue()


class Finta(http.server.BaseHTTPRequestHandler):
    rotte = {}                                      # percorso -> (codice, intestazioni, corpo)

    def do_GET(self):
        codice, intestazioni, corpo = self.rotte.get(self.path, (404, {}, b"{}"))
        self.send_response(codice)
        for k, v in intestazioni.items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def log_message(self, *a):
        pass


@pytest.fixture
def server():
    s = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Finta)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{s.server_address[1]}"

    def release(tag, zip_=None, digest=True, corpo="**Novità**: più veloce", nome="profilemetananni_abc1234.zip",
                byte=None):
        zip_ = zip_pacchetto() if zip_ is None else zip_
        Finta.rotte["/pacchetto.zip"] = (200, {"Content-Type": "application/zip"}, zip_)
        asset = {"name": nome, "size": len(zip_) if byte is None else byte, "browser_download_url": base + "/pacchetto.zip"}
        if digest:
            asset["digest"] = "sha256:" + (hashlib.sha256(zip_).hexdigest() if digest is True else digest)
        Finta.rotte["/latest"] = (200, {"Content-Type": "application/json"},
                                  json.dumps({"tag_name": tag, "body": corpo, "assets": [asset],
                                              "html_url": "https://github.com/x/y/releases/tag/" + tag}).encode())
        return base + "/latest"
    yield release
    s.shutdown()
    Finta.rotte = {}


def test_versione_e_confronto():
    assert aggiorna.versione("v1.10.0") > aggiorna.versione("1.9.9") > aggiorna.versione("v1.1.0")
    assert aggiorna.VERSIONE == "1.1.0" and aggiorna.versione(aggiorna.VERSIONE) == (1, 1, 0)
    for male in ("1.1", "v1.1.0-rc1", "", "latest"):
        with pytest.raises(ValueError):
            aggiorna.versione(male)


@pytest.mark.parametrize("tag, stato", [("v1.1.0", "uguale"), ("v1.2.0", "nuova"), ("v1.0.0", "vecchia")])
def test_controlla_uguale_nuova_vecchia(server, tag, stato):
    r = aggiorna.controlla(server(tag), installata="1.1.0")
    assert r["stato"] == stato and r["installata"] == "1.1.0" and r["nuova"] == tag[1:]
    assert r["novita"] == "Novità: più veloce"
    assert (r["pacchetto"] is not None) == (stato == "nuova")


def test_rete_assente():
    with pytest.raises(aggiorna.ErroreAggiorna) as e:
        aggiorna.controlla("http://127.0.0.1:9/latest", timeout=2)    # porta chiusa
    assert e.value.codice == "RETE"


def test_json_rotto_e_tag_strano(server):
    url = server("v1.2.0")
    for corpo in (b"{non json", json.dumps({"tag_name": "ultima"}).encode(), b"[]"):
        Finta.rotte["/latest"] = (200, {}, corpo)
        with pytest.raises(aggiorna.ErroreAggiorna) as e:
            aggiorna.controlla(url)
        assert e.value.codice == "RISPOSTA"


def test_limite_di_richieste(server):
    url = server("v1.2.0")
    Finta.rotte["/latest"] = (403, {"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "1793340566"}, b"{}")
    with pytest.raises(aggiorna.ErroreAggiorna) as e:
        aggiorna.controlla(url)
    assert e.value.codice == "LIMITE" and "Riprova dopo le" in e.value.cosa_fare
    Finta.rotte["/latest"] = (500, {}, b"{}")
    with pytest.raises(aggiorna.ErroreAggiorna) as e:
        aggiorna.controlla(url)
    assert e.value.codice == "RISPOSTA"


def test_asset_mancante(server):
    r = aggiorna.controlla(server("v1.2.0", nome="sorgenti.tar.gz"))
    assert r["stato"] == "nuova" and r["pacchetto"] is None


def test_solo_https():
    with pytest.raises(aggiorna.ErroreAggiorna) as e:
        aggiorna.controlla("http://example.com/latest")
    assert e.value.codice == "INDIRIZZO"
    assert aggiorna.sicuro(aggiorna.URL_ULTIMA) == aggiorna.URL_ULTIMA


def test_novita_testo_semplice_e_corto():
    t = aggiorna.testo_semplice("## Titolo\n<script>alert(1)</script><b>forte</b> [link](https://x.y) ![i](a.png)\r\n"
                                "\n\n\n- punto `codice`\n" + "parola " * 400)
    assert "<" not in t and "https" not in t and "##" not in t and "`" not in t and "\n\n\n" not in t
    assert t.startswith("Titolo\nalert(1)forte link") and t.endswith(" ...") and len(t) <= aggiorna.MAX_NOVITA + 4


def test_scarica_ed_estrai(server, tmp_path):
    r = aggiorna.controlla(server("v1.2.0"))
    passi = []
    zip_ = aggiorna.scarica(r["pacchetto"], tmp_path, lambda f, t: passi.append((f, t)))
    assert passi[-1] == (r["pacchetto"]["byte"],) * 2
    radice = aggiorna.estrai(zip_, tmp_path)
    assert radice.joinpath(*aggiorna.PS1).is_file() and radice.joinpath(*aggiorna.APP_EXE).read_bytes() == b"nuova"


@pytest.mark.parametrize("caso", ["digest", "byte"])
def test_pacchetto_diverso(server, tmp_path, caso):
    url = server("v1.2.0", digest="0" * 64) if caso == "digest" else server("v1.2.0", byte=10)
    r = aggiorna.controlla(url)
    with pytest.raises(aggiorna.ErroreAggiorna) as e:
        aggiorna.scarica(r["pacchetto"], tmp_path)
    assert e.value.codice == "PACCHETTO_DIVERSO" and list(tmp_path.iterdir()) == []   # niente file a metà


def test_senza_digest_si_controllano_i_byte(server, tmp_path):
    r = aggiorna.controlla(server("v1.2.0", digest=False))
    assert r["pacchetto"]["sha256"] is None
    assert aggiorna.scarica(r["pacchetto"], tmp_path).is_file()


def test_annulla_scarico(server, tmp_path):
    r = aggiorna.controlla(server("v1.2.0"))
    with pytest.raises(aggiorna.ErroreAggiorna) as e:
        aggiorna.scarica(r["pacchetto"], tmp_path, fermo=lambda: True)
    assert e.value.codice == "ANNULLATO" and list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("zip_, codice", [
    (zip_pacchetto(con_script=False), "INCOMPATIBILE"),                       # come lo zip della 1.0.0
    (zip_pacchetto(extra={"../fuori.txt": "x"}), "PACCHETTO_DIVERSO"),        # file fuori dalla cartella
    (b"non sono uno zip", "PACCHETTO_DIVERSO"),
])
def test_estrai_rifiuta(tmp_path, zip_, codice):
    f = tmp_path / "p.zip"
    f.write_bytes(zip_)
    with pytest.raises(aggiorna.ErroreAggiorna) as e:
        aggiorna.estrai(f, tmp_path / "lavoro")
    assert e.value.codice == codice and not (tmp_path / "fuori.txt").exists()


def test_estrai_disco_che_non_va(tmp_path, monkeypatch):
    """Disco pieno o percorso troppo lungo (WinError 206 visto il 30/10 con la 1.0.0 in una cartella profonda)."""
    f = tmp_path / "p.zip"
    f.write_bytes(zip_pacchetto())

    def rotto(*a, **k):
        raise OSError(206, "Nome del file o estensione troppo lunga")
    monkeypatch.setattr(zipfile.ZipFile, "extractall", rotto)
    with pytest.raises(aggiorna.ErroreAggiorna) as e:
        aggiorna.estrai(f, tmp_path / "lavoro")
    assert e.value.codice == "DISCO" and e.value.cosa_fare


def test_precedente(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert aggiorna.precedente() is None
    c = tmp_path / "profilemetananni"
    (c / "app.precedente").mkdir(parents=True)
    (c / "app.precedente" / "ProfileMetaNanni.exe").write_bytes(b"x")
    assert aggiorna.precedente() is None                       # manca lo script che sa rimetterla
    (c / "aggiorna_pmn.ps1").write_text("#", encoding="utf-8")
    assert aggiorna.precedente() == c / "aggiorna_pmn.ps1"


def test_versione_nello_zip():
    """D168: VERSIONE.txt con la versione (prima riga) e il commit (seconda riga, come prima)."""
    pytest.importorskip("PyInstaller")
    pytest.importorskip("PIL")
    sys.path.insert(0, str(RADICE / "installer" / "windows"))
    import costruisci_pacchetto
    assert costruisci_pacchetto.versione_txt("abc1234") == "profilemetananni 1.1.0\ncommit abc1234\n"


# ---------------- la pagina ----------------
pytestqt = pytest.importorskip("pytestqt")
from app import finestra, progetto  # noqa: E402
from app.pagine import home  # noqa: E402
from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QLabel  # noqa: E402


@pytest.fixture
def f(qtbot, monkeypatch, tmp_path):
    monkeypatch.setenv("PMN_MOTORE", "finto")
    monkeypatch.setenv("PMN_FINTO_OPZIONI", "--velocita 0")
    (tmp_path / "temp").mkdir()
    monkeypatch.setenv("TEMP", str(tmp_path / "temp"))
    monkeypatch.setenv("TMP", str(tmp_path / "temp"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "locale"))
    monkeypatch.setattr(progetto, "cartella_progetti", lambda: tmp_path / "progetti")
    monkeypatch.setattr(finestra, "AVVIO_MIN_MS", 0)
    w = finestra.Finestra(movimento=False)
    qtbot.addWidget(w)
    w.show()
    w.avvia()
    qtbot.waitUntil(lambda: w.attuale == "home", timeout=30000)
    return w


CORSA = SimpleNamespace(nome="corsa", cartella=Path("corsa_finta"))   # un progetto in analisi


def scritte(pagina):
    return [lab.text() for lab in pagina.zona_aggiorna.parentWidget().findChildren(QLabel) if not lab.isHidden()]


def test_versione_in_testata_e_in_home(f):
    assert "v1.1.0" in [lab.text() for lab in f.zona_testata.findChildren(QLabel)]
    assert "Versione installata: 1.1.0." in scritte(f.pagine["home"])


def test_spento_durante_un_analisi(f):
    h = f.pagine["home"]
    assert h.cerca.isEnabled() and not h.nota_occupato.isVisible()
    f.contesto.progetto_in_analisi = CORSA
    f.vai("home")
    assert not h.cerca.isEnabled() and h.nota_occupato.isVisible()
    h.cerca_aggiornamenti()                                    # anche premuto per forza: non parte nulla
    assert not h._in_rete
    f.contesto.progetto_in_analisi = None
    f.vai("home")
    assert h.cerca.isEnabled()


def test_controllo_e_aggiornamento_con_consenso(f, qtbot, server, monkeypatch, tmp_path):
    h = f.pagine["home"]
    url = server("v1.2.0", corpo="<b>grassetto</b> e <a href='x'>link</a>")
    monkeypatch.setattr(aggiorna.controlla, "__defaults__", (url, aggiorna.VERSIONE, aggiorna.TIMEOUT))
    monkeypatch.setattr(aggiorna, "puo_installare", lambda: True)
    lanciati, domande = [], []
    monkeypatch.setattr(aggiorna, "avvia_script", lambda s, r=False: lanciati.append((s, r)))
    risposta = [False]
    monkeypatch.setattr(home.PaginaHome, "conferma", lambda self, t, x: domande.append(x) or risposta[0])
    h.cerca_aggiornamenti()
    qtbot.waitUntil(lambda: not h._in_rete, timeout=10000)
    assert "È disponibile la versione 1.2.0." in scritte(h)
    novita = next(lab for lab in h.findChildren(QLabel) if "grassetto" in lab.text())
    assert novita.textFormat() == Qt.PlainText and novita.text() == "grassetto e link"
    aggiorna_adesso = next(b for b in h.findChildren(home.QPushButton) if b.text() == "Aggiorna adesso")
    aggiorna_adesso.click()                                    # risposta No: nulla si scarica
    assert len(domande) == 1 and "1.2.0" in domande[0] and not h._in_rete
    assert not aggiorna.cartella_lavoro().exists() and lanciati == []
    risposta[0] = True
    aggiorna_adesso.click()
    qtbot.waitUntil(lambda: bool(lanciati), timeout=10000)
    script, ripristina = lanciati[0]
    assert script == aggiorna.cartella_lavoro() / "profilemetananni" / "installer" / "windows" / \
        "aggiorna_pmn.ps1" and script.is_file() and ripristina is False
    qtbot.waitUntil(lambda: not f.isVisible(), timeout=5000)  # l'app si chiude: lo script aspetta questo


def test_errori_mostrati(f, qtbot, monkeypatch):
    h = f.pagine["home"]
    monkeypatch.setattr(aggiorna.controlla, "__defaults__", ("http://127.0.0.1:9/latest", aggiorna.VERSIONE, 2))
    h.cerca_aggiornamenti()
    qtbot.waitUntil(lambda: not h._in_rete, timeout=10000)
    assert "Non riesco a raggiungere GitHub." in scritte(h) and h.cerca.isEnabled()


def test_torna_alla_versione_precedente(f, qtbot, monkeypatch, tmp_path):
    h = f.pagine["home"]
    assert not h.indietro.isVisible()
    c = tmp_path / "locale" / "profilemetananni"
    (c / "app.precedente").mkdir(parents=True)
    (c / "app.precedente" / "ProfileMetaNanni.exe").write_bytes(b"x")
    (c / "aggiorna_pmn.ps1").write_text("#", encoding="utf-8")
    lanciati = []
    monkeypatch.setattr(aggiorna, "avvia_script", lambda s, r=False: lanciati.append((s, r)))
    monkeypatch.setattr(home.PaginaHome, "conferma", lambda self, t, x: True)
    f.vai("home")
    assert h.indietro.isVisible() and h.indietro.isEnabled()
    f.contesto.progetto_in_analisi = CORSA
    f.vai("home")
    assert not h.indietro.isEnabled()
    h.torna_indietro()
    assert lanciati == []
    f.contesto.progetto_in_analisi = None
    f.vai("home")
    h.indietro.click()
    assert lanciati == [(c / "aggiorna_pmn.ps1", True)]


# ---------------- aggiorna_pmn.ps1 ----------------
def test_ps1_sintassi():
    leggi = (f"$e = $null; [void][System.Management.Automation.Language.Parser]::ParseFile('{PS1}', [ref]$null, [ref]$e); "
             "$e | ForEach-Object { $_.Message }")
    r = subprocess.run(["powershell.exe", "-NoProfile", "-Command", leggi], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0 and r.stdout.strip() == "", r.stdout + r.stderr


FINTI = r"""
function Avviso($t) { "AVVISO $t" | Out-File -Append -Encoding utf8 $Registro }
function Domanda($t) { "DOMANDA $t" | Out-File -Append -Encoding utf8 $Registro; $Risposta }
function MostraBarra($t, $p) {}
function AvviaApp { 'AVVIA_APP' | Out-File -Append -Encoding utf8 $Registro }
function SpazioWindows { [pscustomobject]@{ Disco = 'D:'; Liberi = $Liberi } }
function Wsl([string]$argomenti, [scriptblock]$ogniRiga = {}) {
    "WSL $argomenti" | Out-File -Append -Encoding utf8 $Registro
    $script:Uscita = New-Object Collections.Generic.List[string]
    if ($argomenti -eq '-l -q') { $script:Uscita.Add('Ubuntu'); $script:Uscita.Add('pmn'); return 0 }
    if ($argomenti -like '*cat /home/pmn/.pmn/stato/esegui.lock') {
        if ($Analisi) { $script:Uscita.Add('{"corsa": "x", "pid": 4242, "pgid": 4242}'); return 0 } else { return 1 } }
    if ($argomenti -like '*cat /home/pmn/.pmn/stato/installa.lock') { return 1 }
    if ($argomenti -like '*test -d /proc/4242') { return 0 }
    if ($argomenti -like '*prepara_pmn.sh') { return $Prepara }
    if ($argomenti -like '*--stima') {
        & $ogniRiga ('{"tipo": "fine", "esito": "ok", "risultato": {"da_scaricare_gb": ' + $Gb + '}}') | Out-Null; return 0 }
    if ($argomenti -like '*--si') { return $Installa }
    return 0
}
"""


def aggiorna_finto(tmp_path, ripristina=False, analisi=False, prepara=0, installa=0, gb=0, risposta=True,
                   liberi=1e12, precedente_vecchia=False):
    """Pacchetto nuovo, app installata e Documenti\\ProfileMetaNanni finti; lancia Aggiorna (o TornaIndietro) con la
    WSL finta. Torna (codice d'uscita, righe del registro, cartella dell'app)."""
    locale = tmp_path / "locale"
    app = locale / "profilemetananni" / "app"
    if not app.exists():
        app.mkdir(parents=True)
        (app / "ProfileMetaNanni.exe").write_bytes(b"vecchia")
    if precedente_vecchia:                                     # resto di un aggiornamento passato
        (app.parent / "app.precedente").mkdir(exist_ok=True)
        (app.parent / "app.precedente" / "ProfileMetaNanni.exe").write_bytes(b"vecchissima")
    pacchetto = tmp_path / "pacchetto" / "profilemetananni"
    (pacchetto / "installer" / "windows").mkdir(parents=True, exist_ok=True)
    (pacchetto / "app_windows" / "ProfileMetaNanni" / "_internal").mkdir(parents=True, exist_ok=True)
    (pacchetto / "app_windows" / "ProfileMetaNanni" / "ProfileMetaNanni.exe").write_bytes(b"nuova")
    (pacchetto / "app_windows" / "ProfileMetaNanni" / "_internal" / "x.dll").write_bytes(b"dll")
    (pacchetto / "VERSIONE.txt").write_text("profilemetananni 9.0.0\ncommit abc1234\n", encoding="utf-8")
    script = pacchetto / "installer" / "windows" / "aggiorna_pmn.ps1"
    script.write_bytes(PS1.read_bytes())
    registro = tmp_path / "registro.txt"
    registro.unlink(missing_ok=True)
    chiama = (f"$env:LOCALAPPDATA = '{locale}'; . '{script}'; $Lingua = 'it'; $Registro = '{registro}'; "
              f"$Analisi = ${str(analisi).lower()}; $Prepara = {prepara}; $Installa = {installa}; $Gb = {gb}; "
              f"$Risposta = ${str(risposta).lower()}; $Liberi = {liberi:.0f}; {FINTI}; "
              + ("TornaIndietro" if ripristina else "Aggiorna"))
    r = subprocess.run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", chiama],
                       capture_output=True, timeout=120)
    righe = registro.read_text(encoding="utf-8-sig").splitlines() if registro.exists() else []
    return r.returncode, righe, app


@pytest.fixture
def documenti(tmp_path):
    """Dati dell'utente finti: non devono cambiare mai."""
    d = tmp_path / "Documenti" / "ProfileMetaNanni" / "salame_1"
    d.mkdir(parents=True)
    (d / "config.yaml").write_text("project: salame_1\n", encoding="utf-8")
    (d / "risultati.json").write_text("{}", encoding="utf-8")
    return lambda: {p.relative_to(tmp_path): p.read_bytes() for p in (tmp_path / "Documenti").rglob("*") if p.is_file()}


@pytest.mark.skipif(sys.platform != "win32", reason="PowerShell di Windows")
def test_ps1_aggiorna_e_torna_indietro(tmp_path, documenti):
    prima = documenti()
    codice, righe, app = aggiorna_finto(tmp_path)
    assert codice == 0, righe
    assert (app / "ProfileMetaNanni.exe").read_bytes() == b"nuova" and (app / "_internal" / "x.dll").is_file()
    assert (app.parent / "app.precedente" / "ProfileMetaNanni.exe").read_bytes() == b"vecchia"
    assert (app / "VERSIONE.txt").read_text(encoding="utf-8").startswith("profilemetananni 9.0.0")
    assert (app.parent / "aggiorna_pmn.ps1").is_file()                       # serve a "Torna alla versione precedente"
    wsl = [r for r in righe if r.startswith("WSL ")]
    assert any("cp -a /home/pmn/profilemetananni /home/pmn/profilemetananni.precedente" in r for r in wsl)
    assert any("prepara_pmn.sh" in r for r in wsl) and any(r.endswith("--si") for r in wsl)
    assert not any("DOMANDA" in r for r in righe)                            # niente da scaricare: nessuna domanda
    assert "AVVIA_APP" in righe and any("ora c'è la versione 9.0.0" in r for r in righe)
    assert documenti() == prima

    codice, righe, app = aggiorna_finto(tmp_path, ripristina=True)
    assert codice == 0, righe
    assert (app / "ProfileMetaNanni.exe").read_bytes() == b"vecchia" and not (app.parent / "app.precedente").exists()
    assert any("mv /home/pmn/profilemetananni.precedente /home/pmn/profilemetananni" in r for r in righe)
    assert any("Sono tornato alla versione precedente" in r for r in righe)
    assert documenti() == prima


@pytest.mark.skipif(sys.platform != "win32", reason="PowerShell di Windows")
def test_ps1_mai_durante_un_analisi(tmp_path, documenti):
    prima = documenti()
    codice, righe, app = aggiorna_finto(tmp_path, analisi=True)
    assert codice == 1 and any("analisi" in r for r in righe if r.startswith("AVVISO"))
    assert (app / "ProfileMetaNanni.exe").read_bytes() == b"vecchia" and not (app.parent / "app.precedente").exists()
    assert not any("prepara_pmn.sh" in r or "rm -rf" in r for r in righe)
    assert documenti() == prima


@pytest.mark.skipif(sys.platform != "win32", reason="PowerShell di Windows")
def test_ps1_motore_fallito_rimette_tutto(tmp_path, documenti):
    prima = documenti()
    codice, righe, app = aggiorna_finto(tmp_path, installa=3)
    assert codice == 2 and any("Ho rimesso la versione di prima" in r for r in righe)
    assert (app / "ProfileMetaNanni.exe").read_bytes() == b"vecchia" and not (app.parent / "app.precedente").exists()
    assert any("mv /home/pmn/profilemetananni.precedente /home/pmn/profilemetananni" in r for r in righe)
    assert documenti() == prima


@pytest.mark.skipif(sys.platform != "win32", reason="PowerShell di Windows")
def test_ps1_prepara_fallito_non_tocca_l_app(tmp_path):
    """Con la app.precedente di un aggiornamento passato, un errore prima dello scambio non deve rimetterla."""
    codice, righe, app = aggiorna_finto(tmp_path, prepara=1, precedente_vecchia=True)
    assert codice == 2 and (app / "ProfileMetaNanni.exe").read_bytes() == b"vecchia"
    assert (app.parent / "app.precedente" / "ProfileMetaNanni.exe").read_bytes() == b"vecchissima"
    assert any("mv /home/pmn/profilemetananni.precedente" in r for r in righe)


@pytest.mark.skipif(sys.platform != "win32", reason="PowerShell di Windows")
def test_ps1_database_da_scaricare_chiede_prima(tmp_path):
    codice, righe, app = aggiorna_finto(tmp_path, gb=12.3, risposta=False)
    assert codice == 0 and any(r.startswith("DOMANDA") and "circa 13 GB" in r for r in righe)
    assert any("non ho cambiato nulla" in r for r in righe) and not any(r.endswith("--si") for r in righe)
    assert (app / "ProfileMetaNanni.exe").read_bytes() == b"vecchia"
    assert any("mv /home/pmn/profilemetananni.precedente" in r for r in righe)

    codice, righe, app = aggiorna_finto(tmp_path, gb=12.3, liberi=5e9)        # spazio di Windows che non basta
    assert codice == 1 and any("non basta" in r for r in righe) and not any("DOMANDA" in r for r in righe)
    assert (app / "ProfileMetaNanni.exe").read_bytes() == b"vecchia"
