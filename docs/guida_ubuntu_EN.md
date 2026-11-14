# ProfileMetaNanni on Ubuntu

This guide installs ProfileMetaNanni on a computer with Ubuntu: the engine and the app with its windows, in the same Linux. No administrator rights are needed, except for the system programs that Ubuntu does not already have (the script says which ones).

Italian version: [guida_ubuntu_IT.md](guida_ubuntu_IT.md).

## 1. What you need

| | |
|---|---|
| System | Ubuntu 24.04 or 26.04, x86_64 processor (64 bit). Version 24.04 was tested on a clean Ubuntu inside a virtual machine, version 26.04 on a physical PC (LXQt desktop on X11, system in Italian) |
| Memory | 8 GB or more. The script stops before downloading if memory and swap together are less than 4.75 GB |
| Disk | about 180 GB free on an internal disk, in your home folder. If you have much more free space, the script keeps the downloaded pieces until they are checked, and says so before starting: on the physical test PC, with 416 GB free, it announced up to about 257 GB in use during the download. Then it deletes the pieces: at the end about 170 GB stay in use |
| Network | to download about 130 GB of databases. Measured: 3 h 23 min on a line at about 10 MB/s, 5 h 56 min on a line at about 6 MB/s |

## 2. Installing: one line in the Terminal

1. Open the Terminal, paste this line and press Enter:

   ```bash
   wget -nv -O- https://github.com/GiampieroFederici/profilemetananni/releases/latest/download/installa_profilemetananni_linux.sh | bash
   ```

   The line takes a small script from the latest release of ProfileMetaNanni on GitHub. The script downloads the Linux package (1 MB), checks that it is the published one (SHA-256 checksum), extracts it in a temporary folder and starts the installation. It never asks for the administrator password.

   If the Terminal answers that `wget` is not found, use this line: it does the same with `curl`.

   ```bash
   curl -fsSL https://github.com/GiampieroFederici/profilemetananni/releases/latest/download/installa_profilemetananni_linux.sh | bash
   ```

2. Answer the question of the script and wait for the end (section 3 says what you will see).
3. Start the program from the applications menu (entry **ProfileMetaNanni**) or from the terminal:

   ```bash
   profilemetananni
   ```

   If the terminal does not find the command, log out and log in again, or use the full path: `~/.local/bin/profilemetananni`.

### If you prefer not to paste a command

1. Download the Linux package from the release page: [profilemetananni_v1.3.0_linux.tar.gz](https://github.com/GiampieroFederici/profilemetananni/releases/download/v1.3.0/profilemetananni_v1.3.0_linux.tar.gz) (1 MB). You can also copy it from another computer.
2. Extract it with the file manager (right-click on the file). The folder can stay where it is, with any name.
3. Open the Terminal in the extracted folder `profilemetananni` and run:

   ```bash
   bash installer/linux/installa_pmn.sh
   ```

In both cases the program is copied to `~/.pmn/programma` and runs from there. The file you downloaded and the extracted folder are not needed after the installation: you can delete them.

## 3. What happens during the installation

- If a system program is missing (for example `curl` on a new Ubuntu), the script stops and shows a line `sudo apt install ...`. Run it, then start the installation again in the same way.
- Before downloading, the script says how much it downloads, how much space is needed and how long it will take. Then it asks `Shall I go ahead with the installation? (y/n)`: answer `y` (yes). If you started from the extracted folder, the option `--si` skips the question.
- The download takes hours. One progress line is updated in place, and the computer stays free for other work. If the network drops, the script tries again by itself: on the physical test PC it happened 6 times in 3 h 23 min, and nothing had to be done.
- You can stop with Ctrl+C. The script answers with one line, `Installation interrupted`. To continue, start the installation again in the same way: it resumes from where it stopped, without downloading again what has already arrived.
- At the end it runs a test on a small sample and writes `GREEN` if the engine works. Then it prepares the app and writes the command and the menu entry.
- If system libraries for the windows are missing, the script says so with another line `sudo apt install ...`: run it before starting the program.
- You can start the installation again whenever you want: what is already there is not done again. The engine repeats only the final test (a few minutes).

## 4. Where things are

| What | Where |
|---|---|
| Projects and results | Documents folder (it can be called `Documents` or `Documenti`), in `ProfileMetaNanni/<project name>/risultati` (the report is in `risultati/referto`) |
| Working files of an analysis | `ProfileMetaNanni/<project name>/pmn_work` |
| Program | `~/.pmn/programma` |
| Logs of the engine and of the installation | `~/.pmn/log` |
| Engine, databases and program environments | `~/.pmn` |
| Command and menu entry | `~/.local/bin/profilemetananni` and `~/.local/share/applications/profilemetananni.desktop` |
| App settings (language, last folder) | `~/.config/ProfileMetaNanni` |
| Settings of sra-tools, the program that downloads the reads from the public archives | `~/.ncbi` |

## 5. Updating

Paste the line of section 2 again: it downloads the package of the latest release and replaces the program. Or download the new Linux package and run `bash installer/linux/installa_pmn.sh` from its folder. Your projects and the databases already downloaded stay; the final test is repeated.

On Ubuntu the **Check for updates** button of the app tells you when a new version exists; the update itself is done as written here.

## 6. Uninstalling

Close the program, then delete:

```bash
rm -rf ~/.pmn
rm -f ~/.local/bin/profilemetananni ~/.local/share/applications/profilemetananni.desktop
rm -rf ~/.config/ProfileMetaNanni
```

The first line removes the program, the engine, the databases and the logs (about 170 GB). If you do not use sra-tools for other work, delete its settings too:

```bash
rm -rf ~/.ncbi
```

Your projects stay in Documents, in the `ProfileMetaNanni` folder: delete it only if you no longer need the results.

## 7. If something does not work

- **"The environment ... does not match the expected versions."** Do not start the installation again: it would stop at the same point. The message names a log file in `~/.pmn/log`: send us that file by opening an issue on the [project page](https://github.com/GiampieroFederici/profilemetananni/issues).
- **The engine check in the app is red.** The dot at the top becomes red, "Engine to be checked", and the page names a log file. If the page says that the engine is installed, send us that file before reinstalling: the button **Open the log** shows it.
- **A sample published a few days ago does not start.** The app says that the sample exists in the archives (ENA and NCBI) but its reads are not there yet. The code is correct: try again in a few days.
- **You stopped an analysis.** Press **Start the analysis** again in the same project: the steps already finished are not done again.

## 8. Measured times and memory

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

Measured on 12 November 2026 with version 1.3.0, on a physical laptop with Ubuntu 26.04 (LXQt desktop on X11, system in Italian): Intel Core i7-1165G7 processor (4 cores, 8 threads), 15.3 GB of memory, 0.5 GB of swap, NVMe disk.

| What | Time | Memory used, maximum |
|---|---|---|
| Database download (128 GB, line at about 10 MB/s) | 3 h 23 min | |
| Final test | 72 to 94 s | 4.7 GB |
| Preparing the app | about 1 min | |
| Opening the app up to the first page | 0.8 s | |
| Analysis of the example sample, started from the app | 3 min 50 s | 5.6 GB |

On this PC the results of the example sample were the same as in the [guide of the example analysis](guida_analisi_esempio_EN.md).
