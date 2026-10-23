# -*- coding: utf-8 -*-
"""Le frasi da tradurre: i testi dentro _("...") e N_("...") del codice (sessione Lingua IT/EN, 18/10/2026).

Due cataloghi, perché app e motore si installano in posti diversi (Windows e WSL):
  app/risorse/lingua_en.json   app/ e app/pagine/
  motore/lingua_en.json        motore/, motore/fssp/, steps/45_previsione_fssp.py, installer/finto_motore.py
                               e le fonti di refs/kraken_profili.tsv (il referto le mostra)
  python tests/lingua_chiavi.py     elenca le frasi che mancano nei due cataloghi
"""
import ast
import json
import re
import sys
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
CATALOGHI = {
    "app": (RADICE / "app" / "risorse" / "lingua_en.json",
            sorted((RADICE / "app").glob("*.py")) + sorted((RADICE / "app" / "pagine").glob("*.py"))),
    "motore": (RADICE / "motore" / "lingua_en.json",
               sorted((RADICE / "motore").glob("*.py")) + sorted((RADICE / "motore" / "fssp").glob("*.py"))
               + [RADICE / "steps" / "45_previsione_fssp.py", RADICE / "installer" / "finto_motore.py"]),
}


def chiavi_file(f):
    """{testo: riga} dei testi letterali passati a _() o N_() in un file Python."""
    out = {}
    for n in ast.walk(ast.parse(Path(f).read_text(encoding="utf-8"))):
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in ("_", "N_") and n.args
                and isinstance(n.args[0], ast.Constant) and isinstance(n.args[0].value, str)):
            out.setdefault(n.args[0].value, n.lineno)
    return out


def fonti_kraken():
    """Le fonti di refs/kraken_profili.tsv (quinta colonna): il referto le traduce come le altre frasi."""
    righe = (RADICE / "refs" / "kraken_profili.tsv").read_text(encoding="utf-8").splitlines()
    return [r.split("\t")[4] for r in righe if r.strip() and not r.startswith("#") and len(r.split("\t")) > 4]


def chiavi(nome):
    """{testo: "file:riga"} di un catalogo."""
    out = {}
    for f in CATALOGHI[nome][1]:
        for testo, riga in chiavi_file(f).items():
            out.setdefault(testo, f"{f.relative_to(RADICE).as_posix()}:{riga}")
    if nome == "motore":
        for testo in fonti_kraken():
            out.setdefault(testo, "refs/kraken_profili.tsv")
    return out


def catalogo(nome):
    f = CATALOGHI[nome][0]
    return json.loads(f.read_text(encoding="utf-8")) if f.is_file() else {}


def segnaposto(testo):
    """I {campi} di str.format in un testo: devono essere gli stessi in italiano e in inglese."""
    return sorted(re.findall(r"\{([^{}]*)\}", testo))


if __name__ == "__main__":
    for nome in CATALOGHI:
        c, k = catalogo(nome), chiavi(nome)
        mancano = {t: dove for t, dove in k.items() if t not in c}
        print(f"== {nome}: {len(k)} frasi, {len(mancano)} senza traduzione, {len(set(c) - set(k))} in più")
        if "--json" in sys.argv:
            print(json.dumps(mancano, ensure_ascii=False, indent=1))
