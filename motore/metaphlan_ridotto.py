"""Database di MetaPhlAn ridotto ai taxa del campione (F3, prototipo N1; NON predefinito: serve il sì di Giampiero).

Perché il profilo resta identico (codice di MetaPhlAn 4.2.4, metaphlan.py, --input_type mapout, opzioni predefinite):
- TaxTree.add_tree_nodes costruisce l'albero da database["taxonomy"], che qui resta intero.
- TaxTree.add_tree_markers mette ogni marcatore nel suo clade con 0 read; add_reads_to_tree conta le read del mapout
  e salta i marcatori che il database non ha.
- TaxClade.compute_coverage: una foglia senza marcatori e una foglia con tutti i marcatori a 0 danno la stessa
  copertura (0) e le stesse read stimate (0); i nodi interni sommano i figli; relative_abundances somma gli 0.0.
- filter_markers_for_ext: una specie esterna senza read ha la frazione di marcatori con read 0 (database intero) o
  nessun marcatore (ridotto): in tutti e due i casi "misidentified" resta falso. Una specie esterna con read è un
  clade del campione, quindi ha tutti i suoi marcatori.
Quindi basta caricare TUTTI i marcatori dei clade che hanno almeno una read nel mapout (anche qualche clade in più
non cambia nulla: ha solo marcatori a 0). Il resto del database (taxonomy, merged_taxon, ...) resta intero.

File derivato (si costruisce una volta dal .pkl ufficiale, con il suo MD5): SQLite con
  meta(chiave, valore)              md5 e dimensione del .pkl, formato, numero di marcatori
  resto(dati)                       pickle del database senza "markers"
  clade(nome, marcatori)            per ogni clade, zlib(pickle([(marcatore, info), ...])) nell'ordine del .pkl
  eccezioni(marcatore, clade)       i marcatori il cui clade non è "t__" + l'ultima parte del nome

Uso: python metaphlan_ridotto.py prepara <file.pkl> <file.sqlite>
"""
import bz2
import gc
import hashlib
import os
import pickle
import sqlite3
import sys
import zlib

FORMATO = "1"


def regola(marcatore):
    return "t__" + marcatore.rsplit("|", 1)[-1]


def md5(percorso):
    h = hashlib.md5()
    with open(percorso, "rb") as f:
        for pezzo in iter(lambda: f.read(1 << 20), b""):
            h.update(pezzo)
    return h.hexdigest()


def prepara(pkl, uscita):
    gc.disable()
    with bz2.BZ2File(pkl, "r") as f:
        db = pickle.load(f)
    gc.enable()
    per_clade, eccezioni = {}, []
    for nome, info in db["markers"].items():
        per_clade.setdefault(info["clade"], []).append((nome, info))
        if info["clade"] != regola(nome):
            eccezioni.append((nome, info["clade"]))
    parziale = uscita + ".parziale"
    if os.path.exists(parziale):
        os.remove(parziale)
    c = sqlite3.connect(parziale)
    c.executescript("CREATE TABLE meta(chiave TEXT PRIMARY KEY, valore TEXT);"
                    "CREATE TABLE resto(dati BLOB);"
                    "CREATE TABLE clade(nome TEXT PRIMARY KEY, marcatori BLOB);"
                    "CREATE TABLE eccezioni(marcatore TEXT PRIMARY KEY, clade TEXT);")
    c.executemany("INSERT INTO meta VALUES (?, ?)", [
        ("formato", FORMATO), ("pkl_md5", md5(pkl)), ("pkl_byte", str(os.path.getsize(pkl))),
        ("marcatori", str(len(db["markers"])))])
    c.execute("INSERT INTO resto VALUES (?)", (pickle.dumps({k: v for k, v in db.items() if k != "markers"}, 4),))
    c.executemany("INSERT INTO clade VALUES (?, ?)",
                  ((k, zlib.compress(pickle.dumps(v, 4), 6)) for k, v in per_clade.items()))
    c.executemany("INSERT INTO eccezioni VALUES (?, ?)", eccezioni)
    c.commit()
    c.close()
    os.replace(parziale, uscita)   # il file prende il suo nome solo quando è intero
    print(f"marcatori {len(db['markers'])}, clade {len(per_clade)}, eccezioni {len(eccezioni)} -> {uscita}")


def viene_da(sqlite, pkl):
    """True se il file derivato è stato costruito da questo .pkl (formato, dimensione e MD5)."""
    try:
        c = sqlite3.connect(f"file:{sqlite}?mode=ro", uri=True)
        meta = dict(c.execute("SELECT chiave, valore FROM meta"))
        c.close()
    except sqlite3.Error:
        return False
    return (meta.get("formato") == FORMATO and meta.get("pkl_byte") == str(os.path.getsize(pkl))
            and meta.get("pkl_md5") == md5(pkl))


def pronto(pkl):
    """Il file derivato accanto al .pkl (<indice>.ridotto.sqlite), costruito ora se manca o se il .pkl è cambiato.
    Una costruzione alla volta (lock); serve una volta sola la memoria della lettura del .pkl intero."""
    import fcntl
    sqlite = pkl[:-len(".pkl")] + ".ridotto.sqlite"
    with open(sqlite + ".lock", "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if not viene_da(sqlite, pkl):
            prepara(pkl, sqlite)
    return sqlite


def riduci(sqlite, pkl, mapout):
    """Il database con i soli marcatori dei clade che hanno read nel mapout (e tutto il resto intero)."""
    if not viene_da(sqlite, pkl):
        raise SystemExit(f"metaphlan_ridotto: {sqlite} non viene da {pkl} (MD5 diverso): rifallo con 'prepara'")
    c = sqlite3.connect(f"file:{sqlite}?mode=ro", uri=True)
    marcatori = set()
    with open(mapout, encoding="utf-8") as f:
        for riga in f:
            if not riga.startswith("#"):
                marcatori.add(riga.rstrip("\n").split("\t")[1])
    cladi = {regola(m) for m in marcatori}
    elenco = sorted(marcatori)
    for i in range(0, len(elenco), 900):   # limite dei parametri di SQLite
        pezzo = elenco[i:i + 900]
        cladi.update(r[0] for r in c.execute(
            f"SELECT clade FROM eccezioni WHERE marcatore IN ({','.join('?' * len(pezzo))})", pezzo))
    db = pickle.loads(c.execute("SELECT dati FROM resto").fetchone()[0])
    db["markers"] = {}
    for (blob,) in (c.execute("SELECT marcatori FROM clade WHERE nome = ?", (k,)).fetchone() or (None,)
                    for k in sorted(cladi)):
        if blob is not None:
            db["markers"].update(pickle.loads(zlib.decompress(blob)))
    c.close()
    return db


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "prepara":
        prepara(sys.argv[2], sys.argv[3])
    else:
        sys.exit(__doc__)
