# installer/windows/installa_pmn.ps1 - parte Windows dell'installatore (D027, D039, D043-D045). Si avvia con un doppio clic su installa_pmn.cmd.
# Fase 1: attiva WSL (finestra Si/No di Windows) e, se serve, chiede il riavvio; al prossimo accesso riparte da solo dalla fase 2.
# Fase 2: sceglie il disco interno con piu' spazio (D045), crea la WSL "pmn", chiede al motore lo spazio che serve (una sola
#         regola, in installa_motore.sh --stima: v1.1 R3) e lo confronta con lo spazio vero di Windows, chiede conferma con
#         peso, spazio e tempo per sorgente (D034), copia l'app solo adesso (v1.1 R7), installa il motore con la barra e il
#         pulsante Interrompi (R6), il coperchio del portatile che non sospende (R5, se la persona dice Si') e lo spazio di
#         Windows controllato ogni minuto (R7).
# Se si interrompe (PC spento durante i download) riparte da solo al prossimo accesso; dopo Interrompi no. L'uscita di wsl.exe (in inglese) va solo nel log.
# Solo per chi sviluppa (D038, D044, D170): file prova.conf accanto a questo script, righe "specchio=URL" e "catalogo=installer/<file>.tsv".
param([int]$Fase = 1)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Windows.Forms
$Radice = Split-Path (Split-Path $PSScriptRoot)   # la cartella che contiene installer\ e motore\
$Cartella = Join-Path $env:LOCALAPPDATA 'profilemetananni'
$Log = Join-Path $Cartella 'installazione_windows.log'
$RunOnce = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\RunOnce'
$FileCoperchio = Join-Path $Cartella 'coperchio.txt'   # R5: l'impostazione del coperchio di prima, finche' non e' rimessa
$env:WSL_UTF8 = '1'  # wsl.exe scrive in UTF-8 invece che in UTF-16
function LeggiConf($file) {   # prova.conf (solo per chi sviluppa): righe chiave=valore
    $c = @{}
    if (Test-Path $file) { Get-Content $file | ForEach-Object { if ($_ -match '^\s*(\w+)\s*=\s*(\S+)\s*$') { $c[$Matches[1]] = $Matches[2] } } }
    $c
}
$Conf = LeggiConf (Join-Path $PSScriptRoot 'prova.conf')
$AppPacchetto = Join-Path $Radice 'app_windows\ProfileMetaNanni'   # c'e' solo nel pacchetto (costruisci_pacchetto.py), non nel repository
$AppExe = Join-Path $Cartella 'app\ProfileMetaNanni.exe'

