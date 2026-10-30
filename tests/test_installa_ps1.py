# -*- coding: utf-8 -*-
"""v1.1 (R3, R5-R7, D170): the Windows part of the installer. Syntax, pure functions with fake values (space, laptop
lid, summary line, prova.conf) and the order of the steps. The real run is the test on the VM.
Windows only:  app\\.venv\\Scripts\\python -m pytest tests/test_installa_ps1.py"""
import json
import os
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(os.name != "nt", reason="installatore Windows")
RADICE = Path(__file__).resolve().parent.parent
PS1 = RADICE / "installer" / "windows" / "installa_pmn.ps1"
TESTO = PS1.read_text(encoding="utf-8-sig")
FASE2 = TESTO[TESTO.index("# ===================== fase 2"):]


def powershell(script):
    r = subprocess.run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command",
                        "[Console]::OutputEncoding = [Text.Encoding]::UTF8; " + script],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


def test_sintassi_senza_errori():
    n = powershell(f"$e = $null; [void][System.Management.Automation.Language.Parser]::ParseFile('{PS1}', [ref]$null, [ref]$e); "
                   "$e.Count")
    assert n == "0"


POWERCFG_IT = """Nome alias sottogruppo: SUB_BUTTONS
    GUID impostazione alimentazione: 5ca83367-6e45-459f-a27b-476b1d01c936  (Azione di chiusura coperchio)
      Alias GUID: LIDACTION
      Indice impostazione possibile: 000
      Nome descrittivo impostazione possibile: Non fare nulla
      Indice impostazione possibile: 001
      Nome descrittivo impostazione possibile: Sospensione
    Indice impostazione alimentazione CA corrente: 0x00000001
    Indice impostazione alimentazione CC corrente: 0x00000003"""
POWERCFG_EN = POWERCFG_IT.replace("Indice impostazione alimentazione CA corrente", "Current AC Power Setting Index") \
    .replace("Indice impostazione alimentazione CC corrente", "Current DC Power Setting Index")


@pytest.mark.parametrize("uscita", [POWERCFG_IT, POWERCFG_EN])
def test_coperchio_letto_in_ogni_lingua(uscita, tmp_path):
    f = tmp_path / "q.txt"
    f.write_text(uscita, encoding="utf-8")
    assert powershell(f". '{PS1}'; $c = LeggiCoperchio (Get-Content '{f}'); \"$($c.AC) $($c.DC)\"") == "1 3"
    assert powershell(f". '{PS1}'; $null -eq (LeggiCoperchio 'niente')") == "True"


def test_coperchio_domanda_solo_se_serve():
    casi = "(ServeDomandaCoperchio 1 7200), (ServeDomandaCoperchio 0 7200), (ServeDomandaCoperchio 1 600), " \
           "(ServeDomandaCoperchio 1 $null), (ServeDomandaCoperchio $null 7200)"
    assert powershell(f". '{PS1}'; {casi} | ForEach-Object {{ \"$_\" }}").split() == ["True", "False", "False", "True", "False"]


def test_coperchio_salvato_e_rimesso_com_era(tmp_path):
    """R5: "Non fare nulla" solo con l'alimentatore; il valore di prima resta in un file finché non è rimesso
    (anche alla ripresa dopo un'interruzione); rimesso una volta sola."""
    f = tmp_path / "coperchio.txt"
    chiamate = powershell(f". '{PS1}'; $script:Fatte = @(); $script:Powercfg = {{ param($a) $script:Fatte += ($a -join ' ') }}; "
                          f"ImpostaCoperchio 1 '{f}'; $script:Fatte += \"file:$(Get-Content '{f}')\"; "
                          f"RipristinaCoperchio '{f}'; RipristinaCoperchio '{f}'; $script:Fatte -join '|'").split("|")
    assert chiamate == ["/setacvalueindex SCHEME_CURRENT SUB_BUTTONS LIDACTION 0", "/setactive SCHEME_CURRENT", "file:1",
                        "/setacvalueindex SCHEME_CURRENT SUB_BUTTONS LIDACTION 1", "/setactive SCHEME_CURRENT"]
    assert not f.exists()


