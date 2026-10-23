"""Diversità alfa a profondità uguale (R1, 18/10/2026): ricchezza, Shannon, Simpson.

La ricchezza (taxa osservati) cresce con il numero di read: per confrontare campioni si usa la stessa profondità, quella
del campione più povero (rarefazione, Schloss 2024, mSphere 9:e00354-23). MetaPhlAn e Kraken SEMPRE separati.
- Kraken: letture stimate da Bracken dei soli taxa del prodotto (batteri, archei, funghi) sopra la soglia D128;
  indici = valore atteso esatto della rarefazione (media di tutte le estrazioni possibili: niente seme, niente rumore).
- MetaPhlAn: nessuna soglia (D128). Profondità = read entrate in MetaPhlAn; i campioni più ricchi si sottocampionano
  sul mapout (seme 1992, come --subsampling_seed di MetaPhlAn) e MetaPhlAn si rifà da lì (steps/42_alpha_equal_depth.py).
Simpson = 1 - somma(p^2) e Shannon col logaritmo naturale, come vegan::diversity (steps/41_diversity.R prima di R1).
Solo libreria standard.
"""
import bz2
import math
import random
import re
from pathlib import Path

SEME = 1992


def indici(abbondanze):
    """{"ricchezza", "shannon", "simpson"} di un campione (conteggi o percentuali, gli zeri non contano)."""
    x = [a for a in abbondanze if a > 0]
    tot = sum(x)
    p = [a / tot for a in x] if tot else []
    return {"ricchezza": len(p), "shannon": -sum(q * math.log(q) for q in p),   # 0 taxa: Simpson 0 come Shannon
            "simpson": 1 - sum(q * q for q in p) if p else 0.0}


def _lnc(n, k):
    return math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)


def rarefazione_attesa(conteggi, n):
    """Valore atteso dei 3 indici in un sottocampione casuale di n letture senza reinserimento, calcolato in modo
    esatto: ogni taxon con Ni letture su N ne ha k nel sottocampione con probabilità ipergeometrica. Ricchezza e
    Simpson hanno una formula chiusa; per Shannon si somma sui k possibili (fuori da media +- 12 deviazioni standard
    la probabilità è trascurabile)."""
    c = [int(a) for a in conteggi if a > 0]
    tot = sum(c)
    if n >= tot:
        return indici(c)
    base = _lnc(tot, n)
    ricchezza = shannon = somma_p2 = 0.0
    for ni in c:
        resto = tot - ni
        ricchezza += 1 - (math.exp(_lnc(resto, n) - base) if resto >= n else 0.0)
        media = n * ni / tot
        varianza = n * (ni / tot) * (1 - ni / tot) * (tot - n) / (tot - 1)
        somma_p2 += (varianza + media * media) / (n * n)
        ds = math.sqrt(varianza)
        da = max(1, n - resto, math.floor(media - 12 * ds) - 1)
        a = min(ni, n, math.ceil(media + 12 * ds) + 1)
        for k in range(da, a + 1):
            pk = math.exp(_lnc(ni, k) + _lnc(resto, n - k) - base)
            shannon -= pk * (k / n) * math.log(k / n)
    return {"ricchezza": ricchezza, "shannon": shannon, "simpson": 1 - somma_p2}


def _riga(nome, letture, usate, stato, valori):
    return {"campione": nome, "letture": letture, "letture_usate": usate, "stato": stato, **valori}


def tabella_kraken(campioni, soglia, categorie):
    """[righe] per campione da {nome: righe di referto.leggi_kraken}: solo i taxa delle categorie (batteri, archei,
    funghi) con pct >= soglia, a profondità uguale (la somma delle loro letture nel campione più povero).
    stato: "intero" (il campione più povero, o l'unico), "pareggiato"."""
    conteggi = {n: [r["letture"] for r in righe if r["categoria"] in categorie and r["pct"] >= soglia
                    and r["letture"] > 0] for n, righe in campioni.items()}
    pieni = {n: c for n, c in conteggi.items() if sum(c) > 0}
    if not pieni:
        return []
    usate = min(sum(c) for c in pieni.values())
    return [_riga(n, sum(c), usate, "intero" if sum(c) == usate else "pareggiato", rarefazione_attesa(c, usate))
            for n, c in sorted(pieni.items())]


