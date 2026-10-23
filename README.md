# ProfileMetaNanni 1.0

<p align="center">
  <img src="ProfileMetaNanni-Avatar.jpg" alt="ProfileMetaNanni" width="320">
</p>

**Italiano** | [English](#english)

## Perché esiste

ProfileMetaNanni ha un obiettivo: **democratizzare la metagenomica**. Vuole portarla nei centri di ricerca e nelle realtà produttive agroalimentari che non possono permettersi un cluster di calcolo né personale tecnico capace di programmare per far girare questi strumenti.

Per questo è un programma per Windows che si installa con un doppio clic e si usa con le finestre, senza terminale. Gira su un normale PC da 16 GB di RAM.

## Che cosa fa

Parte dalle read di sequenziamento shotgun di un salume (file `.fastq.gz` del laboratorio, oppure codici SRR/ERR/DRR di un archivio pubblico) e dice quali taxa ci sono e in che proporzione.

| Passo | Strumento |
|---|---|
| Pulizia e controllo qualità delle read | fastp, FastQC, MultiQC |
| Rimozione del DNA dell'ospite (host read removal) | Bowtie 2 su maiale (Sscrofa11.1), bovino (ARS-UCD1.2), pecora (ARS-UI_Ramb_v2.0) e uomo (GRCh38) |
| Profilo tassonomico con geni marcatori | MetaPhlAn 4.2.4 con il database `mpa_vJan25_CHOCOPhlAnSGB_202503` |
| Profilo tassonomico per k-mer (prototipo) | Kraken 2 + Bracken con PlusPF (completo) o PlusPF-8 (screening rapido) |
| Diversità alfa a profondità uguale | ricchezza, Shannon, Simpson, per ciascun metodo |
| Scenari di sicurezza alimentare (prototipo) | modelli di microbiologia predittiva di FSSP 4.0 (DTU Food) per *Listeria monocytogenes* |
| Referto | HTML, PDF ed Excel, con versioni, parametri, limiti e citazioni |

MetaPhlAn e Kraken restano sempre separati: i loro numeri non si sommano e non si mediano. La soglia di abbondanza vale solo per Kraken (0,1 % col database completo); MetaPhlAn non viene mai filtrato.

### MetaPhlAn su 16 GB: l'indice "a fette"

MetaPhlAn standard con vJan25 chiede circa 33 GB di RAM. ProfileMetaNanni divide l'indice Bowtie 2 di vJan25 in 6 parti per tassonomia, allinea le read su una parte alla volta e ricalcola il MAPQ di Bowtie 2 sul risultato unito; poi MetaPhlAn 4.2.4, invariato, legge l'allineamento con `--input_type mapout`. Su un campione di prova il profilo di specie è identico a quello standard (27 specie su 27) con un picco di RAM di 8,2 GB.

## Requisiti

| Cosa | Valore |
|---|---|
| Sistema | Windows 11 (provato) |
| RAM | 16 GB |
| Disco | interno, circa 300 GB liberi durante l'installazione (circa 170-190 GB a installazione finita) |
| Rete | per scaricare circa 139 GB di database (96,9 GB di indici Kraken pubblici + 41,8 GB di pacchetti ProfileMetaNanni) |

L'installatore attiva WSL2 (una volta chiede il permesso di amministratore e un riavvio), crea uno spazio Linux dedicato e ci installa i programmi da file di blocco con versioni fisse e i database con controllo MD5.

## Stato

Versione 1.0 in prova. L'installazione da zero è stata provata su Windows 11 pulito in una macchina virtuale: 14 interazioni dell'utente, nessun terminale, nessun aiuto. I pacchetti di database di ProfileMetaNanni (fette di MetaPhlAn, indici dell'ospite, campione d'esempio) non sono ancora pubblicati: per ora l'installazione completa funziona solo con uno specchio locale.

| Validazione | Risultato |
|---|---|
| App contro riga di comando, stesso campione | identici al byte |
| Comunità di controllo ZymoBIOMICS D6300 | MetaPhlAn 8 specie attese su 8, 0 specie in più, Bray-Curtis 0,068 |
| Comunità simulate di salume (12) | MetaPhlAn 0 specie false in 12 su 12; criterio di sensibilità superato in 4 su 12, perché i taxa rari con poche read si perdono (limite dichiarato nel referto) |
| Taratura di Kraken (confidence 0,5 + soglia 0,1 %) | F1 1,00 sulla comunità di controllo |
| Modelli FSSP riscritti in Python | 382 casi su 382 uguali al programma originale |

## Documenti

- Guida per l'utente: [`docs/Manuale_uso_ProfileMetaNanni.pdf`](docs/Manuale_uso_ProfileMetaNanni.pdf)
- Contratto fra app e motore: [`docs/contratto_motore.md`](docs/contratto_motore.md)
- Installatore: [`installer/LEGGIMI.md`](installer/LEGGIMI.md)

## Come citare

Se usi i risultati, cita gli strumenti e i database usati: MetaPhlAn 4 (Blanco-Míguez et al. 2023, *Nat Biotechnol* 41:1633-1644), Kraken 2 (Wood et al. 2019, *Genome Biol*), Bracken (Lu et al. 2017, *PeerJ Comput Sci*), Bowtie 2 (Langmead e Salzberg 2012, *Nat Methods* 9:357-359), fastp (Chen et al. 2018, *Bioinformatics*), FSSP (Mejlholm e Dalgaard 2009, *J Food Prot* 72:2132-2143) e i genomi dell'ospite. L'elenco completo, con i DOI, è nella pagina "Come citare" dell'app e in fondo a ogni referto.

## Licenza

MIT (vedi `LICENSE`).

---

<a name="english"></a>

[Italiano](#profilemetananni-10) | **English**

## Why it exists

ProfileMetaNanni has one goal: **to democratise metagenomics**. It brings it to research centres and agri-food companies that cannot afford a computing cluster or technical staff with programming skills to run these tools.

This is why it is a Windows program that installs with a double click and runs with windows, without a terminal. It works on an ordinary PC with 16 GB of RAM.

## What it does

It starts from shotgun sequencing reads of a cured meat product (`.fastq.gz` files from the sequencing lab, or SRR/ERR/DRR accessions from a public archive) and reports which taxa are present and in which proportion.

| Step | Tool |
|---|---|
| Read cleaning and quality control | fastp, FastQC, MultiQC |
| Host read removal | Bowtie 2 against pig (Sscrofa11.1), cattle (ARS-UCD1.2), sheep (ARS-UI_Ramb_v2.0) and human (GRCh38) |
| Marker-gene taxonomic profiling | MetaPhlAn 4.2.4 with the `mpa_vJan25_CHOCOPhlAnSGB_202503` database |
| k-mer taxonomic profiling (prototype) | Kraken 2 + Bracken with PlusPF (full) or PlusPF-8 (quick screening) |
| Alpha diversity at equal depth | richness, Shannon, Simpson, for each method |
| Food safety scenarios (prototype) | FSSP 4.0 predictive microbiology models (DTU Food) for *Listeria monocytogenes* |
| Report | HTML, PDF and Excel, with versions, parameters, limits and citations |

MetaPhlAn and Kraken are always kept separate: their numbers are never summed or averaged. The abundance threshold applies to Kraken only (0.1 % with the full database); MetaPhlAn is never filtered.

### MetaPhlAn on 16 GB: the "sliced" index

Standard MetaPhlAn with vJan25 needs about 33 GB of RAM. ProfileMetaNanni splits the vJan25 Bowtie 2 index into 6 taxonomic slices, aligns the reads to one slice at a time and recomputes the Bowtie 2 MAPQ on the merged result; then the unchanged MetaPhlAn 4.2.4 reads the alignment with `--input_type mapout`. On a test sample the species profile is identical to the standard one (27 species out of 27) with a RAM peak of 8.2 GB.

## Requirements

| What | Value |
|---|---|
| System | Windows 11 (tested) |
| RAM | 16 GB |
| Disk | internal, about 300 GB free during installation (about 170-190 GB once installed) |
| Network | to download about 139 GB of databases (96.9 GB of public Kraken indexes + 41.8 GB of ProfileMetaNanni packages) |

The installer enables WSL2 (it asks once for administrator permission and one restart), creates a dedicated Linux space and installs the programs from lock files with pinned versions and the databases with MD5 checks.

## Status

Version 1.0 under testing. Installation from scratch was tested on a clean Windows 11 virtual machine: 14 user interactions, no terminal, no help. The ProfileMetaNanni database packages (MetaPhlAn slices, host indexes, example sample) are not published yet: for now a full installation works only with a local mirror.

| Validation | Result |
|---|---|
| App versus command line, same sample | byte-identical |
| ZymoBIOMICS D6300 control community | MetaPhlAn 8 expected species out of 8, 0 extra species, Bray-Curtis 0.068 |
| Simulated cured-meat communities (12) | MetaPhlAn 0 false species in 12 out of 12; sensitivity criterion met in 4 out of 12, because rare taxa with few reads are lost (limit declared in the report) |
| Kraken calibration (confidence 0.5 + 0.1 % threshold) | F1 1.00 on the control community |
| FSSP models rewritten in Python | 382 cases out of 382 equal to the original program |

## Documents

- User guide (Italian): [`docs/Manuale_uso_ProfileMetaNanni.pdf`](docs/Manuale_uso_ProfileMetaNanni.pdf)
- App and engine contract: [`docs/contratto_motore.md`](docs/contratto_motore.md)
- Installer: [`installer/LEGGIMI.md`](installer/LEGGIMI.md)

## How to cite

If you use the results, cite the tools and databases you used: MetaPhlAn 4 (Blanco-Míguez et al. 2023, *Nat Biotechnol* 41:1633-1644), Kraken 2 (Wood et al. 2019, *Genome Biol*), Bracken (Lu et al. 2017, *PeerJ Comput Sci*), Bowtie 2 (Langmead and Salzberg 2012, *Nat Methods* 9:357-359), fastp (Chen et al. 2018, *Bioinformatics*), FSSP (Mejlholm and Dalgaard 2009, *J Food Prot* 72:2132-2143) and the host genomes. The full list with DOIs is in the "Come citare" page of the app and at the end of every report.

## Licence

MIT (see `LICENSE`).
