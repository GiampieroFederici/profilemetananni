# Metadati e analisi multicampione (PMN 1.1, R11)

Quando un progetto ha almeno 2 campioni, il referto contiene il confronto fra i campioni: diversità alfa (quanti taxa
ci sono dentro ogni campione) e diversità beta (quanto i campioni sono diversi fra loro). MetaPhlAn e Kraken restano
sempre separati: due cartelle, due serie di tabelle e di grafici, mai una matrice unica.

## Come si compilano i dati dei campioni

Nell'app, pagina **Risultati**, riquadro **Analisi multicampione**: una tabella con una riga per campione, già
riempita con i nomi. Si scrive il gruppo di ogni campione (ed eventualmente soggetto, tempo e una covariata) e si preme
**Salva e aggiorna l'analisi**. L'app salva il file `metadati.tsv` nella cartella del progetto e rifà solo il referto
(comando `referto` del motore): l'analisi delle read non si ripete. Gli errori (campione senza gruppo, gruppo con meno
di 3 campioni, campioni mancanti) compaiono nel riquadro con le parole che dicono che cosa fare.

Chi preferisce Excel può aprire `metadati.tsv` dal pulsante "Apri metadati.tsv" e salvarlo come "Testo delimitato da
tabulazione". Le colonne in più scritte con Excel restano quando si salva dall'app.

## Il file `metadati.tsv`

Testo separato da tabulazioni, UTF-8 (va bene anche con il BOM di Excel, o Windows-1252), una riga per campione.
Le righe che iniziano con `#` non si leggono.

| Colonna | Obbligatoria | Che cosa vuol dire |
|---|---|---|
| `sample_id` | sì | il nome del campione, uguale a quello del progetto |
| `group` | per i test | il gruppo da confrontare (prodotto, lotto, stabilimento) |
| `subject` | no | lo stesso nome per i campioni dello stesso salame o animale (misure ripetute o appaiate) |
| `timepoint` | no | il tempo (per esempio 0, 30, 60 giorni); si confronta come `group` |
| `covariate` e altre | no | informazioni in più: si riportano nelle tabelle, **non** entrano nei test |

Senza file, o senza nessun valore in `group` e `timepoint`, ci sono solo tabelle e grafici descrittivi, nessun test.
Il programma crea da solo il modello del file (solo i nomi dei campioni) alla prima analisi con almeno 2 campioni, e
non lo sovrascrive mai.

## Come si sceglie il test (un fattore alla volta: `group`, poi `timepoint`)

| Disegno (deciso dai metadati) | Diversità alfa | Effetto | PERMANOVA (beta) |
|---|---|---|---|
| campioni indipendenti, 2 gruppi | Mann-Whitney | r di rango = \|Z\|/radice di n | permutazioni libere |
| campioni indipendenti, più di 2 gruppi | Kruskal-Wallis, poi Dunn a coppie con correzione BH | epsilon quadro = H/(n-1) | permutazioni libere |
| più campioni dello stesso soggetto, sempre nello stesso gruppo | come sopra, sulla media di ogni soggetto | come sopra | sui profili medi dei soggetti, permutazioni dei soggetti |
| 2 condizioni sugli stessi soggetti | Wilcoxon per dati appaiati (soggetti con entrambe) | r di rango | permutazioni ristrette dentro ogni soggetto |
| più di 2 condizioni sugli stessi soggetti | Friedman (solo soggetti con dati completi), poi Wilcoxon appaiato a coppie con BH | W di Kendall | permutazioni ristrette dentro ogni soggetto |

Con meno di 3 unità indipendenti per gruppo (campioni, o soggetti) non si fa nessun test: solo i valori e i grafici, e
una frase che dice perché.

Beta: distanza di Aitchison (distanza euclidea sul CLR, dopo aver sostituito gli zeri con metà della più piccola
abbondanza non nulla, sostituzione moltiplicativa) e Bray-Curtis sulle abbondanze relative; PCoA. La PERMANOVA
(`vegan::adonis2`, 999 permutazioni, seme 1992) ha **sempre** accanto PERMDISP (`vegan::betadisper` + `permutest`,
stesse permutazioni): se la dispersione differisce fra i gruppi, il referto lo scrive accanto alla PERMANOVA. R² è la
dimensione dell'effetto.

Quando la statistica non è definita (campioni identici, oppure identici dentro ogni gruppo, dispersione zero o uguale
dentro ogni gruppo) non si scrive nessun valore p: la tabella dice "non definita" e la nota spiega perché in parole
semplici. Con campioni quasi identici, prima, il rumore di arrotondamento dei numeri (circa 1e-17) diventava un F e un
p di 0,001.

Kraken: solo batteri, archei e funghi sopra la soglia del referto (D128), ed è un prototipo. MetaPhlAn: tutte le
specie, nessuna soglia. Diversità alfa: i valori a profondità uguale del referto (`motore/diversita.py`).

## Uscite: `risultati/multicampione/<profiler>/` (`metaphlan`, `kraken`)

- `abundance_relative.tsv`, `alpha_diversity.tsv`, `metadata_used.tsv`, `comparisons.tsv`, `design.tsv`
- `alpha_tests.tsv`, `alpha_posthoc.tsv`, `beta_tests.tsv`, `distance_*.tsv`, `pcoa_*.tsv`
- grafici in inglese, PNG e PDF: `alpha_samples`, `pcoa_aitchison`, `pcoa_braycurtis` (descrittivi) e per ogni
  confronto `alpha_<fattore>` (boxplot con i punti) e `pcoa_<distanza>_<fattore>` (colori per gruppo, ellissi solo con
  almeno 3 campioni per gruppo)
- `parametri.tsv`: profiler, soglia, pseudoconteggio, permutazioni, seme, test scelti e perché, versioni di R, vegan,
  permute, ggplot2, rstatix
- `R_log.txt`; in `risultati/multicampione/riepilogo.json` il riassunto che leggono referto e app

Programmi: Python (libreria standard) per metadati, disegno e referto (`motore/multicampione.py`); R dell'ambiente
`pmn_stats_r` per i calcoli e i grafici (`motore/multicampione.R`).

## Limiti

Un fattore alla volta, niente modelli con più fattori, interazioni o covariate. I valori p non sono corretti fra
indici, distanze e confronti diversi. Con pochi campioni un risultato non significativo non vuol dire che i gruppi
siano uguali. Le abbondanze sono DNA relativo, non cellule vive per grammo.

## Fonti

Anderson 2001, Austral Ecology 26:32-46 (PERMANOVA); Anderson 2006, Biometrics 62:245-253 (PERMDISP); Anderson & Walsh
2013, Ecological Monographs 83:557-574 (dispersione e PERMANOVA); Martín-Fernández et al. 2003, Mathematical Geology
35:253-278 (zeri); Gloor et al. 2017, Front Microbiol 8:2224 (dati composizionali); Kruskal & Wallis 1952, JASA
47:583-621; Dunn 1964, Technometrics 6:241-252; Benjamini & Hochberg 1995, JRSS B 57:289-300; Friedman 1937, JASA
32:675-701; Fritz et al. 2012, J Exp Psychol Gen 141:2-18 (dimensioni dell'effetto); vegan (Oksanen et al., CRAN).
DOI controllati su Crossref il 30/10/2026.