def tabella_metaphlan(profili, pari):
    """[righe] da {nome: ([(specie, %)], read entrate in MetaPhlAn)} e dai profili rifatti a profondità uguale
    {nome: (specie, read)}. Nessuna soglia. Un campione più ricco senza il profilo rifatto alla profondità giusta
    resta "non_pareggiato", con i valori alla sua profondità (si dice, non si stima)."""
    validi = {n: v for n, v in profili.items() if v[1]}
    if not validi:
        return []
    usate = min(v[1] for v in validi.values())
    out = []
    for n, (specie, letture) in sorted(validi.items()):
        if letture == usate:
            out.append(_riga(n, letture, usate, "intero", indici([p for _, p in specie])))
        elif n in pari and pari[n][1] == usate:
            out.append(_riga(n, letture, usate, "pareggiato", indici([p for _, p in pari[n][0]])))
        else:
            out.append(_riga(n, letture, letture, "non_pareggiato", indici([p for _, p in specie])))
    return out


def letture_profilo(profilo):
    """Read entrate in MetaPhlAn ("#2731766 reads processed" nell'intestazione del profilo), o None."""
    for riga in Path(profilo).read_text(encoding="utf-8").splitlines()[:10]:
        m = re.match(r"#(\d+) reads processed", riga)
        if m:
            return int(m.group(1))
    return None


def _apri(f):
    return bz2.open(f, "rt", encoding="utf-8") if str(f).endswith(".bz2") else open(f, encoding="utf-8")


def letture_mapout(mapout):
    """#nreads del mapout di MetaPhlAn (read entrate), o None."""
    with _apri(mapout) as f:
        for riga in f:
            if riga.startswith("#nreads"):
                return int(riga.split("\t")[1])
    return None


def sottocampiona_mapout(entrata, uscita, profondita, seme=SEME):
    """Scrive in `uscita` il mapout di un sottocampione casuale di `profondita` read (senza reinserimento) delle N read
    entrate in MetaPhlAn. Ogni read si allinea da sola, quindi togliere una read prima o dopo l'allineamento dà lo
    stesso risultato: si estraggono gli indici delle read (come --subsampling di MetaPhlAn) e si tengono le righe
    delle read allineate scelte. Le read si ordinano per nome (Bowtie2 con più processori cambia l'ordine): stesso
    seme, stesso sottocampione. Restituisce quante read allineate restano."""
    righe, n_read, lunghezza = {}, None, None
    with _apri(entrata) as f:
        for r in f:
            r = r.rstrip("\n")
            if r.startswith("#nreads"):
                n_read = int(r.split("\t")[1])
            elif r.startswith("#avg_read_length"):
                lunghezza = r.split("\t")[1]
            elif r:
                righe.setdefault(r.split("\t")[0], []).append(r)
    if n_read is None or not 0 < profondita <= n_read or len(righe) > n_read:
        raise ValueError(f"profondità {profondita} non valida per {n_read} read")
    rnd, servono, tenute = random.Random(seme), profondita, []
    for i, nome in enumerate(sorted(righe)):   # algoritmo di selezione sequenziale (Knuth, "S"): uniforme sugli insiemi
        if rnd.random() * (n_read - i) < servono:
            tenute.append(nome)
            servono -= 1
    with open(uscita, "w", encoding="utf-8", newline="\n") as f:
        for nome in tenute:
            f.write("\n".join(righe[nome]) + "\n")
        f.write(f"#nreads\t{profondita}\n")
        if lunghezza is not None:
            f.write(f"#avg_read_length\t{lunghezza}\n")
    return len(tenute)
