# Environments: human faeces, skin, soil and grapevine

ProfileMetaNanni (PMN) was built and validated on fermented meat products. Version 1.1 adds six new
environments to the menu of the app: human faeces, skin, soil (or rhizosphere), and four grapevine
matrices (must, berry, leaf, root). This page says, for each one, which reads PMN accepts, which
quality checks it runs, what the two databases cover there, which host DNA it removes, and how to read
the results. Each method statement has its source; the numbers about the databases were measured on
the installed files. A short Italian summary is at the end.

Everything the person needs to choose an environment is also written inside the app (the menu entry,
its sentence and its reason). An environment is marked **experimental** in the app until a test with
public data has finished and its main taxa agree with the article that published those data
(section 5).

## 1. What does not change

The analysis is the same for every environment; only the host genome changes.

- **Input**: Illumina shotgun metagenomes, paired-end (R1 and R2) or single-end FASTQ (`.fastq.gz`),
  or SRA/ENA run accessions. Amplicon data (16S, ITS) are not supported in any environment.
- **Quality control**: adapter and quality trimming with fastp [T1], MultiQC report, and the optional
  triage (host share, non-host fragments, Q30) with the same thresholds as for meat.
- **Host removal**: Bowtie 2 [T2] in `--very-sensitive` mode against the host genome(s), then always
  against the human genome GRCh38 (D021). The filter itself (`steps/21_hostfilter.sh`) is unchanged.
- **Profiling**: MetaPhlAn 4 [T3] with the pinned database `mpa_vJan25_CHOCOPhlAnSGB_202503`, never
  filtered; Kraken 2 [T4] with Bracken [T5] on the PlusPF index (complete, or PlusPF-8 for the quick
  screening), abundance threshold on Kraken only. MetaPhlAn and Kraken results are always kept
  separate.
- **Bracken read length** (`profiling.bracken_readlen`) must match the read length of the run (for
  example 100 for HiSeq 2x100, 150 for 2x150). This depends on the sequencer, not on the environment,
  but public data from older studies are often 100 bp.
- **Kraken parameters**: the confidence and the threshold of the complete PlusPF (0.5 and 0.1 %) were
  calibrated on simulated meat communities (`refs/kraken_profili.tsv`, K4). They have not been
  calibrated on the new environments; PMN keeps them unchanged (section 4 says where this matters).

## 2. What the databases cover (measured on the installed files)

| Database | Content | Measured on the installed index |
|---|---|---|
| MetaPhlAn vJan25 | marker genes of species-level genome bins (SGBs), including SGBs without a cultured or named species [T3] | taxonomy entries: 55,504 bacterial, 2,338 archaeal, 489 eukaryotic; eukaryotes include *Malassezia* (15 species), *Saccharomyces cerevisiae*, *Candida* (58), *Plasmopara* (5); no *Hanseniaspora*, no *Metschnikowia*, no *Aureobasidium*; no plants |
| Kraken 2 PlusPF (2026-06-26) | RefSeq archaea, bacteria, viruses, plasmids, human, UniVec_Core, plus RefSeq protozoa and fungi [T6] | libraries in `library_report.tsv`: archaea, bacteria, fungi (2,323 sequences), human, plasmid, protozoa, viral, UniVec_Core; genera *Saccharomyces*, *Malassezia*, *Cutibacterium* present; *Hanseniaspora*, *Metschnikowia*, *Aureobasidium*, *Vitis* absent; Viridiplantae practically absent (3,455 minimizers out of about 2·10^10) |

Plant genomes are only in the larger PlusPFP index (171.8 GB archive) [T6]. PMN does not use it: the
grapevine DNA is removed before profiling instead (section 3.4).

## 3. The environments

### 3.0 Fermented meat (reference)

Host: pig, cattle or sheep, plus human. Validated in PMN 1.0 (internal validation L1 to L4). Nothing
changes in version 1.1.

### 3.1 Human faeces

- **Host**: human (GRCh38). Faecal metagenomes usually carry little human DNA, but it is removed for
  privacy and because it says nothing about the taxa. Public faecal data are often deposited after
  human reads were already removed: for example, the reads of the colorectal cancer study used in the
  test were screened against the human genome before analysis [E1].
