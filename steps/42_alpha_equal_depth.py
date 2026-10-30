#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# steps/42_alpha_equal_depth.py - alpha diversity at equal depth (R1, 18/10/2026). MetaPhlAn and Kraken SEPARATE.
# Conda env: pmn_reports_py (standard library only; the maths is in motore/diversita.py, the parsers in motore/referto.py).
#
#   sottocampiona --metaphlan-dir DIR --out DIR2
#       MetaPhlAn: for every sample deeper than the shallowest one, writes DIR2/<sample>.mapout = a random subsample
#       (seed 1992) of its reads at the shallowest depth. bin/run.sh then re-runs MetaPhlAn on each of them.
#   calcola --metaphlan-dir DIR [--pari-dir DIR2] [--kraken-dir DIR] --threshold-pct P --out RES
#       writes RES/alpha_diversity_metaphlan.tsv and RES/alpha_diversity_kraken.tsv (one file per tool, never merged):
#       sample, reads, reads_used, status (full | equalized | not_equalized), richness, shannon, simpson.
#       Kraken: only bacteria/archaea/fungi above the threshold (D128), exact expected rarefaction of Bracken reads.
#       MetaPhlAn: no threshold (D128).
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "motore"))
import diversita  # noqa: E402
import referto  # noqa: E402

STATO = {"intero": "full", "pareggiato": "equalized", "non_pareggiato": "not_equalized"}


def mapout(cartella, campione):
    for nome in (f"{campione}.mapout", f"{campione}.bowtie2.bz2"):   # fette (motore/) o standard (steps/30)
        if (Path(cartella) / nome).is_file():
            return Path(cartella) / nome
    return None


def profili(cartella):
    """{campione: ([(specie, %)], read entrate in MetaPhlAn)} dai *_profile.txt di una cartella."""
    out = {}
    for f in sorted(Path(cartella).glob("*_profile.txt")) if cartella and Path(cartella).is_dir() else []:
        out[f.name[:-len("_profile.txt")]] = (referto.leggi_metaphlan(f)[0], diversita.letture_profilo(f))
    return out


def sottocampiona(a):
    # un profilo senza specie (VM B3-3) non entra: la sua profondita' farebbe scendere tutti gli altri
    prof = {s: v for s, v in profili(a.metaphlan_dir).items() if v[0]}
    letture = {s: diversita.letture_mapout(m) if (m := mapout(a.metaphlan_dir, s)) else None for s in prof}
    if len(letture) < 2:
        print("[OK] one MetaPhlAn sample: nothing to equalize")
        return 0
    if any(v is None for v in letture.values()):
        print("[WARN] a MetaPhlAn mapout is missing: alpha diversity stays not_equalized for the deeper samples")
        return 0
    minimo = min(letture.values())
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    for s, n in sorted(letture.items()):
        if n == minimo:
            continue
        f = out / f"{s}.mapout"
        if f.is_file() and diversita.letture_mapout(f) == minimo:   # same seed, same depth: already there
            continue
        tenute = diversita.sottocampiona_mapout(mapout(a.metaphlan_dir, s), f, minimo)
        print(f"[OK] {s}: {minimo} of {n} reads, {tenute} mapped reads kept -> {f}")
    return 0


def scrivi(f, righe):
    with open(f, "w", encoding="utf-8", newline="\n") as t:
        t.write("sample\treads\treads_used\tstatus\trichness\tshannon\tsimpson\n")
        for r in righe:
            t.write(f"{r['campione']}\t{r['letture']}\t{r['letture_usate']}\t{STATO[r['stato']]}\t"
                    f"{r['ricchezza']:.6g}\t{r['shannon']:.6g}\t{r['simpson']:.6g}\n")
    print(f"[OK] {len(righe)} samples -> {f}")


def calcola(a):
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    mpa = diversita.tabella_metaphlan(profili(a.metaphlan_dir), profili(a.pari_dir))
    if mpa:
        scrivi(out / "alpha_diversity_metaphlan.tsv", mpa)
    if a.kraken_dir and Path(a.kraken_dir).is_dir():
        campioni = {f.stem: referto.leggi_kraken(f, f.with_suffix(".k2report"))
                    for f in sorted(Path(a.kraken_dir).glob("*.bracken"))}
        krk = diversita.tabella_kraken(campioni, a.threshold_pct, referto.MICROBI)
        if krk:
            scrivi(out / "alpha_diversity_kraken.tsv", krk)
    return 0


def main():
    ap = argparse.ArgumentParser(description="Alpha diversity at equal depth (MetaPhlAn and Kraken separate).")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sottocampiona")
    s.add_argument("--metaphlan-dir", required=True)
    s.add_argument("--out", required=True)
    c = sub.add_parser("calcola")
    c.add_argument("--metaphlan-dir")
    c.add_argument("--pari-dir")
    c.add_argument("--kraken-dir")
    c.add_argument("--threshold-pct", type=float, required=True)
    c.add_argument("--out", required=True)
    a = ap.parse_args()
    return sottocampiona(a) if a.cmd == "sottocampiona" else calcola(a)


if __name__ == "__main__":
    raise SystemExit(main())
