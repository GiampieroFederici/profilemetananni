@echo off
rem installer\windows\installa_pmn.cmd - doppio clic per installare profilemetananni (D027). Avvia installa_pmn.ps1 senza finestre nere.
start "" powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%~dp0installa_pmn.ps1"