- **Databases**: the human gut is the environment both databases know best. MetaPhlAn 4 explains
  about 20 % more reads than earlier versions in most international human gut metagenomes [T3]; the
  known-species fraction of human metagenomes is among the highest of all environments [L1].
- **Limits**: guts from populations that are less represented in the databases (for example
  non-Western) have more unknown species; the proportion of bacterial and archaeal DNA in public
  faecal metagenomes is high (median 77.2 % [L2]).

### 3.2 Skin

- **Host**: human (GRCh38). Skin samples have a low microbial biomass and a variable human DNA
  admixture, which sets how deep each site must be sequenced [E2].
- **Databases**: the dominant bacteria (*Cutibacterium acnes*, formerly *Propionibacterium acnes*,
  *Staphylococcus epidermidis*, *Corynebacterium*) and the skin fungi *Malassezia* are in both
  databases (section 2). In the reference skin study fungi were 3.9 ± 5.0 % of the classified reads,
  higher near the ears (retroauricular crease 7.5 ± 4.2 %) [E2].
- **Limits**: with low biomass, DNA from extraction kits and reagents can dominate the result; always
  sequence negative controls (extraction blanks) and read rare taxa only against them [L3, L4]. Public
  skin data, like faecal data, are often deposited without the human reads.

### 3.3 Soil and rhizosphere (also of a vineyard)

- **Host**: none. PMN still removes human DNA (from the people who collected and handled the sample):
  it costs little and the human genome is in the Kraken index, so human reads would otherwise be
  counted. The rhizosphere soil of the grapevine uses the same method as soil: there is no host to
  remove.
- **Databases**: soil is the environment where reference databases are weakest. The fraction of a
  soil community that can be named at species level is 14 % on average (median 8 %) [L1]. On real soil
  reads a Kraken 2 database built for soil classified 58 % of the reads [L5]; the default databases
  classify fewer. MetaPhlAn 4 profiles also SGBs without a named species [T3], but it detects only
  species that have marker genes.
- **Limits**: the profile describes the known taxa, not the whole community; Kraken leaves many reads
  unclassified. The low share of named species is due to diversity and missing genomes, not to
  eukaryotic DNA: in most soil metagenomes bacteria and archaea are more than half of the DNA [L2].
  Low abundance thresholds (0.001 % to 0.005 %) gave the best accuracy for Kraken 2 in soil [L5],
  which is the threshold PMN already uses with PlusPF-8.

### 3.4 Grapevine: must, berry, leaf, root

- **Host**: *Vitis vinifera*, reference genome T2T PN40024 (`GCF_030704535.1`, ASM3070453v1, 494.9 Mb)
  [H1], plus human. The RefSeq assembly has 21 sequences including the mitochondrion (`NC_012119.1`,
  773,279 bp) and the chloroplast (`NC_007957.1`, 160,928 bp), so organelle reads are removed together
  with the nuclear ones (checked on NCBI Datasets). The index is built by PMN at the first analysis
  (D167); it is not part of the installation.
- **Why the host matters**: neither database contains the grapevine (section 2). Without removal,
  plant reads stay unclassified at best or are assigned to some microbial taxon by mistake. Chloroplast
  reads are a known trap: their sequences resemble cyanobacteria, so leaf studies remove them [V3].
- **Does the matrix change the method?** No. The four grapevine matrices use the same host and the same
  steps; what changes is how much plant DNA is expected and therefore how many reads are needed:
  - *Leaf (phyllosphere)*: plant DNA is usually the majority of the reads. In 275 wild *Arabidopsis*
    leaf metagenomes the microbial reads ranged from below 1 % to 77 % of the plant reads [V3].
  - *Berry or bunch*: the microbial biomass on the berry surface is low; plant DNA is expected to be
    high (no shotgun test was available, so this matrix stays experimental).
  - *Root*: shotgun sequencing of the root endosphere was avoided in a grapevine study because of the
    excess plant DNA; rhizoplane and rhizosphere soil were sequenced instead [V2].
  - *Must*: plant DNA comes from the crushed berries; the measured share is in section 5.
  - *Rhizosphere soil*: no host, see 3.3.
