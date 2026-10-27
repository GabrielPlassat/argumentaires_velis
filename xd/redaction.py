"""Mise en forme rédigée de l'argumentaire : paragraphes suivis plutôt que listes à puces.

Le contenu (preuves, sources, chiffres) est strictement le même que dans la version en liste ;
seule la présentation change. Un seul tableau est conservé : la sélection de vélis du catalogue.
"""
from __future__ import annotations

import re

from .generateur import NIVEAUX, Argumentaire, _cite

# Niveaux de preuve signalés dans le texte (les mesures, textes en vigueur et retours de terrain se lisent tels quels)
NIVEAUX_SIGNALES = {"estimation", "projection", "objectif"}
CONNECTEURS = ["", "Par ailleurs, ", "De plus, ", "En outre, ", "Enfin, "]
ETAPES = ["d'abord", "ensuite", "puis", "en parallèle", "par ailleurs", "de même", "enfin"]


def _minuscule(phrase: str) -> str:
    phrase = phrase.strip().rstrip(".")
    if len(phrase) > 1 and phrase[0].isupper() and not phrase[1].isupper():
        return phrase[0].lower() + phrase[1:]
    return phrase


def _enumerer(items: list[str], final: str = " et ") -> str:
    items = [_minuscule(i) for i in items if i.strip()]
    if len(items) <= 1:
        return "".join(items)
    return " ; ".join(items[:-1]) + " ;" + final + items[-1]


def _phrase_preuve(b, afficher_niveaux: bool, deja_dit: set | None = None) -> str:
    texte = b.texte.strip().rstrip(".")
    phrase = texte + _cite(b) + "."
    if afficher_niveaux:
        precisions = []
        if b.niveau in NIVEAUX_SIGNALES:
            precisions.append(NIVEAUX.get(b.niveau, b.niveau))
        if b.limite and (deja_dit is None or b.limite not in deja_dit):
            precisions.append(_minuscule(b.limite))
            if deja_dit is not None:
                deja_dit.add(b.limite)
        if precisions:
            phrase = phrase[:-1] + " (" + " ; ".join(precisions) + ")."
    return phrase


def _connecter(phrases: list[str]) -> list[str]:
    """Regroupe les phrases en paragraphes de deux ou trois, reliés par des connecteurs."""
    paragraphes, courant = [], []
    for i, ph in enumerate(phrases):
        if courant:
            connecteur = CONNECTEURS[min(len(courant), len(CONNECTEURS) - 1)]
            if connecteur and not re.match(r"^(Selon|Dans|Avec|Pour|Sur|Par|Au|En|Depuis|Entre|Grâce|Face|Habitués)\b", ph):
                premier = ph.split(" ")[0]
                if re.match(r"^(Le|La|Les|L'|L’|Un|Une|Des|Ce|Cette|Ces|Chaque|Plus|Deux|Trois|Quatre|Cinq|Mettre|Livrer|Passer|Remplacer|Avec|Fabrication)\b", premier) or premier in ("Le", "La", "Les"):
                    ph = connecteur + ph[0].lower() + ph[1:]
                else:
                    ph = connecteur + ph
        courant.append(ph)
        if len(courant) == 3 or i == len(phrases) - 1:
            paragraphes.append(" ".join(courant))
            courant = []
    return paragraphes


def en_prose(arg: Argumentaire, afficher_niveaux: bool = True, inclure_notes: bool = True) -> list:
    """Renvoie [(titre_section, [élément, ...])] avec élément = ("p", texte) | ("h", texte) | ("table", titre, df)."""
    sortie = []
    for s in arg.sections:
        if s.note_interne and not inclure_notes:
            continue
        elements, preuves, verbatims, deja_dit = [], [], [], set()

        def vider():
            for p in _connecter(preuves):
                elements.append(("p", p))
            preuves.clear()
            if verbatims:
                citations = " ; ".join(f"« {v.texte.rstrip('. ')} » ({v.attribution}) [{v.ref}]" for v in verbatims)
                elements.append(("p", "Les testeurs le disent avec leurs mots : " + citations + "."))
                verbatims.clear()

        for b in s.blocs:
            if b.type == "preuve":
                preuves.append(_phrase_preuve(b, afficher_niveaux, deja_dit))
                continue
            if b.type == "verbatim":
                verbatims.append(b)
                continue
            vider()
            if b.type == "paragraphe":
                elements.append(("p", b.texte))
            elif b.type == "question":
                elements.append(("h", f"« {b.titre} »"))
                elements.append(("p", b.texte))
            elif b.type == "puces":
                elements.append(("p", _puces_en_phrase(s.titre, b)))
            elif b.type == "tableau" and b.tableau is not None and not b.tableau.empty:
                if "Territoire" == (b.tableau.index.name or ""):
                    elements.append(("p", _territoires_en_phrase(b.tableau)))
                else:
                    elements.append(("table", b.titre, b.tableau))
        vider()
        # « À savoir » rattaché au paragraphe de réponse qui précède
        fusion = []
        for el in elements:
            if el[0] == "p" and el[1].startswith("À savoir : ") and fusion and fusion[-1][0] == "p":
                fusion[-1] = ("p", fusion[-1][1] + " Précisons que " + _minuscule(el[1][11:]) + ".")
            elif el[0] == "p" and el[1].startswith("Voir les éléments sourcés") and fusion and fusion[-1][0] == "p":
                fusion[-1] = ("p", fusion[-1][1] + " " + el[1].replace("Voir les éléments sourcés ci-dessus", "Les éléments chiffrés figurent plus haut"))
            else:
                fusion.append(el)
        sortie.append((s.titre, fusion))
    return sortie


def _puces_en_phrase(titre_section: str, b) -> str:
    items = b.items
    t = (b.titre or titre_section).lower()
    if "compte pour vous" in t:
        return "Les enjeux sont clairs : " + _enumerer(items) + "."
    if "engager" in t:
        etapes = []
        for i, x in enumerate(items):
            mot = "enfin" if i == len(items) - 1 else ETAPES[min(i, len(ETAPES) - 2)]
            etapes.append(f"{mot}, {_minuscule(x)}")
        if len(items) == 1:
            return "La première étape consiste à " + _minuscule(items[0]) + "."
        return "La démarche proposée est progressive : " + " ; ".join(etapes) + "."
    if "plus loin" in t:
        liens = [re.sub(r"^(.*) — (https?://\S+)$", r"\1 (\2)", x) for x in items]
        return "Pour approfondir, plusieurs ressources sont disponibles : " + " ; ".join(liens) + "."
    if "conseil" in t:
        return " ".join(x.rstrip(".") + "." for x in items)
    return _enumerer(items).capitalize() + "."


def _territoires_en_phrase(df) -> str:
    morceaux = [f"{terr} ({int(r['Carnets'])} carnets, {r['Bilan positif']} de bilans positifs, avec {r['Modèles testés']})"
                for terr, r in df.iterrows()]
    return "Dans les territoires retenus, les résultats sont les suivants : " + " ; ".join(morceaux) + "."
