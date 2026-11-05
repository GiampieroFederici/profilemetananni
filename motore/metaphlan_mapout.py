"""MetaPhlAn 4.2.4 da mapout senza l'indice Bowtie2 intero (D028).

MetaPhlAn si ferma se nella cartella del database non trova i 6 file .bt2l dell'indice intero (34 GB),
anche con --input_type mapout, dove Bowtie2 non si usa (utils/database_controller.py:197-230, check_database).
Con le fette (D026) l'utente ha solo il .pkl: qui si sostituisce quel solo controllo con
"il .pkl c'e' e si legge" (stessa lettura dell'originale, riga 210-211) e si chiama lo stesso main() di MetaPhlAn.
I file di MetaPhlAn non si modificano.

Uso: python metaphlan_mapout.py <file.mapout> --input_type mapout [altre opzioni di metaphlan]
     python metaphlan_mapout.py --lotto <elenco.tsv> --input_type mapout [altre opzioni di metaphlan]
Con --lotto (F3, L3) il .pkl si legge una volta per tutti i campioni dell'elenco (righe "mapout<TAB>campione<TAB>
profilo"): per ognuno MetaPhlAn riceve gli stessi argomenti della chiamata singola, quindi anche la riga del comando
nell'intestazione del profilo resta uguale. Con --input_type mapout MetaPhlAn legge il database e non lo modifica
(metaphlan.py: TaxTree.add_tree_nodes, add_tree_markers, report_results).
"""
import bz2
import gc
import os
import pickle
import sys

from metaphlan import metaphlan
from metaphlan.utils.database_controller import MetaphlanDatabaseController

LETTI = {}   # percorso del .pkl -> database letto (uno solo per processo)


def check_database(self):
    pkl = os.path.join(self.db_dir, f"{self.index}.pkl")
    if not os.path.isfile(pkl):
        return False
    ridotto = os.environ.get("PMN_MPA_RIDOTTO")   # prototipo N1 (F3), spento di serie: vedi metaphlan_ridotto.py
    if ridotto:
        import metaphlan_ridotto
        self.database_pkl = metaphlan_ridotto.riduci(ridotto, pkl, sys.argv[1])
        return True
    if pkl not in LETTI:
        # Il .pkl di vJan25 sono 11,4 M di marcatori, ognuno un dizionario: mentre si creano, il raccoglitore dei cicli
        # di Python li ripercorre tutti di continuo. Spento durante la lettura, poi gli oggetti letti si "congelano"
        # (restano fino alla fine): stessi oggetti, stesso profilo, stessa memoria; MetaPhlAn da mapout su 66.000 read
        # da 1:27-1:37 a 1:00-1:02 (VM B2-4, 30/10).
        gc.disable()
        try:
            with bz2.BZ2File(pkl, "r") as handle:
                LETTI[pkl] = pickle.load(handle)
        finally:
            gc.enable()
        gc.freeze()
    self.database_pkl = LETTI[pkl]
    return True


def lotto(elenco, comuni):
    """MetaPhlAn su ogni mapout dell'elenco, uno dopo l'altro, nello stesso processo. Un errore ferma il lotto (come
    il passo singolo); i profili gia' scritti restano."""
    with open(elenco, encoding="utf-8") as f:
        righe = [r.rstrip("\n").split("\t") for r in f if r.strip()]
    for mapout, campione, profilo in righe:
        sys.argv = ["metaphlan", mapout, *comuni, "--sample_id", campione, "-o", profilo]
        metaphlan.main()
        # MetaPhlAn lascia sulla classe TaxClade gli indici dei marcatori dell'ultimo campione (2,2 GB): tolti prima
        # del campione dopo, cosi' il picco resta quello di una chiamata singola
        for nome in ("markers2lens", "markers2exts", "taxa2clades"):
            setattr(metaphlan.TaxClade, nome, None)
        gc.collect()


if __name__ == "__main__":
    if "--input_type mapout" not in " ".join(sys.argv):
        sys.exit("metaphlan_mapout.py: solo con --input_type mapout (senza indice intero Bowtie2 non puo' allineare)")
    MetaphlanDatabaseController.check_database = check_database
    if sys.argv[1] == "--lotto":
        lotto(sys.argv[2], sys.argv[3:])
        sys.exit(0)
    sys.argv[0] = "metaphlan"
    sys.exit(metaphlan.main())
