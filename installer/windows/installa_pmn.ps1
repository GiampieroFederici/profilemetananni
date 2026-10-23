# installer/windows/installa_pmn.ps1 - parte Windows dell'installatore (D027, D039, D043-D045). Si avvia con un doppio clic su installa_pmn.cmd.
# Fase 1: attiva WSL (finestra Si/No di Windows) e, se serve, chiede il riavvio; al prossimo accesso riparte da solo dalla fase 2.
# Fase 2: controlla lo spazio vero sul disco di Windows e sceglie il disco interno con piu' spazio (D045), crea la WSL "pmn",
#         chiede conferma con peso, spazio e tempo (D034), installa il motore con la barra di avanzamento.
# Se si interrompe (PC spento durante i download) riparte da solo al prossimo accesso. L'uscita di wsl.exe (in inglese) va solo nel log.
# Prova con lo specchio locale (D038, D044): file prova.conf accanto a questo script, righe "specchio=URL" e "catalogo=installer/<file>.tsv".
param([int]$Fase = 1)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Windows.Forms
$Radice = Split-Path (Split-Path $PSScriptRoot)   # la cartella che contiene installer\ e motore\
$Cartella = Join-Path $env:LOCALAPPDATA 'profilemetananni'
$Log = Join-Path $Cartella 'installazione_windows.log'
$RunOnce = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\RunOnce'
$GB_PROGRAMMI = 16   # come installer/installa_motore.sh
$env:WSL_UTF8 = '1'  # wsl.exe scrive in UTF-8 invece che in UTF-16
$Conf = @{}
$f = Join-Path $PSScriptRoot 'prova.conf'
if (Test-Path $f) { Get-Content $f | ForEach-Object { if ($_ -match '^\s*(\w+)\s*=\s*(\S+)\s*$') { $Conf[$Matches[1]] = $Matches[2] } } }
$CatalogoRel = if ($Conf.catalogo) { $Conf.catalogo } else { 'installer/catalogo.tsv' }
$AppPacchetto = Join-Path $Radice 'app_windows\ProfileMetaNanni'   # c'e' solo nel pacchetto (costruisci_pacchetto.py), non nel repository
$AppExe = Join-Path $Cartella 'app\ProfileMetaNanni.exe'

