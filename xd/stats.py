"""Statistiques calculées à partir des carnets de bord de l'expérimentation 30 vélis.

Chaque fonction renvoie une « preuve calculée » (même format qu'une preuve de data/preuves.yaml)
ou None si l'échantillon est trop petit pour être cité.
"""
from __future__ import annotations

import re
import unicodedata

import pandas as pd

SOURCE = "exp_30veli"
SEUIL_MIN = 20       # en dessous : on ne cite pas
SEUIL_PRUDENCE = 50  # en dessous : on ajoute une mise en garde

AVANTAGES = {
    "avantage_agilite": "l'agilité et la facilité à se garer",
    "avantage_observation": "le plaisir d'observer le paysage",
    "avantage_reactions": "les réactions positives de l'entourage",
    "avantage_bien_etre": "le bien-être",
    "avantage_fierté": "la fierté d'utiliser un véli",
    "avantage_confort": "le confort",
}
DIFFICULTES = {
    "difficulte_visibilite": "le manque de visibilité vis-à-vis des autres usagers",
    "difficulte_vehicule": "une limite du véhicule (puissance, équipement)",
    "difficulte_amenagement": "des aménagements inadaptés",
    "difficulte_comportement": "le comportement des autres usagers",
    "difficulte_stationnement": "le stationnement",
}
LIBELLES_MOTIFS = {
    "domicile_travail": "domicile-travail",
    "professionnel": "professionnels",
    "courses": "courses",
    "loisirs": "loisirs",
    "ecole": "accompagnement scolaire",
    "sante": "santé",
    "association": "associatifs",
}

# Règles de classement des motifs saisis librement (ordre = priorité)
_REGLES = [
    ("gestion_expe", r"r[ée]cup|restitu|remise|rendre|rendu|retour du pr[êe]t|essai|test|prise en main|livraison du v|transfert|d[ée]placement d.une voiture|pr[ée]sentation|d[ée]monstration|tournage|interview|journ[ée]e de|ramener le v[ée]hicule|r[ée]ception"),
    ("professionnel", r"\bpro\b|professionn|trajet pro|r[ée]union|reunion|mission|distribution|travaux|tourn[ée]e|contr[ôo]le|service|\bvad\b|livraison|mat[ée]riel|chantier|pompier|ccff|[ée]lu|mairie|permanence|recrutement|ehpad|epad|visite travail|rdv travail|soins \+|livraison et soins|cadres|animation|in.?vd|garage|maraîcher|apicole"),
    ("ecole", r"[ée]cole|enfant|scolaire|nounou|centre de loisirs|activit[ée] de ma fille"),
    ("sante", r"m[ée]dic|m[ée]decin|kin[ée]|pneumo|sant[ée]|pharmacie|\bsoin"),
    ("domicile_travail", r"domicile|travail"),
    ("courses", r"course|achat|banque|march[ée]"),
    ("association", r"asso|b[ée]n[ée]vol|emma[üu]s|croix rouge"),
    ("loisirs", r"loisir|balade|ballade|sport|famille|ami|visite|tour du village|trail|vide grenier|manifestation|[ée]v[ée]nement|m[ée]di[ée]vales|jardin|d[ée]jeuner|voyage|lien social|festival"),
]


def _norm(s: str) -> str:
    return unicodedata.normalize("NFC", str(s)).lower()


def categoriser_motif(motif) -> str:
    if not isinstance(motif, str) or not motif.strip():
        return "non_renseigne"
    m = _norm(motif)
    for cat, motif_re in _REGLES:
        if re.search(motif_re, m):
            return cat
    return "autre"