# B2 (P12): i testi per la persona, in italiano e in inglese, tutti qui. Lingua = quella di Windows (it: italiano, altro: inglese).
function SceltaLingua($cultura) { if ("$cultura" -like 'it*') { 'it' } else { 'en' } }
$Lingua = SceltaLingua (Get-UICulture).Name
$TESTI = [ordered]@{
    dettagli = @("{0}`n`nDettagli tecnici nel file:`n{1}", "{0}`n`nTechnical details in the file:`n{1}")
    riavvio_domanda = @("Serve un riavvio del computer. Dopo il riavvio l'installazione riprende da sola (al massimo 2 minuti dopo l'accesso).`n`nSe dopo 5 minuti non vedi la finestra di profilemetananni, fai di nuovo doppio clic su `"Installa profilemetananni`": riprende da dove era.`n`nRiavvio adesso?",
                        "The computer needs a restart. After the restart the installation resumes by itself (at most 2 minutes after you sign in).`n`nIf after 5 minutes you do not see the profilemetananni window, double-click `"Installa profilemetananni`" again: it resumes from where it was.`n`nRestart now?")
    riavvio_dopo = @("Va bene. Quando riavvii il computer, l'installazione riprende da sola. Se non riprende, fai di nuovo doppio clic su `"Installa profilemetananni`".",
                     "All right. When you restart the computer, the installation resumes by itself. If it does not, double-click `"Installa profilemetananni`" again.")
    spazio = @("Lo spazio sul disco non basta: servono {0} sul disco {1}, ce ne sono {2}.`n`nLibera almeno {3} GB e riapri l'installazione.",
               "There is not enough space on the disk: {0} are needed on disk {1}, there are {2}.`n`nFree at least {3} GB and open the installation again.")
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
    domanda_scarico = @("profilemetananni scaricherà {0} di database, più i programmi (circa 11 GB, se non ci sono già).`nSpazio necessario sul disco {1} {2} (liberi: {3}).`n{4}`n`nProcedo con l'installazione?",
                        "profilemetananni will download {0} of databases, plus the programs (about 11 GB, if they are not there yet).`nSpace needed on disk {1} {2} (free: {3}).`n{4}`n`nShall I go ahead with the installation?")
    circa_gb = @("circa {0} GB", "about {0} GB")
    meno_di_1_gb = @("meno di 1 GB", "less than 1 GB")
    domanda_niente = @("I database di profilemetananni sono già tutti su questo PC: non li scarico di nuovo. Se manca qualche programma, lo scarico (al massimo circa 11 GB).`n`nProcedo con l'installazione?",
                       "All the profilemetananni databases are already on this PC: I will not download them again. If a program is missing, I download it (about 11 GB at most).`n`nShall I go ahead with the installation?")
    niente_scaricato = @("Va bene: non ho scaricato nulla. Riapri l'installazione quando vuoi.",
                         "All right: I have not downloaded anything. Open the installation again when you like.")
    inizio_barra = @("Inizio l'installazione...", "Starting the installation...")
    installazione_ferma = @("L'installazione si è fermata (codice {0}). Riapri l'installazione: riprende da dove era rimasta.",
                            "The installation stopped (code {0}). Open the installation again: it resumes from where it stopped.")
    pronto_app = @("Tutto pronto: profilemetananni è installato e funziona.`n`nOra apro il programma. Le prossime volte lo trovi sul desktop e nel menu Start: ProfileMetaNanni.",
                   "All ready: profilemetananni is installed and works.`n`nNow I open the program. Next time you will find it on the desktop and in the Start menu: ProfileMetaNanni.")
    pronto = @("Tutto pronto: profilemetananni è installato e funziona.", "All ready: profilemetananni is installed and works.")
    memoria = @("Questo PC ha {0} GB di memoria: ProfileMetaNanni ne chiede almeno 16 (l'analisi con MetaPhlAn usa fino a 8 GB dentro Linux).`n`nNon ho installato né scaricato nulla. Installa ProfileMetaNanni su un PC con 16 GB di memoria o più.",
                "This PC has {0} GB of memory: ProfileMetaNanni needs at least 16 (the analysis with MetaPhlAn uses up to 8 GB inside Linux).`n`nI have not installed or downloaded anything. Install ProfileMetaNanni on a PC with 16 GB of memory or more.")
    durata_minuto = @("1 minuto", "1 minute")
    durata_minuti = @("{0} minuti", "{0} minutes")
    durata_ore = @("{0} ore", "{0} hours")
    coperchio_domanda = @("Lo scarico durerà circa {0}. Se chiudi il coperchio del portatile, Windows lo mette in sospensione e lo scarico si ferma.`n`nVuoi che imposti la chiusura del coperchio su `"Non fare nulla`" finché l'installazione finisce? Alla fine rimetto l'impostazione di adesso.`n`nSe rispondi No, tieni il coperchio aperto.",
                          "The download will take about {0}. If you close the lid of the laptop, Windows puts it to sleep and the download stops.`n`nShall I set closing the lid to `"Do nothing`" until the installation ends? At the end I put back the current setting.`n`nIf you answer No, keep the lid open.")
    batteria = @("Il computer sta andando a batteria e lo scarico durerà circa {0}.`n`nCollega l'alimentatore: se la batteria si scarica, l'installazione si ferma (riprende quando riaccendi).",
                 "The computer is running on battery and the download will take about {0}.`n`nConnect the power supply: if the battery runs out, the installation stops (it resumes when you switch on again).")
    interrompi = @("Interrompi", "Stop")
    interrompi_domanda = @("Vuoi fermare l'installazione?`n`nQuello che è già scaricato resta sul computer: quando riapri l'installazione, riprende da qui.",
                           "Do you want to stop the installation?`n`nWhat is already downloaded stays on the computer: when you open the installation again, it resumes from here.")
    fermando = @("Fermo l'installazione...", "Stopping the installation...")
    fermata = @("Fermato: riapri l'installazione quando vuoi, riprende da qui.", "Stopped: open the installation again when you like, it resumes from here.")
    spazio_finito = @("Sul disco {0} restano solo {1} liberi: ho fermato l'installazione per non riempirlo.`n`nLibera almeno {2} GB (per esempio svuota il Cestino o disinstalla un programma che non usi) e riapri l'installazione: riprende da qui.",
                      "Only {1} are left free on disk {0}: I stopped the installation so as not to fill it.`n`nFree at least {2} GB (for example empty the Recycle Bin or uninstall a program you do not use) and open the installation again: it resumes from here.")
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
$Attivita = 'profilemetananni - continua installazione'
function Riprendi($voce = 'profilemetananni', $attivita = $Attivita, $file = $PSCommandPath) {   # al prossimo accesso di questo utente riparte da solo dalla fase 2
    # conhost --headless: nessuna finestra (Windows Terminal ignora -WindowStyle Hidden e lascia una finestra vuota, S3-W)
    $argomenti = "--headless powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$file`" -Fase 2"
    New-ItemProperty -Path $RunOnce -Name $voce -Value "conhost.exe $argomenti" -PropertyType String -Force | Out-Null
    # A0 (VM 30/10): RunOnce ha lanciato conhost nei primi secondi dell'accesso e PowerShell non e' mai partito. Seconda via,
    # senza amministratore: un'attivita' pianificata "all'accesso" di questo utente, 2 minuti dopo; se la fase 2 e' gia'
    # partita da RunOnce, la seconda copia trova l'installazione aperta (UnaSolaInstallazione) ed esce. Tolta da NonRiprendere.
    try {
        $u = "$env:USERDOMAIN\$env:USERNAME"
        $t = New-ScheduledTaskTrigger -AtLogOn -User $u; $t.Delay = 'PT2M'
        Register-ScheduledTask -TaskName $attivita -Force -Action (New-ScheduledTaskAction -Execute 'conhost.exe' -Argument $argomenti) -Trigger $t `
            -Principal (New-ScheduledTaskPrincipal -UserId $u -LogonType Interactive -RunLevel Limited) `
            -Settings (New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit 0) | Out-Null
    } catch { Scrivi "attivita' di riserva non creata (resta RunOnce): $_" }
}
function NonRiprendere($voce = 'profilemetananni', $attivita = $Attivita) {
    Remove-ItemProperty -Path $RunOnce -Name $voce -ErrorAction SilentlyContinue
    try { Unregister-ScheduledTask -TaskName $attivita -Confirm:$false -ErrorAction Stop } catch { }   # non c'e': niente da togliere
}
function UnaSolaInstallazione($nome = 'Local\profilemetananni_installa') {   # A0: RunOnce e l'attivita' di riserva possono partire
    # entrambe (o la persona riapre l'installazione mentre gira): solo la prima continua. Il lucchetto si libera all'uscita.
    $script:Unico = New-Object Threading.Mutex($false, $nome)
    try { $script:Unico.WaitOne(0) } catch [Threading.AbandonedMutexException] { $true }   # lasciato da una copia finita male: e' nostro
}
function NienteSospensione {   # B2: i download durano piu' del tempo dopo cui Windows sospende il PC; vale finche' questo processo e' vivo
    Add-Type -Namespace Pmn -Name Energia -MemberDefinition '[DllImport("kernel32.dll")] public static extern uint SetThreadExecutionState(uint f);'
    [void][Pmn.Energia]::SetThreadExecutionState(2147483649)   # 0x80000001 = ES_CONTINUOUS + ES_SYSTEM_REQUIRED (lo schermo si puo' spegnere)
}
function ChiudiBarra { if ($script:Barra) { $script:Barra.f.Close(); $script:Barra = $null } }
function Ferma($t) {   # errore: lo dice in italiano e si ferma; l'utente riapre l'installazione quando ha risolto
    Scrivi "STOP: $t"; ChiudiBarra; NonRiprendere; RipristinaCoperchio
    Avviso ((T 'dettagli') -f $t, $Log); exit 2
}
function MostraBarra($testo, $pct, [switch]$Interrompi) {   # finestra di avanzamento; $pct vuoto = barra animata
    # senza X (si chiuderebbe solo la finestra, non il motore): per fermare c'e' il pulsante Interrompi (R6), solo mentre lavora il motore
    if (-not $script:Barra) {
        $fo = New-Object Windows.Forms.Form -Property @{ Text = 'profilemetananni'; Width = 580; Height = 205; ControlBox = $false; FormBorderStyle = 'FixedDialog'; StartPosition = 'CenterScreen'; TopMost = $true }
        $l = New-Object Windows.Forms.Label -Property @{ Left = 20; Top = 20; Width = 530; Height = 50 }
        $b = New-Object Windows.Forms.ProgressBar -Property @{ Left = 20; Top = 80; Width = 530; Height = 25 }
        $i = New-Object Windows.Forms.Button -Property @{ Left = 430; Top = 120; Width = 120; Height = 30; Text = (T 'interrompi'); Visible = $false }
        $i.Add_Click({ if (-not $script:ChiestoStop -and (Domanda (T 'interrompi_domanda'))) { $script:ChiestoStop = $true; $script:Barra.i.Enabled = $false } })
        $fo.Controls.AddRange(@($l, $b, $i)); $fo.Show()
        $script:Barra = @{ f = $fo; l = $l; b = $b; i = $i }
    }
    $script:Barra.i.Visible = [bool]$Interrompi
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
function Attendi($p, [scriptblock]$ogniRiga = {}, [scriptblock]$ogniGiro = {}) {   # legge l'uscita riga per riga senza bloccare la finestra; torna il codice
    $script:Uscita = New-Object Collections.Generic.List[string]
    $err = $p.StandardError.ReadToEndAsync()
    while ($true) {
        $t = $p.StandardOutput.ReadLineAsync()
        while (-not $t.IsCompleted) { [Windows.Forms.Application]::DoEvents(); & $ogniGiro | Out-Null; Start-Sleep -Milliseconds 100 }
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
# B1-b (VM 30/10, 8 GB): si scaricavano 44 GB e poi la prova finale era ROSSO per memoria. Soglia 14 GB: un PC da 16 GB ne
# mostra 15,2-15,6 (una parte la tiene la scheda video integrata); 14 lascia questo margine e ferma i PC da 8 e 12 GB.
function MemoriaInsufficiente($byte, $soglia = 14GB) {   # $null se basta, altrimenti il messaggio per la persona
    if ([double]$byte -ge $soglia) { return $null }
    (T 'memoria') -f [Math]::Round([double]$byte / 1GB)
}
function MemoriaDelPC { [double](Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory }
# B1-a: i messaggi del motore citano il suo log con il percorso di Linux, che da Windows non si apre. Alla fine (errore)
# il log si copia accanto a quello di Windows e il messaggio dice quel percorso.
$LogMotoreWin = Join-Path $Cartella 'installazione_motore.log'
function PercorsoWsl($linux, $distro = 'pmn') { "\\wsl.localhost\$distro" + ($linux -replace '/', '\') }
function CopiaLogMotore($linux, $dest = $LogMotoreWin, $sorgente = (PercorsoWsl $linux)) {   # il percorso da dare alla persona
    if (-not $linux) { return $null }
    try { Copy-Item -LiteralPath $sorgente -Destination $dest -Force -ErrorAction Stop; return $dest }
    catch { Scrivi "log del motore non copiato ($sorgente): $_"; return $sorgente }   # \\wsl.localhost si apre lo stesso da Esplora file
}
function TestoErrore($e, $logLinux) {   # messaggio + cosa fare dell'errore del motore, con il log in un percorso di Windows
    $t = (T 'cosa_fare') -f $e.messaggio, $e.cosa_fare
    if ($logLinux -and $t.Contains($logLinux)) { $t = $t.Replace($logLinux, (CopiaLogMotore $logLinux)) }
    $t
}

function ArgomentiMotore($Conf, $Lingua) {   # la riga per wsl.exe che lancia il motore; D170: prova.conf con la sola riga
    # "catalogo=..." usa le sorgenti vere (GitHub e S3) con un altro catalogo
    $CatalogoRel = if ($Conf.catalogo) { $Conf.catalogo } else { 'installer/catalogo.tsv' }
    $motore = "-d pmn -u pmn -- bash /home/pmn/profilemetananni/installer/installa_motore.sh --json --catalogo /home/pmn/profilemetananni/$CatalogoRel"
    if ($Conf.specchio) { $motore += " --specchio $($Conf.specchio)" }
    if ($Lingua -ne 'it') { $motore += " --lingua $Lingua" }   # P12: anche le righe del motore nella barra nella lingua di Windows
    $motore
}
function Durata($secondi) {   # "40 minuti", "8,1 ore"; $null se il tempo non si sa
    if ($null -eq $secondi) { return $null }
    $min = [Math]::Floor([double]$secondi / 60) + 1
    if ($min -eq 1) { return T 'durata_minuto' }   # non "1 minuti"
    if ($min -lt 60) { return (T 'durata_minuti') -f $min }
    $ore = ([Math]::Round($min / 60, 1)).ToString([Globalization.CultureInfo]::InvariantCulture)
    if ($Lingua -eq 'it') { $ore = $ore -replace '\.', ',' }
    (T 'durata_ore') -f $ore
}
# --- R5: coperchio del portatile. SetThreadExecutionState (NienteSospensione) non basta: la chiusura del coperchio la
#     decide l'impostazione LIDACTION (sottogruppo SUB_BUTTONS). Si cambia solo con il Si' della persona e solo con
#     l'alimentatore (AC), senza permessi di amministratore; il valore di prima resta in $FileCoperchio finche' non e' rimesso.
$script:Powercfg = { param([string[]]$a) & powercfg.exe @a }   # nelle prove si sostituisce
function LeggiCoperchio($testo) {   # uscita di "powercfg /q SCHEME_CURRENT SUB_BUTTONS LIDACTION", in qualsiasi lingua:
    # gli unici valori 0x... a fine riga sono l'impostazione con l'alimentatore (AC) e poi a batteria (DC)
    $v = @([regex]::Matches(($testo -join "`n"), ':\s*0x([0-9a-fA-F]{8})\s*$', 'Multiline') | ForEach-Object { [Convert]::ToInt32($_.Groups[1].Value, 16) })
    if ($v.Count -lt 2) { return $null }
    [pscustomobject]@{ AC = $v[-2]; DC = $v[-1] }
}
function ServeDomandaCoperchio($ac, $secondi) {   # 0 = "Non fare nulla"; si chiede solo se lo scarico supera 30 minuti (o non si sa)
    ($null -ne $ac) -and ($ac -ne 0) -and (($null -eq $secondi) -or ([double]$secondi -gt 1800))
}
function ImpostaCoperchio($originale, $file = $FileCoperchio) {
    Set-Content $file $originale
    & $script:Powercfg @('/setacvalueindex', 'SCHEME_CURRENT', 'SUB_BUTTONS', 'LIDACTION', '0')
    & $script:Powercfg @('/setactive', 'SCHEME_CURRENT')
}
function RipristinaCoperchio($file = $FileCoperchio) {   # a fine installazione, dopo un errore o Interrompi, e alla ripresa dopo un'interruzione
    if (-not (Test-Path $file)) { return }
    $v = "$(Get-Content $file | Select-Object -First 1)".Trim()
    if ($v -match '^\d+$') {
        & $script:Powercfg @('/setacvalueindex', 'SCHEME_CURRENT', 'SUB_BUTTONS', 'LIDACTION', $v)
        & $script:Powercfg @('/setactive', 'SCHEME_CURRENT')
    }
    Remove-Item $file
}
function ABatteria { [Windows.Forms.SystemInformation]::PowerStatus.PowerLineStatus -eq 'Offline' }
# --- R7: spazio di Windows durante lo scarico (dentro WSL "df" vede il disco virtuale da 1 TB e non se ne accorge)
function LiberiSu($disco) { [double](Get-Volume -DriveLetter $disco[0]).SizeRemaining }
function SpazioBasso($liberi, $soglia = 5GB) { [double]$liberi -lt $soglia }
function Riassunto($e) {   # R4 (§2.5): una riga per il log ogni 5 minuti dall'ultimo avanzamento del motore
    if ($null -eq $e -or $null -eq $e.byte_totali) { return $null }
    # A6 (VM 30/10): numeri con la virgola in italiano, come la barra (la riga col punto sembrava un messaggio della barra)
    $n = { param($x) $s = ([double]$x).ToString([Globalization.CultureInfo]::InvariantCulture); if ($Lingua -eq 'it') { $s -replace '\.', ',' } else { $s } }
    $gb = { param($b) & $n ([Math]::Round([double]$b / 1GB, 1)) }
    $eta = if ($null -ne $e.eta_s) { "$([Math]::Floor($e.eta_s / 3600)) h $([Math]::Floor(($e.eta_s % 3600) / 60)) min" } else { '?' }
    $parti = @($e.sorgenti | ForEach-Object { "$($_.sorgente) $(& $gb $_.byte_fatti)/$(& $gb $_.byte_totali) GB $(& $n $_.velocita_mb_s) MB/s" }) -join ', '
    "RIASSUNTO: $(& $gb $e.byte_fatti) di $(& $gb $e.byte_totali) GB, $(& $n $e.velocita_mb_s) MB/s, mancano $eta ($parti)"
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
function DoveInstallare {   # disco e cartella della WSL "pmn" (quella che c'e' gia', o il disco interno con piu' spazio) e
    # spazio vero di Windows: dentro WSL si vede solo il disco virtuale (S3). Lo spazio che serve lo dice il motore (--stima).
    $dove = CartellaPmn
    if ($dove) { $vol = Get-Volume -DriveLetter $dove[0] }
    else {
        $vol = DiscoMigliore
        if (-not $vol) { return $null }
        $dove = if ("$($vol.DriveLetter):" -eq $env:SystemDrive) { Join-Path $Cartella 'wsl' } else { "$($vol.DriveLetter):\profilemetananni\wsl" }
    }
    [pscustomobject]@{ Dove = $dove; Disco = "$($vol.DriveLetter):"; Serve = 0.0; Liberi = [double]$vol.SizeRemaining }
}
function MessaggioSpazio($s) {   # $null se lo spazio basta; GB come li mostra Esplora file (1.024^3 byte)
    if ($s.Liberi -ge $s.Serve) { return $null }
    (T 'spazio') -f (GbParole $s.Serve -Circa), $s.Disco, (GbParole $s.Liberi), [Math]::Ceiling(($s.Serve - $s.Liberi) / 1GB)
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
function GbParole($byte, [switch]$Circa) {   # B4-e: mai "0 GB": "meno di 1 GB", "circa 40 GB" (in su), "146 GB" (in giu')
    if ([double]$byte -lt 1GB) { return T 'meno_di_1_gb' }
    if ($Circa) { return (T 'circa_gb') -f [Math]::Ceiling([double]$byte / 1GB) }
    "{0} GB" -f [Math]::Floor([double]$byte / 1GB)
}
function DomandaScarico($byte, $s, $tempo) {   # B4-e: con i database gia' tutti sul PC era "circa 0 GB di database... circa 0 GB"
    if ([double]$byte -le 0) { return T 'domanda_niente' }
    (T 'domanda_scarico') -f (GbParole $byte -Circa), $s.Disco, (GbParole $s.Serve -Circa), (GbParole $s.Liberi), $tempo
}
if ($MyInvocation.InvocationName -eq '.') { return }   # caricato con ". installa_pmn.ps1" (prove): solo le funzioni

New-Item -ItemType Directory -Force $Cartella | Out-Null
[Windows.Forms.Application]::EnableVisualStyles()
if (-not (UnaSolaInstallazione)) { Scrivi "=== fase ${Fase}: l'installazione è già aperta, questa copia esce"; exit 0 }
Scrivi "=== fase $Fase, cartella $Radice"
$ram = MemoriaDelPC; Scrivi "memoria del PC: $ram byte"
$m = MemoriaInsufficiente $ram   # B1-b: prima di attivare WSL, copiare l'app o scaricare qualsiasi cosa
if ($m) { Ferma $m }

# ===================== fase 1: WSL =====================
# v1.1 (R7, §1.6): l'app e le icone non si copiano piu' qui ma in fase 2, dopo il controllo dello spazio e il Si' della
# persona: un tentativo fermato per lo spazio (o un No) non lascia nulla sul PC. Dopo un riavvio la fase 2 riparte da sola.
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
RipristinaCoperchio   # R5: un'installazione interrotta (PC spento) aveva cambiato il coperchio: si rimette com'era
if (-not (WslPronta)) { ChiediRiavvio }
Remove-Item (Join-Path $Cartella 'wsl_installata.txt') -ErrorAction SilentlyContinue   # WSL pronta: un aggiornamento successivo non conta più
$s = DoveInstallare
if (-not $s) { Ferma (T 'disco') }

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

# peso, spazio e tempo PRIMA di scaricare (D034): il motore misura la rete per sorgente e calcola lo spazio che serve
# (una sola regola, R3); lo spazio libero vero e' quello di Windows
$motore = ArgomentiMotore $Conf $Lingua
MostraBarra (T 'rete_barra') $null
$script:Eventi = @()
$c = Attendi (Avvia "$motore --stima") { param($r) $e = Evento $r; if ($e) { $script:Eventi += $e } }
$errore = $script:Eventi | Where-Object tipo -eq 'errore' | Select-Object -Last 1
$logStima = ($script:Eventi | Where-Object tipo -eq 'inizio' | Select-Object -First 1).log
if ($c -ne 0) { Ferma $(if ($errore) { TestoErrore $errore $logStima } else { (T 'preparazione_ferma') -f $c }) }
$stima = ($script:Eventi | Where-Object tipo -eq 'fine' | Select-Object -Last 1).risultato
$daScaricare = [double]$stima.da_scaricare_byte   # P12: il numero (byte), non il testo; B4-e: GbParole, mai "0 GB"
$tempo = ($script:Eventi | Where-Object { $_.passo -eq 'controllo' -and $_.percentuale -eq 2 }).messaggio   # velocita' e tempo per sorgente
$s.Serve = [double]$stima.spazio_necessario_byte
$s.Liberi = LiberiSu $s.Disco   # dopo la WSL nuova
Scrivi "spazio: servono $($s.Serve) byte (dal motore), liberi $($s.Liberi) su $($s.Disco), cartella della WSL $($s.Dove)"
$m = MessaggioSpazio $s
if ($m) { Ferma $m }
ChiudiBarra
$testo = DomandaScarico $daScaricare $s $tempo
if (-not (Domanda $testo)) { NonRiprendere; Avviso (T 'niente_scaricato'); exit 0 }

if (Test-Path $AppPacchetto) {   # R7: l'app e le icone solo adesso, con lo spazio controllato e il Si' della persona
    try { InstallaApp $AppPacchetto $AppExe (Collegamenti); Scrivi "app copiata in $(Split-Path $AppExe), icone: $(Collegamenti)" }
    catch { Scrivi "$_"; Ferma (T 'app_copia') }
}
$lungo = Durata $stima.tempo_stimato_s
if ($null -eq $lungo) { $lungo = (T 'durata_ore') -f '?' }
if ((ABatteria) -and (ServeDomandaCoperchio 1 $stima.tempo_stimato_s)) { Avviso ((T 'batteria') -f $lungo) }
$coperchio = LeggiCoperchio (& $script:Powercfg @('/q', 'SCHEME_CURRENT', 'SUB_BUTTONS', 'LIDACTION'))
Scrivi "coperchio con l'alimentatore: $($coperchio.AC), a batteria: $($coperchio.DC)"
if ((ServeDomandaCoperchio $coperchio.AC $stima.tempo_stimato_s) -and (Domanda ((T 'coperchio_domanda') -f $lungo))) {
    ImpostaCoperchio $coperchio.AC; Scrivi "coperchio: 'Non fare nulla' con l'alimentatore fino alla fine (prima: $($coperchio.AC))"
}

# il motore, con Interrompi (R6), lo spazio di Windows ogni minuto (R7) e una riga riassuntiva nel log ogni 5 minuti (R4)
MostraBarra (T 'inizio_barra') 0 -Interrompi
$script:Errore = $null; $script:Corsa = $null; $script:Ultimo = $null; $script:ChiestoStop = $false; $script:Fermando = $null
$script:ProssimoSpazio = (Get-Date).AddMinutes(1); $script:ProssimoRiassunto = (Get-Date).AddMinutes(5)
function FermaMotore {   # annulla --corsa del motore (P41: ferma il gruppo di processi); se non basta, si spegne la WSL "pmn"
    if (-not $script:FermoChiesto -and $script:Corsa) {
        $script:FermoChiesto = Get-Date
        [void](Avvia "-d pmn -u pmn -- bash /home/pmn/profilemetananni/motore/pmn-motore annulla --corsa $($script:Corsa)")
    } elseif ($script:FermoChiesto -and ((Get-Date) - $script:FermoChiesto).TotalSeconds -gt 30 -and -not $script:Spenta) {
        $script:Spenta = $true; [void](Avvia '--terminate pmn')   # come un PC spento: riprende lo stesso da dove era
    }
}
$giro = {
    if ($script:ChiestoStop -and -not $script:Fermando) { $script:Fermando = 'persona'; Scrivi 'Interrompi: chiesto dalla persona'; MostraBarra (T 'fermando') $null -Interrompi }
    if ((Get-Date) -ge $script:ProssimoSpazio) {
        $script:ProssimoSpazio = (Get-Date).AddMinutes(1)
        $l = LiberiSu $s.Disco
        if ((SpazioBasso $l) -and -not $script:Fermando) { $script:Fermando = 'spazio'; $script:LiberiFine = $l; Scrivi "spazio di Windows quasi finito: $l byte liberi" }
    }
    if ($script:Fermando) { FermaMotore }
    if ((Get-Date) -ge $script:ProssimoRiassunto) {
        $script:ProssimoRiassunto = (Get-Date).AddMinutes(5)
        $r = Riassunto $script:Ultimo; if ($r) { Scrivi $r }
    }
}
$c = Attendi (Avvia "$motore --si --spazio-libero $([long]$s.Liberi)") { param($r) $e = Evento $r   # i messaggi del controllo li ha gia' visti
    if ($e) {
        if ($e.tipo -eq 'inizio') { $script:Corsa = $e.corsa; $script:LogMotore = $e.log }
        if ($e.tipo -eq 'errore') { $script:Errore = $e }
        if ($null -ne $e.byte_totali) { $script:Ultimo = $e }
        if ($e.passo -ne 'controllo' -and -not $script:Fermando) { MostraBarra $e.messaggio $e.percentuale -Interrompi }
    } } $giro
if ($c -ne 0) {
    if ($script:Fermando -eq 'persona') {   # arresto voluto: niente ripresa da sola al prossimo accesso (R6)
        ChiudiBarra; NonRiprendere; RipristinaCoperchio; Scrivi "fermata dalla persona (codice $c)"
        Avviso (T 'fermata'); exit 3
    }
    if ($script:Fermando -eq 'spazio') { Ferma ((T 'spazio_finito') -f $s.Disco, (GbParole $script:LiberiFine), 10) }
    Ferma $(if ($script:Errore) { TestoErrore $script:Errore $script:LogMotore } else { (T 'installazione_ferma') -f $c })
}
ChiudiBarra; NonRiprendere; RipristinaCoperchio
Scrivi 'Tutto pronto'
if (Test-Path $AppExe) {   # alla fine si apre l'app (B1): col motore installato il pallino e' verde
    if ($Lingua -ne 'it') { ImpostaLinguaApp $Lingua }   # P12: l'app si apre nella lingua dell'installatore (se la persona non ha già scelto)
    Avviso (T 'pronto_app')
    Start-Process $AppExe
} else { Avviso (T 'pronto') }
