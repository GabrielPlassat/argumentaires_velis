"""Sélection des vélis à la vente adaptés à un usage (données déclarées par les constructeurs)."""
from __future__ import annotations

import pandas as pd

from .stats import fmt_nb

SOURCE = "catalogue_velis"

FAMILLES = {
    "Actif ≤ 25 km/h (VAE, tricycles et quadricycles à pédalage)": lambda c, v: v <= 25,
    "Jusqu'à 45 km/h (L1e, L2e, L6e)": lambda c, v: 25 < v <= 45,
    "Au-delà de 45 km/h (L5e, L7e)": lambda c, v: v > 45,
}

USAGES = [
    "véhicules municipaux", "pour opérateur de maintenance et entretien", "pour artisans",
    "Faire ses courses", "distribuer courrier et colis", "pour commerçants et stands mobiles",
    "se rendre sur les sites d'activités sportives", "Tourisme Découverte d'un territoire",
    "trajets domicile travail", "Véhicule En libre service", "pour secteur agricole",
    "surveillance incendie", "Transport scolaire et périscolaire avec plusieurs enfants",
]


def filtrer(cat: pd.DataFrame, usages=None, familles=None, prix_max=None, location_seulement=False) -> pd.DataFrame:
    if cat.empty:
        return cat
    sel = cat.copy()
    if usages:
        sel["pertinence"] = sel["usages"].fillna("").apply(lambda s: sum(u in s for u in usages))
        sel = sel[sel["pertinence"] > 0]
    else:
        sel["pertinence"] = 0
    if familles:
        regles = [FAMILLES[f] for f in familles if f in FAMILLES]
        sel = sel[sel.apply(lambda r: any(rg(r["categorie"], r["vitesse_max_kmh"]) for rg in regles), axis=1)]
    if prix_max:
        sel = sel[(sel["prix_vente_ht"].isna()) | (sel["prix_vente_ht"] <= prix_max)]
    if location_seulement:
        sel = sel[sel["loyer_mensuel_ht"].notna()]
    return sel


def tableau(sel: pd.DataFrame, max_lignes: int | None = None) -> pd.DataFrame:
    if max_lignes and len(sel) > max_lignes:
        # priorité aux modèles qui couvrent le plus d'usages visés, puis diversité de constructeurs
        sel = (sel.sort_values(["pertinence", "loyer_mensuel_ht"], ascending=[False, True])
                  .drop_duplicates("constructeur").head(max_lignes))
    t = sel[["vehicule", "constructeur", "categorie", "vitesse_max_kmh", "prix_vente_ht",
             "loyer_mensuel_ht", "delai_livraison_mois", "date_commande"]].copy()
    t.columns = ["Véli", "Constructeur", "Catégorie", "Vitesse max (km/h)", "Prix HT (€)",
                 "Location HT (€/mois)", "Délai (mois)", "Commande possible"]
    for c in ["Prix HT (€)", "Location HT (€/mois)"]:
        t[c] = t[c].map(lambda x: fmt_nb(x) if pd.notna(x) else "—")
    return t.sort_values(["Vitesse max (km/h)", "Véli"]).reset_index(drop=True)


def preuve_synthese(sel: pd.DataFrame, usages=None) -> dict | None:
    if sel.empty:
        return None
    n = len(sel)
    prix = sel["prix_vente_ht"].dropna()
    loyer = sel["loyer_mensuel_ht"].dropna()
    delai = sel["delai_livraison_mois"].dropna()
    morceaux = [f"{n} références de vélis proposées par {sel['constructeur'].nunique()} constructeurs "
                + ("correspondent aux usages visés" if usages else "sont déclarées à la vente")]
    if len(prix) >= 3:
        morceaux.append(f"prix médian de {fmt_nb(prix.median())} € HT (de {fmt_nb(prix.min())} à {fmt_nb(prix.max())} €)")
    if len(loyer) >= 3:
        morceaux.append(f"location médiane de {fmt_nb(loyer.median())} € HT par mois pour le véhicule seul")
    if len(delai) >= 3:
        morceaux.append(f"délai de livraison médian de {delai.median():.0f} mois")
    texte = morceaux[0] + (" : " + ", ".join(morceaux[1:]) if len(morceaux) > 1 else "") + "."
    return {"id": "CALC-CATALOGUE", "titre": "Des vélis disponibles pour cet usage", "texte": texte,
            "source": SOURCE, "page": "calcul de l'outil", "niveau": "mesure",
            "limite": "Prix, loyers et délais déclarés par les constructeurs, à confirmer par devis.", "n": n}
