# installer/windows/aggiorna_pmn.ps1 - aggiornamento di app e motore (R12, D168). Lo lancia l'app (app/aggiorna.py) dalla
# cartella del pacchetto nuovo, dopo il "Si'" della persona; poi l'app si chiude e questo script aspetta (-Attendi <pid>).
# 1. si ferma senza toccare nulla se nel motore gira un'analisi o un'installazione (lucchetti di ~/.pmn/stato);
# 2. motore: copia di riserva nella WSL (profilemetananni.precedente), prepara_pmn.sh del pacchetto nuovo, poi
#    installa_motore.sh: scarica solo cio' che manca (salta quello che c'e' gia' con l'MD5 giusto) e fa la prova finale;
#    se c'e' da scaricare lo dice e chiede prima (No = tutto come prima);
# 3. app: la vecchia diventa app.precedente, la nuova va al suo posto; le icone puntano allo stesso ProfileMetaNanni.exe;
# 4. se qualcosa va storto rimette app e motore di prima e lo dice.
# Non tocca Documenti\ProfileMetaNanni (progetti e risultati), le impostazioni (registro) e ~/.pmn (database, programmi,
# ospiti aggiunti). Si copia in %LOCALAPPDATA%\profilemetananni: da li' l'app lo rilancia con -Ripristina
# ("Torna alla versione precedente"), che rimette app.precedente e la copia del motore.
param([int]$Attendi = 0, [switch]$Ripristina)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Windows.Forms
$Questo = $PSCommandPath                         # questo script (anche quando lo si carica con ". " nelle prove)
$Radice = Split-Path (Split-Path $PSScriptRoot)   # il pacchetto nuovo: contiene installer\ e app_windows\
$Cartella = Join-Path $env:LOCALAPPDATA 'profilemetananni'
$App = Join-Path $Cartella 'app'
$Precedente = Join-Path $Cartella 'app.precedente'
$Log = Join-Path $Cartella 'aggiornamento.log'
$MotoreWsl = '/home/pmn/profilemetananni'
$MotoreRiserva = '/home/pmn/profilemetananni.precedente'
$Stato = '/home/pmn/.pmn/stato'
$env:WSL_UTF8 = '1'

