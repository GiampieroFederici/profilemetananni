# -*- coding: utf-8 -*-
"""B1: il pacchetto dell'app. installa_pmn.ps1 copia l'app e mette le icone (rifacibile); il pacchetto contiene
le stesse cartelle che prepara_pmn.sh copia nella WSL e il doppio clic punta all'installatore vero.
Solo su Windows:  app\\.venv\\Scripts\\python -m pytest tests/test_app_pacchetto.py"""
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(os.name != "nt", reason="installatore Windows")
RADICE = Path(__file__).resolve().parent.parent
PS1 = RADICE / "installer" / "windows" / "installa_pmn.ps1"


def powershell(script):
    r = subprocess.run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command",
                        "[Console]::OutputEncoding = [Text.Encoding]::UTF8; " + script],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert r.returncode == 0, r.stderr
    return r.stdout


def test_installa_app_copia_e_mette_le_icone(tmp_path):
    sorgente = tmp_path / "pacchetto" / "ProfileMetaNanni"
    (sorgente / "_internal").mkdir(parents=True)
    (sorgente / "ProfileMetaNanni.exe").write_bytes(b"nuova")
    (sorgente / "_internal" / "libreria.dll").write_bytes(b"x")
    exe = tmp_path / "locale" / "app" / "ProfileMetaNanni.exe"
    exe.parent.mkdir(parents=True)
    (exe.parent / "vecchio.txt").write_text("di una versione prima")          # rifare l'installazione lo toglie
    lnk = [tmp_path / "Desktop.lnk", tmp_path / "Start.lnk"]
    chiama = f". '{PS1}'; InstallaApp '{sorgente}' '{exe}' @('{lnk[0]}', '{lnk[1]}')"
    powershell(chiama)
    powershell(chiama)                                                           # due volte: deve andare lo stesso
    assert exe.read_bytes() == b"nuova" and (exe.parent / "_internal" / "libreria.dll").is_file()
    assert not (exe.parent / "vecchio.txt").exists()
    for c in lnk:
        bersaglio = powershell(f"(New-Object -ComObject WScript.Shell).CreateShortcut('{c}').TargetPath").strip()
        assert Path(bersaglio) == exe


def test_pacchetto_come_prepara_pmn():
    sys.path.insert(0, str(RADICE / "installer" / "windows"))
    import costruisci_pacchetto as c
    from test_prepara_pmn import copiate
    assert set(c.MOTORE) == copiate()                                            # stesse cartelle copiate nella WSL
    bersaglio = c.LANCIATORE.split('"%~dp0')[1].split('"')[0].replace("\\", "/")
    assert (RADICE / bersaglio) == PS1                                           # il doppio clic avvia l'installatore vero
    assert "--headless" in c.LANCIATORE and c.LANCIATORE.endswith("\r\n")        # niente finestra nera; .cmd con CRLF


def test_doppio_clic_dentro_lo_zip_spiega_come_estrarre():
    """B2: dal doppio clic dentro lo zip Windows estrae solo il .cmd in %TEMP%: senza controllo non succedeva nulla."""
    import base64
    sys.path.insert(0, str(RADICE / "installer" / "windows"))
    import costruisci_pacchetto as c
    righe = c.LANCIATORE.split("\r\n")
    controllo = next(i for i, r in enumerate(righe) if r.startswith(r'if not exist "%~dp0installer\windows\installa_pmn.ps1"'))
    avvio = next(i for i, r in enumerate(righe) if "-File" in r)
    assert controllo < avvio                                                     # prima controlla, poi installa
    codice = righe[controllo].split("-EncodedCommand ")[1].split()[0].rstrip(")")
    testo = base64.b64decode(codice).decode("utf-16-le")
    assert "Estrai tutto" in testo and "Installa profilemetananni" in testo and "TopMost" in testo
    c.LANCIATORE.encode("ascii")                                                 # il .cmd resta ASCII


