"""S1-bis passo 1: ricalcolo del MAPQ di Bowtie2 2.5.5 (BowtieMapq2, end-to-end, read singole).

Fonte: bowtie2 v2.5.5 unique.h (classe BowtieMapq2, scelta di default: bt2_search.cpp:486 mapqv = 2),
scoring.h:50-52 (score-min L,-0.6,-0.6), simple_func.h:104-110 (cast a intero), sam.cpp:146-157 (XS:i).
In end-to-end il punteggio perfetto e' 0 (scoring.h:310-312).
Uso: python mapq_bowtie2.py file.sam  -> confronta il MAPQ ricalcolato con quello scritto da Bowtie2.
"""
import sys

# soglie di BowtieMapq2, ramo end-to-end con secondo migliore: (soglia bestdiff, se bestOver==diff, [(soglia bestOver, mapq)...], altrimenti)
_WITH_SEC = [
    (0.9, 39, [], 33),
    (0.8, 38, [], 27),
    (0.7, 37, [], 26),
    (0.6, 36, [], 22),
    (0.5, 35, [(0.84, 25), (0.68, 16)], 5),
    (0.4, 34, [(0.84, 21), (0.68, 14)], 4),
    (0.3, 32, [(0.88, 18), (0.67, 15)], 3),
    (0.2, 31, [(0.88, 17), (0.67, 11)], 0),
    (0.1, 30, [(0.88, 12), (0.67, 7)], 0),
]
_NO_SEC = [(0.8, 42), (0.7, 40), (0.6, 24), (0.5, 23), (0.4, 8), (0.3, 3)]


def f32(x):
    """Le soglie in C++ sono letterali float (0.8f) promossi a double: replico il valore float."""
    import struct
    return struct.unpack("f", struct.pack("f", x))[0]


def score_min(rdlen):
    # SimpleFunc lineare: C + L*x con C = L = -0.6f, poi cast a intero (troncamento verso zero)
    return int(f32(-0.6) + f32(-0.6) * float(rdlen))


def mapq(best, secbest, rdlen):
    """best = AS:i, secbest = XS:i oppure None, rdlen = lunghezza della read."""
    sc_min = score_min(rdlen)
    diff = max(1, 0 - sc_min)
    best_over = best - sc_min
    if secbest is None:
        for t, q in _NO_SEC:
            if best_over >= diff * f32(t):
                return q
        return 0
    bestdiff = abs(abs(best) - abs(secbest))
    for t, top, inner, other in _WITH_SEC:
        if bestdiff >= diff * f32(t):
            if best_over == diff:
                return top
            for t2, q2 in inner:
                if best_over >= diff * f32(t2):
                    return q2
            return other
    if bestdiff > 0:
        return 6 if best_over >= diff * f32(0.67) else 2
    return 1 if best_over >= diff * f32(0.67) else 0


def main(path):
    n = ok = 0
    bad = []
    with open(path) as fh:
        for line in fh:
            if line.startswith("@"):
                continue
            c = line.rstrip("\n").split("\t")
            if int(c[1]) & 4:          # non allineata
                continue
            tags = dict(t.split(":", 2)[0::2] for t in c[11:])
            xs = int(tags["XS"]) if "XS" in tags else None
            q = mapq(int(tags["AS"]), xs, len(c[9]))
            n += 1
            if q == int(c[4]):
                ok += 1
            elif len(bad) < 10:
                bad.append((c[0], c[4], q, tags.get("AS"), xs, len(c[9])))
    print(f"allineamenti: {n}  MAPQ uguali: {ok}  diversi: {n - ok}")
    for b in bad:
        print("DIVERSO", b)


if __name__ == "__main__":
    main(sys.argv[1])
