# ProfileMetaNanni on Ubuntu

This guide installs ProfileMetaNanni on a computer with Ubuntu: the engine and the app with its windows, in the same Linux. No administrator rights are needed, except for the system programs that Ubuntu does not already have (the script says which ones).

Italian version: [guida_ubuntu_IT.md](guida_ubuntu_IT.md).

## 1. What you need

| | |
|---|---|
| System | Ubuntu 24.04, x86_64 processor (64 bit) |
| Memory | `[DA COMPLETARE DOPO LA PROVA]` |
| Disk | about 180 GB free on an internal disk, in your home folder |
| Network | to download about 139 GB of databases (a few hours) |

## 2. The three commands

1. Download the ProfileMetaNanni folder from the project page on GitHub and extract it, or copy it from another computer. Put it in a fixed place, for example `~/profilemetananni`: the program runs from there, so after the installation do not move it and do not delete it.
2. Open the terminal in the folder and start the installation:

   ```bash
   cd ~/profilemetananni
   bash installer/linux/installa_pmn.sh
   ```

3. Start the program from the applications menu (entry **ProfileMetaNanni**) or from the terminal:

   ```bash
   profilemetananni
   ```

   If the terminal does not find the command, log out and log in again, or use the full path: `~/.local/bin/profilemetananni`.

## 3. What happens during the installation

- If a system program is missing, the script stops and shows a line `sudo apt install ...`. Run it, then run the script again.
- Before downloading, the script says how much it downloads, how much space is needed and how long it will take. Then it asks `Procedo con l'installazione? (s/n)`: answer `s` (yes). With the option `--si` it does not ask.
- The download takes hours. You can stop it with Ctrl+C: when you run the same command again it resumes from where it stopped, without downloading again.
- At the end it runs a test on a small sample and writes `GREEN` if the engine works. Then it prepares the app and writes the command and the menu entry.
- If system libraries for the windows are missing, the script says so with another line `sudo apt install ...`: run it before starting the program.
- You can run the script again whenever you want: what is already there is not done again. The engine repeats only the final test (a few minutes).

## 4. Where things are

| What | Where |
|---|---|
| Projects and results | Documents folder, in `ProfileMetaNanni/<project name>/risultati` (the report is in `risultati/referto`) |
| Working files of an analysis | `ProfileMetaNanni/<project name>/pmn_work` |
| Logs of the engine and of the installation | `~/.pmn/log` |
| Engine, databases and program environments | `~/.pmn` |
| Command and menu entry | `~/.local/bin/profilemetananni` and `~/.local/share/applications/profilemetananni.desktop` |
| App settings (language, last folder) | `~/.config/ProfileMetaNanni` |

## 5. Updating

Download the folder of the new version and, from that folder, run `bash installer/linux/installa_pmn.sh` again. Your projects and the databases already downloaded stay.

## 6. Uninstalling

Close the program, then delete:

```bash
rm -rf ~/.pmn
rm -f ~/.local/bin/profilemetananni ~/.local/share/applications/profilemetananni.desktop
rm -rf ~/.config/ProfileMetaNanni
```

Then delete the program folder (for example `~/profilemetananni`). Your projects stay in Documents, in the `ProfileMetaNanni` folder: delete it only if you no longer need the results.
