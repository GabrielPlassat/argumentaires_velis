"""Rédaction facultative par IA (API Claude), strictement limitée aux preuves sélectionnées.

Principe : l'IA reçoit uniquement le dossier de preuves numérotées assemblé par le générateur.
Elle reformule pour la cible, sans ajouter de fait. Une vérification automatique signale ensuite
tout nombre du texte rédigé qui ne figure pas dans le dossier de preuves.
"""
from __future__ import annotations

import re

from .generateur import NIVEAUX, Argumentaire

MODELE_DEFAUT = "claude-sonnet-5-5"

CONSIGNES = """Tu es rédacteur pour le programme eXtrême Défi Mobilité de l'ADEME.
Tu rédiges en français un argumentaire destiné à convaincre la cible décrite, à partir d'un dossier de preuves.

Règles impératives :
1. N'utilise QUE les faits du dossier de preuves. N'ajoute aucun chiffre, nom, date ou fait extérieur.
2. Recopie chaque nombre exactement comme dans le dossier (même unité, même arrondi).
3. Place la référence entre crochets du dossier, par exemple [3], juste après chaque fait.
4. Présente les estimations et projections comme telles (« selon les estimations du Bilan XD... »).
5. Reprends les précautions signalées quand tu utilises le chiffre concerné.
6. Ne dénigre pas l'automobile : les comparaisons servent à situer des ordres de grandeur.
7. Ton : clair, factuel, concret, orienté vers l'action. Pas de superlatifs non étayés.
8. Structure : titre, introduction courte adaptée à la cible, 3 à 5 parties avec intertitres,
   réponses aux objections si fournies, appel à l'action, puis la liste « Sources » reprise telle quelle.
"""


def dossier(arg: Argumentaire, base) -> str:
    lignes = []
    for s in arg.sections:
        if s.note_interne:
            continue
        lignes.append(f"\n## {s.titre}")
        for b in s.blocs:
            if b.type == "preuve":
                prec = f" (précaution : {b.limite})" if b.limite else ""
                page = f", {b.page}" if b.page and b.page != "calcul de l'outil" else ""
                lignes.append(f"- [{b.ref}{page}] ({NIVEAUX.get(b.niveau, b.niveau)}) {b.texte}{prec}")
            elif b.type in ("paragraphe",):
                lignes.append(b.texte)
            elif b.type == "puces":
                lignes += [f"- {i}" for i in b.items]
            elif b.type == "verbatim":
                lignes.append(f"- Verbatim [{b.ref}] : « {b.texte} » ({b.attribution})")
            elif b.type == "question":
                lignes.append(f"- Objection : « {b.titre} » — Réponse : {b.texte}")
            elif b.type == "tableau" and b.tableau is not None:
                lignes.append(b.tableau.head(12).to_markdown())
    lignes.append("\n## Sources")
    for num, sid in arg.references:
        src = base.sources.get(sid, {})
        lignes.append(f"[{num}] {src.get('auteur', '')}, {src.get('titre', sid)}, {src.get('date', '')}")
    return "\n".join(lignes)


def rediger(arg: Argumentaire, base, cle_api: str, consignes_cible: str, longueur: str = "2 pages",
            ton: str = "institutionnel", modele: str = MODELE_DEFAUT) -> str:
    import anthropic  # importé ici pour que l'outil fonctionne sans cette dépendance

    client = anthropic.Anthropic(api_key=cle_api)
    message = client.messages.create(
        model=modele,
        max_tokens=6000,
        system=CONSIGNES,
        messages=[{"role": "user", "content": (
            f"Cible et contexte : {consignes_cible}\n"
            f"Longueur visée : {longueur}. Ton : {ton}.\n\n"
            f"Dossier de preuves :\n{dossier(arg, base)}"
        )}],
    )
    return "".join(b.text for b in message.content if getattr(b, "type", "") == "text")


_NOMBRE = re.compile(r"(?<![\[\w])\d[\d   ]*(?:[,.]\d+)?")


def _normaliser(n: str) -> str:
    return re.sub(r"[\s  ]", "", n).replace(".", ",").rstrip(",")


def verifier_nombres(texte_ia: str, arg: Argumentaire, base, contexte: str = "") -> list[str]:
    """Renvoie les nombres présents dans le texte rédigé mais absents du dossier de preuves."""
    reference = dossier(arg, base) + " " + contexte
    connus = {_normaliser(m) for m in _NOMBRE.findall(reference)}
    sans_refs = re.sub(r"\[[^\]]*\]", " ", texte_ia)  # on ignore les appels de source
    suspects = []
    for m in _NOMBRE.findall(sans_refs):
        n = _normaliser(m)
        if n and n not in connus and n not in suspects and len(n.replace(",", "")) > 1:
            suspects.append(n)
    return suspects
