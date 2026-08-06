#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# steps/50_biomni_dossier.py - Phase C: build a per-taxon dossier via a Biomni A1 agent.
# Conda env: pmn_biomni (biomni + pandas). OPTIONAL step, off by default.
#
# Only NORMALIZED SPECIES NAMES ever leave the machine. No samples, no SRR, no paths,
# no abundances, no reads. Consent is asked once per project and recorded in
# <work-dir>/.biomni_consent.json. API keys are read from the environment or from
# ~/.pmn/credentials and are never written to any output.
#
# Usage:
#   50_biomni_dossier.py [--metaphlan MERGED.txt] [--kraken MATRIX.tsv] --out DIR
#                        --llm MODEL --work-dir DIR [--threshold-pct 0.001]
#                        [--max-taxa 5] [--dry-run] [--yes-send-taxa]
import argparse
import getpass
import json
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _biomni_core as core          # noqa: E402
import _biomni_consent as consent    # noqa: E402


def _fail(msg: str) -> int:
    print(f"[FAIL] {msg}", file=sys.stderr)
    return 1


def _ask_consent(llm, provider, taxa, ask, show):
    """Show exactly what is about to leave, say that it costs, and require an explicit yes."""
    if provider.local:
        show(f"\n  Fase C · Biomni — modello LOCALE\n"
             f"  Modello : {llm}  (gira sul tuo computer)\n"
             f"  Costo   : ZERO\n"
             f"  Dati    : NON escono dal tuo computer\n"
             f"  Nota    : su questo compito un modello locale sbaglia più di uno grande.\n")
    else:
        show(f"\n  Fase C · Biomni — ATTENZIONE: QUESTA OPERAZIONE TI COSTA SOLDI\n"
             f"  Modello scelto da TE : {llm}  ({provider.label})\n"
             f"  Chi paga             : TU, con la tua {provider.env_var}\n"
             f"  Quanto costa         : NON è prevedibile in anticipo.\n"
             f"                         L'agente ragiona a più passaggi.\n"
             f"  Esce dal tuo PC      : {len(taxa)} nomi di specie\n"
             f"  NON esce             : campioni, SRR, path, abbondanze, FASTQ\n"
             f"  Alternativa gratuita : un modello locale (ollama/...), costo zero,\n"
             f"                         nessun dato fuori, ma sbaglia di più.\n")
    return ask("  Procedo, e accetto il costo? [s/N] ").strip().lower() in ("s", "si", "sì", "y")


_LOCAL_GUIDE = (
    "\n  MODELLO LOCALE — gratis, nessun dato esce dal tuo computer.\n"
    "   1. Scarica Ollama da  https://ollama.com/download\n"
    "   2. Apri il terminale e scarica un modello:   ollama pull <modello>\n"
    "   3. Scrivi in config.yaml:   llm: \"ollama/<modello>\"\n"
    "   4. Rilancia:  bash bin/run.sh --config config.yaml --phase c\n"
    "\n  Nota onesta: su un compito di ragionamento come questo un modello locale\n"
    "  sbaglia più di un modello grande a pagamento. Guadagni privacy e costo zero,\n"
    "  perdi in qualità.\n"
)


def _setup_api_key(llm, provider, cred_path, ask, show, ask_secret, check_key):
    """SPEC 6.4: when the key is missing the tool does not fail — it teaches.

    Returns the key, or None if the user gave up or the key does not work. The key is only
    ever handed to store_credential and returned: it is never shown, printed or logged, and
    the paste itself is masked (ask_secret), so it never appears on screen either.
    """
    show(f"\n  Fase C · serve una chiave API\n"
         f"  Hai scelto il modello : {llm}  (fornitore: {provider.label})\n"
         f"  Per usarlo serve una TUA chiave personale. Non l'ho trovata.\n"
         f"\n"
         f"  COME OTTENERLA — circa 3 minuti:\n"
         f"   1. Apri  {provider.console_url}\n"
         f"   2. Registrati o accedi\n"
         f"   3. Crea una nuova chiave e COPIALA\n"
         f"   4. ATTENZIONE: serve un metodo di pagamento attivo sul tuo account,\n"
         f"      altrimenti la chiave non funziona.\n"
         f"\n"
         f"  Oppure:  [L] uso un modello LOCALE gratis   ·   [A] annulla\n")
    key = ask_secret("  Incolla qui la chiave (NON verrà mostrata mentre la scrivi): ").strip()
    if key.lower() == "l":
        show(_LOCAL_GUIDE)
        return None
    if not key or key.lower() == "a":
        show("  Annullato: non è stato inviato niente.")
        return None

    # Verify BEFORE offering to store it, so an invalid key is never left behind in the
    # credentials file to be picked up silently by the next run.
    show("\n  Verifico la chiave...")
    status = check_key(provider, key)
    if status is None:
        show("  Questo fornitore non si può verificare con una sola chiamata: proseguo.")
    elif status:
        show("  " + consent.translate_provider_error(status))
        return None
    else:
        show("  OK — la chiave funziona.")

    show(f"\n  Dove salvo la chiave?\n"
         f"   [1] {cred_path}   (consigliato)\n"
         f"       File riservato, fuori dalla cartella del progetto, mai su Git.\n"
         f"       Le prossime volte non ti chiederò più nulla.\n"
         f"   [2] da nessuna parte\n"
         f"       La uso solo per questa esecuzione. Dovrai reincollarla ogni volta.\n")
    if ask("  Scelta [1/2]: ").strip() == "1":
        warning = consent.store_credential(cred_path, provider.env_var, key)
        show(("  " + warning) if warning else f"  Salvata in {cred_path} (permessi 600).")
    return key