function LinguaApp($chiave = 'HKCU:\Software\ProfileMetaNanni\app') {   # quella scelta nell'app; altrimenti quella di Windows
    $l = (Get-ItemProperty $chiave -Name lingua -ErrorAction SilentlyContinue).lingua
    if (-not $l) { $l = (Get-UICulture).Name }
    if ("$l" -like 'it*') { 'it' } else { 'en' }
}
$Lingua = LinguaApp
$TESTI = [ordered]@{
    dettagli = @("{0}`n`nDettagli tecnici nel file:`n{1}", "{0}`n`nTechnical details in the file:`n{1}")
    app_aperta = @("ProfileMetaNanni è ancora aperto: chiudilo e riprova l'aggiornamento.",
                   "ProfileMetaNanni is still open: close it and try the update again.")
    analisi = @("Un'analisi o un'installazione del motore è in corso: non aggiorno nulla adesso.`nAspetta che finisca, poi riprova.",
                "An analysis or an installation of the engine is running: I do not update anything now.`nWait until it finishes, then try again.")
    barra_motore = @("Aggiorno il motore di profilemetananni...", "Updating the profilemetananni engine...")
    barra_stima = @("Controllo che cosa manca al motore nuovo...", "Checking what the new engine is missing...")
    domanda_scarico = @("La versione nuova del motore deve scaricare circa {0} GB (spazio libero sul disco {1}: {2} GB).`nI database che hai già non si riscaricano.`n`nProcedo con l'aggiornamento?",
                        "The new version of the engine needs to download about {0} GB (free space on disk {1}: {2} GB).`nThe databases you already have are not downloaded again.`n`nShall I go ahead with the update?")
    spazio = @("Lo spazio sul disco {0} non basta per l'aggiornamento: servono circa {1} GB, ce ne sono {2}.`nHo rimesso tutto come prima. Libera spazio e riprova.",
               "There is not enough space on disk {0} for the update: about {1} GB are needed, there are {2}.`nI put everything back as before. Free some space and try again.")
    niente = @("Va bene: non ho cambiato nulla.", "All right: I have not changed anything.")
    barra_app = @("Installo la versione nuova del programma...", "Installing the new version of the program...")
    fatto = @("Aggiornamento finito: ora c'è la versione {0}.`nI tuoi progetti e le impostazioni sono rimasti come prima.`n`nSe qualcosa non va, nella pagina I miei progetti trovi Torna alla versione precedente.",
              "Update finished: now you have version {0}.`nYour projects and settings are as before.`n`nIf something is wrong, on the My projects page you find Go back to the previous version.")
    fatto_senza_motore = @("Il programma è aggiornato alla versione {0}. Il motore non è ancora installato: lo installi dalla pagina Motore.",
                           "The program is updated to version {0}. The engine is not installed yet: you can install it from the Engine page.")
    fallito = @("L'aggiornamento non è riuscito: {0}`nHo rimesso la versione di prima, che funziona come prima.",
                "The update did not succeed: {0}`nI put back the previous version, which works as before.")
    fallito_ripristino = @("L'aggiornamento non è riuscito e non sono riuscito a rimettere tutto come prima: {0}`nRiscarica l'ultima versione dalla pagina della Release e installala con il doppio clic: i tuoi progetti restano dove sono.",
                           "The update did not succeed and I could not put everything back as before: {0}`nDownload the latest version again from the Release page and install it with a double click: your projects stay where they are.")
    errore_app = @("non riesco a copiare il programma nuovo.", "I cannot copy the new program.")
    errore_motore = @("il motore nuovo non si è installato (codice {0}).", "the new engine was not installed (code {0}).")
    nessun_precedente = @("Non c'è una versione precedente da rimettere.", "There is no previous version to put back.")
    tornato = @("Sono tornato alla versione precedente. I tuoi progetti e le impostazioni sono rimasti come prima.",
                "I went back to the previous version. Your projects and settings are as before.")
    ritorno_fallito = @("Non sono riuscito a tornare alla versione precedente: {0}`nRiscarica la versione che vuoi dalla pagina delle Release e installala con il doppio clic.",
                        "I could not go back to the previous version: {0}`nDownload the version you want from the Releases page and install it with a double click.")
}
function T($chiave) { $TESTI[$chiave][[int]($Lingua -ne 'it')] }

function Scrivi($t) { "$(Get-Date -Format s)  $t" | Out-File -Append -Encoding utf8 $Log }
function Finestra($t, $pulsanti = 'OK') {   # sempre in primo piano: questo processo non ha una finestra sua
    $o = New-Object Windows.Forms.Form -Property @{ TopMost = $true }
    $r = [Windows.Forms.MessageBox]::Show($o, $t, 'profilemetananni', $pulsanti); $o.Dispose(); $r
}
function Avviso($t) { [void](Finestra $t) }
function Domanda($t) { (Finestra $t 'YesNo') -eq 'Yes' }
function MostraBarra($testo, $pct) {   # finestra di avanzamento senza pulsante di chiusura; $pct vuoto = barra animata
    if (-not $script:Barra) {
        $fo = New-Object Windows.Forms.Form -Property @{ Text = 'profilemetananni'; Width = 580; Height = 170; ControlBox = $false; FormBorderStyle = 'FixedDialog'; StartPosition = 'CenterScreen'; TopMost = $true }
        $l = New-Object Windows.Forms.Label -Property @{ Left = 20; Top = 20; Width = 530; Height = 50 }
        $b = New-Object Windows.Forms.ProgressBar -Property @{ Left = 20; Top = 80; Width = 530; Height = 25 }
        $fo.Controls.AddRange(@($l, $b)); $fo.Show()
        $script:Barra = @{ f = $fo; l = $l; b = $b }
    }
    $script:Barra.l.Text = $testo
    if ($null -eq $pct) { $script:Barra.b.Style = 'Marquee' }
    else { $script:Barra.b.Style = 'Continuous'; $script:Barra.b.Value = [Math]::Max(0, [Math]::Min(100, [int]$pct)) }
    [Windows.Forms.Application]::DoEvents()
}
function ChiudiBarra { if ($script:Barra) { $script:Barra.f.Close(); $script:Barra = $null } }
function Fine($codice, $testo) { ChiudiBarra; Scrivi "FINE $codice $testo"; if ($testo) { Avviso $testo }; exit $codice }
function Evento($r) { if ($r -like '{*') { try { $r | ConvertFrom-Json } catch { $null } } }   # docs/contratto_motore.md