# B2 (P12): i testi per la persona, in italiano e in inglese, tutti qui. Lingua = quella di Windows (it: italiano, altro: inglese).
function SceltaLingua($cultura) { if ("$cultura" -like 'it*') { 'it' } else { 'en' } }
$Lingua = SceltaLingua (Get-UICulture).Name
$TESTI = [ordered]@{
    dettagli = @("{0}`n`nDettagli tecnici nel file:`n{1}", "{0}`n`nTechnical details in the file:`n{1}")
    riavvio_domanda = @("Serve un riavvio del computer. Dopo il riavvio l'installazione riprende da sola.`n`nRiavvio adesso?",
                        "The computer needs a restart. After the restart the installation resumes by itself.`n`nRestart now?")
    riavvio_dopo = @("Va bene. Quando riavvii il computer, l'installazione riprende da sola.",
                     "All right. When you restart the computer, the installation resumes by itself.")
    spazio = @("Lo spazio sul disco non basta: servono circa {0} GB sul disco {1}, ce ne sono {2}.`n`nLibera almeno {3} GB e riapri l'installazione.",
               "There is not enough space on the disk: about {0} GB are needed on disk {1}, there are {2}.`n`nFree at least {3} GB and open the installation again.")
    app_copia = @("Non riesco a copiare il programma ProfileMetaNanni.`nSe è aperto, chiudilo e riapri l'installazione.",
                  "I cannot copy the ProfileMetaNanni program.`nIf it is open, close it and open the installation again.")
    wsl_serve = @("Per funzionare, profilemetananni ha bisogno di un componente di Windows (WSL).`n`nTra poco Windows ti chiederà il permesso: rispondi Sì.",
                  "To work, profilemetananni needs a component of Windows (WSL).`n`nIn a moment Windows will ask for your permission: answer Yes.")
    wsl_permesso = @("Senza il permesso di Windows non posso attivare WSL.`nRiapri l'installazione quando vuoi e rispondi Sì.",
                     "Without the permission of Windows I cannot turn on WSL.`nOpen the installation again when you like and answer Yes.")
    wsl_barra = @("Attivo il componente WSL di Windows (qualche minuto)...", "Turning on the WSL component of Windows (a few minutes)...")
    wsl_codice = @("Non è stato possibile attivare WSL (codice {0}). Riprova; se si ripete, mandaci il file indicato qui sotto.",
                   "WSL could not be turned on (code {0}). Try again; if it happens again, send us the file shown below.")
    disco = @("Non trovo un disco interno adatto (NTFS) per installare profilemetananni.",
              "I cannot find a suitable internal disk (NTFS) to install profilemetananni.")
    linux_barra = @("Preparo l'ambiente Linux di profilemetananni (qualche minuto)...",
                    "Preparing the Linux environment of profilemetananni (a few minutes)...")
    linux_codice = @("Non riesco a preparare l'ambiente Linux (codice {0}).`nControlla la connessione a internet e riapri l'installazione.",
                     "I cannot prepare the Linux environment (code {0}).`nCheck the internet connection and open the installation again.")
    utente_barra = @("Preparo l'utente e i file di profilemetananni...", "Preparing the user and the files of profilemetananni...")
    utente_errore = @("Non riesco a preparare i file di profilemetananni nell'ambiente Linux.",
                      "I cannot prepare the files of profilemetananni in the Linux environment.")
    rete_barra = @("Misuro la velocità della rete...", "Measuring the speed of the network...")
    cosa_fare = @("{0}`n`nCosa fare: {1}", "{0}`n`nWhat to do: {1}")
    preparazione_ferma = @("La preparazione si è fermata (codice {0}).", "The preparation stopped (code {0}).")
    domanda_scarico = @("profilemetananni scaricherà circa {0} GB di database, più i programmi (circa 11 GB, se non ci sono già).`nSpazio necessario sul disco {1} circa {2} GB (liberi: {3} GB).`n{4}`n`nProcedo con l'installazione?",
                        "profilemetananni will download about {0} GB of databases, plus the programs (about 11 GB, if they are not there yet).`nSpace needed on disk {1} about {2} GB (free: {3} GB).`n{4}`n`nShall I go ahead with the installation?")
    niente_scaricato = @("Va bene: non ho scaricato nulla. Riapri l'installazione quando vuoi.",
                         "All right: I have not downloaded anything. Open the installation again when you like.")
    inizio_barra = @("Inizio l'installazione...", "Starting the installation...")
    installazione_ferma = @("L'installazione si è fermata (codice {0}). Riapri l'installazione: riprende da dove era rimasta.",
                            "The installation stopped (code {0}). Open the installation again: it resumes from where it stopped.")
    pronto_app = @("Tutto pronto: profilemetananni è installato e funziona.`n`nOra apro il programma. Le prossime volte lo trovi sul desktop e nel menu Start: ProfileMetaNanni.",
                   "All ready: profilemetananni is installed and works.`n`nNow I open the program. Next time you will find it on the desktop and in the Start menu: ProfileMetaNanni.")
    pronto = @("Tutto pronto: profilemetananni è installato e funziona.", "All ready: profilemetananni is installed and works.")
}
function T($chiave) { $TESTI[$chiave][[int]($Lingua -ne 'it')] }
function ImpostaLinguaApp($codice, $chiave = 'HKCU:\Software\ProfileMetaNanni\app') {   # come QSettings("ProfileMetaNanni", "app") dell'app
    if (-not (Test-Path $chiave)) { New-Item -Path $chiave -Force | Out-Null }
    if ($null -eq (Get-ItemProperty $chiave -Name lingua -ErrorAction SilentlyContinue)) {   # una scelta della persona non si tocca
        New-ItemProperty -Path $chiave -Name lingua -Value $codice -PropertyType String | Out-Null
    }
}

