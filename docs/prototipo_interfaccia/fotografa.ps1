# Fotografa le schermate del prototipo con Edge senza finestra (headless), 1366x860.
# Serve il server del prototipo acceso: python -m http.server 8766 --bind 127.0.0.1 --directory docs/prototipo_interfaccia
# Uso: powershell -File fotografa.ps1 [-Cartella <dove salvare>]
param([string]$Cartella = "$PSScriptRoot\schermate")
$edge = "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
$profilo = Join-Path $env:TEMP "pmn_edge_foto"
New-Item -ItemType Directory -Force $Cartella | Out-Null
$viste = [ordered]@{
  "00_avvio"                = @("index.html#home", 2300)
  "01_home"                 = @("index.html?senza_avvio#home", 1500)
  "02_progetto"             = @("index.html?senza_avvio#progetto", 1500)
  "03_scelte"               = @("index.html?senza_avvio#scelte", 1500)
  "04_scelte_tempo_lungo"   = @("index.html?senza_avvio&scenario=stima_TEMPO_LUNGO#scelte", 1500)
  "05_esecuzione"           = @("index.html?senza_avvio#esecuzione", 4200)
  "06_esecuzione_finita"    = @("index.html?senza_avvio#esecuzione", 12000)
  "07_errore_db_mancante"   = @("index.html?senza_avvio&scenario=esegui_DB_MANCANTE#esecuzione", 12000)
  "08_risultati"            = @("index.html?senza_avvio#risultati", 1500)
  "09_sicurezza"            = @("index.html?senza_avvio#sicurezza", 1500)
  "10_motore"               = @("index.html?senza_avvio#motore", 1500)
}
foreach ($nome in $viste.Keys) {
  $url, $tempo = $viste[$nome]
  $png = Join-Path $Cartella "$nome.png"
  Start-Process -Wait -FilePath $edge -ArgumentList @("--headless=new", "--disable-gpu", "--hide-scrollbars",
    "--user-data-dir=$profilo", "--window-size=1366,860", "--virtual-time-budget=$tempo",
    "--screenshot=$png", "http://127.0.0.1:8766/$url")
  Write-Output "$nome $(if (Test-Path $png) { 'ok' } else { 'MANCA' })"
}
# pagine lunghe (finestra alta)
foreach ($v in @(@("08b_risultati_lunga", "index.html?senza_avvio#risultati", 1700),
                 @("09c_salame_fuori_campo", "index.html?senza_avvio&caso=salame#sicurezza", 1400),
                 @("09d_salsiccia_con_lab", "index.html?senza_avvio&caso=salsiccia_lab#sicurezza", 1400))) {
  $png = Join-Path $Cartella "$($v[0]).png"
  Start-Process -Wait -FilePath $edge -ArgumentList @("--headless=new", "--disable-gpu", "--hide-scrollbars",
    "--user-data-dir=$profilo", "--window-size=1366,$($v[2])", "--virtual-time-budget=1500",
    "--screenshot=$png", "http://127.0.0.1:8766/$($v[1])")
  Write-Output "$($v[0]) $(if (Test-Path $png) { 'ok' } else { 'MANCA' })"
}