def test_spazio_dal_motore_e_messaggio():
    """R3: lo spazio che serve è il numero del motore (spazio_necessario_byte di --stima): una sola regola."""
    assert "SpazioNecessario" not in TESTO and "GB_PROGRAMMI" not in TESTO and "byte_finale" not in TESTO
    assert "$s.Serve = [double]$stima.spazio_necessario_byte" in FASE2
    m = powershell(f". '{PS1}'; $Lingua = 'it'; MessaggioSpazio ([pscustomobject]@{{ Serve = 190GB; Liberi = 150GB; Disco = 'C:' }})")
    assert "servono circa 190 GB sul disco C:, ce ne sono 150" in m and "Libera almeno 40 GB" in m
    assert powershell(f". '{PS1}'; $null -eq (MessaggioSpazio ([pscustomobject]@{{ Serve = 1GB; Liberi = 2GB; Disco = 'C:' }}))") == "True"
    assert powershell(f". '{PS1}'; (SpazioBasso 4GB), (SpazioBasso 6GB) | ForEach-Object {{ \"$_\" }}").split() == ["True", "False"]


def test_durata_in_due_lingue():
    assert powershell(f". '{PS1}'; $Lingua = 'it'; Durata 600; Durata 29160") .splitlines() == ["11 minuti", "8,1 ore"]
    assert powershell(f". '{PS1}'; $Lingua = 'en'; Durata 29160") == "8.1 hours"


def test_riga_riassuntiva_per_il_log():
    e = {"tipo": "avanzamento", "byte_fatti": 12 * 2**30, "byte_totali": 133 * 2**30, "velocita_mb_s": 8.4, "eta_s": 15000,
         "sorgente": "kraken", "sorgenti": [{"sorgente": "kraken", "byte_fatti": 2**30, "byte_totali": 85 * 2**30,
                                              "velocita_mb_s": 1.4}]}
    r = powershell(f". '{PS1}'; $Lingua = 'en'; Riassunto ('{json.dumps(e)}' | ConvertFrom-Json)")
    assert r == "RIASSUNTO: 12 di 133 GB, 8.4 MB/s, mancano 4 h 10 min (kraken 1/85 GB 1.4 MB/s)"
    e["byte_fatti"] = int(0.2 * 2**30) + 1                     # A6 (VM 30/10): "0.2 di 129.2" in Italian is "0,2 di 129,2"
    r = powershell(f". '{PS1}'; $Lingua = 'it'; Riassunto ('{json.dumps(e)}' | ConvertFrom-Json)")
    assert r == "RIASSUNTO: 0,2 di 133 GB, 8,4 MB/s, mancano 4 h 10 min (kraken 1/85 GB 1,4 MB/s)"
    assert powershell(f". '{PS1}'; $null -eq (Riassunto ('{{\"tipo\": \"avanzamento\"}}' | ConvertFrom-Json))") == "True"


def test_d170_prova_conf_con_il_solo_catalogo(tmp_path):
    """D170: la VM usa prova.conf con la sola riga catalogo=installer/catalogo_vm.tsv: sorgenti vere, altro catalogo."""
    f = tmp_path / "prova.conf"
    f.write_text("catalogo=installer/catalogo_vm.tsv\n", encoding="utf-8")
    riga = powershell(f". '{PS1}'; ArgomentiMotore (LeggiConf '{f}') 'it'")
    assert riga == ("-d pmn -u pmn -- bash /home/pmn/profilemetananni/installer/installa_motore.sh --json "
                    "--catalogo /home/pmn/profilemetananni/installer/catalogo_vm.tsv")
    assert powershell(f". '{PS1}'; ArgomentiMotore (LeggiConf '{tmp_path / 'manca.conf'}') 'en'").endswith(
        "--catalogo /home/pmn/profilemetananni/installer/catalogo.tsv --lingua en")
    f.write_text("specchio=http://192.168.1.5:8765\ncatalogo=installer/x.tsv\n", encoding="utf-8")
    assert powershell(f". '{PS1}'; ArgomentiMotore (LeggiConf '{f}') 'it'").endswith(
        "--catalogo /home/pmn/profilemetananni/installer/x.tsv --specchio http://192.168.1.5:8765")
    assert "$motore = ArgomentiMotore $Conf $Lingua" in FASE2


def test_app_copiata_solo_dopo_spazio_e_si():
    """R7 (§1.6): l'app e le icone restavano sul PC anche quando lo spazio non bastava."""
    fase1 = TESTO[TESTO.index("# ===================== fase 1"):TESTO.index("# ===================== fase 2")]
    assert "InstallaApp" not in fase1
    i = [FASE2.index(s) for s in ("MessaggioSpazio $s", "if (-not (Domanda $testo))", "InstallaApp $AppPacchetto",
                                  "--si --spazio-libero")]
    assert i == sorted(i)


