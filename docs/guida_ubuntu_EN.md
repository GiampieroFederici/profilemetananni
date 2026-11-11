# ProfileMetaNanni on Ubuntu

This guide installs ProfileMetaNanni on a computer with Ubuntu: the engine and the app with its windows, in the same Linux. No administrator rights are needed, except for the system programs that Ubuntu does not already have (the script says which ones).

Italian version: [guida_ubuntu_IT.md](guida_ubuntu_IT.md).

## 1. What you need

| | |
|---|---|
| System | Ubuntu 24.04, x86_64 processor (64 bit) |
| Memory | 8 GB or more. The script stops before downloading if memory and swap together are less than 4.75 GB |
| Disk | about 180 GB free on an internal disk, in your home folder |
| Network | to download about 130 GB of databases (about 6 hours on a 6 MB/s line) |

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

## 7. Measured times and memory

Measured on 10 November 2026 with version 1.3.0, on Ubuntu 24.04 in a virtual machine with 4 processors, 8 GB of memory and 2 GB of swap, SSD disk. The whole sample is the public run SRR4875279 (3.24 million read pairs from a salami).

| What | Time | Memory used, maximum |
|---|---|---|
| Installation from scratch, in total | 6 h 2 min | 5.2 GB |
| of which database download (line at about 6 MB/s) | 5 h 56 min | 0.8 GB |
| of which final test | 72 s | 5.2 GB |
| Opening the app up to the first page | about 3 s | |
| Analysis of the example sample (200,000 pairs) | 3 min 10 s | 4.7 GB |
| The same analysis started from the app | 3 min 20 s | 4.7 GB |
| Analysis of the whole sample, from the run code to the report | 24 min | 5.0 GB |
| The same sample with 6 GB of memory, no swap | 26 min | 4.9 GB |
| The same sample with 4 GB of memory and 1 GB of swap | 29 min 30 s | swap 90 % used |
| Community with no host (public run ERR2984773, 7.9 million pairs) | 2 h 34 min | 4.9 GB |

The installation time is almost all download and depends on the line. During the download the computer stays free for other work. With 4 GB of memory the analysis finishes and gives the same results, but with little margin: 8 GB is better. Kraken time grows with the reads left after host removal: 7 minutes for the whole salami, 99 minutes for the community with no host.
