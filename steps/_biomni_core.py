# -*- coding: utf-8 -*-
# steps/_biomni_core.py - pure logic for Phase C (taxa dossier). No Biomni import here,
# so the whole module is testable offline and at zero cost.
# Conda env: pmn_reports_py (pandas, via _profiling_io). Not meant to be run directly.
import os
import sys
from dataclasses import dataclass, replace

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _profiling_io import load_metaphlan_species, load_kraken_matrix  # noqa: E402

LABELS = ("noto", "assente", "atteso", "ipotesi")
CATEGORIES = ("ruolo", "batteriocine", "ammine_biogene", "cazymes", "resistoma", "virulenza")


@dataclass(frozen=True)
class Citation:
    pmid: str
    title: str
    year: str


@dataclass(frozen=True)
class Claim:
    category: str
    statement: str
    label: str
    refs: tuple          # 1-based indices into RawDossier.references

    def __post_init__(self):
        if self.category not in CATEGORIES:
            raise ValueError(f"unknown category: {self.category}")
        if self.label not in LABELS:
            raise ValueError(f"unknown label: {self.label}")


@dataclass(frozen=True)
class RawDossier:
    taxon: str
    detected_by: str
    claims: tuple
    references: tuple      # ordered Citation objects WE retrieved from NCBI
    ncbi_dropped: int = 0  # PMIDs esearch returned but esummary would not confirm


@dataclass(frozen=True)
class Dossier:
    taxon: str
    detected_by: str
    claims: tuple
    references: tuple
    dropped_refs: int      # reference NUMBERS the model invented (outside 1..N)
    ncbi_dropped: int = 0  # carried through from RawDossier; a different thing entirely


def resolve_citations(raw: RawDossier):
    """Rule 1: the model cites by NUMBER into a list we supplied.

    It never sees a free-form identifier, so it cannot invent a plausible one. A number
    outside 1..len(references) is not evidence — it is dropped and counted.
    Returns (cleaned RawDossier, how many references were dropped).
    """
    n = len(raw.references)
    dropped = 0
    kept = []
    for c in raw.claims:
        good = tuple(i for i in c.refs if isinstance(i, int) and 1 <= i <= n)
        dropped += len(c.refs) - len(good)
        kept.append(replace(c, refs=good))
    return replace(raw, claims=tuple(kept)), dropped


def verify_pmids(pmids, fetch):
    """Rule 2: re-check every PMID against NCBI. Anything we cannot confirm is DROPPED.

    `fetch(pmid)` returns a Citation or None; it is injected so tests never hit the network.
    A network error drops the citation: silence is not confirmation.
    """
    confirmed = {}
    dropped = []
    for pmid in sorted(pmids):
        try:
            cit = fetch(pmid)
        except Exception:
            cit = None
        if cit is None or not cit.title:
            dropped.append(pmid)
        else:
            confirmed[pmid] = cit
    return confirmed, dropped


def apply_labels(claims):
    """Rule 3: 'noto' and 'assente' require at least one SURVIVING reference number.

    Without one the claim is rewritten to 'ipotesi', whatever the model answered.
    'atteso' is an explicit inference and needs no citation.
    """
    out = []
    for c in claims:
        if c.label in ("noto", "assente") and not c.refs:
            out.append(replace(c, label="ipotesi"))
        else:
            out.append(c)
    return tuple(out)


def build_dossier(raw: RawDossier) -> Dossier:
    """Apply the anti-invention rules in order and return a finished Dossier.

    The references were retrieved and verified by the client BEFORE the model saw them,
    so there is nothing left to fetch here: resolve the numbers, then demote what has no
    surviving reference.
    """
    resolved, dropped = resolve_citations(raw)
    return Dossier(
        taxon=resolved.taxon,
        detected_by=resolved.detected_by,
        claims=apply_labels(resolved.claims),
        references=resolved.references,
        dropped_refs=dropped,
        ncbi_dropped=resolved.ncbi_dropped,
    )


def _display(normalized: str) -> str:
    """Turn a normalized name ('latilactobacillus sakei') into a display name."""
    return normalized[:1].upper() + normalized[1:] if normalized else normalized


def select_taxa(metaphlan_path: str, kraken_path: str, threshold_pct: float, max_taxa: int):
    """Return [(display_name, detected_by)], capped at max_taxa. The threshold is for Kraken only:
    MetaPhlAn is never filtered (D128), every species it finds is kept.

    detected_by is 'metaphlan', 'kraken' or 'metaphlan+kraken'. Ordering is by descending
    max abundance across the tools, then alphabetical, so the cap keeps the most abundant.
    """
    mpa = load_metaphlan_species(metaphlan_path, 0.0) if metaphlan_path else {}
    krk = load_kraken_matrix(kraken_path, threshold_pct) if kraken_path else {}
    rows = []
    for name in set(mpa) | set(krk):
        if name in mpa and name in krk:
            src = "metaphlan+kraken"
        elif name in mpa:
            src = "metaphlan"
        else:
            src = "kraken"
        rows.append((_display(name), src, max(mpa.get(name, 0.0), krk.get(name, 0.0))))
    rows.sort(key=lambda r: (-r[2], r[0]))
    return [(name, src) for name, src, _ in rows[:max_taxa]]


# The two counts below measure DIFFERENT things and used to share one line, which said
# "scartate" of a number that never had anything to do with NCBI. Keep them apart:
#   confirmed / ncbi_dropped -> fonti che NOI abbiamo cercato e ricontrollato su NCBI
#   invented_refs            -> numeri di riferimento che il MODELLO si e' inventato
_HEADER = (
    "> ATTENZIONE: documento generato da un modello linguistico (LLM), non da un esperto.\n"
    "> Modello: {model} ({provider}) · Data: {date} · Taxa analizzati: {n_taxa}\n"
    "> Fonti ricontrollate su NCBI: {confirmed} confermate, {ncbi_dropped} rifiutate da NCBI.\n"
    "> Numeri di riferimento inventati dal modello e scartati: {invented_refs}.\n"
    "> Le righe \"atteso\" e \"ipotesi\" NON sono prove. Vanno verificate a mano.\n\n"
)


def _pmids(claim, references):
    """Map surviving 1-based reference numbers back to the PMIDs we retrieved."""
    return [references[i - 1].pmid for i in claim.refs]


def render_markdown(dossiers, meta) -> str:
    """Human-readable dossier. Only references WE retrieved are ever printed as evidence."""
    parts = [_HEADER.format(**meta)]
    for d in dossiers:
        parts.append(f"## {d.taxon}\n")
        parts.append(f"Rilevato da: {d.detected_by}\n\n")
        for c in d.claims:
            proof = _pmids(c, d.references)
            refs = "  [" + "; ".join(f"PMID {p}" for p in proof) + "]" if proof else ""
            parts.append(f"- {c.category}: {c.statement}  ({c.label}){refs}\n")
        if d.references:
            parts.append("\nFonti consultate:\n")
            for i, cit in enumerate(d.references, 1):
                parts.append(f"  [{i}] PMID {cit.pmid} — {cit.title} ({cit.year})\n")
        parts.append("\n")
    return "".join(parts)


def render_tsv(dossiers) -> str:
    """Machine-readable dossier: one row per claim."""
    rows = ["taxon\trilevato_da\tcategoria\taffermazione\tetichetta\tcitazioni_verificate"]
    for d in dossiers:
        for c in d.claims:
            proof = ";".join(_pmids(c, d.references))
            rows.append(f"{d.taxon}\t{d.detected_by}\t{c.category}\t{c.statement}\t{c.label}\t{proof}")
    return "\n".join(rows) + "\n"
