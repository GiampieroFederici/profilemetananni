---
type: synthesis
title: "Research: read-based metagenomic profiling — pipeline best practices (2023-2025)"
created: 2026-07-10
updated: 2026-07-10
tags: [research, metagenomics, host-depletion, kraken2, metaphlan, profilemetananni]
status: developing
related:
  - "[[ProfileMetaNanni]]"
  - "[[Kraken2]]"
  - "[[Bracken]]"
  - "[[MetaPhlAn4]]"
sources:
  - "Zhou 2025 mSystems 10:e00840-25"
  - "Forbes 2025 Cell Reports Methods PMC12664888"
  - "Barcenilla 2024 Microbiome 12:199"
  - "Edwin 2024 Environmental Microbiome"
  - "Carlino 2024 (cFMD)"
---

# Research: read-based metagenomic profiling — best practices (2023-2025)

Autoresearch multi-agente (grounding sul second brain + sweep web 2023-2025, ogni claim
verificato in modo avversariale) per migliorare la pipeline **ProfileMetaNanni**. Sotto: gli 11
candidati sopravvissuti alla verifica, con stato (implementato / da valutare) e citazione.

## Overview
Il driver reale dell'accuratezza del profiling read-based non è "quale tool" ma **quanto bene il
DB copre la matrice** e **quanto è pulita la depletion dell'host**. I guadagni con più evidenza
riguardano il riferimento umano e l'osservabilità della host-removal.

## Implementato in questa iterazione (evidenza forte)
- **Riferimento umano GRCh38 → T2T-CHM13v2.0** *(CONFIRMED)*. GRCh38 lascia reads umane residue
  (mediana ~0.08%, fino a 2.48%) che vengono misclassificate come taxa microbici; T2T-CHM13
  le rimuove (−~48% falsi positivi) ed elimina il segnale del cromosoma Y (privacy).
  *Zhou 2025, mSystems 10:e00840-25; Forbes 2025, Cell Reports Methods PMC12664888.* → **ACC-3**.
- **QC della host-removal nel report MultiQC** *(PLAUSIBLE)*. Persiste le statistiche per-campione
  di Bowtie2 (reads in/out, % rimossa) dove MultiQC le mostra → intercetta over-/under-depletion.
  *GigaScience 2025, PMC11878760.* → **ACC-4**.
- **Preset `--very-sensitive-local` (opt-in)** *(PLAUSIBLE)*. Soft-clip delle reads host parziali:
  sensibilità host lievemente maggiore a perdita microbica ~trascurabile. *Forbes 2025.* → **ACC-7**.
- **phiX174 come host selezionabile** *(dominio carni/WMS)*. *Barcenilla 2024, Microbiome 12:199.* → **ACC-6**.

## Da valutare in una prossima iterazione (evidenza buona, ma fuori dallo scope minimo o in tensione con scelte deliberate)
- **Kraken2 `--confidence` default 0.2** *(CONFIRMED)*. La ricerca indica 0.2 come valore "moderato";
  la pipeline usa **0.4** *di proposito* (SPEC §4: valori bassi gonfiano la richness con falsi
  positivi). Tensione reale → decisione dell'autore, non un bug. Documentare il trade-off, non
  cambiare in automatico.
- **Kraken2 `--minimum-hit-groups >=2` esplicito** *(CONFIRMED)*, soprattutto per DB custom/targeted.
- **Preferire DB standard/comprensivo a minikraken** *(CONFIRMED)* così la taratura di `--confidence`
  resta sensata; documentare la scelta.
- **Bracken `-r` = read length post-QC** *(PLAUSIBLE)*: già configurabile (`bracken_readlen`);
  aggiungere una guida/validazione che lo lega alla lunghezza reale.
- **Pin della versione esatta del DB MetaPhlAn (`--index`) nei metadati di run** *(CONFIRMED)*:
  riproducibilità.
- **Indice umano mascherato (Hostile human-t2t-hla-argos985)** *(PLAUSIBLE)*: guadagno marginale per
  short-read; nessun riferimento host mascherato per il bestiame → rimandato.
- **Gate privacy sui residui umani (profondità cromosoma Y / frazione host residua)** *(PLAUSIBLE)*:
  richiede un allineamento extra; da costruire sopra i log di ACC-4.
- **Step opzionale di decontaminazione / controllo negativo per matrici a bassa biomassa** *(PLAUSIBLE)*.

## Gap del DB per il dominio (carni fermentate / food)
Carlino 2024 (cFMD) quantifica centinaia di SGB alimentari assenti dai DB standard: la pipeline
già supporta `kraken_db_mode: custom` con lista di accession → curare una lista cFMD/MiFoDB è
**lavoro di dominio**, non di architettura. *(deferito, vedi ITERATION1_PLAN.md)*

## Open questions
- Serve un arm "breadth-of-coverage" (presenza-genoma) per evitare che pochi reads spuri sembrino
  "presenti"? (Caffrey 2025) — fuori dallo scope read-based dichiarato; mitigato dalla soglia
  Bracken + filtro di abbondanza in `41_diversity.R`.
- Quale profiler primario per matrici a bassa biomassa (Ciauscolo)? → da fissare col tutor FEM.

_Fonte: workflow autoresearch (33 agenti) su ProfileMetaNanni, 2026-07-10. Accession NCBI
verificati live. Ingeribile nel vault con `ingest` dentro una sessione in `second_brain`._