def test_installazione_lunga_senza_sospensione():
    """B2: col catalogo intero il download dura piu' del tempo dopo cui Windows sospende il PC: l'installatore lo impedisce."""
    stato = ("Add-Type -Namespace Prova -Name Energia -MemberDefinition "
             "'[DllImport(\"powrprof.dll\")] public static extern uint CallNtPowerInformation(int l, System.IntPtr i, uint il, out uint o, uint ol);'; "
             "$o = 0; [void][Prova.Energia]::CallNtPowerInformation(16, [System.IntPtr]::Zero, 0, [ref]$o, 4); $o")
    assert int(powershell(f". '{PS1}'; NienteSospensione; {stato}").strip()) & 0x1    # ES_SYSTEM_REQUIRED attivo
    testo = PS1.read_text(encoding="utf-8")
    assert testo.index("NienteSospensione\n") < testo.index("Riprendi   # se si interrompe")             # chiamata in fase 2


def test_attivazione_wsl_con_la_barra():
    """B2 (P3): WSL si attivava per circa 2 min 30 s senza nessun segno a schermo. Ora c'e' una barra animata e
    l'attesa non blocca la finestra (un processo atteso con -Wait la farebbe risultare "Non risponde")."""
    codice = powershell(f". '{PS1}'; $p = Start-Process cmd.exe -ArgumentList '/c', 'ping -n 2 127.0.0.1 >nul & exit 7' "
                        "-WindowStyle Hidden -PassThru; AttendiProcesso $p").strip()
    assert codice == "7"
    testo = PS1.read_text(encoding="utf-8-sig")
    fase1 = testo[testo.index("if ($Fase -eq 1 -and -not (WslPronta))"):testo.index("# ===================== fase 2")]
    assert "-Wait" not in fase1
    i, j, k = (fase1.index(s) for s in ("Start-Process wsl.exe", "MostraBarra", "AttendiProcesso $p"))
    assert i < j < k                                                             # dopo il Si di Windows, poi si aspetta


def test_app_copiata_senza_segno_di_internet(tmp_path):
    """B2 (P10): estratti da uno zip scaricato, i file portano il segno "da internet" (Zone.Identifier) e Windows
    chiede conferma anche per l'app. Resta un solo avviso, quello del primo doppio clic: l'app copiata non lo porta."""
    sorgente = tmp_path / "pacchetto" / "ProfileMetaNanni"
    (sorgente / "_internal").mkdir(parents=True)
    for f in (sorgente / "ProfileMetaNanni.exe", sorgente / "_internal" / "libreria.dll"):
        f.write_bytes(b"x")
        with open(f"{f}:Zone.Identifier", "w") as z:                               # come dopo "Estrai tutto"
            z.write("[ZoneTransfer]\nZoneId=3\n")
    exe = tmp_path / "locale" / "app" / "ProfileMetaNanni.exe"
    powershell(f". '{PS1}'; InstallaApp '{sorgente}' '{exe}' @('{tmp_path / 'Desktop.lnk'}')")
    for f in (exe, exe.parent / "_internal" / "libreria.dll"):
        assert f.is_file() and not os.path.exists(f"{f}:Zone.Identifier")


def test_messaggi_con_gli_accenti_veri():
    """B2 (P5): i messaggi dell'installatore avevano apostrofi al posto degli accenti ("scarichera'", "e'").
    Si controlla il testo come lo legge PowerShell 5.1 (UTF-8 con BOM, altrimenti le lettere accentate si rompono)."""
    import re
    assert PS1.read_bytes().startswith(b"\xef\xbb\xbf")
    leggi = (f"$a = [System.Management.Automation.Language.Parser]::ParseFile('{PS1}', [ref]$null, [ref]$null); "
             "$a.FindAll({ param($n) $n -is [System.Management.Automation.Language.StringConstantExpressionAst] -or "
             "$n -is [System.Management.Automation.Language.ExpandableStringExpressionAst] }, $true) | "
             "ForEach-Object { $_.Value }")
    r = subprocess.run(["powershell.exe", "-NoProfile", "-Command", "[Console]::OutputEncoding = [Text.Encoding]::UTF8; " + leggi],
                       capture_output=True, text=True, encoding="utf-8")
    testi = r.stdout
    assert "Tutto pronto: profilemetananni è installato e funziona." in testi
    assert "Tra poco Windows ti chiederà il permesso: rispondi Sì." in testi
    rimasti = re.findall(r"\b(?:e|piu|gia|puo|chiedera|scarichera|velocita|cosi|perche)'(?=[\s.,:;)!?]|$)", testi, re.M)
    assert rimasti == []