- **Limits**: many yeasts of grapes and must (*Hanseniaspora*, *Metschnikowia*, *Aureobasidium*) are in
  neither database (section 2); at the onset of a spontaneous fermentation these genera can dominate
  the fungal community [V1]. PMN cannot see them: the profile of must is a profile of bacteria and of
  the few yeasts in RefSeq (*Saccharomyces cerevisiae*). *Plasmopara* (downy mildew) is in MetaPhlAn.

## 4. Open scientific questions (kept as in version 1.0)

- Kraken confidence and threshold for the complete PlusPF are calibrated on meat; a calibration on
  simulated communities of each new environment has not been done.
- Grape and must yeasts missing from both databases: a custom database would be needed.
- The triage thresholds (host at most 95 %) were set for meat; leaf and berry samples may exceed them,
  which correctly signals that more reads are needed.

## 5. Tests with small public data

Design: one public Illumina paired-end shotgun run per environment, with its article; the first
500,000 read pairs (taken from the start of both files, so the pairs stay matched); the whole PMN
pipeline of this version with PlusPF-8 (quick screening) and MetaPhlAn in slices, 8 threads, on a
Linux machine with about 12 GB of memory. An environment is **verified** when the run finishes and its
main taxa (MetaPhlAn and Kraken read separately) agree with the dominant taxa reported in the article.

| Environment | Run (project) | Article | Host removed |
|---|---|---|---|
| Human faeces | ERR478976 (PRJEB6070) | [E1] | human |
| Skin, retroauricular crease (sebaceous) | SRR1620994 (PRJNA46333) | [E2] | human |
| Topsoil, Estonian forest | ERR2603036 (PRJEB24121) | [E3] | human only |
| Grapevine must, Chardonnay, onset of fermentation (Y2 D1 B) | SRR3017099 (PRJNA305659) | [V1] | grapevine + human |
| Grapevine rhizosphere soil, Chardonnay, flowering (CNTS1F) | SRR30765320 (PRJNA1162681) | [V2] | human only |
| Grapevine rhizoplane (root surface), Chardonnay, flowering (CNTR1F) | SRR30765297 (PRJNA1162681) | [V2] | grapevine + human |

Grapevine index: built from `GCF_030704535.1` by the same step PMN uses (`steps/11_host_index.sh`) in
4 min 20 s with 1.27 GB of memory peak, 678 MB on disk. Share of the 500,000 raw pairs that Bowtie 2
`--very-sensitive` aligns to it: must 0.39 % of reads (199 concordant pairs), rhizoplane 0.30 % (1,265
concordant pairs). These public reads were probably deposited after plant reads were removed (the must
study analysed reads "pre-filtered to remove grapevine matches" [V1]), so they test that the index
works, not a sample rich in plant DNA. No public shotgun run of grape berry or leaf was used: those two
matrices stay experimental.

The results of each run (host share, main taxa of MetaPhlAn and of Kraken, agreement with the article,
time and memory) are in the project validation folder (`validazione/ambienti/ESITO.md`, not
distributed); the status shown in the app (`sperimentale`) follows that table.

## Riassunto in italiano

PMN 1.1 aggiunge al menu sei ambienti oltre ai salumi: feci umane, cute, suolo o rizosfera, e quattro
matrici della vite (mosto, acino, foglia, radice). L'analisi è la stessa per tutti: read Illumina
shotgun, pulizia con fastp, DNA dell'ospite tolto con Bowtie 2, profili di MetaPhlAn 4 e di Kraken 2
sempre separati, soglia di abbondanza solo su Kraken. Cambia solo l'ospite: l'uomo per feci e cute,
nessuno per suolo e rizosfera (si toglie comunque il DNA umano di chi ha toccato il campione), la vite
(genoma T2T PN40024 con cloroplasto e mitocondrio) più l'uomo per mosto, acino, foglia e radice. La
matrice della vite non cambia il metodo, cambia la quota attesa di DNA della pianta e quindi quante read
servono.

