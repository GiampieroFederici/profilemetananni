# -*- coding: utf-8 -*-
# Hermetic tests for the ONE thing in _biomni_client.py that can be checked without a network:
# how the PubMed query is assembled. Importing the module is safe - biomni is imported inside
# BiomniClient.__init__, never at module level.
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "steps"))

import _biomni_client as client  # noqa: E402


def test_the_species_is_required_not_merely_preferred():
    """AND, not OR. With OR the query would return the whole fermented-meat literature and
    the agent would be handed papers that have nothing to do with the species it was asked
    about - every dossier would look well-cited and be wrong."""
    term = client.search_term("Latilactobacillus sakei")
    head, sep, domain = term.partition(" AND ")
    assert sep == " AND ", term
    assert head == '"Latilactobacillus sakei"[tiab]'
    assert domain.startswith("(") and domain.endswith(")")
    assert " AND " not in domain          # the domain is one OR group, nothing sneaks in
    assert " OR " not in head


def test_every_domain_term_is_restricted_to_title_and_abstract():
    """An untagged term searches every field (author names, affiliations, journal titles):
    'Salame' as a surname would then qualify a paper as fermented-meat literature."""
    domain = client.search_term("X").partition(" AND ")[2]
    pieces = domain[1:-1].split(" OR ")
    assert len(pieces) == len(client._DOMAIN_TERMS)
    for p in pieces:
        assert re.fullmatch(r'"[^"]+"\[tiab\]', p), p