function Wsl([string]$argomenti, [scriptblock]$ogniRiga = {}) {   # wsl.exe senza finestra; righe in $script:Uscita; torna il codice
    $si = New-Object Diagnostics.ProcessStartInfo 'wsl.exe', $argomenti
    $si.UseShellExecute = $false; $si.CreateNoWindow = $true
    $si.RedirectStandardOutput = $true; $si.RedirectStandardError = $true
    $si.StandardOutputEncoding = [Text.Encoding]::UTF8; $si.StandardErrorEncoding = [Text.Encoding]::UTF8
    Scrivi "wsl.exe $argomenti"
    $p = [Diagnostics.Process]::Start($si)
    $script:Uscita = New-Object Collections.Generic.List[string]
    $err = $p.StandardError.ReadToEndAsync()
    while ($true) {   # riga per riga senza bloccare la barra
        $t = $p.StandardOutput.ReadLineAsync()
        while (-not $t.IsCompleted) { [Windows.Forms.Application]::DoEvents(); Start-Sleep -Milliseconds 100 }
        if ($null -eq $t.Result) { break }
        Scrivi "  $($t.Result)"; $script:Uscita.Add($t.Result); & $ogniRiga $t.Result | Out-Null
    }
    $p.WaitForExit()
    if ($err.Result) { Scrivi "  (errori) $($err.Result)" }
    Scrivi "  codice $($p.ExitCode)"
    $p.ExitCode
}
function MotorePresente {   # la WSL "pmn" esiste e contiene il motore
    [void](Wsl '-l -q')
    (($script:Uscita | ForEach-Object { $_.Trim() }) -contains 'pmn') -and ((Wsl "-d pmn -u pmn -e test -d $MotoreWsl") -eq 0)
}
function AnalisiAttiva {   # come pmn_motore.py: un lucchetto conta solo se il suo processo e' ancora vivo
    foreach ($nome in 'esegui.lock', 'installa.lock') {
        if ((Wsl "-d pmn -u pmn -e cat $Stato/$nome") -ne 0) { continue }
        $pid_ = (Evento (($script:Uscita) -join '')).pid
        if ("$pid_" -match '^\d+$' -and (Wsl "-d pmn -u pmn -e test -d /proc/$pid_") -eq 0) { return $true }
    }
    $false
}
function SpazioWindows {   # byte liberi e disco di Windows che contiene la WSL "pmn" (dentro la WSL si vede solo il disco virtuale)
    $d = Get-ChildItem 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Lxss' -ErrorAction SilentlyContinue | Get-ItemProperty |
        Where-Object DistributionName -eq 'pmn' | Select-Object -First 1
    if (-not $d) { return $null }
    $lettera = ($d.BasePath -replace '^\\\\\?\\', '')[0]
    [pscustomobject]@{ Disco = "$($lettera):"; Liberi = [double](Get-Volume -DriveLetter $lettera).SizeRemaining }
}
function RiservaMotore {   # copia di riserva del motore installato (pochi MB: codice e tabelle, non i database)
    if ((Wsl "-d pmn -u root -e rm -rf $MotoreRiserva") -ne 0) { return $false }
    (Wsl "-d pmn -u root -e cp -a $MotoreWsl $MotoreRiserva") -eq 0
}
function RimettiMotore {   # la copia di riserva torna al suo posto (anche per "Torna alla versione precedente")
    if ((Wsl "-d pmn -u root -e test -d $MotoreRiserva") -ne 0) { return $false }
    if ((Wsl "-d pmn -u root -e rm -rf $MotoreWsl") -ne 0) { return $false }
    (Wsl "-d pmn -u root -e mv $MotoreRiserva $MotoreWsl") -eq 0
}
function ComandoMotore {
    $c = "-d pmn -u pmn -- bash $MotoreWsl/installer/installa_motore.sh --json --catalogo $MotoreWsl/installer/catalogo.tsv"
    if ($Lingua -ne 'it') { $c += " --lingua $Lingua" }
    $c
}
$script:AppSpostata = $false   # true solo dopo che QUESTO aggiornamento ha spostato l'app in app.precedente
function SostituisciApp($nuova) {   # app -> app.precedente, nuova -> app (se non riesce, Torna rimette la vecchia)
    if (Test-Path $Precedente) { Remove-Item -Recurse -Force $Precedente }   # la precedente di un aggiornamento passato
    if (Test-Path $App) { Move-Item $App $Precedente; $script:AppSpostata = $true }   # rinomina: con l'app aperta si ferma qui
    Copy-Item -Recurse $nuova $App
    Get-ChildItem -Recurse -File $App | Unblock-File
    $v = Join-Path $Radice 'VERSIONE.txt'
    if (Test-Path $v) { Copy-Item $v $App }
}
function RimettiApp {   # app.precedente torna app, solo se l'ha spostata questo aggiornamento
    if (-not $script:AppSpostata) { return }
    if (Test-Path $App) { Remove-Item -Recurse -Force $App }
    Move-Item $Precedente $App
    $script:AppSpostata = $false
}
function VersioneNuova {   # prima riga di VERSIONE.txt: "profilemetananni 1.1.0"
    $v = Join-Path $Radice 'VERSIONE.txt'
    if ((Test-Path $v) -and ((Get-Content $v -TotalCount 1) -match '(\d+\.\d+\.\d+)')) { $Matches[1] } else { '?' }
}
function AvviaApp { $exe = Join-Path $App 'ProfileMetaNanni.exe'; if (Test-Path $exe) { Start-Process $exe } }
function AspettaApp {   # l'app si chiude da sola dopo aver lanciato questo script
    if ($Attendi -gt 0) {
        Wait-Process -Id $Attendi -Timeout 60 -ErrorAction SilentlyContinue
        if (Get-Process -Id $Attendi -ErrorAction SilentlyContinue) { Fine 1 (T 'app_aperta') }
    }
}
function Torna($motore, $perche) {   # qualcosa e' andato storto: rimette app e motore e lo dice
    Scrivi "torno indietro: $perche"
    $ok = $true
    try { RimettiApp } catch { Scrivi "$_"; $ok = $false }
    if ($motore -and -not (RimettiMotore)) { $ok = $false }
    $t = if ($ok) { (T 'fallito') -f $perche } else { (T 'fallito_ripristino') -f $perche }
    Fine 2 ((T 'dettagli') -f $t, $Log)
}

