"""Pagina "Come citare" (S5b, D036, R14): tutte le fonti degli strumenti e dei database, con il DOI.

Testi copiati dalle fonti già verificate su PubMed: README §21 "Citations" e CITAZIONI di motore/pmn_motore.py
(installer/riferimenti.tsv per le versioni). Ogni referto elenca solo quelli usati davvero nella corsa.
"""
from PySide6.QtGui import QGuiApplication

from app.lingua import N_, _
from app.pagine.base import Pagina, etichetta, pannello

FONTI = [
    (N_("Profilo delle specie"), [
        N_("Blanco-Míguez et al. 2023, Nat Biotechnol 41(11):1633-1644: MetaPhlAn 4 (e StrainPhlAn). "
           "DOI 10.1038/s41587-023-01688-w"),
        N_("Beghini et al. 2021, eLife: bioBakery 3 e MetaPhlAn. DOI 10.7554/eLife.65088"),
        "Wood et al. 2019, Genome Biol 20:257: Kraken 2. DOI 10.1186/s13059-019-1891-0",
        "Lu et al. 2017, PeerJ Comput Sci 3:e104: Bracken. DOI 10.7717/peerj-cs.104",
    ]),
    (N_("Preparazione delle read"), [
        N_("Langmead & Salzberg 2012, Nat Methods 9(4):357-359: Bowtie 2 (toglie il DNA dell'ospite e allinea sulle "
           "parti del database di MetaPhlAn). DOI 10.1038/nmeth.1923"),
        "Chen et al. 2018, Bioinformatics 34(17):i884-i890: fastp. DOI 10.1093/bioinformatics/bty560",
        N_("Chen 2023, iMeta 2(2):e107: fastp, preparazione in un solo passaggio. DOI 10.1002/imt2.107"),
        "Danecek et al. 2021, GigaScience 10(2):giab008: SAMtools. DOI 10.1093/gigascience/giab008",
        "Ewels et al. 2016, Bioinformatics 32(19):3047-3048: MultiQC. DOI 10.1093/bioinformatics/btw354",
        N_("Andrews 2010: FastQC (programma, Babraham Bioinformatics)."),
        "Leinonen, Sugawara, Shumway; International Nucleotide Sequence Database Collaboration 2011, Nucleic Acids "
        "Res 39(Database issue):D19-D21: Sequence Read Archive (SRA Toolkit). DOI 10.1093/nar/gkq1019",
        N_("Grüning et al. 2018, Nat Methods 15(7):475-476: Bioconda (da qui si installano i programmi, con "
           "micromamba 2.9.0 di mamba-org). DOI 10.1038/s41592-018-0046-7"),
    ]),
    (N_("Database e genomi di riferimento"), [
        N_("Database MetaPhlAn mpa_vJan25_CHOCOPhlAnSGB_202503 (le 6 parti sono un derivato del suo indice "
           "Bowtie 2, costruito da ProfileMetaNanni)."),
        N_("Indici Kraken 2 e Bracken PlusPF e PlusPF-8 del 26/06/2026 di Ben Langmead "
           "(genome-idx.s3.amazonaws.com/kraken)."),
        N_("Warr et al. 2020, GigaScience 9(6):giaa051: maiale Sscrofa11.1. DOI 10.1093/gigascience/giaa051"),
        N_("Rosen et al. 2020, GigaScience 9(3):giaa021: bovino ARS-UCD1.2. DOI 10.1093/gigascience/giaa021"),
        N_("Davenport et al. 2022, GigaScience 11:giab096: pecora ARS-UI_Ramb_v2.0. DOI 10.1093/gigascience/giab096"),
        N_("Schneider et al. 2017, Genome Res 27(5):849-864: uomo GRCh38. DOI 10.1101/gr.213611.116"),
    ]),
    (N_("Scelta dei parametri e statistica"), [
        N_("Wright, Comeau & Langille 2023, Microb Genom 9(3):000949: scelta della soglia di confidenza e del "
           "database di Kraken 2. DOI 10.1099/mgen.0.000949"),
        N_("Edwin et al. 2024, Environ Microbiome 19:19: soglia di abbondanza 0,005 %. DOI 10.1186/s40793-024-00561-w"),
        N_("Gloor et al. 2017, Front Microbiol: dati composizionali e trasformazione CLR. "
           "DOI 10.3389/fmicb.2017.02224"),
        N_("Kruskal & Wallis 1952, J Am Stat Assoc 47:583-621: test di Kruskal-Wallis (confronto fra gruppi)."),
        N_("Dunn 1964, Technometrics 6:241-252: test di Dunn dopo Kruskal-Wallis (correzione di Benjamini-Hochberg)."),
    ]),
    (N_("Sicurezza alimentare (FSSP, DTU Food)"), [
        N_("Le previsioni usano i modelli del Food Spoilage and Safety Predictor (FSSP) 4.0 di DTU Food (Danimarca), "
           "riscritti in Python con il permesso di DTU e provati uguali a FSSP (382 casi su 382)."),
        N_("Dalgaard, Buch & Silberg 2002, Int J Food Microbiol 73(2-3):343-349: Seafood Spoilage Predictor, il "
           "programma da cui è nato FSSP. DOI 10.1016/S0168-1605(01)00670-5"),
        N_("Mejlholm & Dalgaard 2009, J Food Prot 72(10):2132-2143: crescita e limite di crescita di Listeria "
           "monocytogenes. DOI 10.4315/0362-028X-72.10.2132"),
        N_("Mejlholm & Dalgaard 2013, Int J Food Microbiol 167(2):244-260: Lactobacillus psicrotolleranti (modello "
           "costruito su L. sakei). DOI 10.1016/j.ijfoodmicro.2013.09.013"),
        N_("Mejlholm & Dalgaard 2007, J Food Prot 70(11):2485-2497: batteri lattici e il loro effetto su "
           "L. monocytogenes. DOI 10.4315/0362-028X-70.11.2485"),
        N_("Mejlholm & Dalgaard 2015, Food Microbiol 46:1-14: crescita insieme di L. monocytogenes e batteri "
           "lattici. DOI 10.1016/j.fm.2014.07.005"),
        N_("Le Marc et al. 2002, Int J Food Microbiol 73(2-3):219-237: interazioni fra i fattori (limite di "
           "crescita). DOI 10.1016/S0168-1605(01)00640-7"),
        N_("Zheng et al. 2020, Int J Syst Evol Microbiol 70(4):2782-2858: nuova classificazione dei Lactobacillus "
           "(per esempio Latilactobacillus sakei). DOI 10.1099/ijsem.0.004107"),
        N_("Regolamento (CE) n. 2073/2005 e modifiche, Allegato I, categoria 1.3: alimenti pronti che non favoriscono "
           "la crescita di L. monocytogenes (testo ufficiale su EUR-Lex, CELEX 32005R2073)."),
    ]),
]


class PaginaCrediti(Pagina):
    titolo = N_("Come citare")
    testo_principale = N_("Torna ai progetti")
    destinazione = "home"

    def __init__(self, contesto, parent=None):
        super().__init__(contesto, parent)
        self.corpo.addWidget(etichetta(_("ProfileMetaNanni mette insieme strumenti e database scritti da altri. "
                                         "Ogni referto elenca quelli usati davvero; qui c'è l'elenco completo. Se "
                                         "pubblichi un risultato, cita le fonti che hai usato.")))
        for titolo, voci in FONTI:
            self.corpo.addSpacing(6)
            self.corpo.addWidget(etichetta(_(titolo), "sottotitolo"))
            p, s = pannello()
            for v in voci:
                s.addWidget(etichetta(_(v)))
            self.corpo.addWidget(p)
        self.secondari = [(_("Copia tutte le citazioni"), self.copia)]
        self.aiuto = ""

    def copia(self):
        QGuiApplication.clipboard().setText("\n".join(_(v) for _t, voci in FONTI for v in voci))
        self.aiuto = _("Citazioni copiate: incollale dove ti servono.")
        self.azioni_cambiate.emit()
