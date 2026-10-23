"""Arbitro delle fette: unisce gli allineamenti Bowtie2 di piu' fette come se l'indice fosse intero.

Comandi:
  compatta  < file.sam > fetta.tsv
      tiene solo le righe allineate e primarie; colonne: read, marker, AS, XS ('' se assente), lunghezza, MAPQ di Bowtie2
  unisci    nreads.txt uscita.mapout fetta1.tsv [fetta2.tsv ...]
      per ogni read: migliore = AS piu' alto fra le fette; secondo = max(XS della fetta vincente, AS delle altre fette);
      MAPQ ricalcolato con la formula di Bowtie2 (mapq_bowtie2.py); filtro di MetaPhlAn (metaphlan.py:842-875).
      Con una sola fetta usa il MAPQ scritto da Bowtie2 (e' il riferimento "indice intero").
  confronta a.mapout b.mapout
      read tenute da entrambi con lo stesso marker / con marker diverso / solo in a / solo in b

Il formato .mapout e' quello di MetaPhlAn (metaphlan.py:815-829): "read<TAB>marker" e in coda #nreads e #avg_read_length.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mapq_bowtie2 import mapq  # noqa: E402

MIN_MAPQ = 5  # metaphlan.py:2279 (read corte)


def passa_filtro(marker, q):
    # metaphlan.py:860-875 mapq_filter: GeneID/VDB passano sempre, gli altri servono MAPQ > 5
    return "GeneID:" in marker or "VDB" in marker or q > MIN_MAPQ


def compatta():
    out = sys.stdout
    for line in sys.stdin:
        if line.startswith("@"):
            continue
        c = line.rstrip("\n").split("\t")
        flag = int(c[1])
        if flag & 4 or flag & 0x100 or c[2].endswith("*"):
            continue
        tags = dict(t.split(":", 2)[0::2] for t in c[11:])
        out.write(f"{c[0]}\t{c[2].split('/')[0]}\t{tags['AS']}\t{tags.get('XS', '')}\t{len(c[9])}\t{c[4]}\n")


def unisci(nreads_file, out_path, fette):
    best = {}  # read -> [AS, XS, marker, lunghezza, mapq_bowtie2, fetta, secondo_da_altre]
    for k, f in enumerate(fette):
        with open(f) as fh:
            for line in fh:
                r, m, a, x, ln, q = line.rstrip("\n").split("\t")
                a = int(a)
                x = int(x) if x else None
                cur = best.get(r)
                if cur is None:
                    best[r] = [a, x, m, int(ln), int(q), k, None]
                elif a > cur[0]:
                    # la nuova fetta vince: il vecchio migliore diventa un rivale da un'altra fetta
                    other = cur[0] if cur[6] is None else max(cur[0], cur[6])
                    best[r] = [a, x, m, int(ln), int(q), k, other]
                else:
                    cur[6] = a if cur[6] is None else max(cur[6], a)
    tenute = 0
    with open(out_path, "w") as fo:
        for r, (a, x, m, ln, qbt, _k, other) in best.items():
            if len(fette) == 1:
                q = qbt
            else:
                cands = [v for v in (x, other) if v is not None]
                q = mapq(a, max(cands) if cands else None, ln)
            if passa_filtro(m, q):
                fo.write(f"{r}\t{m}\n")
                tenute += 1
        with open(nreads_file) as fh:
            nreads, avg, _ = fh.read().split()
        fo.write(f"#nreads\t{int(float(nreads))}\n#avg_read_length\t{float(avg)}")
    print(f"read allineate in almeno una fetta: {len(best)}; tenute dopo il filtro MetaPhlAn: {tenute}")


def leggi(path):
    d = {}
    with open(path) as fh:
        for line in fh:
            if not line.startswith("#"):
                r, m = line.rstrip("\n").split("\t")
                d[r] = m
    return d


def confronta(a_path, b_path):
    a, b = leggi(a_path), leggi(b_path)
    comuni = a.keys() & b.keys()
    uguali = sum(1 for r in comuni if a[r] == b[r])
    print(f"tenute in A: {len(a)}  in B: {len(b)}")
    print(f"in entrambe, stesso marker: {uguali}")
    print(f"in entrambe, marker diverso: {len(comuni) - uguali}")
    print(f"solo in A: {len(a.keys() - b.keys())}  solo in B: {len(b.keys() - a.keys())}")
    tot = len(a.keys() | b.keys())
    print(f"concordanza: {100 * uguali / tot:.4f} % delle read tenute da almeno uno")


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "compatta":
        compatta()
    elif cmd == "unisci":
        unisci(sys.argv[2], sys.argv[3], sys.argv[4:])
    elif cmd == "confronta":
        confronta(sys.argv[2], sys.argv[3])
    else:
        sys.exit(__doc__)
