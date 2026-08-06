# -*- coding: utf-8 -*-
# steps/_biomni_client.py - the ONLY module that talks to Biomni and to NCBI over the network.
# Conda env: pmn_biomni. Imported late by 50_biomni_dossier.py so the pure logic stays testable.
#
# We do the literature search ourselves. Biomni's query_pubmed searches PubMed for real but
# returns only Title/Abstract/Journal - the PMID never appears in its return value, which would
# make every citation untraceable. So: esearch -> esummary -> a NUMBERED reference list handed
# to the agent, which cites by number and never sees a free-form identifier.
import json
import urllib.parse
import urllib.request

import _biomni_core as core

_EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

# The fermented-meat literature is not written only in English: a paper on ciauscolo, chorizo
# or sucuk may never contain the word "sausage". Every term below was counted on PubMed before
# being added; the ones left out were left out for a measured reason, not by oversight:
#   embutido, "lap cheong"    -> 0 records in title/abstract: they would add nothing
#   coppa                     -> ambiguous; 5 of the first 6 hits are chemistry, oncology,
#                                entomology and a privacy law, not the salume
#   "fermented sausage"[MeSH] -> not a MeSH heading at all (esearch: phrase not found)
#   "Meat Products"[MeSH]     -> adds real records (+9 for L. sakei, +36 for S. xylosus) but
#                                also fresh-meat spoilage work, which is a different domain
# The trade is recall for precision. It stays cheap: the taxon is required in the same query,
# and every citation that survives is still re-checked against NCBI in build_references.
_DOMAIN_TERMS = (
    "fermented meat", "sausage", "salami", "dry-cured", "cured meat", "charcuterie",
    "salame", "ciauscolo", "soppressata", "bresaola",       # it
    "chorizo", "salchichon", "sobrasada", "fuet",           # es
    "saucisson",                                            # fr
    "linguica", "alheira",                                  # pt
    "sucuk", "sujuk", "pastirma",                           # tr
    "Rohwurst",                                             # de
    "Chinese sausage",                                      # zh
)
_DOMAIN = "(" + " OR ".join(f'"{t}"[tiab]' for t in _DOMAIN_TERMS) + ")"

_PROMPT = """You are given ONE microbial species: "{taxon}", and a NUMBERED list of papers.
Use ONLY these papers as evidence. Do not use any other source.

{refs}

Return ONLY valid JSON, no prose, with this exact shape:
{{"claims":[{{"category":"ruolo|batteriocine|ammine_biogene|cazymes|resistoma|virulenza",
"statement":"one short sentence","label":"noto|assente|atteso","refs":[1,3]}}]}}

Rules:
- "refs" holds NUMBERS from the list above. Never write a PubMed ID or a DOI.
- Use label "noto" or "assente" ONLY when a listed paper supports it, and cite its number.
- With no supporting paper, use label "atteso" (inference from the genus) and "refs": [].
"""


def search_term(taxon: str) -> str:
    """The species is REQUIRED (AND); the domain is one OR group. Widening the domain must
    never turn into 'this species OR anything about salami' - that would hand the agent the
    whole fermented-meat literature as if it were about the taxon."""
    return f'"{taxon}"[tiab] AND {_DOMAIN}'


def pubmed_search(taxon: str, retmax: int = 12):
    """esearch restricted to the fermented-meat domain. Returns a list of PMID strings."""
    term = search_term(taxon)
    url = (f"{_EUTILS}/esearch.fcgi?db=pubmed&retmode=json&retmax={int(retmax)}"
           f"&term={urllib.parse.quote(term)}")
    with urllib.request.urlopen(url, timeout=30) as r:
        data = json.load(r)
    return list(data.get("esearchresult", {}).get("idlist", []))


def ncbi_fetch(pmid: str):
    """esummary for one PMID. Returns a Citation, or None when NCBI has no usable record."""
    url = (f"{_EUTILS}/esummary.fcgi?db=pubmed&retmode=json&id={urllib.parse.quote(pmid)}")
    with urllib.request.urlopen(url, timeout=30) as r:
        data = json.load(r)
    rec = data.get("result", {}).get(pmid)
    if not rec or not rec.get("title"):
        return None
    return core.Citation(pmid, rec["title"], (rec.get("pubdate", "") or "")[:4])


def build_references(taxon: str):
    """Search, then keep only the PMIDs esummary can actually confirm (Task 3's rule 2).

    Returns (references, how many PMIDs NCBI refused to confirm). The second number is
    reported separately: it is not the same thing as a reference number the model invented.
    """
    confirmed, dropped = core.verify_pmids(set(pubmed_search(taxon)), ncbi_fetch)
    refs = tuple(sorted(confirmed.values(), key=lambda c: (c.year, c.pmid), reverse=True))
    return refs, len(dropped)


def _extract_json(text: str) -> str:
    """A1 may wrap the JSON in prose or a fence; take the outermost object."""
    s, e = text.find("{"), text.rfind("}")
    if s < 0 or e <= s:
        raise ValueError("the model did not return JSON")
    return text[s:e + 1]


class BiomniClient:
    def __init__(self, llm: str, data_path: str = ""):
        from biomni.agent import A1
        self._agent = A1(path=data_path or "./biomni_data", llm=llm)

    def ask(self, taxon: str, detected_by: str) -> core.RawDossier:
        refs, ncbi_dropped = build_references(taxon)
        listing = "\n".join(
            f"[{i}] {c.title} ({c.year})" for i, c in enumerate(refs, 1)
        ) or "(no papers found for this species in this domain)"
        answer = self._agent.go(_PROMPT.format(taxon=taxon, refs=listing))
        payload = json.loads(_extract_json(answer))
        claims = tuple(
            core.Claim(c["category"], c["statement"], c["label"],
                       tuple(i for i in c.get("refs", []) if isinstance(i, int)))
            for c in payload.get("claims", [])
            if c.get("category") in core.CATEGORIES and c.get("label") in core.LABELS
        )
        return core.RawDossier(taxon, detected_by, claims, refs, ncbi_dropped)