I limiti principali, misurati sui database installati o presi dalle fonti: nel suolo solo una piccola
parte delle specie ha un nome (14 % in media), quindi il profilo descrive i taxa noti; sulla cute la
biomassa è bassa e servono controlli negativi; nessuno dei due database contiene la vite, e molti
lieviti di uva e mosto (*Hanseniaspora*, *Metschnikowia*, *Aureobasidium*) mancano in entrambi. Un
ambiente resta "sperimentale" nell'app finché la prova con dati pubblici (sezione 5) non è finita e
coerente con l'articolo.

## 6. Sources

Tools and databases
- [T1] Chen S et al. 2018. fastp: an ultra-fast all-in-one FASTQ preprocessor. *Bioinformatics* 34:i884-i890. doi:10.1093/bioinformatics/bty560
- [T2] Langmead B, Salzberg SL. 2012. Fast gapped-read alignment with Bowtie 2. *Nat Methods* 9:357-359. doi:10.1038/nmeth.1923
- [T3] Blanco-Míguez A et al. 2023. Extending and improving metagenomic taxonomic profiling with uncharacterized species using MetaPhlAn 4. *Nat Biotechnol* 41:1633-1644. doi:10.1038/s41587-023-01688-w
- [T4] Wood DE, Lu J, Langmead B. 2019. Improved metagenomic analysis with Kraken 2. *Genome Biol* 20:257. doi:10.1186/s13059-019-1891-0
- [T5] Lu J et al. 2017. Bracken: estimating species abundance in metagenomics data. *PeerJ Comput Sci* 3:e104. doi:10.7717/peerj-cs.104
- [T6] Kraken 2 / Bracken Refseq indexes, collection table (PlusPF, PlusPF-8, PlusPFP), https://benlangmead.github.io/aws-indexes/k2 (read on 30/10/2026)

Environments
- [E1] Zeller G et al. 2014. Potential of fecal microbiota for early-stage detection of colorectal cancer. *Mol Syst Biol* 10:766. doi:10.15252/msb.20145645
- [E2] Oh J et al. 2014. Biogeography and individuality shape function in the human skin metagenome. *Nature* 514:59-64. doi:10.1038/nature13786
- [E3] Bahram M et al. 2018. Structure and function of the global topsoil microbiome. *Nature* 560:233-237. doi:10.1038/s41586-018-0386-6
- [H1] Shi X et al. 2023. The complete reference genome for grapevine (*Vitis vinifera* L.) genetics and breeding. *Hortic Res* 10:uhad061. doi:10.1093/hr/uhad061
- [V1] Sternes PR et al. 2017. A combined meta-barcoding and shotgun metagenomic analysis of spontaneous wine fermentation. *GigaScience* 6:1-10. doi:10.1093/gigascience/gix040
- [V2] Duret M et al. 2025. Diversity and functional features of the root-associated bacteriome are dependent on grapevine susceptibility to *Plasmopara viticola*. *Environ Microbiome* 20:30. doi:10.1186/s40793-025-00690-w
- [V3] Regalado J et al. 2020. Combining whole-genome shotgun sequencing and rRNA gene amplicon analyses to improve detection of microbe-microbe interaction networks in plant leaves. *ISME J* 14:2116-2130. doi:10.1038/s41396-020-0665-8

Limits
- [L1] Woodcroft BJ et al. 2026. Comprehensive taxonomic identification of microbial species in metagenomic data using SingleM and Sandpiper. *Nat Biotechnol*. doi:10.1038/s41587-025-02738-1
- [L2] Eisenhofer R, Alberdi A, Woodcroft BJ. 2026. Large-scale estimation of bacterial and archaeal DNA prevalence in metagenomes reveals biome-specific patterns. *mSystems* 11:e01062-25. doi:10.1128/msystems.01062-25
- [L3] Salter SJ et al. 2014. Reagent and laboratory contamination can critically impact sequence-based microbiome analyses. *BMC Biol* 12:87. doi:10.1186/s12915-014-0087-z
- [L4] Eisenhofer R et al. 2019. Contamination in low microbial biomass microbiome studies: issues and recommendations. *Trends Microbiol* 27:105-117. doi:10.1016/j.tim.2018.11.003
- [L5] Edwin NR et al. 2024. An in-depth evaluation of metagenomic classifiers for soil microbiomes. *Environ Microbiome* 19:19. doi:10.1186/s40793-024-00561-w