class _LazyClient:
    """Defer building the Biomni agent until a taxon is actually asked.

    A1(...) downloads an ~11GB data lake on construction. Nothing may be fetched before
    --dry-run has been honoured and the consent gate and API key have both passed.
    """

    def __init__(self, llm: str):
        self._llm = llm
        self._client = None

    def ask(self, taxon: str, detected_by: str):
        if self._client is None:
            from _biomni_client import BiomniClient   # heavy import, deferred
            self._client = BiomniClient(self._llm)
        return self._client.ask(taxon, detected_by)


def run(metaphlan, kraken, out, llm, work_dir, threshold_pct, max_taxa,
        dry_run, assume_yes, client, environ, interactive,
        cred_path=None, ask=input, show=print,
        ask_secret=getpass.getpass, check_key=consent.check_api_key):
    """Everything is injected (client, environ, interactive, cred_path, ask, show,
    ask_secret, check_key) so tests are hermetic and cost nothing."""
    try:
        provider = consent.provider_for(llm)
    except ValueError as e:
        return _fail(str(e))

    taxa = core.select_taxa(metaphlan, kraken, threshold_pct, max_taxa)
    if not taxa:
        return _fail("no taxa above the abundance threshold: nothing to do")

    if dry_run:
        print(f"DRY-RUN: {len(taxa)} species would be sent to {llm} ({provider.label}).")
        print("Nothing else leaves this machine. Species:")
        for name, _src in taxa:
            print(f"  - {name}")
        return 0

    cred = cred_path or consent.credentials_path()
    key = consent.resolve_api_key(provider, environ, cred)
    if key is None and interactive:
        key = _setup_api_key(llm, provider, cred, ask, show, ask_secret, check_key)
    if key is None:
        return _fail(
            f"no API key for {provider.label}. Set {provider.env_var} in your environment, "
            f"or create one at {provider.console_url}"
        )
    # The provider SDK reads its key from the process environment, so a key that came from
    # ~/.pmn/credentials or from the wizard above has to be put there before the client is
    # built - otherwise it is resolved, checked, and then thrown away. setdefault, so a key
    # the user already exported always wins.
    if key and not provider.local:
        environ.setdefault(provider.env_var, key)

    rec_path = consent.consent_record_path(work_dir)
    record = json.loads(rec_path.read_text(encoding="utf-8")) if rec_path.exists() else None
    if not consent.consent_is_valid(record, llm, provider):
        if assume_yes:
            consent.save_consent(rec_path, llm, provider, len(taxa))
        elif not interactive:
            return _fail(
                "Phase C needs your consent before any species name leaves this machine, "
                "and there is no terminal to ask on. Re-run with --yes-send-taxa."
            )
        elif _ask_consent(llm, provider, taxa, ask, show):
            consent.save_consent(rec_path, llm, provider, len(taxa))
        else:
            show("  Nessun problema: non è stato inviato niente.")
            return 0

    dossiers, confirmed, dropped = [], 0, 0
    for name, src in taxa:
        d = core.build_dossier(client.ask(name, src))
        dossiers.append(d)
        confirmed += len(d.references)
        dropped += d.dropped_refs

    meta = {"model": llm, "provider": provider.label, "date": date.today().isoformat(),
            "n_taxa": len(dossiers), "confirmed": confirmed, "dropped": dropped,
            "max_taxa": max_taxa, "threshold_pct": threshold_pct}

    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "dossier_taxa.md"), "w", encoding="utf-8") as f:
        f.write(core.render_markdown(dossiers, meta))
    with open(os.path.join(out, "dossier_taxa.tsv"), "w", encoding="utf-8") as f:
        f.write(core.render_tsv(dossiers))
    with open(os.path.join(out, "run_meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)
    print(f"[OK] {len(dossiers)} dossiers written to {out} "
          f"({confirmed} citations confirmed, {dropped} dropped)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Phase C: per-taxon dossier via Biomni.")
    ap.add_argument("--metaphlan", default="", help="merged MetaPhlAn table (optional)")
    ap.add_argument("--kraken", default="", help="Kraken/Bracken matrix TSV (optional)")
    ap.add_argument("--out", required=True, help="output directory")
    ap.add_argument("--llm", required=True, help="model name, e.g. gpt-4o or ollama/llama3.1")
    ap.add_argument("--work-dir", required=True, help="where the consent record lives")
    ap.add_argument("--threshold-pct", type=float, default=0.001)
    ap.add_argument("--max-taxa", type=int, default=5)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--yes-send-taxa", action="store_true")
    a = ap.parse_args()
    if not a.metaphlan and not a.kraken:
        return _fail("provide at least one of --metaphlan / --kraken")

    return run(a.metaphlan, a.kraken, a.out, a.llm, a.work_dir, a.threshold_pct,
               a.max_taxa, a.dry_run, a.yes_send_taxa,
               _LazyClient(a.llm), os.environ, sys.stdin.isatty())


if __name__ == "__main__":
    sys.exit(main())
