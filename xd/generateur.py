"""Assemblage d'un argumentaire sourcé à partir des cibles choisies et du contexte.

Le générateur est déterministe : il n'invente rien, il sélectionne et ordonne des preuves
sourcées (data/preuves.yaml) et des statistiques recalculées sur les données. La reformulation
par IA (xd/ia.py) est une étape facultative, appliquée ensuite.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from . import catalogue as cat_mod
from . import stats as st
from .donnees import Base

NIVEAUX = {
    "mesure": "donnée mesurée",
    "terrain": "retour de terrain",
    "reglementaire": "texte en vigueur",
    "estimation": "estimation",
    "projection": "projection",
    "objectif": "objectif du programme",
}

TERRITOIRES = {
    "rural": ("Rural", ["SOC-02", "ECO-05", "SHS-02"]),
    "periurbain": ("Périurbain", ["ECO-05"]),
    "urbain": ("Urbain dense", ["PRO-05", "AMG-05"]),
    "touristique": ("Touristique", ["TOU-02", "TOU-03"]),
    "montagne": ("Relief marqué", ["PRO-03"]),
}

PREUVES_RELATIVISER = ["PUB-04", "PUB-05", "PUB-06", "PUB-01", "PUB-10"]


@dataclass
class Contexte:
    selection: list                      # [(famille_id, objectif_id), ...]
    structure: str = ""
    precisions: str = ""                 # contexte libre saisi par l'utilisateur
    reprendre_precisions: bool = True    # reprendre ce texte en introduction
    types_territoire: list = field(default_factory=list)
    territoires_30veli: list = field(default_factory=list)
    diffusion_externe: bool = True
    inclure_objections: bool = True
    inclure_relativiser: bool = False
    inclure_conseils: bool = True
    inclure_catalogue: bool = True
    max_preuves: int = 9
    familles_vehicules: list = field(default_factory=list)
    prix_max: float | None = None
    location_seulement: bool = False


@dataclass
class Bloc:
    type: str            # paragraphe | preuve | puces | tableau | verbatim | question
    texte: str = ""
    items: list = field(default_factory=list)
    tableau: pd.DataFrame | None = None
    ref: int | None = None
    page: str = ""
    niveau: str = ""
    limite: str = ""
    titre: str = ""
    attribution: str = ""


@dataclass
class Section:
    titre: str
    blocs: list = field(default_factory=list)
    note_interne: bool = False


@dataclass
class Argumentaire:
    titre: str
    sous_titre: str
    sections: list
    references: list          # [(numéro, source_id)]
    avertissements: list
    preuves_utilisees: list   # preuves (dict) dans l'ordre, pour l'IA et la vérification


class _Citations:
    def __init__(self, base: Base):
        self.base = base
        self.ordre: list[str] = []

    def numero(self, source_id: str) -> int:
        if source_id not in self.ordre:
            self.ordre.append(source_id)
        return self.ordre.index(source_id) + 1


def _objectifs(base: Base, selection):
    for fam_id, obj_id in selection:
        fam = base.cibles.get(fam_id, {})
        obj = fam.get("objectifs", {}).get(obj_id)
        if obj:
            yield fam_id, obj_id, fam, obj


def _uniques(seq):
    vus, out = set(), []
    for x in seq:
        if x not in vus:
            vus.add(x)
            out.append(x)
    return out


def _entrelacer(listes, limite):
    """Prend les éléments à tour de rôle dans chaque liste (diversité entre objectifs)."""
    out, i = [], 0
    while len(out) < limite and any(i < len(l) for l in listes):
        for l in listes:
            if i < len(l) and l[i] not in out:
                out.append(l[i])
                if len(out) >= limite:
                    break
        i += 1
    return out


def preuve_deploiement(base: Base, variante: str = "demande") -> dict | None:
    d = base.deploiement
    if not d:
        return None
    tp = d.get("types_projet", {})
    if variante == "maintenance":
        texte = (f"Parmi les {d['nb_reponses']} structures qui ont répondu au questionnaire « Déploiement des vélis 2026 », "
                 f"{d['contact_maintenance_oui']} ont déjà identifié un acteur local de maintenance et "
                 f"{d['contact_constructeur_oui']} ont contacté un constructeur.")
    else:
        n_exp = tp.get("J'expérimente", 0)
        texte = (f"{d['nb_reponses']} structures de {len(d.get('regions', {}))} régions (collectivités, entreprises, acteurs de "
                 f"l'inclusion, du tourisme, de la santé...) ont répondu au questionnaire « Déploiement des vélis 2026 » : "
                 f"{n_exp} veulent expérimenter, {tp.get('Je déploie', 0)} déployer et "
                 f"{tp.get('Je découvre', 0)} découvrir, avec une médiane de {d['velis_envisages_mediane']:.0f} vélis par projet.")
    return {"id": f"CALC-DEPLOIEMENT-{variante}", "titre": "Une demande qui se structure", "texte": texte,
            "source": "enquete_deploiement", "page": "indicateurs agrégés", "niveau": "mesure",
            "limite": "Intentions déclarées, non des commandes."}


def generer(base: Base, ctx: Contexte) -> Argumentaire:
    cit = _Citations(base)
    avert: list[str] = []
    utilisees: list[dict] = []
    deja: set[str] = set()

    def autorisee(p: dict) -> bool:
        return (not ctx.diffusion_externe) or base.source_publique(p["source"])

    def bloc_preuve(p: dict) -> Bloc:
        deja.add(p["id"])
        utilisees.append(p)
        return Bloc("preuve", texte=p["texte"].strip(), ref=cit.numero(p["source"]), page=str(p.get("page", "")),
                    niveau=p.get("niveau", ""), limite=p.get("limite") or "", titre=p.get("titre", ""))

    objectifs = list(_objectifs(base, ctx.selection))
    if not objectifs:
        raise ValueError("Aucune cible sélectionnée.")
    structure = ctx.structure.strip() or "votre structure"

    familles_lib = _uniques(fam["label"] for _, _, fam, _ in objectifs)
    titre = f"Les vélis pour {structure}" if ctx.structure.strip() else "Pourquoi s'engager avec les vélis"
    sous_titre = " · ".join(obj["label"] for *_, obj in objectifs)

    sections: list[Section] = []

    # 1. Accroche et enjeux
    s = Section("En bref")
    for *_, obj in objectifs:
        s.blocs.append(Bloc("paragraphe", texte=obj["accroche"].replace("{structure}", structure)))
    if ctx.precisions.strip() and ctx.reprendre_precisions:
        s.blocs.append(Bloc("paragraphe", texte=ctx.precisions.strip()))
    enjeux = _uniques(e for *_, obj in objectifs for e in obj.get("enjeux", []))[:7]
    if enjeux:
        s.blocs.append(Bloc("puces", titre="Ce qui compte pour vous", items=enjeux))
    sections.append(s)

    # 2. Arguments clés
    listes = [[pid for pid in obj.get("preuves", []) if pid in base.preuves and autorisee(base.preuves[pid])]
              for *_, obj in objectifs]
    choix = _entrelacer(listes, ctx.max_preuves)
    extra = []
    for t in ctx.types_territoire:
        for pid in TERRITOIRES.get(t, ("", []))[1]:
            if pid in base.preuves and autorisee(base.preuves[pid]) and pid not in choix:
                extra.append(pid)
    s = Section("Les arguments clés")
    for pid in _uniques(choix + extra[:3]):
        s.blocs.append(bloc_preuve(base.preuves[pid]))
    exclues = sum(1 for l_obj in objectifs for pid in l_obj[3].get("preuves", [])
                  if pid in base.preuves and not autorisee(base.preuves[pid]))
    if exclues and ctx.diffusion_externe:
        avert.append(f"{exclues} élément(s) issus de documents internes ont été écartés (mode diffusion externe).")
    sections.append(s)

    # 3. Expérimentations : statistiques recalculées
    motifs = _uniques(m for *_, obj in objectifs for m in obj.get("motifs", []))
    exp = st.preparer(base.experiences)
    s = Section("Ce que montrent les expérimentations de terrain")
    if not exp.empty:
        territoires = ctx.territoires_30veli or None
        calc = st.preuves_calculees(exp, motifs or None, territoires)
        if not calc and (motifs or territoires):
            avert.append("Pas assez de carnets de bord pour ce périmètre : statistiques calculées sur l'ensemble des trajets.")
            calc = st.preuves_calculees(exp, None, None)
            motifs = []
        for p in calc[:4]:
            s.blocs.append(bloc_preuve(p))
        sel = st.filtrer(exp, motifs or None, territoires)
        for v in st.verbatims(sel, n=3):
            s.blocs.append(Bloc("verbatim", texte=v["texte"], ref=cit.numero(st.SOURCE),
                                attribution=f"testeur·rice, {v['territoire']}, {v['vehicule']}"))
        if ctx.territoires_30veli:
            s.blocs.append(Bloc("tableau", titre="Résultats par territoire retenu",
                                tableau=st.tableau_territoires(sel)))
    for pid in ["EXP-01"]:
        if pid not in deja and pid in base.preuves and autorisee(base.preuves[pid]):
            s.blocs.insert(0, bloc_preuve(base.preuves[pid]))
    dep = preuve_deploiement(base)
    if dep and autorisee(dep) and any(f in ("collectivite", "entreprise_flotte", "association", "entreprise_financeur")
                                      for f, *_ in objectifs):
        s.blocs.append(bloc_preuve(dep))
    if s.blocs:
        sections.append(s)

    # 4. Catalogue
    usages = _uniques(u for *_, obj in objectifs for u in obj.get("usages", []))
    if ctx.inclure_catalogue and (usages or ctx.familles_vehicules) and not base.catalogue.empty:
        selcat = cat_mod.filtrer(base.catalogue, usages or None, ctx.familles_vehicules or None,
                                 ctx.prix_max, ctx.location_seulement)
        synth = cat_mod.preuve_synthese(selcat, usages)
        if synth and autorisee(synth):
            s = Section("Des vélis disponibles pour vos usages")
            s.blocs.append(bloc_preuve(synth))
            n_max = 12
            titre_tab = "Sélection du catalogue" if len(selcat) <= n_max else (
                f"Sélection de {n_max} modèles (un par constructeur, les plus adaptés aux usages visés) "
                f"parmi {len(selcat)} références")
            s.blocs.append(Bloc("tableau", tableau=cat_mod.tableau(selcat, n_max), titre=titre_tab))
            sections.append(s)
        elif not synth:
            avert.append("Aucun véli du catalogue ne correspond aux filtres choisis.")

    # 5. Ordres de grandeur
    if ctx.inclure_relativiser:
        s = Section("Ordres de grandeur")
        s.blocs.append(Bloc("paragraphe", texte="Ces repères permettent de situer l'effort public consacré aux vélis, "
                            "sans opposer vélis et automobile : les deux répondent à des besoins différents et complémentaires."))
        for pid in PREUVES_RELATIVISER:
            p = base.preuves.get(pid)
            if p and pid not in deja and autorisee(p):
                s.blocs.append(bloc_preuve(p))
        if len(s.blocs) > 1:
            sections.append(s)

    # 6. Objections
    if ctx.inclure_objections:
        oids = _uniques(o for *_, obj in objectifs for o in obj.get("objections", []))[:6]
        s = Section("Vos questions, nos réponses")
        for oid in oids:
            o = base.objections.get(oid)
            if not o:
                continue
            s.blocs.append(Bloc("question", titre=o["question"], texte=o["reponse"]))
            reperes = [base.preuves[p] for p in o.get("preuves", []) if p in base.preuves and autorisee(base.preuves[p])]
            nouveaux = [p for p in reperes if p["id"] not in deja][:2]
            for p in nouveaux:
                s.blocs.append(bloc_preuve(p))
            if not nouveaux:
                cites = [cit.numero(p["source"]) for p in reperes[:3]]
                if cites:
                    s.blocs.append(Bloc("paragraphe", texte="Voir les éléments sourcés ci-dessus "
                                        + ", ".join(f"[{c}]" for c in _uniques(cites)) + "."))
            if o.get("vigilance"):
                s.blocs.append(Bloc("paragraphe", texte="À savoir : " + o["vigilance"]))
        if s.blocs:
            sections.append(s)

    # 7. Passer à l'action
    actions = _uniques(a for *_, obj in objectifs for a in obj.get("actions", []))
    if actions:
        sections.append(Section("Comment s'engager concrètement", [Bloc("puces", items=actions)]))

    # 8. Pour aller plus loin
    rids = _uniques(r for *_, obj in objectifs for r in obj.get("ressources", []))
    liens = [f"{base.ressources[r]['titre']} — {base.ressources[r]['url']}" for r in rids if r in base.ressources]
    if liens:
        sections.append(Section("Pour aller plus loin", [Bloc("puces", items=liens[:10])]))

    # 9. Conseils pour la personne qui présente (note interne)
    if ctx.inclure_conseils:
        conseils = _uniques(obj["conseil"] for *_, obj in objectifs if obj.get("conseil"))
        if any(t in ctx.types_territoire for t in ("rural", "periurbain")) or any(
                o in ("communication", "tourisme") for _, o, *_ in objectifs):
            p = base.preuves.get("SHS-01")
            if p:
                conseils.append(p["texte"])
        if conseils:
            sections.append(Section("Conseils pour présenter cet argumentaire (à retirer avant envoi)",
                                    [Bloc("puces", items=conseils)], note_interne=True))

    references = [(i + 1, sid) for i, sid in enumerate(cit.ordre)]
    for _, sid in references:
        if base.sources.get(sid, {}).get("diffusion") != "publique":
            avert.append("Cet argumentaire cite des documents internes : vérifier avant toute diffusion externe.")
            break
    return Argumentaire(titre, sous_titre, sections, references, _uniques(avert), utilisees)


# ───────────────────────────── Rendu Markdown ─────────────────────────────

def _cite(b: Bloc) -> str:
    if b.ref is None:
        return ""
    page = f", {b.page}" if b.page and b.page != "calcul de l'outil" else ""
    return f" [{b.ref}{page}]"


def vers_markdown(arg: Argumentaire, base: Base, afficher_niveaux: bool = True, inclure_notes: bool = True,
                  style: str = "redige") -> str:
    lignes = [f"# {arg.titre}", f"*{arg.sous_titre}*", ""]
    if style == "redige":
        from .redaction import en_prose
        for titre, elements in en_prose(arg, afficher_niveaux, inclure_notes):
            lignes += [f"## {titre}", ""]
            for el in elements:
                if el[0] == "p":
                    lignes += [el[1], ""]
                elif el[0] == "h":
                    lignes += [f"**{el[1]}**", ""]
                elif el[0] == "table":
                    if el[1]:
                        lignes += [f"*{el[1]}*", ""]
                    lignes += [el[2].to_markdown(index=False), ""]
        return "\n".join(lignes + _sources_markdown(arg, base, afficher_niveaux))
    for s in arg.sections:
        if s.note_interne and not inclure_notes:
            continue
        lignes += [f"## {s.titre}", ""]
        for b in s.blocs:
            if b.type == "paragraphe":
                lignes += ["", b.texte, ""]
            elif b.type == "preuve":
                badge = f" *({NIVEAUX.get(b.niveau, b.niveau)})*" if afficher_niveaux and b.niveau else ""
                titre = f"**{b.titre}.** " if b.titre else ""
                lignes.append(f"- {titre}{b.texte}{_cite(b)}{badge}")
                if b.limite and afficher_niveaux:
                    lignes.append(f"  - *Précaution : {b.limite}*")
            elif b.type == "puces":
                if b.titre:
                    lignes += [f"**{b.titre}**", ""]
                lignes += [f"- {i}" for i in b.items]
                lignes.append("")
            elif b.type == "verbatim":
                lignes += ["", f"> « {b.texte} » — {b.attribution} [{b.ref}]", ""]
            elif b.type == "question":
                lignes += ["", f"**« {b.titre} »**", "", b.texte, ""]
            elif b.type == "tableau" and b.tableau is not None and not b.tableau.empty:
                if b.titre:
                    lignes += ["", f"**{b.titre}**", ""]
                lignes += [b.tableau.to_markdown(index=b.tableau.index.name is not None), ""]
        lignes.append("")
    return "\n".join(lignes + _sources_markdown(arg, base, afficher_niveaux))


def _sources_markdown(arg: Argumentaire, base: Base, afficher_niveaux: bool) -> list:
    lignes = ["## Sources", ""]
    for num, sid in arg.references:
        src = base.sources.get(sid, {})
        statut = "" if src.get("diffusion") == "publique" else " — *document interne*"
        url = f" — {src['url']}" if src.get("url") else ""
        lignes.append(f"{num}. {src.get('auteur', '')}, *{src.get('titre', sid)}*, {src.get('date', '')}{url}{statut}")
    if afficher_niveaux:
        lignes += ["", "*Les mentions « estimation », « projection » et « objectif » signalent des chiffres qui reposent "
                   "sur les hypothèses des documents cités ; les autres chiffres sont des données mesurées, des retours "
                   "de terrain ou des textes en vigueur.*"]
    return lignes
