"""
Prépare les données publiables de l'outil à partir des fichiers bruts.

À lancer (dans Google Colab ou en local) chaque fois qu'un fichier source change :

    python outils/preparer_donnees.py

Entrées attendues dans le dossier brut/ (ce dossier est exclu de Git, voir .gitignore) :
  - brut/30veli_export_experiences.csv   export de https://30veli.fabmob.io/export
  - brut/velis_a_la_vente.csv            tableau « Vélis vendus - Vélis à la vente »
  - brut/deploiement_reponses.xlsx       réponses au questionnaire déploiement (optionnel)

Sorties dans data/ :
  - data/experiences_30veli.csv   carnets de bord, colonnes utiles uniquement
  - data/catalogue_velis.csv      catalogue SANS nom, prénom ni e-mail des contacts
  - data/deploiement_agrege.json  indicateurs agrégés et anonymes du questionnaire déploiement
"""
from __future__ import annotations

import json
import re
from collections import Counter
from datetime import date
from pathlib import Path

import pandas as pd

RACINE = Path(__file__).resolve().parents[1]
BRUT = RACINE / "brut"
DATA = RACINE / "data"

COLONNES_EXPERIENCES = [
    "vehicule", "territoire", "totalDistanceKm", "nbTrips", "moment",
    "meteo_ensoleille", "meteo_nuageux", "meteo_pluvieux", "meteo_venteux",
    "meteo_neigeux", "meteo_brouillard", "motif",
    "avantage_aucun", "avantage_agilite", "avantage_confort", "avantage_observation",
    "avantage_fierté", "avantage_reactions", "avantage_bien_etre", "avantage_autre",
    "difficulte_aucune", "difficulte_visibilite", "difficulte_amenagement",
    "difficulte_stationnement", "difficulte_vehicule", "difficulte_comportement",
    "difficulte_autre", "difficultes_details", "bilan", "commentaires",
    "mode_domicile_travail",
]

MOTIF_ADRESSE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
MOTIF_TEL = re.compile(r"(?:\+33\s?|0)[1-9](?:[\s.-]?\d{2}){4}")


def anonymiser_texte(valeur):
    """Masque les e-mails et numéros de téléphone éventuellement saisis en texte libre."""
    if not isinstance(valeur, str):
        return valeur
    valeur = MOTIF_ADRESSE.sub("[e-mail masqué]", valeur)
    return MOTIF_TEL.sub("[téléphone masqué]", valeur)


def preparer_experiences() -> None:
    source = BRUT / "30veli_export_experiences.csv"
    if not source.exists():
        print(f"(ignoré) {source} absent")
        return
    df = pd.read_csv(source)
    df.columns = [c.replace("﻿", "") for c in df.columns]
    garder = [c for c in COLONNES_EXPERIENCES if c in df.columns]
    df = df[garder].copy()
    for col in ["commentaires", "difficultes_details", "avantage_autre", "difficulte_autre", "motif"]:
        if col in df.columns:
            df[col] = df[col].map(anonymiser_texte)
    df.to_csv(DATA / "experiences_30veli.csv", index=False)
    (DATA / "experiences_30veli.meta.json").write_text(
        json.dumps({"date_preparation": date.today().isoformat(), "lignes": len(df)}, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"OK experiences_30veli.csv : {len(df)} carnets")


def preparer_catalogue() -> None:
    source = BRUT / "velis_a_la_vente.csv"
    if not source.exists():
        print(f"(ignoré) {source} absent")
        return
    df = pd.read_csv(source)
    df.columns = [c.replace("﻿", "").strip() for c in df.columns]
    renommer = {
        "Nom Véhicule": "vehicule",
        "Nom Constructeur": "constructeur",
        "Catégorie du véhicule": "categorie",
        "Vitesse maxi (en km/h)": "vitesse_max_kmh",
        "Cas d'usages détaillés (plusieurs choix possibles)": "usages",
        "Prix de vente (en € HT)": "prix_vente_ht",
        "Prix de location du véhicule seul par mois (en € HT)": "loyer_mensuel_ht",
        "Date de commande possible du Véhicule": "date_commande",
        "Délai de livraison après la commande (en mois)": "delai_livraison_mois",
        "Volume de production maximal faisable sur 12 mois glissants": "capacite_12_mois",
    }
    df = df.rename(columns=renommer)
    # Les coordonnées personnelles des responsables commerciaux ne sont jamais publiées.
    df = df[[c for c in renommer.values() if c in df.columns]]
    df.to_csv(DATA / "catalogue_velis.csv", index=False)
    print(f"OK catalogue_velis.csv : {len(df)} références (coordonnées retirées)")


def preparer_deploiement() -> None:
    source = BRUT / "deploiement_reponses.xlsx"
    if not source.exists():
        print(f"(ignoré) {source} absent")
        return
    df = pd.read_excel(source)

    def col(debut: str) -> str:
        return next(c for c in df.columns if c.startswith(debut))

    nb_velis = pd.to_numeric(df[col("combien de vélis")], errors="coerce")
    types_projet = df[col("Quel type de projet")].fillna("").map(lambda s: s.split(":")[0].strip())
    vehicules = Counter(
        v.strip() for s in df[col("Découvrez les vélis")].dropna() for v in str(s).split(",") if v.strip()
    )
    agrege = {
        "date_preparation": date.today().isoformat(),
        "nb_reponses": int(len(df)),
        "profils": df[col("Vous êtes")].value_counts().to_dict(),
        "regions": df[col("Votre région")].value_counts().to_dict(),
        "types_projet": types_projet.value_counts().to_dict(),
        "velis_envisages_total": int(nb_velis.sum()),
        "velis_envisages_mediane": float(nb_velis.median()),
        "velis_envisages_max": int(nb_velis.max()),
        "contact_constructeur_oui": int((df[col("Avez vous déjà pris contact avec le")] == "oui").sum()),
        "contact_maintenance_oui": int(df[col("Avez-vous pris contact avec un acteur")].astype(str).str.startswith("oui").sum()),
        "contact_territoire_oui": int(df[col("Avez vous pris contact avec votre")].astype(str).str.startswith("oui").sum()),
        "vehicules_les_plus_cites": dict(vehicules.most_common(12)),
    }
    (DATA / "deploiement_agrege.json").write_text(json.dumps(agrege, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OK deploiement_agrege.json : {agrege['nb_reponses']} réponses agrégées (aucune donnée nominative)")


if __name__ == "__main__":
    DATA.mkdir(exist_ok=True)
    preparer_experiences()
    preparer_catalogue()
    preparer_deploiement()
