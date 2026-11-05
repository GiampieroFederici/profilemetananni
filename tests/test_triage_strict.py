# -*- coding: utf-8 -*-
"""Triage dell'ospite (steps/16) con la stessa regola strict della rimozione (steps/21, F1, KneadData 0.12.5): una
coppia è senza ospite solo se nessuna delle due read si allinea. Prima (--un-conc-gz) contava come senza ospite anche
le coppie con una sola read sull'ospite e le discordanti, e la stima del triage diceva meno ospite di quello che la
rimozione toglie davvero. Bowtie2 e samtools veri (pmn_hostfilter), le coppie di prova di test_ospite_standard.
Gira con la suite del motore nella WSL di sviluppo."""
import os
import subprocess

from test_ospite_standard import HF, RADICE, con_bowtie2, coppie_di_prova, genomi, indice, linux, scrivi_gz  # noqa: F401


@linux
@con_bowtie2
def test_triage_conta_le_coppie_come_la_rimozione(tmp_path, genomi):  # noqa: F811
    coppie, q = coppie_di_prova(genomi)
    r1, r2 = tmp_path / "R1.fastq.gz", tmp_path / "R2.fastq.gz"
    scrivi_gz(r1, [(n, a, q) for n, (a, _b) in coppie.items()])
    scrivi_gz(r2, [(n, b, q) for n, (_a, b) in coppie.items()])
    idx = [indice(tmp_path / "idx", "sus_scrofa", genomi["maiale"]), indice(tmp_path / "idx", "grch38", genomi["uomo"])]
    a = ["--sample", "S", "--in1", r1, "--in2", r2, "--index", idx[0], "--index", idx[1], "--out", tmp_path / "tri",
         "--reads", "100", "--threads", "2"]
    (tmp_path / "t").mkdir()
    p = subprocess.run(["bash", str(RADICE / "steps" / "16_triage_host.sh"), *map(str, a)], capture_output=True,
                       text=True, env={**os.environ, "PATH": f"{HF}:{os.environ['PATH']}", "NO_COLOR": "1",
                                       "PMN_LANG": "en", "TMPDIR": str(tmp_path / "t")})
    assert p.returncode == 0, p.stdout + p.stderr
    # 7 coppie: restano le 2 del taxon, come in 21_hostfilter.sh (test_strict_coppia_tolta_se_una_read_va_sull_ospite)
    assert (tmp_path / "tri" / "S.triage_host.tsv").read_text() == "tested\t7\nnonhost\t2\n"
    assert list((tmp_path / "t").iterdir()) == []
