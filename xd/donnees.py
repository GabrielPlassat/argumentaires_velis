"""Chargement et validation des données de l'outil (fichiers du dossier data/)."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
import yaml

DATA = Path(__file__).resolve().parents[1] / "data"


def _yaml(nom: str):
    chemin = DATA / nom
    if not chemin.exists():
        return None
    return yaml.safe_load(chemin.read_text(encoding="utf-8"))


@dataclass
class Base:
    sources: dict
    preuves: dict          # id -> preuve
    objections: dict       # id -> objection
    ressources: dict       # id -> ressource
    cibles: dict
    experiences: pd.DataFrame
    catalogue: pd.DataFrame
    deploiement: dict | None
    anomalies: list = field(default_factory=list)

    def source_publique(self, source_id: str) -> bool:
        return self.sources.get(source_id, {}).get("diffusion") == "publique"


def charger() -> Base:
    sources = _yaml("sources.yaml") or {}
    liste_preuves = list(_yaml("preuves.yaml") or [])
    # Fichier facultatif pour des preuves supplémentaires (par exemple issues du wiki)
    liste_preuves += list(_yaml("preuves_complementaires.yaml") or [])
    preuves = {p["id"]: p for p in liste_preuves}
    objections = {o["id"]: o for o in (_yaml("objections.yaml") or [])}
    ressources = {r["id"]: r for r in (_yaml("ressources.yaml") or [])}
    cibles = _yaml("cibles.yaml") or {}

    exp_path = DATA / "experiences_30veli.csv"
    experiences = pd.read_csv(exp_path) if exp_path.exists() else pd.DataFrame()
    cat_path = DATA / "catalogue_velis.csv"
    catalogue = pd.read_csv(cat_path) if cat_path.exists() else pd.DataFrame()
    dep_path = DATA / "deploiement_agrege.json"
    deploiement = json.loads(dep_path.read_text(encoding="utf-8")) if dep_path.exists() else None

    base = Base(sources, preuves, objections, ressources, cibles, experiences, catalogue, deploiement)
    base.anomalies = verifier(base)
    return base


def verifier(base: Base) -> list[str]:
    """Contrôle de cohérence : toute référence doit exister. Renvoie la liste des problèmes."""
    pb = []
    for pid, p in base.preuves.items():
        if p.get("source") not in base.sources:
            pb.append(f"Preuve {pid} : source inconnue « {p.get('source')} »")
        for champ in ("texte", "niveau"):
            if not p.get(champ):
                pb.append(f"Preuve {pid} : champ « {champ} » manquant")
    for oid, o in base.objections.items():
        for pid in o.get("preuves", []):
            if pid not in base.preuves:
                pb.append(f"Objection {oid} : preuve inconnue {pid}")
    for fam_id, fam in base.cibles.items():
        for obj_id, obj in fam.get("objectifs", {}).items():
            ref = f"{fam_id}/{obj_id}"
            for pid in obj.get("preuves", []):
                if pid not in base.preuves:
                    pb.append(f"Cible {ref} : preuve inconnue {pid}")
            for oid in obj.get("objections", []):
                if oid not in base.objections:
                    pb.append(f"Cible {ref} : objection inconnue {oid}")
            for rid in obj.get("ressources", []):
                if rid not in base.ressources:
                    pb.append(f"Cible {ref} : ressource inconnue {rid}")
    return pb
