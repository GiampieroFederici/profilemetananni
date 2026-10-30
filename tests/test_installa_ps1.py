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
    r = powershell(f". '{PS1}'; Riassunto ('{json.dumps(e)}' | ConvertFrom-Json)")
    assert r == "RIASSUNTO: 12 di 133 GB, 8.4 MB/s, mancano 4 h 10 min (kraken 1/85 GB 1.4 MB/s)"
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


def test_spazio_di_windows_controllato_ogni_minuto():
    giro = FASE2[FASE2.index("$giro = {"):FASE2.index("$c = Attendi (Avvia \"$motore --si")]
    assert "AddMinutes(1)" in giro and "SpazioBasso" in giro and "LiberiSu $s.Disco" in giro
    assert "AddMinutes(5)" in giro and "Riassunto" in giro