def preparer(df: pd.DataFrame) -> pd.DataFrame:
    """Ajoute la catégorie de motif et des colonnes numériques propres."""
    if df.empty:
        return df
    df = df.copy()
    df["categorie_motif"] = df["motif"].map(categoriser_motif)
    for col in list(AVANTAGES) + list(DIFFICULTES) + ["difficulte_aucune", "meteo_pluvieux"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    df["bilan_positif"] = df["bilan"].isin(["Positif", "Très positif"])
    df["bilan_renseigne"] = df["bilan"].isin(["Positif", "Très positif", "Négatif", "Très négatif"])
    return df


def filtrer(df: pd.DataFrame, motifs=None, territoires=None, vehicules=None) -> pd.DataFrame:
    if df.empty:
        return df
    sel = df[df["categorie_motif"] != "gestion_expe"]
    if motifs:
        sel = sel[sel["categorie_motif"].isin(motifs)]
    if territoires:
        sel = sel[sel["territoire"].isin(territoires)]
    if vehicules:
        sel = sel[sel["vehicule"].isin(vehicules)]
    return sel


def fmt_nb(n: float) -> str:
    return f"{int(round(n)):,}".replace(",", " ")


def fmt_pct(x: float) -> str:
    return f"{round(100 * x)} %"


def _perimetre(motifs) -> str:
    if not motifs:
        return "l'ensemble des trajets"
    noms = [LIBELLES_MOTIFS.get(m, m) for m in motifs]
    return "les trajets " + (", ".join(noms[:-1]) + " et " + noms[-1] if len(noms) > 1 else noms[0])


def _limite(n: int) -> str | None:
    base = "Retours déclaratifs de testeurs volontaires."
    if n < SEUIL_PRUDENCE:
        return base + f" Échantillon restreint ({n} carnets) : à interpréter avec prudence."
    return base


def bilan(df: pd.DataFrame, motifs=None) -> dict | None:
    renseignes = df[df["bilan_renseigne"]]
    n = len(renseignes)
    if n < SEUIL_MIN:
        return None
    part = renseignes["bilan_positif"].mean()
    texte = (
        f"Sur {fmt_nb(n)} carnets de bord renseignés pour {_perimetre(motifs)} "
        f"({df['territoire'].nunique()} territoires, {df['vehicule'].nunique()} modèles de vélis), "
        f"{fmt_pct(part)} des testeurs tirent un bilan positif ou très positif de leur trajet."
    )
    return {"id": "CALC-BILAN", "titre": "Le bilan des testeurs", "texte": texte, "source": SOURCE,
            "page": "calcul de l'outil", "niveau": "mesure", "limite": _limite(n), "n": n, "valeur": part}


def avantages(df: pd.DataFrame, motifs=None) -> dict | None:
    sous = df[df[list(AVANTAGES)].notna().any(axis=1)]
    n = len(sous)
    if n < SEUIL_MIN:
        return None
    parts = (sous[list(AVANTAGES)].fillna(0) > 0).mean().sort_values(ascending=False)
    top = [f"{AVANTAGES[c]} ({fmt_pct(v)})" for c, v in parts.head(3).items()]
    texte = (f"Pour {_perimetre(motifs)}, les bénéfices les plus cités dans {fmt_nb(n)} carnets sont "
             f"{top[0]}, {top[1]} et {top[2]}.")
    return {"id": "CALC-AVANTAGES", "titre": "Ce que les testeurs apprécient", "texte": texte,
            "source": SOURCE, "page": "calcul de l'outil", "niveau": "mesure", "limite": _limite(n), "n": n}


def difficultes(df: pd.DataFrame, motifs=None) -> dict | None:
    sous = df[df["difficulte_aucune"].notna()]
    n = len(sous)
    if n < SEUIL_MIN:
        return None
    aucune = (sous["difficulte_aucune"] > 0).mean()
    sous2 = df[df[list(DIFFICULTES)].notna().any(axis=1)]
    parts = (sous2[list(DIFFICULTES)].fillna(0) > 0).mean().sort_values(ascending=False)
    (c1, v1), (c2, v2) = list(parts.head(2).items())
    texte = (f"Pour {_perimetre(motifs)}, {fmt_pct(aucune)} des carnets ne signalent aucune difficulté ; "
             f"les difficultés les plus citées sont {DIFFICULTES[c1]} ({fmt_pct(v1)} des carnets) "
             f"et {DIFFICULTES[c2]} ({fmt_pct(v2)}).")
    return {"id": "CALC-DIFFICULTES", "titre": "Les difficultés rencontrées", "texte": texte,
            "source": SOURCE, "page": "calcul de l'outil", "niveau": "mesure", "limite": _limite(n), "n": n}


def meteo(df: pd.DataFrame, motifs=None) -> dict | None:
    pluie = df[(df["meteo_pluvieux"] == 1) & df["bilan_renseigne"]]
    n = len(pluie)
    if n < SEUIL_MIN:
        return None
    texte = (f"Par temps de pluie, {fmt_pct(pluie['bilan_positif'].mean())} des {fmt_nb(n)} trajets "
             f"renseignés ({_perimetre(motifs)}) restent jugés positifs ou très positifs par les testeurs.")
    return {"id": "CALC-METEO", "titre": "Même sous la pluie", "texte": texte, "source": SOURCE,
            "page": "calcul de l'outil", "niveau": "mesure", "limite": _limite(n), "n": n}


def distances(df: pd.DataFrame, motifs=None) -> dict | None:
    d = pd.to_numeric(df["totalDistanceKm"], errors="coerce").dropna()
    d = d[d > 0.2]
    n = len(d)
    if n < SEUIL_MIN:
        return None
    texte = (f"Les boîtiers embarqués montrent, pour {_perimetre(motifs)}, une distance médiane de "
             f"{d.median():.0f} km par carnet ; 75 % des carnets restent sous {d.quantile(0.75):.0f} km "
             f"({fmt_nb(n)} carnets mesurés, {fmt_nb(d.sum())} km au total).")
    limite = "Distances mesurées par les boîtiers connectés, sur les carnets qui en disposent."
    if n < SEUIL_PRUDENCE:
        limite += f" Échantillon restreint ({n} carnets)."
    return {"id": "CALC-DISTANCES", "titre": "Des trajets courts", "texte": texte, "source": SOURCE,
            "page": "calcul de l'outil", "niveau": "mesure", "limite": limite, "n": n}


_POSITIFS = ["agréable", "plaisir", "super", "génial", "pratique", "confort", "top", "facile", "ravi",
             "content", "sympa", "adoré", "j'adore", "parfait", "excellent", "silencieux", "écono", "liberté",
             "rapide", "joie", "bonheur", "aucun souci", "très bien", "idéal"]
_NEGATIFS = ["difficile", "dur", "problème", "inefficace", "pas commode", "panne", "dangereu", "peur",
             "manque", "pas assez", "trop ", "regret", "nul", "galère", "mal ", "ne démarre", "arrosoir",
             "doublé", "pénible", "froid", "impossible", "attention", "défaut", "dommage", "mais", "peu ", "désagréable", "sèche", "pas "]


def _score_ton(texte: str) -> int:
    return sum(m in texte for m in _POSITIFS) - 2 * sum(m in texte for m in _NEGATIFS)


def verbatims(df: pd.DataFrame, n: int = 3, positifs: bool = True) -> list[dict]:
    """Courts commentaires de testeurs (anonymes), sélection déterministe."""
    if df.empty:
        return []
    sous = df[df["bilan_positif"] == positifs] if positifs is not None else df
    sous = sous[sous["commentaires"].astype(str).str.len().between(50, 230)]
    sous = sous[~sous["commentaires"].astype(str).str.contains(r"@|\d{2}[ .]?\d{2}[ .]?\d{2}[ .]?\d{2}", regex=True)]
    if sous.empty:
        return []
    if positifs:
        # on garde des commentaires réellement positifs (le bilan peut être positif malgré une critique)
        score = sous["commentaires"].astype(str).str.lower().map(_score_ton)
        sous = sous.assign(_score=score)
        sous = sous[sous["_score"] > 0].sort_values(["_score", "commentaires"], ascending=[False, True])
    # diversité : un verbatim par territoire autant que possible
    choix = sous.drop_duplicates("territoire").head(n)
    return [{"texte": str(r.commentaires).strip().replace("\n", " "), "territoire": r.territoire,
             "vehicule": r.vehicule} for r in choix.itertuples()]


def tableau_territoires(df: pd.DataFrame) -> pd.DataFrame:
    g = df[df["bilan_renseigne"]].groupby("territoire")
    t = pd.DataFrame({
        "Carnets": g.size(),
        "Bilan positif": g["bilan_positif"].mean().map(fmt_pct),
        "Modèles testés": df.groupby("territoire")["vehicule"].apply(lambda s: ", ".join(sorted(s.dropna().unique()))),
    }).dropna(subset=["Carnets"])
    t["Carnets"] = t["Carnets"].astype(int)
    t.index.name = "Territoire"
    return t.sort_values("Carnets", ascending=False)


def tableau_vehicules(df: pd.DataFrame) -> pd.DataFrame:
    g = df[df["bilan_renseigne"]].groupby("vehicule")
    t = pd.DataFrame({"Carnets": g.size(), "Bilan positif": g["bilan_positif"].mean().map(fmt_pct)})
    t = t[t["Carnets"] >= 10]
    t.index.name = "Véli"
    return t.sort_values("Carnets", ascending=False)


def preuves_calculees(df: pd.DataFrame, motifs=None, territoires=None, vehicules=None) -> list[dict]:
    sel = filtrer(df, motifs, territoires, vehicules)
    resultats = [f(sel, motifs) for f in (bilan, avantages, difficultes, meteo, distances)]
    return [r for r in resultats if r]
