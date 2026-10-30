"""MetaPhlAn 4.2.4 da mapout senza l'indice Bowtie2 intero (D028).

MetaPhlAn si ferma se nella cartella del database non trova i 6 file .bt2l dell'indice intero (34 GB),
anche con --input_type mapout, dove Bowtie2 non si usa (utils/database_controller.py:197-230, check_database).
Con le fette (D026) l'utente ha solo il .pkl: qui si sostituisce quel solo controllo con
"il .pkl c'e' e si legge" (stessa lettura dell'originale, riga 210-211) e si chiama lo stesso main() di MetaPhlAn.
I file di MetaPhlAn non si modificano.

Uso: python metaphlan_mapout.py <file.mapout> --input_type mapout [altre opzioni di metaphlan]
"""
import bz2
import gc
import os
import pickle
import sys

from metaphlan import metaphlan
from metaphlan.utils.database_controller import MetaphlanDatabaseController


def check_database(self):
    pkl = os.path.join(self.db_dir, f"{self.index}.pkl")
    if not os.path.isfile(pkl):
        return False
    # Il .pkl di vJan25 sono 11,4 M di marcatori, ognuno un dizionario: mentre si creano, il raccoglitore dei cicli di
    # Python li ripercorre tutti di continuo. Spento durante la lettura, poi gli oggetti letti si "congelano" (restano
    # fino alla fine): stessi oggetti, stesso profilo, stessa memoria; MetaPhlAn da mapout su 66.000 read da 1:27-1:37
    # a 1:00-1:02 (VM B2-4, 30/10).
    gc.disable()
    try:
        with bz2.BZ2File(pkl, "r") as handle:
            self.database_pkl = pickle.load(handle)
    finally:
        gc.enable()
    gc.freeze()
    return True


if __name__ == "__main__":
    if "--input_type mapout" not in " ".join(sys.argv):
        sys.exit("metaphlan_mapout.py: solo con --input_type mapout (senza indice intero Bowtie2 non puo' allineare)")
    MetaphlanDatabaseController.check_database = check_database
    sys.argv[0] = "metaphlan"
    sys.exit(metaphlan.main())
