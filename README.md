# ProfileMetaNanni 1.3

**New in 1.3 / Novità della 1.3**

| English | Italiano |
|---|---|
| **Now also for Linux (Ubuntu 24.04)**, with one installation command. | **Ora anche per Linux (Ubuntu 24.04)**, con un solo comando di installazione. |
| **Faster: a whole analysis takes 34 % less time** than with version 1.2 (22.1 minutes instead of 33.5; the Kraken step 62 % less). | **Più veloce: un'analisi intera dura il 34 % in meno** rispetto alla versione 1.2 (22,1 minuti invece di 33,5; il passo di Kraken il 62 % in meno). |
| **8 GB of RAM are enough** (they were 16). | **Bastano 8 GB di RAM** (erano 16). |
| **Same results**: all the output files are byte-identical to those of version 1.2. | **Stessi risultati**: tutti i file in uscita sono identici al byte a quelli della versione 1.2. |

Measured on the same computer limited to 4 processors and 8 GB, on a whole salami sample (public run SRR4875279, 3.24 million read pairs). / Misurato sullo stesso computer limitato a 4 processori e 8 GB, su un salame intero (corsa pubblica SRR4875279, 3,24 milioni di coppie di read).

## Download / Scarica

| | English | Italiano |
|---|---|---|
| **Ubuntu 24.04** | [Download version 1.3](https://github.com/GiampieroFederici/profilemetananni/archive/refs/heads/main.zip), extract it, then run `bash installer/linux/installa_pmn.sh` in the folder. [Ubuntu guide](docs/guida_ubuntu_EN.md). | [Scarica la versione 1.3](https://github.com/GiampieroFederici/profilemetananni/archive/refs/heads/main.zip), estraila, poi lancia `bash installer/linux/installa_pmn.sh` nella cartella. [Guida per Ubuntu](docs/guida_ubuntu_IT.md). |
| **Windows 11** | [Download the zip](https://github.com/GiampieroFederici/profilemetananni/releases/download/v1.3.0/profilemetananni_v1.3.0.zip) (50 MB), extract it, double-click **Installa profilemetananni**. If you already have version 1.2: open the program and press **Cerca aggiornamenti** (check for updates). | [Scarica lo zip](https://github.com/GiampieroFederici/profilemetananni/releases/download/v1.3.0/profilemetananni_v1.3.0.zip) (50 MB), estrailo, doppio clic su **Installa profilemetananni**. Se hai già la versione 1.2: apri il programma e premi **Cerca aggiornamenti**. |

**You need** Windows 11 or Ubuntu 24.04 (not Mac), 8 GB of RAM, about 180 GB free on the internal disk, a few hours of download. Every window explained: [How to install](#how-to-install).

**First analysis:** [step-by-step guide on the example sample](docs/guida_analisi_esempio_EN.md) (also as [PDF](https://github.com/GiampieroFederici/profilemetananni/releases/download/v1.3.0/guida_analisi_esempio_EN.pdf)). The two example read files are in the [release](https://github.com/GiampieroFederici/profilemetananni/releases/tag/v1.3.0) too.

**Serve** Windows 11 o Ubuntu 24.04 (non Mac), 8 GB di RAM, circa 180 GB liberi sul disco interno, alcune ore di download. Ogni finestra spiegata: [Come si installa](#come-si-installa).

**Prima analisi:** [guida passo passo sul campione d'esempio](docs/guida_analisi_esempio_IT.md) (anche in [PDF](https://github.com/GiampieroFederici/profilemetananni/releases/download/v1.3.0/guida_analisi_esempio_IT.pdf)). I due file di read dell'esempio sono anche nella [Release](https://github.com/GiampieroFederici/profilemetananni/releases/tag/v1.3.0).

<p align="center">
  <img src="ProfileMetaNanni-Avatar.jpg" alt="ProfileMetaNanni" width="320">
</p>

**English** | [Italiano](#italiano)

**Metagenomics of cured meat products on an ordinary PC with 8 GB of RAM, with Windows or with Ubuntu.** Since version 1.1 also human faeces, skin, soil and grapevine (experimental). From the DNA sequencing reads of a sample to which taxa are present and in which proportion. It installs with a double click on Windows and with one command on Ubuntu, and it works with windows, without a terminal.

<p align="center">
  <img src="docs/vetrina/en_results.png" alt="ProfileMetaNanni, the Results page" width="720">
</p>

<p align="center">
  <img src="docs/vetrina/profilemetananni_video_en.gif" alt="ProfileMetaNanni in 43 seconds" width="720"><br>
  <i>The program in 43 seconds. <a href="docs/vetrina/profilemetananni_video_en.mp4">Video MP4</a> (11 MB, to download).</i>
</p>

## How to install

### On Ubuntu 24.04 (version 1.3)

1. [Download version 1.3](https://github.com/GiampieroFederici/profilemetananni/archive/refs/heads/main.zip) and extract it in a fixed place, for example `~/profilemetananni`: the program runs from there.
2. Open the terminal in that folder and run `bash installer/linux/installa_pmn.sh`. The script says what it will download and asks before starting; at the end it tests the engine on a small sample and writes VERDE (green).
3. Start the program from the applications menu (**ProfileMetaNanni**) or with the command `profilemetananni`.

You need 8 GB of RAM, about 180 GB free in your home folder and no administrator rights (except for system programs that Ubuntu may lack: the script names them). Everything else, with the measured times: [Ubuntu guide](docs/guida_ubuntu_EN.md).

### On Windows 11: [download the zip (50 MB)](https://github.com/GiampieroFederici/profilemetananni/releases/download/v1.3.0/profilemetananni_v1.3.0.zip)

Before you start, check that you have:

- a PC with **Windows 11** and **8 GB of RAM** (the installer checks that Windows shows at least 7.9 GB);
- about **180 GB free** on an internal disk (not a USB disk). Once installed, about 180 GB stay in use;
- an internet connection, better with a cable. About 139 GB of databases are downloaded, in pieces over several connections at once: with a 100 Mbit/s network it takes about 3 hours, with a 30 Mbit/s one about 10 hours. Meanwhile you can use the PC.

Then 3 steps:

1. Click the link above: the browser saves the zip in the **Downloads** folder.
2. Open the **Downloads** folder, right-click the zip and choose **Extract All**, then **Extract**.
3. In the extracted folder double-click **Installa profilemetananni**.

What you will see (in order) and how to answer. The installer speaks the language of Windows: Italian on an Italian Windows, English otherwise.

| Window | What to do |
|---|---|
| Windows security warning about the file (the program has no digital signature) | **Open** or **Run**. If "Windows protected your PC" appears: **More info**, then **Run anyway** |
| The installer needs a Windows component (WSL) | **OK**, then answer **Yes** to the Windows question |
| A restart is needed, restart now? | **Yes**. After the restart the installation starts again by itself, within about 2 minutes |
| profilemetananni will download about ... GB of databases, with the space and the estimated time | read it and answer **Yes** |
| Laptop lid question (only for long downloads) | keep the lid open, or answer **Yes** and the setting is put back at the end |
| Progress bar, with speed and time left | wait. The PC does not go to sleep by itself during the downloads. **Interrompi** (Stop) pauses the installation |
| Everything is ready: profilemetananni is installed and works | **OK**: the program opens |

If WSL is already on the PC, the WSL and restart windows do not appear. If the network drops, you press **Interrompi** or you switch the PC off, double-click **Installa profilemetananni** again: it resumes from where it stopped and does not download again the pieces already received. To update later, use the **Cerca aggiornamenti** (check for updates) button in the app: it asks before changing anything and keeps your projects.

<p align="center">
  <img src="docs/installazione/1_domanda_download.jpg" alt="Question before the download" width="420"><br>
  <i>The question before the download, on an Italian Windows (the numbers change from PC to PC: this picture comes from a reduced test).</i>
</p>

At the end you find **ProfileMetaNanni** on the desktop and in the Start menu. The green dot at the top, "Motore pronto" (engine ready), means you can work. The **Controlla il motore** (check the engine) button tests databases and programs on a small sample and answers VERDE (green).

<p align="center">
  <img src="docs/installazione/2_app_pronta.jpg" alt="ProfileMetaNanni ready" width="420">
  <img src="docs/installazione/3_motore_verde.jpg" alt="Engine check GREEN" width="420">
</p>

Full guide, with how to use the program (Italian): [User guide (PDF)](docs/Manuale_uso_ProfileMetaNanni.pdf).

## Why it exists

ProfileMetaNanni has one goal: **to democratise metagenomics**. It brings it to research centres and agri-food companies that cannot afford a computing cluster or technical staff with programming skills to run these tools.

This is why it installs with a double click on Windows, or with one command on Ubuntu, and runs with windows, without a terminal. It works on an ordinary PC with 8 GB of RAM.

## What it does

It starts from shotgun sequencing reads (`.fastq.gz` files from the sequencing lab, or SRR/ERR/DRR accessions from a public archive) and reports which taxa are present and in which proportion. It was built and validated on cured meat products; human faeces, skin, soil and grapevine (must, berry, leaf, root) are available as **experimental** sample types, with their limits explained in the app and in [`docs/ambienti.md`](docs/ambienti.md).

| Step | Tool |
|---|---|
| Read cleaning and quality control | fastp, FastQC, MultiQC |
| Host read removal | Bowtie 2 (`--very-sensitive-local`; a read pair is removed if either read aligns, as in KneadData 0.12.5) against pig (Sscrofa11.1), cattle (ARS-UCD1.2), sheep (ARS-UI_Ramb_v2.0), grapevine (T2T-PN40024) and human (GRCh38), none, or a host you add from an NCBI assembly accession or a FASTA file |
| Marker-gene taxonomic profiling | MetaPhlAn 4.2.4 with the `mpa_vJan25_CHOCOPhlAnSGB_202503` database |
| k-mer taxonomic profiling (prototype) | Kraken 2 + Bracken with PlusPF (full) or PlusPF-8 (quick screening) |
| Alpha diversity at equal depth | richness, Shannon, Simpson, for each method |
| Several samples | alpha and beta diversity (Aitchison, Bray-Curtis), tests chosen from the study design, PERMANOVA always with the dispersion test; groups filled in a table in the app ([`docs/metadati.md`](docs/metadati.md)) |
| Food safety scenarios (prototype) | FSSP 4.0 predictive microbiology models for *Listeria monocytogenes* |
| Report | HTML, PDF and Excel, with versions, parameters, limits and citations |

MetaPhlAn and Kraken are always kept separate: their numbers are never summed or averaged. The abundance threshold applies to Kraken only (0.1 % with the full database); MetaPhlAn is never filtered.

### MetaPhlAn on an ordinary PC: the "sliced" index

Standard MetaPhlAn with vJan25 needs about 33 GB of RAM. ProfileMetaNanni splits the vJan25 Bowtie 2 index into 6 taxonomic slices, aligns the reads to one slice at a time and recomputes the Bowtie 2 MAPQ on the merged result; then the unchanged MetaPhlAn 4.2.4 reads the alignment with `--input_type mapout`. On a test sample the species profile is identical to the standard one (27 species out of 27). In version 1.3 the memory peak of a whole analysis is about 5 GB (measured: 4.7 GB on the example sample, 5.0 GB on a whole salami sample), and when free memory is short the index is read from the disk instead of being loaded.

## Screenshots

<p align="center">
  <img src="docs/vetrina/en_my_projects.png" alt="My projects" width="420">
  <img src="docs/vetrina/en_choices.png" alt="Choices of the analysis" width="420"><br>
  <i>My projects, with the example sample ready. The choices of the analysis, with the estimated time.</i>
</p>
<p align="center">
  <img src="docs/vetrina/en_report_qc.png" alt="Report, quality check section" width="420">
  <img src="docs/vetrina/en_food_safety.png" alt="Food safety scenarios" width="420"><br>
  <i>The report with the quality check of the reads. Food safety scenarios (prototype, not for decisions).</i>
</p>

## Requirements

| What | Value |
|---|---|
| System | Windows 11 (tested) or Ubuntu 24.04 with an x86_64 processor (tested on a clean Ubuntu inside a virtual machine, not on a physical PC). Not available for macOS |
| RAM | 8 GB (they were 16 with version 1.2). On Windows the installer checks that the PC shows at least 7.9 GB; a PC sold as "8 GB" with integrated graphics can show less, and then the installer stops at once and says so. An analysis uses at most about 5 GB |
| Time | Measured with version 1.3 on Ubuntu, 4 processors and 8 GB: the example sample (0.2 million read pairs) 3 min 10 s; a whole salami sample (3.24 million pairs) 24 minutes, almost half of it removing pig DNA; a community with no host (ZymoBIOMICS standard, 7.9 million pairs) 2 h 34 min, most of it in Kraken. The same salami sample with version 1.2 on the same machine: 33.5 minutes instead of 22.1 (without the download of the reads). On a Windows 11 virtual machine with 8 GB the salami sample took 59 minutes |
| Disk | internal, about 180 GB free during installation (about 180 GB once installed). With much more free space the downloaded pieces are kept until they are checked, so an interruption never costs a new download; on Windows the file of the Linux disk then grows more than the data it holds (measured: 242 GB for 179 GB of data), and the installer says it before starting |
| Network | to download about 139 GB of databases (96.9 GB of public Kraken indexes + 42.1 GB of ProfileMetaNanni packages; the installer shows it as "about 130 GB" because it counts in binary units). Measured: 3 h 18 min at about 11 MB/s, 5 h 56 min at about 6 MB/s |

On Windows the installer enables WSL2 (it asks once for administrator permission and one restart) and creates a dedicated Linux space; on Ubuntu everything goes in `~/.pmn`. On both it installs the programs from lock files with pinned versions and the databases with MD5 checks.

## Status

Version 1.3. It runs on native Ubuntu, it needs 8 GB of RAM instead of 16, and it is faster, with the same results. Four changes, each one kept only because the output files stayed byte-identical to those of version 1.2: the step that merges the six slices of MetaPhlAn uses a fixed amount of memory; when free memory is short Bowtie 2 reads its index from the disk instead of loading it; Kraken tells Linux that it reads its 110 GB table in scattered pieces, so Linux stops reading the neighbouring pieces that nobody needs; the reduced MetaPhlAn database is downloaded ready-made instead of being built on the PC.

| Whole salami sample (SRR4875279), 4 processors, same machine | Version 1.3 | Version 1.2 | Time saved |
|---|---|---|---|
| 8 GB of RAM + 2 GB of swap | 22.1 min | 33.5 min | 34 % |
| 6 GB of RAM, no swap | 23.7 min | 36.0 min | 34 % |
| 4 GB of RAM + 1 GB of swap | 27.2 min | 39.4 min | 31 % |
| Kraken step alone, 8 GB + 2 GB | 424 s | 1,106 s | 62 % |

In all three rows the 13 output files of the two versions have the same MD5. Times are without the download of the reads.

Limits of version 1.3, stated as they are. Ubuntu was tested on a clean Ubuntu 24.04 inside a virtual machine, not on a physical PC. Windows with 8 GB was tested on a clean Windows 11 virtual machine (installation GREEN in 3 h 28 min, whole sample from the app in 59 minutes, identical outputs): a real 8 GB PC is not tested yet. Times depend on the machine and on the line, so the installer gives the download time as a range (for example "from 2.2 to 3.1 hours"): a few seconds of measurement cannot tell how the line will be shared between the two download sources, and in the two installations measured from scratch the real time falls inside the range. The time of an analysis is estimated for a real Windows PC (example sample: about 6 minutes announced, 5 and a half measured); on the two virtual test machines the same analysis took 3 and 10 minutes.

Version 1.2. Host and human reads are removed as in KneadData 0.12.5 (Bowtie 2 `--very-sensitive-local`, a pair is removed if either read aligns), and MetaPhlAn computes the profile from a database reduced to the clades with reads: the profiles are byte-identical to a classic MetaPhlAn 4.2.4 run with the full database, and the memory peak of an analysis goes from 8.4 to 5.4 GB. Validated on simulated cured-meat communities with known truth (0.18 % of the true taxa read pairs removed by the host filter), on the ZymoBIOMICS D6300 standard (8 of 8 bacteria, no unexpected species above 0.1 % with MetaPhlAn or Kraken) and on real cured-meat samples compared with the previous version. Installation from scratch was tested on a clean Windows 11 virtual machine with the real downloads (Stop and resume, restart, the engine check GREEN, the example analysis); each correction found there was checked again on the same machine before this release. The full Kraken index does not fit on the test machine's disk, so on the virtual machine Kraken was run with the quick index; the full index was used on a real PC. Projects analysed with 1.1 redo cleaning, host removal, MetaPhlAn and Kraken by themselves, because the method changed.

| Validation | Result |
|---|---|
| App versus command line, same sample | byte-identical |
| Version 1.3 versus 1.2, same samples, 8, 6 and 4 GB of RAM | 13 output files out of 13 byte-identical, every time |
| ZymoBIOMICS D6300 with version 1.3 | 11 comparisons out of 11 identical to version 1.2 |
| ZymoBIOMICS D6300 control community | MetaPhlAn 8 expected species out of 8, 0 extra species, Bray-Curtis 0.068 |
| Simulated cured-meat communities (12) | MetaPhlAn 0 false species in 12 out of 12; sensitivity criterion met in 4 out of 12, because rare taxa with few reads are lost (limit declared in the report) |
| Kraken calibration (confidence 0.5 + 0.1 % threshold) | F1 1.00 on the control community |
| FSSP models rewritten in Python | 382 cases out of 382 equal to the original program |

## Documents

- First analysis, step by step, on the example sample: [`docs/guida_analisi_esempio_EN.md`](docs/guida_analisi_esempio_EN.md)
- Installation on Ubuntu, with measured times and memory: [`docs/guida_ubuntu_EN.md`](docs/guida_ubuntu_EN.md)
- User guide (Italian): [`docs/Manuale_uso_ProfileMetaNanni.pdf`](docs/Manuale_uso_ProfileMetaNanni.pdf)
- App and engine contract: [`docs/contratto_motore.md`](docs/contratto_motore.md)
- Installer: [`installer/LEGGIMI.md`](installer/LEGGIMI.md)

## How to cite

If you use the results, cite the tools and databases you used: MetaPhlAn 4 (Blanco-Míguez et al. 2023, *Nat Biotechnol* 41:1633-1644), Kraken 2 (Wood et al. 2019, *Genome Biol*), Bracken (Lu et al. 2017, *PeerJ Comput Sci*), Bowtie 2 (Langmead and Salzberg 2012, *Nat Methods* 9:357-359), fastp (Chen et al. 2018, *Bioinformatics*), FSSP (Mejlholm and Dalgaard 2009, *J Food Prot* 72:2132-2143) and the host genomes. The full list with DOIs is in the "Come citare" page of the app and at the end of every report.

The recommended Kraken settings come from the literature and from our calibration on simulated cured-meat communities and on the Zymo mock. The 0.1 % abundance threshold follows Portik, Brown and Pierce-Ward 2022 (*BMC Bioinformatics* 23:541): with Kraken 2, Bracken and PlusPF it cut the false species from hundreds to fewer than 15. They compute it on the total reads; ProfileMetaNanni computes it on the reads that Bracken assigns to a species. Confidence 0.5 is in line with Galanis et al. 2022 (*Mol Ecol Resour* 22:2506-2523). Lower thresholds, such as 0.001 %, are meant for very complex communities like soil (Edwin et al. 2024, *Environ Microbiome* 19:19).

## Licence

MIT (see `LICENSE`).

---

<a name="italiano"></a>

[English](#profilemetananni-13) | **Italiano**

**La metagenomica dei salumi su un normale PC con 8 GB di RAM, con Windows o con Ubuntu.** Dalla versione 1.1 anche feci umane, cute, suolo e vite (sperimentale). Dalle read di sequenziamento del DNA di un campione a quali taxa ci sono e in che proporzione. Si installa con un doppio clic su Windows e con un comando su Ubuntu, e si usa con le finestre, senza terminale.

<p align="center">
  <img src="docs/vetrina/profilemetananni_video_en.gif" alt="ProfileMetaNanni in 43 secondi" width="720"><br>
  <i>Il programma in 43 secondi (in inglese). <a href="docs/vetrina/profilemetananni_video_en.mp4">Video MP4</a> (11 MB, da scaricare).</i>
</p>

## Come si installa

### Su Ubuntu 24.04 (versione 1.3)

1. [Scarica la versione 1.3](https://github.com/GiampieroFederici/profilemetananni/archive/refs/heads/main.zip) ed estraila in un posto fisso, per esempio `~/profilemetananni`: il programma gira da lì.
2. Apri il terminale in quella cartella e lancia `bash installer/linux/installa_pmn.sh`. Lo script dice che cosa scaricherà e chiede prima di partire; alla fine prova il motore su un piccolo campione e scrive VERDE.
3. Avvia il programma dal menu delle applicazioni (**ProfileMetaNanni**) o con il comando `profilemetananni`.

Servono 8 GB di RAM, circa 180 GB liberi nella tua cartella personale e nessun permesso di amministratore (tranne per i programmi di sistema che a Ubuntu possono mancare: lo script dice quali). Tutto il resto, con i tempi misurati: [guida per Ubuntu](docs/guida_ubuntu_IT.md).

### Su Windows 11: [scarica lo zip (50 MB)](https://github.com/GiampieroFederici/profilemetananni/releases/download/v1.3.0/profilemetananni_v1.3.0.zip)

Prima di iniziare controlla di avere:

- un PC con **Windows 11** e **8 GB di RAM** (l'installatore controlla che Windows ne mostri almeno 7,9);
- circa **180 GB liberi** su un disco interno (non un disco USB). A installazione finita ne restano occupati circa 180;
- una connessione a internet, meglio col cavo. Si scaricano circa 139 GB di database, a pezzi su più connessioni insieme: con una rete da 100 Mbit/s servono circa 3 ore, con una da 30 Mbit/s circa 10 ore. Intanto puoi usare il PC.

Poi 3 passi:

1. Fai clic sul link qui sopra: il browser salva lo zip nella cartella **Download**.
2. Apri la cartella **Download**, fai clic destro sullo zip e scegli **Estrai tutto**, poi **Estrai**.
3. Nella cartella estratta fai doppio clic su **Installa profilemetananni**.

Che cosa vedrai (in ordine) e che cosa rispondere:

| Finestra | Che cosa fare |
|---|---|
| Avviso di sicurezza di Windows sul file (il programma non ha una firma digitale) | **Apri** o **Esegui**. Se compare "Windows ha protetto il PC": **Ulteriori informazioni**, poi **Esegui comunque** |
| "Per funzionare, profilemetananni ha bisogno di un componente di Windows (WSL)" | **OK**, poi alla domanda di Windows rispondi **Sì** |
| "Serve un riavvio del computer... Riavvio adesso?" | **Sì**. Dopo il riavvio l'installazione riparte da sola, entro circa 2 minuti |
| "profilemetananni scaricherà circa ... GB di database", con lo spazio e il tempo stimato | leggi e rispondi **Sì** |
| Domanda sul coperchio del portatile (solo per scarichi lunghi) | tieni il coperchio aperto, oppure rispondi **Sì** e alla fine l'impostazione torna com'era |
| Barra di avanzamento, con velocità e tempo che manca | aspetta. Il PC non va in sospensione da solo durante i download. **Interrompi** mette in pausa l'installazione |
| "Tutto pronto: profilemetananni è installato e funziona" | **OK**: si apre il programma |

Se WSL c'è già sul PC, le finestre di WSL e del riavvio non compaiono. Se la rete cade, premi **Interrompi** o spegni il PC, fai di nuovo doppio clic su **Installa profilemetananni**: riprende da dove era arrivata e non riscarica i pezzi già arrivati. Per aggiornare in seguito c'è il pulsante **Cerca aggiornamenti** nell'app: chiede prima di cambiare qualcosa e conserva i tuoi progetti.

<p align="center">
  <img src="docs/installazione/1_domanda_download.jpg" alt="Domanda prima del download" width="420"><br>
  <i>La domanda prima del download (i numeri cambiano da PC a PC: questa foto viene da una prova ridotta).</i>
</p>

Alla fine trovi **ProfileMetaNanni** sul desktop e nel menu Start. Il pallino verde in alto, "Motore pronto", vuol dire che puoi lavorare. Il pulsante **Controlla il motore** prova database e programmi su un piccolo campione e risponde VERDE.

<p align="center">
  <img src="docs/installazione/2_app_pronta.jpg" alt="ProfileMetaNanni pronto" width="420">
  <img src="docs/installazione/3_motore_verde.jpg" alt="Controllo del motore VERDE" width="420">
</p>

Guida completa, con l'uso del programma: [Manuale d'uso (PDF)](docs/Manuale_uso_ProfileMetaNanni.pdf).

## Perché esiste

ProfileMetaNanni ha un obiettivo: **democratizzare la metagenomica**. Vuole portarla nei centri di ricerca e nelle realtà produttive agroalimentari che non possono permettersi un cluster di calcolo né personale tecnico capace di programmare per far girare questi strumenti.

Per questo si installa con un doppio clic su Windows, o con un comando su Ubuntu, e si usa con le finestre, senza terminale. Gira su un normale PC da 8 GB di RAM.

## Che cosa fa

Parte dalle read di sequenziamento shotgun (file `.fastq.gz` del laboratorio, oppure codici SRR/ERR/DRR di un archivio pubblico) e dice quali taxa ci sono e in che proporzione. È stato costruito e validato sui salumi; feci umane, cute, suolo e vite (mosto, acino, foglia, radice) sono disponibili come tipi di campione **sperimentali**, con i limiti spiegati nell'app e in [`docs/ambienti.md`](docs/ambienti.md).

| Passo | Strumento |
|---|---|
| Pulizia e controllo qualità delle read | fastp, FastQC, MultiQC |
| Rimozione del DNA dell'ospite (host read removal) | Bowtie 2 (`--very-sensitive-local`; una coppia di read si toglie se anche una sola read si allinea, come in KneadData 0.12.5) su maiale (Sscrofa11.1), bovino (ARS-UCD1.2), pecora (ARS-UI_Ramb_v2.0), vite (T2T-PN40024) e uomo (GRCh38), nessuno, oppure un ospite che aggiungi tu con il codice di un assembly NCBI o un file FASTA |
| Profilo tassonomico con geni marcatori | MetaPhlAn 4.2.4 con il database `mpa_vJan25_CHOCOPhlAnSGB_202503` |
| Profilo tassonomico per k-mer (prototipo) | Kraken 2 + Bracken con PlusPF (completo) o PlusPF-8 (screening rapido) |
| Diversità alfa a profondità uguale | ricchezza, Shannon, Simpson, per ciascun metodo |
| Più campioni | diversità alfa e beta (Aitchison, Bray-Curtis), test scelti in base al disegno sperimentale, PERMANOVA sempre insieme al test della dispersione; gruppi compilati in una tabella nell'app ([`docs/metadati.md`](docs/metadati.md)) |
| Scenari di sicurezza alimentare (prototipo) | modelli di microbiologia predittiva di FSSP 4.0 per *Listeria monocytogenes* |
| Referto | HTML, PDF ed Excel, con versioni, parametri, limiti e citazioni |

MetaPhlAn e Kraken restano sempre separati: i loro numeri non si sommano e non si mediano. La soglia di abbondanza vale solo per Kraken (0,1 % col database completo); MetaPhlAn non viene mai filtrato.

### MetaPhlAn su un PC normale: l'indice "a fette"

MetaPhlAn standard con vJan25 chiede circa 33 GB di RAM. ProfileMetaNanni divide l'indice Bowtie 2 di vJan25 in 6 parti per tassonomia, allinea le read su una parte alla volta e ricalcola il MAPQ di Bowtie 2 sul risultato unito; poi MetaPhlAn 4.2.4, invariato, legge l'allineamento con `--input_type mapout`. Su un campione di prova il profilo di specie è identico a quello standard (27 specie su 27). Nella versione 1.3 il picco di memoria di un'analisi intera è di circa 5 GB (misurato: 4,7 GB sul campione d'esempio, 5,0 GB su un salame intero), e quando la memoria libera è poca l'indice viene letto dal disco invece di essere caricato.

## Schermate

<p align="center">
  <img src="docs/vetrina/en_my_projects.png" alt="I miei progetti" width="420">
  <img src="docs/vetrina/en_choices.png" alt="Scelte dell'analisi" width="420"><br>
  <i>I miei progetti, con il campione d'esempio pronto. Le scelte dell'analisi, con il tempo stimato (app in inglese; l'italiano è a un clic).</i>
</p>
<p align="center">
  <img src="docs/vetrina/en_report_qc.png" alt="Referto, controllo qualità" width="420">
  <img src="docs/vetrina/en_food_safety.png" alt="Scenari di sicurezza alimentare" width="420"><br>
  <i>Il referto con il controllo qualità delle read. Gli scenari di sicurezza alimentare (prototipo, non per decisioni).</i>
</p>

## Requisiti

| Cosa | Valore |
|---|---|
| Sistema | Windows 11 (provato) oppure Ubuntu 24.04 con processore x86_64 (provato su un Ubuntu pulito dentro una macchina virtuale, non su un PC fisico). Non disponibile per macOS |
| RAM | 8 GB (erano 16 con la versione 1.2). Su Windows l'installatore controlla che il PC ne mostri almeno 7,9; un PC venduto come "da 8 GB" con la grafica integrata può mostrarne meno, e allora l'installatore si ferma subito e lo dice. Un'analisi usa al massimo circa 5 GB |
| Tempo | Misurato con la versione 1.3 su Ubuntu, 4 processori e 8 GB: il campione d'esempio (0,2 milioni di coppie di read) 3 min 10 s; un salame intero (3,24 milioni di coppie) 24 minuti, quasi la metà per togliere il DNA del maiale; una comunità senza ospite (standard ZymoBIOMICS, 7,9 milioni di coppie) 2 h 34 min, quasi tutti in Kraken. Lo stesso salame con la versione 1.2 sulla stessa macchina: 33,5 minuti invece di 22,1 (senza lo scarico delle read). Su Windows 11 in una macchina virtuale con 8 GB il salame ha richiesto 59 minuti |
| Disco | interno, circa 180 GB liberi durante l'installazione (circa 180 GB a installazione finita). Con molto più spazio libero i pezzi scaricati restano fino al controllo, così un'interruzione non costa mai un nuovo scarico; su Windows il file del disco di Linux cresce allora più dei dati che contiene (misurato: 242 GB per 179 GB di dati), e l'installatore lo dice prima di partire |
| Rete | per scaricare circa 139 GB di database (96,9 GB di indici Kraken pubblici + 42,1 GB di pacchetti ProfileMetaNanni; l'installatore li mostra come "circa 130 GB" perché conta in unità binarie). Misurato: 3 h 18 min a circa 11 MB/s, 5 h 56 min a circa 6 MB/s |

Su Windows l'installatore attiva WSL2 (una volta chiede il permesso di amministratore e un riavvio) e crea uno spazio Linux dedicato; su Ubuntu tutto va in `~/.pmn`. In tutti e due i casi installa i programmi da file di blocco con versioni fisse e i database con controllo MD5.

## Stato

Versione 1.3. Gira su Ubuntu nativo, chiede 8 GB di RAM invece di 16 ed è più veloce, con gli stessi risultati. Quattro modifiche, ognuna tenuta solo perché i file in uscita sono rimasti identici al byte a quelli della versione 1.2: il passo che unisce le sei fette di MetaPhlAn usa una quantità fissa di memoria; quando la memoria libera è poca Bowtie 2 legge il suo indice dal disco invece di caricarlo; Kraken dice a Linux che legge la sua tabella da 110 GB a pezzi sparsi, così Linux smette di leggere i pezzi vicini che non servono a nessuno; il database ridotto di MetaPhlAn si scarica già pronto invece di essere costruito sul PC.

| Salame intero (SRR4875279), 4 processori, stessa macchina | Versione 1.3 | Versione 1.2 | Tempo in meno |
|---|---|---|---|
| 8 GB di RAM + 2 GB di swap | 22,1 min | 33,5 min | 34 % |
| 6 GB di RAM, senza swap | 23,7 min | 36,0 min | 34 % |
| 4 GB di RAM + 1 GB di swap | 27,2 min | 39,4 min | 31 % |
| Solo il passo di Kraken, 8 GB + 2 GB | 424 s | 1.106 s | 62 % |

In tutte e tre le righe i 13 file in uscita delle due versioni hanno lo stesso MD5. I tempi sono senza lo scarico delle read.

Limiti della versione 1.3, detti come sono. Ubuntu è stato provato su un Ubuntu 24.04 pulito dentro una macchina virtuale, non su un PC fisico. Windows con 8 GB è stato provato su Windows 11 pulito in una macchina virtuale (installazione VERDE in 3 h 28 min, campione intero dall'app in 59 minuti, uscite identiche): un PC vero da 8 GB non è ancora provato. I tempi dipendono dalla macchina e dalla linea, quindi l'installatore dà il tempo dello scarico come intervallo (per esempio "da 2,2 ore a 3,1 ore"): pochi secondi di misura non dicono come la linea si dividerà fra le due sorgenti dello scarico, e nelle due installazioni da zero misurate il tempo vero cade dentro l'intervallo. Il tempo di un'analisi è stimato per un PC Windows vero (campione d'esempio: circa 6 minuti annunciati, 5 e mezzo misurati); sulle due macchine virtuali di prova la stessa analisi ha richiesto 3 e 10 minuti.

Versione 1.2. Le read dell'ospite e dell'uomo si tolgono come in KneadData 0.12.5 (Bowtie 2 `--very-sensitive-local`, una coppia si toglie se anche una sola read si allinea), e MetaPhlAn calcola il profilo da un database ridotto ai clade che hanno read: i profili sono identici al byte a quelli di MetaPhlAn 4.2.4 classico con il database intero, e il picco di memoria di un'analisi scende da 8,4 a 5,4 GB. Validata su comunità simulate di salume a composizione nota (lo 0,18 % delle coppie di read dei taxa veri tolto dal filtro dell'ospite), sullo standard ZymoBIOMICS D6300 (8 batteri su 8, nessuna specie inattesa sopra lo 0,1 % con MetaPhlAn e con Kraken) e su campioni veri di salume confrontati con la versione precedente. L'installazione da zero è stata provata su Windows 11 pulito in una macchina virtuale con gli scarichi veri (Interrompi e ripresa, riavvio, controllo del motore VERDE, analisi d'esempio); ogni correzione trovata lì è stata riprovata sulla stessa macchina prima di questa Release. L'indice Kraken completo non sta sul disco della macchina di prova: lì Kraken ha usato l'indice rapido; l'indice completo è stato usato su un PC vero. I progetti analizzati con la 1.1 rifanno da soli pulizia, rimozione dell'ospite, MetaPhlAn e Kraken, perché il metodo è cambiato.

| Validazione | Risultato |
|---|---|
| App contro riga di comando, stesso campione | identici al byte |
| Versione 1.3 contro 1.2, stessi campioni, 8, 6 e 4 GB di RAM | 13 file in uscita su 13 identici al byte, ogni volta |
| ZymoBIOMICS D6300 con la versione 1.3 | 11 confronti su 11 identici alla versione 1.2 |
| Comunità di controllo ZymoBIOMICS D6300 | MetaPhlAn 8 specie attese su 8, 0 specie in più, Bray-Curtis 0,068 |
| Comunità simulate di salume (12) | MetaPhlAn 0 specie false in 12 su 12; criterio di sensibilità superato in 4 su 12, perché i taxa rari con poche read si perdono (limite dichiarato nel referto) |
| Taratura di Kraken (confidence 0,5 + soglia 0,1 %) | F1 1,00 sulla comunità di controllo |
| Modelli FSSP riscritti in Python | 382 casi su 382 uguali al programma originale |

## Documenti

- Prima analisi, passo passo, sul campione d'esempio: [`docs/guida_analisi_esempio_IT.md`](docs/guida_analisi_esempio_IT.md)
- Installazione su Ubuntu, con tempi e memoria misurati: [`docs/guida_ubuntu_IT.md`](docs/guida_ubuntu_IT.md)
- Guida per l'utente: [`docs/Manuale_uso_ProfileMetaNanni.pdf`](docs/Manuale_uso_ProfileMetaNanni.pdf)
- Contratto fra app e motore: [`docs/contratto_motore.md`](docs/contratto_motore.md)
- Installatore: [`installer/LEGGIMI.md`](installer/LEGGIMI.md)

## Come citare

Se usi i risultati, cita gli strumenti e i database usati: MetaPhlAn 4 (Blanco-Míguez et al. 2023, *Nat Biotechnol* 41:1633-1644), Kraken 2 (Wood et al. 2019, *Genome Biol*), Bracken (Lu et al. 2017, *PeerJ Comput Sci*), Bowtie 2 (Langmead e Salzberg 2012, *Nat Methods* 9:357-359), fastp (Chen et al. 2018, *Bioinformatics*), FSSP (Mejlholm e Dalgaard 2009, *J Food Prot* 72:2132-2143) e i genomi dell'ospite. L'elenco completo, con i DOI, è nella pagina "Come citare" dell'app e in fondo a ogni referto.

Le impostazioni consigliate di Kraken vengono dalla letteratura e dalla nostra taratura su comunità simulate di salume e sul campione Zymo. La soglia di abbondanza 0,1 % segue Portik, Brown e Pierce-Ward 2022 (*BMC Bioinformatics* 23:541): con Kraken 2, Bracken e PlusPF ha portato le specie false da centinaia a meno di 15. Loro la calcolano sulle read totali; ProfileMetaNanni sulle read che Bracken assegna a una specie. La confidence 0,5 è in accordo con Galanis et al. 2022 (*Mol Ecol Resour* 22:2506-2523). Soglie più basse, come 0,001 %, servono per comunità molto complesse come il suolo (Edwin et al. 2024, *Environ Microbiome* 19:19).

## Licenza

MIT (vedi `LICENSE`).