def test_interrompi_ferma_senza_ripresa_da_sola():
    """R6: pulsante Interrompi con conferma; arresto voluto = niente RunOnce, coperchio rimesso; il motore si ferma con
    annulla --corsa e, se non basta, si spegne la WSL (come un PC spento: riprende lo stesso)."""
    assert "T 'interrompi_domanda'" in TESTO and "Visible = $false" in TESTO
    persona = FASE2[FASE2.index("if ($script:Fermando -eq 'persona')"):FASE2.index("if ($script:Fermando -eq 'spazio')")]
    assert "NonRiprendere" in persona and "RipristinaCoperchio" in persona and "Riprendi" not in persona.replace("NonRiprendere", "")
    assert "pmn-motore annulla --corsa" in FASE2 and "'--terminate pmn'" in FASE2[FASE2.index("function FermaMotore"):]
    ferma = TESTO[TESTO.index("function Ferma($t)"):TESTO.index("function MostraBarra")]
    assert "NonRiprendere" in ferma and "RipristinaCoperchio" in ferma
    assert FASE2.index("RipristinaCoperchio") < FASE2.index("DoveInstallare")      # alla ripresa dopo un'interruzione


VOCE, ATTIVITA = "pmn_prova_A0", "pmn_prova_A0_attivita"


def _togli_prove():
    powershell(f"Remove-ItemProperty 'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\RunOnce' -Name {VOCE} "
               f"-ErrorAction SilentlyContinue; Unregister-ScheduledTask -TaskName {ATTIVITA} -Confirm:$false "
               "-ErrorAction SilentlyContinue; 'ok'")


def test_a0_ripresa_con_runonce_e_attivita_di_riserva():
    """A0 (VM 30/10): dopo il riavvio RunOnce ha lanciato conhost ma PowerShell non è mai partito. Ora Riprendi scrive
    anche un'attività pianificata all'accesso di questo utente, 2 minuti dopo, senza amministratore; NonRiprendere
    toglie tutte e due."""
    try:
        r = powershell(f". '{PS1}'; Riprendi '{VOCE}' '{ATTIVITA}'; "
                       f"$v = (Get-ItemProperty 'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\RunOnce').{VOCE}; "
                       f"$t = Get-ScheduledTask -TaskName '{ATTIVITA}'; "
                       "@{ runonce = $v; exe = $t.Actions[0].Execute; arg = $t.Actions[0].Arguments; "
                       "trigger = $t.Triggers[0].CimClass.CimClassName; ritardo = $t.Triggers[0].Delay; "
                       "utente = $t.Triggers[0].UserId; livello = \"$($t.Principal.RunLevel)\" } | ConvertTo-Json")
        d = json.loads(r)
        atteso = f'--headless powershell.exe -NoProfile -ExecutionPolicy Bypass -File "{PS1}" -Fase 2'
        assert d["runonce"] == f"conhost.exe {atteso}" and len(d["runonce"]) <= 260
        assert (d["exe"], d["arg"]) == ("conhost.exe", atteso)
        assert d["trigger"] == "MSFT_TaskLogonTrigger" and d["ritardo"] == "PT2M" and d["livello"] == "Limited"
        assert d["utente"].lower().endswith(os.environ["USERNAME"].lower())
        assert powershell(f". '{PS1}'; NonRiprendere '{VOCE}' '{ATTIVITA}'; "
                          f"[bool](Get-ScheduledTask -TaskName '{ATTIVITA}' -ErrorAction SilentlyContinue); "
                          f"[bool](Get-ItemProperty 'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\RunOnce' -Name {VOCE} "
                          "-ErrorAction SilentlyContinue)").split() == ["False", "False"]
        assert powershell(f". '{PS1}'; NonRiprendere '{VOCE}' '{ATTIVITA}'; 'ok'") == "ok"     # due volte: niente errori
    finally:
        _togli_prove()


def test_a0_l_attivita_di_riserva_lancia_davvero_la_fase_2(tmp_path):
    """Lo stesso comando, avviato dal Pianificatore (nessuna console, come all'accesso): PowerShell parte con -Fase 2."""
    prova = tmp_path / "prova fase 2.ps1"                         # con uno spazio nel percorso, come una cartella vera
    esito = tmp_path / "esito.txt"
    prova.write_text(f"param([int]$Fase)\n$p = Get-CimInstance Win32_Process -Filter \"ProcessId = $PID\"\n"
                     f"$q = Get-CimInstance Win32_Process -Filter \"ProcessId = $($p.ParentProcessId)\"\n"
                     f"\"fase=$Fase padre=$($q.Name)\" | Set-Content '{esito}'\n", encoding="utf-8")
    try:
        powershell(f". '{PS1}'; Riprendi '{VOCE}' '{ATTIVITA}' '{prova}'; Start-ScheduledTask -TaskName '{ATTIVITA}'; 'ok'")
        import time
        fine = time.monotonic() + 30
        while not esito.exists() and time.monotonic() < fine:
            time.sleep(0.5)
        assert esito.read_text(encoding="utf-8-sig").strip() == "fase=2 padre=conhost.exe"
    finally:
        _togli_prove()


