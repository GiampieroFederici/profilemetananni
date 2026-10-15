# installer/windows/installa_pmn.ps1 - PROTOTIPO della parte Windows dell'installatore (D027, D039).
# Da provare in S3-W su una macchina virtuale Hyper-V con Windows pulito: NON ancora provato.
# Fa solo: attiva WSL (finestra Si/No di Windows) -> riavvio -> riprende da solo -> crea la WSL "pmn" -> scrive OK.
# Il motore (installer/installa_motore.sh) si aggancera' dopo la fase 2, quando questa parte sara' provata.
param([int]$Fase = 1)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName PresentationFramework
$Cartella = Join-Path $env:LOCALAPPDATA 'profilemetananni'
$Log = Join-Path $Cartella 'installazione_windows.log'
New-Item -ItemType Directory -Force $Cartella | Out-Null
function Scrivi($t) { "$(Get-Date -Format s)  $t" | Out-File -Append -Encoding utf8 $Log }
function Avviso($t, $titolo = 'profilemetananni') { [System.Windows.MessageBox]::Show($t, $titolo) | Out-Null }
function WslPronta { & wsl.exe --status *> $null; return ($LASTEXITCODE -eq 0) }

Scrivi "fase $Fase"
if ($Fase -eq 1) {
    if (-not (WslPronta)) {
        Avviso "Per funzionare, profilemetananni ha bisogno di un componente di Windows (WSL).`n`nTra poco Windows ti chiedera' il permesso: rispondi Si."
        # finestra Si/No di Windows (controllo dell'account utente): serve l'amministratore
        $p = Start-Process wsl.exe -ArgumentList '--install', '--no-distribution' -Verb RunAs -Wait -PassThru
        Scrivi "wsl --install --no-distribution: codice $($p.ExitCode)"
        if ($p.ExitCode -ne 0) { Avviso "Non e' stato possibile attivare WSL (codice $($p.ExitCode)). Riprova; se si ripete, mandaci il file $Log"; exit 2 }
        # al prossimo accesso di questo utente, riparte da solo dalla fase 2
        $cmd = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`" -Fase 2"
        New-ItemProperty -Path 'HKCU:\Software\Microsoft\Windows\CurrentVersion\RunOnce' -Name 'profilemetananni' -Value $cmd -PropertyType String -Force | Out-Null
        $r = [System.Windows.MessageBox]::Show("Serve un riavvio del computer. Dopo il riavvio l'installazione riprende da sola.`n`nRiavvio adesso?", 'profilemetananni', 'YesNo')
        if ($r -eq 'Yes') { Restart-Computer -Force } else { Avviso "Va bene. Quando riavvii il computer, l'installazione riprende da sola." }
        exit 0
    }
    $Fase = 2   # WSL c'era gia': nessun riavvio
}
if ($Fase -eq 2) {
    if (-not (WslPronta)) { Avviso "WSL non risulta ancora attivo. Riavvia il computer: l'installazione riprende da sola."; exit 2 }
    $nomi = (& wsl.exe -l -q) -replace "`0", ''
    if ($nomi -notcontains 'pmn') {
        & wsl.exe --install Ubuntu-24.04 --name pmn --no-launch
        Scrivi "wsl --install Ubuntu-24.04 --name pmn: codice $LASTEXITCODE"
        if ($LASTEXITCODE -ne 0) { Avviso "Non riesco a preparare l'ambiente Linux (codice $LASTEXITCODE). Controlla la connessione e riprova."; exit 2 }
    }
    # utente Linux senza password, creato da root (nessuna domanda all'utente)
    & wsl.exe -d pmn -u root -- useradd -m -s /bin/bash pmn 2>$null
    & wsl.exe -d pmn -u root -- sh -c "grep -q '^default=pmn' /etc/wsl.conf || printf '[user]\ndefault=pmn\n' >> /etc/wsl.conf"
    $ok = (& wsl.exe -d pmn -u pmn -- echo OK) -replace "`0", ''
    Scrivi "prova finale: $ok"
    if ($ok -eq 'OK') { Avviso 'Tutto pronto: la parte Windows e'' installata.' } else { Avviso "Qualcosa non ha funzionato. Mandaci il file $Log"; exit 2 }
}