function Scrivi($t) { "$(Get-Date -Format s)  $t" | Out-File -Append -Encoding utf8 $Log }
function Finestra($t, $pulsanti = 'OK') {   # messaggio sempre in primo piano (il processo non ha una finestra sua)
    $o = New-Object Windows.Forms.Form -Property @{ TopMost = $true }
    $r = [Windows.Forms.MessageBox]::Show($o, $t, 'profilemetananni', $pulsanti); $o.Dispose(); $r
}
function Avviso($t) { [void](Finestra $t) }
function Domanda($t) { (Finestra $t 'YesNo') -eq 'Yes' }
function Riprendi {   # al prossimo accesso di questo utente riparte da solo dalla fase 2
    # conhost --headless: nessuna finestra (Windows Terminal ignora -WindowStyle Hidden e lascia una finestra vuota, S3-W)
    $cmd = "conhost.exe --headless powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`" -Fase 2"
    New-ItemProperty -Path $RunOnce -Name 'profilemetananni' -Value $cmd -PropertyType String -Force | Out-Null
}
function NonRiprendere { Remove-ItemProperty -Path $RunOnce -Name 'profilemetananni' -ErrorAction SilentlyContinue }
function NienteSospensione {   # B2: i download durano piu' del tempo dopo cui Windows sospende il PC; vale finche' questo processo e' vivo
    Add-Type -Namespace Pmn -Name Energia -MemberDefinition '[DllImport("kernel32.dll")] public static extern uint SetThreadExecutionState(uint f);'
    [void][Pmn.Energia]::SetThreadExecutionState(2147483649)   # 0x80000001 = ES_CONTINUOUS + ES_SYSTEM_REQUIRED (lo schermo si puo' spegnere)
}
function ChiudiBarra { if ($script:Barra) { $script:Barra.f.Close(); $script:Barra = $null } }
function Ferma($t) {   # errore: lo dice in italiano e si ferma; l'utente riapre l'installazione quando ha risolto
    Scrivi "STOP: $t"; ChiudiBarra; NonRiprendere
    Avviso ((T 'dettagli') -f $t, $Log); exit 2
}
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
function Avvia([string]$argomenti) {   # wsl.exe senza finestra, con l'uscita da leggere
    $si = New-Object Diagnostics.ProcessStartInfo 'wsl.exe', $argomenti
    $si.UseShellExecute = $false; $si.CreateNoWindow = $true
    $si.RedirectStandardOutput = $true; $si.RedirectStandardError = $true
    $si.StandardOutputEncoding = [Text.Encoding]::UTF8; $si.StandardErrorEncoding = [Text.Encoding]::UTF8
    Scrivi "wsl.exe $argomenti"
    [Diagnostics.Process]::Start($si)
}
function Attendi($p, [scriptblock]$ogniRiga = {}) {   # legge l'uscita riga per riga senza bloccare la finestra; torna il codice
    $script:Uscita = New-Object Collections.Generic.List[string]
    $err = $p.StandardError.ReadToEndAsync()
    while ($true) {
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
function AttendiProcesso($p) {   # B2 (P3): aspetta senza bloccare la finestra (con -Wait la barra si ferma e Windows la da' per bloccata)
    while (-not $p.WaitForExit(100)) { [Windows.Forms.Application]::DoEvents() }
    $p.ExitCode
}
function ChiudiBenvenuto($dopo, $nome = 'wslsettings', $secondi = 15) {   # B2 (P4): "Benvenuto in WSL" lo apre Windows dopo la registrazione della prima distribuzione
    # (wslsettings.exe, LxssUserSession.cpp _LaunchOOBEIfNeeded); si chiude come con la X, solo se e' nato durante l'installazione
    $fine = (Get-Date).AddSeconds($secondi)
    while ((Get-Date) -lt $fine) {
        $p = Get-Process $nome -ErrorAction SilentlyContinue | Where-Object { $_.StartTime -gt $dopo -and $_.MainWindowHandle -ne 0 }
        if ($p) { $p | ForEach-Object { [void]$_.CloseMainWindow() }; Scrivi "chiusa la finestra di $nome"; return }
        [Windows.Forms.Application]::DoEvents(); Start-Sleep -Milliseconds 300
    }
}
function SaltaBenvenuto($chiave = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Lxss') {   # B2 (P4)
    # Il servizio WSL apre "Benvenuto in WSL" dopo la registrazione della prima distribuzione se manca OOBEComplete
    # (microsoft/WSL, src/windows/service/exe/LxssUserSession.cpp, _LaunchOOBEIfNeeded; lo scrive poi WSL stesso).
    # Solo per questo utente; se Microsoft cambia, la finestra ricompare e la chiude ChiudiBenvenuto.
    if (-not (Test-Path $chiave)) { New-Item -Path $chiave -Force | Out-Null }
    New-ItemProperty -Path $chiave -Name OOBEComplete -Value 1 -PropertyType DWord -Force | Out-Null
}
function RiavvioInSospeso($segno = (Join-Path $Cartella 'wsl_installata.txt'), $chiave = 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending') {
    (Test-Path $segno) -and (Test-Path $chiave)   # conta solo dopo il NOSTRO wsl --install (S3-W); un aggiornamento di Windows estraneo non basta (P16)
}
function WslPronta {   # wsl --status da' 0 anche quando WSL2 parte solo dopo il riavvio (S3-W, VM): conta anche il riavvio in sospeso
    $c = Attendi (Avvia '--status'); $r = RiavvioInSospeso; Scrivi "  riavvio in sospeso: $r"
    ($c -eq 0) -and -not $r
}
function ChiediRiavvio {   # chiede il riavvio; al prossimo accesso riparte da solo dalla fase 2
    Riprendi; ChiudiBarra
    if (Domanda (T 'riavvio_domanda')) { Restart-Computer -Force }
    else { Avviso (T 'riavvio_dopo') }
    exit 0
}
function Evento($r) { if ($r -like '{*') { try { $r | ConvertFrom-Json } catch { $null } } }   # evento JSON del motore (docs/contratto_motore.md)

function SpazioNecessario($catalogo) {   # stessa regola di installa_motore.sh: byte finali + archivio piu' grande + programmi
    $righe = Import-Csv $catalogo -Delimiter "`t"
    $fin = ($righe | ForEach-Object { [double]$_.byte_finale } | Measure-Object -Sum).Sum
    $tar = ($righe | Where-Object tipo -eq 'tar' | ForEach-Object { [double]$_.byte } | Measure-Object -Maximum).Maximum
    $fin + [double]$tar + $GB_PROGRAMMI * 1e9
}
function DiscoMigliore {   # dischi interni (non USB, SD, rete), NTFS: quello con piu' spazio libero (D045)
    Get-Disk | Where-Object { $_.BusType -notin 'USB', 'SD', 'MMC', 'iSCSI', 'File Backed Virtual' } | Get-Partition |
        Where-Object DriveLetter | Get-Volume | Where-Object FileSystem -eq 'NTFS' | Sort-Object SizeRemaining -Descending | Select-Object -First 1
}
function CartellaPmn {   # dove Windows tiene il disco virtuale della WSL "pmn", se c'e' gia'
    $d = Get-ChildItem 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Lxss' -ErrorAction SilentlyContinue | Get-ItemProperty |
        Where-Object DistributionName -eq 'pmn' | Select-Object -First 1
    if ($d) { $d.BasePath -replace '^\\\\\?\\', '' }
}
function ControllaSpazio($catalogo) {   # spazio vero sul disco di Windows: dentro WSL si vede solo il disco virtuale (S3)
    $serve = SpazioNecessario $catalogo
    $dove = CartellaPmn
    if ($dove) {
        $v = Join-Path $dove 'ext4.vhdx'
        if (Test-Path $v) { $serve -= (Get-Item $v).Length }   # ripresa: cio' che e' gia' installato sta nel disco virtuale
        $vol = Get-Volume -DriveLetter $dove[0]
    } else {
        $vol = DiscoMigliore
        if (-not $vol) { return $null }
        $dove = if ("$($vol.DriveLetter):" -eq $env:SystemDrive) { Join-Path $Cartella 'wsl' } else { "$($vol.DriveLetter):\profilemetananni\wsl" }
    }
    [pscustomobject]@{ Dove = $dove; Disco = "$($vol.DriveLetter):"; Serve = [Math]::Max(0.0, $serve); Liberi = [double]$vol.SizeRemaining }
}
function MessaggioSpazio($s) {   # $null se lo spazio basta; GB come li mostra Esplora file (1.024^3 byte)
    if ($s.Liberi -ge $s.Serve) { return $null }
    (T 'spazio') -f [Math]::Ceiling($s.Serve / 1GB), $s.Disco, [Math]::Floor($s.Liberi / 1GB), [Math]::Ceiling(($s.Serve - $s.Liberi) / 1GB)
}
function Collegamenti {   # icona sul desktop e nel menu Start di questo utente (B1)
    'Desktop', 'Programs' | ForEach-Object { Join-Path ([Environment]::GetFolderPath($_)) 'ProfileMetaNanni.lnk' }
}
function InstallaApp($sorgente, $exe, $collegamenti) {   # copia l'app (PyInstaller a cartella) e mette le icone; si puo' rifare
    $dest = Split-Path $exe
    if (Test-Path $dest) { Remove-Item -Recurse -Force $dest }   # i file sono bloccati se l'app e' aperta: errore, lo dice chi chiama
    Copy-Item -Recurse $sorgente $dest
    Get-ChildItem -Recurse -File $dest | Unblock-File   # B2 (P10): via il segno "da internet" dello zip, l'app parte senza altri avvisi
    $sh = New-Object -ComObject WScript.Shell
    foreach ($c in $collegamenti) {   # l'icona la prende dall'exe
        $l = $sh.CreateShortcut($c); $l.TargetPath = $exe; $l.WorkingDirectory = $dest; $l.Description = 'ProfileMetaNanni'; $l.Save()
    }
}
if ($MyInvocation.InvocationName -eq '.') { return }   # caricato con ". installa_pmn.ps1" (prove): solo le funzioni

New-Item -ItemType Directory -Force $Cartella | Out-Null
[Windows.Forms.Application]::EnableVisualStyles()
Scrivi "=== fase $Fase, cartella $Radice"

# ===================== fase 1: app, poi WSL =====================
if ($Fase -eq 1 -and (Test-Path $AppPacchetto)) {   # subito: l'icona c'e' anche se il motore si installa dopo un riavvio
    try { InstallaApp $AppPacchetto $AppExe (Collegamenti); Scrivi "app copiata in $(Split-Path $AppExe), icone: $(Collegamenti)" }
    catch { Scrivi "$_"; Ferma (T 'app_copia') }
}
if ($Fase -eq 1 -and -not (WslPronta)) {
    Avviso (T 'wsl_serve')
    try { $p = Start-Process wsl.exe -ArgumentList '--install', '--no-distribution' -Verb RunAs -WindowStyle Hidden -PassThru }
    catch { Scrivi "$_"; Ferma (T 'wsl_permesso') }
    MostraBarra (T 'wsl_barra') $null
    $c = AttendiProcesso $p
    Scrivi "wsl --install --no-distribution: codice $c"
    if ($c -ne 0) { Ferma ((T 'wsl_codice') -f $c) }
    Set-Content (Join-Path $Cartella 'wsl_installata.txt') (Get-Date -Format o)   # segno per RiavvioInSospeso
    if (-not (WslPronta)) { ChiediRiavvio }
}

# ===================== fase 2: WSL "pmn" e motore =====================
NienteSospensione
Riprendi   # se si interrompe da qui in poi (PC spento durante i download), riparte al prossimo accesso
if (-not (WslPronta)) { ChiediRiavvio }
Remove-Item (Join-Path $Cartella 'wsl_installata.txt') -ErrorAction SilentlyContinue   # WSL pronta: un aggiornamento successivo non conta più
$s = ControllaSpazio (Join-Path $Radice $CatalogoRel)
if (-not $s) { Ferma (T 'disco') }
Scrivi "spazio: servono $($s.Serve) byte, liberi $($s.Liberi) su $($s.Disco), cartella della WSL $($s.Dove)"
$m = MessaggioSpazio $s
if ($m) { Ferma $m }

[void](Attendi (Avvia '-l -q'))
if (($script:Uscita | ForEach-Object { $_.Trim() }) -notcontains 'pmn') {
    MostraBarra (T 'linux_barra') $null
    New-Item -ItemType Directory -Force $s.Dove | Out-Null
    SaltaBenvenuto
    $inizio = Get-Date
    $c = Attendi (Avvia "--install Ubuntu-24.04 --name pmn --location `"$($s.Dove)`" --no-launch")
    ChiudiBenvenuto $inizio
    if ($c -ne 0) { Ferma ((T 'linux_codice') -f $c) }
    [void](Attendi (Avvia '-l -q'))   # anche qui il codice 0 non basta: se "pmn" non c'e' ancora, Windows aspetta il riavvio (S3-W)
    if (($script:Uscita | ForEach-Object { $_.Trim() }) -notcontains 'pmn') { ChiediRiavvio }
}
MostraBarra (T 'utente_barra') $null
if ((Attendi (Avvia "-d pmn -u root --cd `"$PSScriptRoot`" -- bash prepara_pmn.sh")) -ne 0) { Ferma (T 'utente_errore') }
[void](Attendi (Avvia '--terminate pmn'))   # l'utente predefinito scritto in wsl.conf vale dal prossimo avvio

# peso, spazio e tempo PRIMA di scaricare (D034): il motore misura la rete con --stima; lo spazio vero e' quello di Windows
$motore = "-d pmn -u pmn -- bash /home/pmn/profilemetananni/installer/installa_motore.sh --json --catalogo /home/pmn/profilemetananni/$CatalogoRel"
if ($Conf.specchio) { $motore += " --specchio $($Conf.specchio)" }
if ($Lingua -ne 'it') { $motore += " --lingua $Lingua" }   # P12: anche le righe del motore nella barra nella lingua di Windows
MostraBarra (T 'rete_barra') $null
$script:Eventi = @()
$c = Attendi (Avvia "$motore --stima") { param($r) $e = Evento $r; if ($e) { $script:Eventi += $e } }
$errore = $script:Eventi | Where-Object tipo -eq 'errore' | Select-Object -Last 1
if ($c -ne 0) { Ferma $(if ($errore) { (T 'cosa_fare') -f $errore.messaggio, $errore.cosa_fare } else { (T 'preparazione_ferma') -f $c }) }
$gb = [Math]::Round(($script:Eventi | Where-Object tipo -eq 'fine' | Select-Object -Last 1).risultato.da_scaricare_gb)   # P12: il numero, non il testo
$tempo = ($script:Eventi | Where-Object { $_.passo -eq 'controllo' -and $_.percentuale -eq 2 }).messaggio   # velocita' e tempo stimato
ChiudiBarra
$testo = (T 'domanda_scarico') -f $gb, $s.Disco, [Math]::Ceiling($s.Serve / 1GB), [Math]::Floor($s.Liberi / 1GB), $tempo
if (-not (Domanda $testo)) { NonRiprendere; Avviso (T 'niente_scaricato'); exit 0 }

MostraBarra (T 'inizio_barra') 0
$script:Errore = $null
$c = Attendi (Avvia "$motore --si") { param($r) $e = Evento $r   # i messaggi del controllo li ha gia' visti, con lo spazio vero
    if ($e) { if ($e.tipo -eq 'errore') { $script:Errore = $e }; if ($e.passo -ne 'controllo') { MostraBarra $e.messaggio $e.percentuale } } }
if ($c -ne 0) {
    Ferma $(if ($script:Errore) { (T 'cosa_fare') -f $script:Errore.messaggio, $script:Errore.cosa_fare } else { (T 'installazione_ferma') -f $c })
}
ChiudiBarra; NonRiprendere
Scrivi 'Tutto pronto'
if (Test-Path $AppExe) {   # alla fine si apre l'app (B1): col motore installato il pallino e' verde
    if ($Lingua -ne 'it') { ImpostaLinguaApp $Lingua }   # P12: l'app si apre nella lingua dell'installatore (se la persona non ha già scelto)
    Avviso (T 'pronto_app')
    Start-Process $AppExe
} else { Avviso (T 'pronto') }