def test_a0_una_sola_installazione_alla_volta():
    """RunOnce e l'attività di riserva possono partire tutte e due: la seconda copia esce senza fare nulla."""
    import time
    nome = "Local\\pmn_prova_A0_unico"
    prima = subprocess.Popen(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command",
                              f". '{PS1}'; if (UnaSolaInstallazione '{nome}') {{ 'presa' }}; Start-Sleep 10"],
                             stdout=subprocess.PIPE, text=True)
    try:
        assert prima.stdout.readline().strip() == "presa"
        assert powershell(f". '{PS1}'; UnaSolaInstallazione '{nome}'") == "False"
    finally:
        prima.kill()
        prima.wait()
    time.sleep(1)
    assert powershell(f". '{PS1}'; UnaSolaInstallazione '{nome}'") == "True"           # copia morta: si riprende
    assert TESTO.index("if (-not (UnaSolaInstallazione))") < TESTO.index('Scrivi "=== fase $Fase, cartella $Radice"')


def test_b1_memoria_del_pc_controllata_prima_di_tutto():
    """B1-b (VM 30/10, 8 GB): 44 GB scaricati, poi ROSSO per memoria. Ora si ferma subito, prima di WSL e dell'app."""
    it = powershell(f". '{PS1}'; $Lingua = 'it'; MemoriaInsufficiente 8GB")
    assert it.startswith("Questo PC ha 8 GB di memoria: ProfileMetaNanni ne chiede almeno 16") and "Non ho installato" in it
    en = powershell(f". '{PS1}'; $Lingua = 'en'; MemoriaInsufficiente 12GB")
    assert en.startswith("This PC has 12 GB of memory: ProfileMetaNanni needs at least 16")
    # un PC da 16 GB ne mostra 15,2-15,6 (la scheda video integrata ne tiene una parte): passa
    assert powershell(f". '{PS1}'; (MemoriaInsufficiente 15.6GB) -eq $null; (MemoriaInsufficiente 14.2GB) -eq $null").split() == ["True", "True"]
    i = TESTO.index("$m = MemoriaInsufficiente $ram")
    assert i < TESTO.index("# ===================== fase 1") < TESTO.index("InstallaApp $AppPacchetto")
    assert float(powershell(f". '{PS1}'; MemoriaDelPC")) > 1e9


def test_b1_log_del_motore_con_un_percorso_di_windows(tmp_path):
    """B1-a: il ROSSO diceva di mandare /home/pmn/.pmn/log/..., che da Windows non si apre."""
    linux = "/home/pmn/.pmn/log/installazione_20261030_111200.log"
    assert powershell(f". '{PS1}'; PercorsoWsl '{linux}'") == \
        "\\\\wsl.localhost\\pmn\\home\\pmn\\.pmn\\log\\installazione_20261030_111200.log"
    sorgente = tmp_path / "motore.log"
    sorgente.write_text("riga del motore", encoding="utf-8")
    dest = tmp_path / "installazione_motore.log"
    assert powershell(f". '{PS1}'; CopiaLogMotore '{linux}' '{dest}' '{sorgente}'") == str(dest)
    assert dest.read_text(encoding="utf-8") == "riga del motore"
    e = json.dumps({"messaggio": "ROSSO: la prova finale non ha dato il risultato atteso.",
                    "cosa_fare": f"Manda a noi il file {linux}."})
    t = powershell(f". '{PS1}'; $Lingua = 'it'; $LogMotoreWin = '{tmp_path / 'copia.log'}'; "
                   f"TestoErrore ('{e}' | ConvertFrom-Json) '{linux}'")
    assert linux not in t and "Manda a noi il file " in t
    assert str(tmp_path / "copia.log") in t or "\\\\wsl.localhost\\pmn\\home\\pmn" in t    # copia, o il percorso di rete
    for riga in ("TestoErrore $errore $logStima", "TestoErrore $script:Errore $script:LogMotore"):
        assert riga in FASE2


def test_spazio_di_windows_controllato_ogni_minuto():
    giro = FASE2[FASE2.index("$giro = {"):FASE2.index("$c = Attendi (Avvia \"$motore --si")]
    assert "AddMinutes(1)" in giro and "SpazioBasso" in giro and "LiberiSu $s.Disco" in giro
    assert "AddMinutes(5)" in giro and "Riassunto" in giro