function Aggiorna {
    AspettaApp
    $motore = MotorePresente
    if ($motore -and (AnalisiAttiva)) { Fine 1 (T 'analisi') }
    $versione = VersioneNuova
    if ($motore) {
        MostraBarra (T 'barra_motore') $null
        if (-not (RiservaMotore)) { Fine 2 ((T 'dettagli') -f ((T 'fallito') -f ((T 'errore_motore') -f 'riserva')), $Log) }
        $c = Wsl "-d pmn -u root --cd `"$(Split-Path $Questo)`" -- bash prepara_pmn.sh"
        if ($c -ne 0) { Torna $true ((T 'errore_motore') -f $c) }
        MostraBarra (T 'barra_stima') $null
        $script:Eventi = @()
        $c = Wsl "$(ComandoMotore) --stima" { param($r) $e = Evento $r; if ($e) { $script:Eventi += $e } }
        if ($c -ne 0) { Torna $true ((T 'errore_motore') -f $c) }
        $gb = [double](($script:Eventi | Where-Object tipo -eq 'fine' | Select-Object -Last 1).risultato.da_scaricare_gb)
        if ($gb -gt 0.05) {
            $s = SpazioWindows
            $serve = 2 * $gb * 1e9 + 2e9   # archivio + estratto, piu' margine: prudente, come il controllo dell'installazione
            if ($s -and $s.Liberi -lt $serve) {
                [void](RimettiMotore)
                Fine 1 ((T 'spazio') -f $s.Disco, [Math]::Ceiling($serve / 1GB), [Math]::Floor($s.Liberi / 1GB))
            }
            ChiudiBarra
            $disco = if ($s) { $s.Disco } else { '?' }; $liberi = if ($s) { [Math]::Floor($s.Liberi / 1GB) } else { '?' }
            if (-not (Domanda ((T 'domanda_scarico') -f [Math]::Ceiling($gb), $disco, $liberi))) {
                [void](RimettiMotore); Fine 0 (T 'niente')
            }
        }
    }
    MostraBarra (T 'barra_app') $null
    try { SostituisciApp (Join-Path $Radice 'app_windows\ProfileMetaNanni') }
    catch { Scrivi "$_"; Torna $motore (T 'errore_app') }
    Copy-Item $Questo (Join-Path $Cartella 'aggiorna_pmn.ps1') -Force   # per "Torna alla versione precedente"
    if ($motore) {
        MostraBarra (T 'barra_motore') 0
        $script:Errore = $null
        $c = Wsl "$(ComandoMotore) --si" { param($r) $e = Evento $r
            if ($e) { if ($e.tipo -eq 'errore') { $script:Errore = $e }; if ($e.passo -ne 'controllo') { MostraBarra $e.messaggio $e.percentuale } } }
        if ($c -ne 0) { Torna $true $(if ($script:Errore) { "$($script:Errore.messaggio) $($script:Errore.cosa_fare)" } else { (T 'errore_motore') -f $c }) }
    }
    ChiudiBarra
    Scrivi "aggiornato alla versione $versione"
    AvviaApp
    Fine 0 $(if ($motore) { (T 'fatto') -f $versione } else { (T 'fatto_senza_motore') -f $versione })
}

function TornaIndietro {
    AspettaApp
    if (-not (Test-Path (Join-Path $Precedente 'ProfileMetaNanni.exe'))) { Fine 1 (T 'nessun_precedente') }
    $motore = MotorePresente
    if ($motore -and (AnalisiAttiva)) { Fine 1 (T 'analisi') }
    $scartata = Join-Path $Cartella 'app.scartata'
    try {
        if (Test-Path $scartata) { Remove-Item -Recurse -Force $scartata }
        if (Test-Path $App) { Move-Item $App $scartata }
        Move-Item $Precedente $App
        if (Test-Path $scartata) { Remove-Item -Recurse -Force $scartata }
    } catch { Scrivi "$_"; Fine 2 ((T 'dettagli') -f ((T 'ritorno_fallito') -f (T 'errore_app')), $Log) }
    if ($motore -and ((Wsl "-d pmn -u root -e test -d $MotoreRiserva") -eq 0) -and -not (RimettiMotore)) {
        Fine 2 ((T 'dettagli') -f ((T 'ritorno_fallito') -f ((T 'errore_motore') -f 'mv')), $Log)
    }
    Scrivi 'tornato alla versione precedente'
    AvviaApp
    Fine 0 (T 'tornato')
}
if ($MyInvocation.InvocationName -eq '.') { return }   # caricato con ". aggiorna_pmn.ps1" (prove): solo le funzioni

New-Item -ItemType Directory -Force $Cartella | Out-Null
[Windows.Forms.Application]::EnableVisualStyles()
Scrivi "=== $(if ($Ripristina) { 'ripristino' } else { "aggiornamento da $Radice" })"
if ($Ripristina) { TornaIndietro } else { Aggiorna }