def test_benvenuto_di_wsl_chiuso_se_compare():
    """B2 (P4): dopo la registrazione di Ubuntu il servizio WSL apre da solo "Benvenuto in WSL" (wslsettings.exe,
    LxssUserSession.cpp _LaunchOOBEIfNeeded). Rete di sicurezza: si chiudono solo le finestre nate dopo l'inizio."""
    import time
    finestra = subprocess.Popen(["powershell.exe", "-NoProfile", "-Command",
                                 "Add-Type -AssemblyName System.Windows.Forms; "
                                 "(New-Object Windows.Forms.Form -Property @{ Text = 'prova_B2_benvenuto' }).ShowDialog()"])
    try:
        time.sleep(4)                                                            # la finestra si apre
        powershell(f". '{PS1}'; ChiudiBenvenuto (Get-Process -Id {finestra.pid}).StartTime.AddSeconds(-1) 'powershell' 10")
        assert finestra.wait(timeout=15) is not None                             # chiusa come con la X
    finally:
        if finestra.poll() is None:
            finestra.kill()
    testo = PS1.read_text(encoding="utf-8-sig")
    i = testo.index("--install Ubuntu-24.04")
    assert "MostraBarra (T 'linux_barra')" in testo[testo.rindex("MostraBarra", 0, i):i]
    assert "ChiudiBenvenuto" in testo[i:testo.index("prepara_pmn.sh")]           # chiuso subito dopo


def _testi_ps1():
    """{chiave: [italiano, inglese]} della tabella $TESTI dell'installatore, come la legge PowerShell 5.1."""
    import json
    uscita = powershell("[Console]::OutputEncoding = [Text.Encoding]::UTF8; "
                        f". '{PS1}'; $TESTI | ConvertTo-Json -Compress")
    return json.loads(uscita)


def test_installatore_in_italiano_e_inglese():
    """B2 (P12): testi in una sola tabella, ognuno in italiano e in inglese, con gli stessi {0} {1}..."""
    import re
    testi = _testi_ps1()
    assert len(testi) >= 20
    for chiave, (it, en) in testi.items():
        assert it and en and it != en, chiave
        assert sorted(re.findall(r"\{\d\}", it)) == sorted(re.findall(r"\{\d\}", en)), chiave
        assert "—" not in it + en and "microb" not in (it + en).lower(), chiave
    sorgente = PS1.read_text(encoding="utf-8-sig")
    assert not re.findall(r'\b(Avviso|Ferma|Domanda|MostraBarra) "', sorgente)        # niente frasi fuori tabella


def test_lingua_dell_installatore_dalla_lingua_di_windows():
    scelte = powershell(f". '{PS1}'; 'it-IT', 'it-CH', 'en-US', 'de-DE' | ForEach-Object {{ SceltaLingua $_ }}").split()
    assert scelte == ["it", "it", "en", "en"]
    it = powershell("[Console]::OutputEncoding = [Text.Encoding]::UTF8; "
                    f". '{PS1}'; $Lingua = 'it'; T 'pronto'").strip()
    en = powershell(f". '{PS1}'; $Lingua = 'en'; T 'pronto'").strip()
    assert it == "Tutto pronto: profilemetananni è installato e funziona."       # italiano come prima, con l'accento
    assert en == "All ready: profilemetananni is installed and works."


