"""Ponte fra il profilo metagenomico e i modelli di FSSP (D019, D050).

Il profilo dice CHI c'e' (percentuali di DNA), non QUANTI per grammo. Quindi (D019):
  - scenari "e se" per la Listeria (predefiniti 1 e 100 ufc/g), sempre, anche se il profilo non la trova;
  - conta in piastra facoltativa: conta dei LAB (ufc/g) oppure conta totale x percentuale delle specie LAB
    del modello (opzione A, con avviso: % di DNA non e' % di cellule vive);
  - senza una conta dei LAB la Listeria si prevede da sola: e' il caso peggiore (nessun freno dai LAB).
"""
import re

LISTERIA_NOMI = {"listeria monocytogenes"}

# Specie che attivano il modello LAB (Lactobacillus spp. psicrotolleranti, Mejlholm & Dalgaard 2013):
# il modello e' costruito su 4 isolati di L. sakei; l'articolo indica L. sakei e L. curvatus come dominanti
# nei prodotti per cui e' validato (pesce e carne). Nomi dopo la riclassificazione del 2020 e vecchi nomi.
LAB_SPECIE = {"latilactobacillus sakei", "lactobacillus sakei", "latilactobacillus curvatus", "lactobacillus curvatus"}
# Generi LAB per cui l'articolo giudica il modello non adatto (prestazioni inaccettabili)
LAB_NON_ADATTI = ("carnobacterium", "leuconostoc", "weissella")


def normalizza(nome):
    """'k__Bacteria|...|s__Latilactobacillus_sakei' o 'Latilactobacillus sakei' -> 'latilactobacillus sakei'."""
    n = nome.split("|")[-1].strip()
    n = re.sub(r"^[a-z]__", "", n)
    return re.sub(r"\s+", " ", n.replace("_", " ")).strip().lower()


def piano(profilo_specie, conte, scenari_listeria):
    """Decide quali previsioni fare. profilo_specie: {nome: %}; conte: {"lab_ufc_g"} o {"totale_ufc_g"}."""
    norm = {}
    for k, v in profilo_specie.items():
        n = normalizza(k)
        norm[n] = norm.get(n, 0.0) + v
    listeria_pct = sum(v for k, v in norm.items() if k in LISTERIA_NOMI)
    lab = {k: v for k, v in norm.items() if k in LAB_SPECIE and v > 0.0}
    lab_pct = sum(lab.values())
    note = ["Le percentuali del profilo sono DNA relativo, non concentrazioni: le previsioni partono da scenari."]
    n0_lab = None
    if "lab_ufc_g" in conte:
        n0_lab = conte["lab_ufc_g"]
        note.append("LAB iniziali dalla conta in piastra indicata.")
    elif "totale_ufc_g" in conte and lab_pct > 0.0:
        n0_lab = lab_pct / 100.0 * conte["totale_ufc_g"]
        note.append(f"LAB iniziali = {lab_pct:.1f} % (DNA) x conta totale: stima approssimata, "
                    "la % di DNA non e' la % di cellule vive.")
    if n0_lab is None:
        note.append("Senza una conta dei LAB la Listeria e' prevista da sola: e' il caso peggiore "
                    "(nessun freno dai batteri lattici).")
    scenari = [{"nome": f"Listeria {n:g} ufc/g (e se)", "n0_listeria": n, "n0_lab": n0_lab} for n in scenari_listeria]
    if listeria_pct > 0.0:
        note.append(f"Listeria monocytogenes trovata nel profilo ({listeria_pct:g} %).")
        if "totale_ufc_g" in conte:
            scenari.append({"nome": "Listeria dal profilo (% x conta totale)",
                            "n0_listeria": listeria_pct / 100.0 * conte["totale_ufc_g"], "n0_lab": n0_lab})
    else:
        note.append("Listeria non trovata nel profilo: non vuol dire assente (sotto la soglia di rilevamento "
                    "puo' esserci). Gli scenari rispondono a: se ci fosse, crescerebbe?")
    if lab:
        note.append("Modello LAB costruito su Latilactobacillus sakei e valido per i lattobacilli psicrotolleranti "
                    "(L. sakei, L. curvatus) in pesce e carne (Mejlholm & Dalgaard 2013).")
    non_adatti = sorted(k for k, v in norm.items() if v > 0.0 and k.split(" ")[0] in LAB_NON_ADATTI)
    if non_adatti:
        note.append(f"Nel profilo ci sono LAB per cui il modello non e' adatto ({', '.join(non_adatti)}): "
                    "la loro crescita non si prevede (Mejlholm & Dalgaard 2013).")
    coperte = LISTERIA_NOMI | set(LAB_SPECIE)
    return {"scenari": scenari, "note": note, "listeria_trovata": listeria_pct > 0.0,
            "lab_trovati": sorted(lab), "specie_non_coperte": sorted(k for k, v in norm.items()
                                                                    if v > 0.0 and k not in coperte)}
