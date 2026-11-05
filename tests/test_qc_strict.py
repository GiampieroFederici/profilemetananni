# -*- coding: utf-8 -*-
"""F1 (5/11/2026): quota dell'ospite e coppie ai profili nel referto con la regola strict.

Con la regola strict (steps/21_hostfilter.sh) una coppia esce anche se una sola read si allinea all'ospite: le coppie
tenute non sono più le "aligned concordantly 0 times" del log di Bowtie2, ma quelle scritte in
hostfilter_logs/<campione>.<indice>.coppie.tsv. Senza quel file (progetti vecchi) si legge il log come prima."""
import sys
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADICE / "motore"))
import pmn_motore  # noqa: E402

LOG = ("{n} reads; of these:\n  {n} (100.00%) were paired; of these:\n"
       "    {zero} (50.00%) aligned concordantly 0 times\n    0 (0.00%) aligned concordantly exactly 1 time\n")


def test_coppie_tenute_dal_file_della_regola_strict(tmp_path):
    h = tmp_path / "hostfilter_logs"
    h.mkdir()
    # maiale: 1.900.000 coppie entrate, 600.000 non concordanti ma solo 500.000 con tutte e due le read fuori
    (h / "S1.sus_scrofa.bowtie2.log").write_text(LOG.format(n=1900000, zero=600000))
    (h / "S1.sus_scrofa.coppie.tsv").write_text("entrate\ttenute\n1900000\t500000\n")
    (h / "S1.homo_sapiens.bowtie2.log").write_text(LOG.format(n=500000, zero=480000))
    (h / "S1.homo_sapiens.coppie.tsv").write_text("entrate\ttenute\n500000\t450000\n")
    assert pmn_motore.coppie_ospite(tmp_path) == {"S1": (1900000, 450000)}


def test_progetto_vecchio_senza_file_come_prima(tmp_path):
    h = tmp_path / "hostfilter_logs"
    h.mkdir()
    (h / "S1.sus_scrofa.bowtie2.log").write_text(LOG.format(n=1900000, zero=600000))
    (h / "S1.homo_sapiens.bowtie2.log").write_text(LOG.format(n=600000, zero=570000))
    assert pmn_motore.coppie_ospite(tmp_path) == {"S1": (1900000, 570000)}