def test_lingua_dell_app_coerente_con_l_installatore():
    """Con Windows in inglese l'app si apre in inglese, ma una scelta già fatta dalla persona non si tocca."""
    chiave = r"HKCU:\Software\ProfileMetaNanni_prova_B2\app"
    try:
        powershell(f". '{PS1}'; ImpostaLinguaApp 'en' '{chiave}'")
        assert powershell(f"(Get-ItemProperty '{chiave}').lingua").strip() == "en"
        powershell(f"Set-ItemProperty '{chiave}' lingua 'it'; . '{PS1}'; ImpostaLinguaApp 'en' '{chiave}'")
        assert powershell(f"(Get-ItemProperty '{chiave}').lingua").strip() == "it"
    finally:
        powershell(r"Remove-Item -Recurse -Force 'HKCU:\Software\ProfileMetaNanni_prova_B2' -ErrorAction SilentlyContinue")


def test_messaggio_estrai_in_due_lingue():
    import base64
    sys.path.insert(0, str(RADICE / "installer" / "windows"))
    import costruisci_pacchetto as c
    riga = next(r for r in c.LANCIATORE.split("\r\n") if r.startswith("if not exist"))
    testo = base64.b64decode(riga.split("-EncodedCommand ")[1].split()[0]).decode("utf-16-le")
    assert "Get-UICulture" in testo and "Estrai tutto" in testo and "Extract All" in testo


def test_benvenuto_di_wsl_evitato_con_oobecomplete():
    """B2 (P4): OOBEComplete=1 per l'utente PRIMA della prima distribuzione, così il servizio
    WSL non apre "Benvenuto in WSL"; la chiusura automatica resta come rete di sicurezza."""
    chiave = r"HKCU:\Software\ProfileMetaNanni_prova_B2\Lxss"
    try:
        powershell(f". '{PS1}'; SaltaBenvenuto '{chiave}'")
        tipo = powershell(f"(Get-Item '{chiave}').GetValueKind('OOBEComplete')").strip()
        valore = powershell(f"(Get-ItemProperty '{chiave}').OOBEComplete").strip()
        assert (tipo, valore) == ("DWord", "1")
    finally:
        powershell(r"Remove-Item -Recurse -Force 'HKCU:\Software\ProfileMetaNanni_prova_B2' -ErrorAction SilentlyContinue")
    testo = PS1.read_text(encoding="utf-8-sig")
    i = testo.index("--install Ubuntu-24.04")
    assert "SaltaBenvenuto" in testo[testo.rindex("MostraBarra", 0, i):i]          # prima della registrazione
    assert "_LaunchOOBEIfNeeded" in testo                                            # riferimento al sorgente di WSL


def test_messaggi_del_motore_in_inglese():
    """B2 (P12): ogni frase che installa_motore.sh passa a T ha la traduzione nella tabella EN, con gli stessi %s."""
    import re
    testo = (RADICE / "installer" / "installa_motore.sh").read_text(encoding="utf-8")
    tabella = dict(re.findall(r'^  \["(.*)"\]="(.*)"$', testo, re.M))
    usate = set(re.findall(r"\$\(T '([^']*)'", testo)) | set(re.findall(r'\$\(T "([^"]*)"', testo))
    assert len(usate) >= 40
    assert sorted(usate - set(tabella)) == []
    for it in usate:
        assert it.count("%s") == tabella[it].count("%s"), it
        assert "\u2014" not in tabella[it] and "microb" not in tabella[it].lower()



def test_installatore_passa_la_lingua_al_motore():
    """B2 (P12): con Windows in inglese anche le righe del motore nella barra sono in inglese; i GB da scaricare si
    leggono dal risultato della stima (un numero), non dal testo italiano."""
    testo = PS1.read_text(encoding="utf-8-sig")
    assert "if ($Lingua -ne 'it') { $motore += \" --lingua $Lingua\" }" in testo
    assert "Da scaricare: circa" not in testo and "da_scaricare_gb" in testo


def test_disco_scritto_una_volta_sola():
    """B2 (L6a sulla VM del 19/10): "sul disco C:: circa 40 GB": la lettera del disco ha già i suoi due punti."""
    for lingua in ("it", "en"):
        t = powershell(f". '{PS1}'; $Lingua = '{lingua}'; (T 'domanda_scarico') -f 26, 'C:', 40, 146, 'x'")
        assert "C::" not in t and "C: " in t, t
