"""
Importe le contenu des pages du wiki XD et des partages cloud.fabmob listés dans
data/ressources.yaml, puis propose des « preuves candidates » à valider.

Pourquoi ce script ? Ces pages ne sont pas accessibles depuis l'environnement où l'outil a été
construit : il faut donc les récupérer depuis votre ordinateur ou Google Colab.

Utilisation dans Google Colab :
    !git clone https://github.com/<votre-compte>/xd-argumentaires.git
    %cd xd-argumentaires
    !pip install -q pyyaml requests pypdf python-docx
    !python outils/importer_wiki.py

Résultats :
  - brut/import/<id>.txt                 texte brut de chaque page ou document
  - data/preuves_a_valider.yaml          phrases chiffrées repérées, à relire
Pour publier une preuve : la recopier (en la reformulant si besoin) dans
data/preuves_complementaires.yaml et ajouter sa source dans data/sources.yaml.
Les preuves de ce fichier sont automatiquement chargées par l'application.
"""
from __future__ import annotations

import io
import re
import sys
import zipfile
from pathlib import Path
from urllib.parse import unquote, urlparse

import requests
import yaml

RACINE = Path(__file__).resolve().parents[1]
SORTIE = RACINE / "brut" / "import"
ENTETE = {"User-Agent": "xd-argumentaires/1.0 (outil ADEME eXtreme Defi)"}


def texte_wiki(url: str) -> str | None:
    """Récupère le texte d'une page MediaWiki via son API (plusieurs chemins possibles)."""
    p = urlparse(url)
    titre = unquote(p.path.split("/wiki/", 1)[-1])
    for chemin in ("/api.php", "/w/api.php"):
        api = f"{p.scheme}://{p.netloc}{chemin}"
        try:
            r = requests.get(api, params={"action": "parse", "page": titre, "prop": "text",
                                          "format": "json", "formatversion": 2}, headers=ENTETE, timeout=30)
            if r.ok and "parse" in r.json():
                html = r.json()["parse"]["text"]
                txt = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.S)
                txt = re.sub(r"<br\s*/?>|</p>|</li>|</h\d>|</tr>", "\n", txt)
                txt = re.sub(r"<[^>]+>", " ", txt)
                return re.sub(r"[ \t]+", " ", txt)
        except Exception:
            continue
    return None


def texte_document(contenu: bytes, nom: str) -> str:
    nom = nom.lower()
    if nom.endswith(".pdf") or contenu[:4] == b"%PDF":
        from pypdf import PdfReader
        return "\n".join((pg.extract_text() or "") for pg in PdfReader(io.BytesIO(contenu)).pages)
    if nom.endswith(".docx"):
        import docx
        return "\n".join(par.text for par in docx.Document(io.BytesIO(contenu)).paragraphs)
    if nom.endswith((".txt", ".md", ".csv")):
        return contenu.decode("utf-8", errors="ignore")
    return ""


def texte_cloud(url: str) -> str | None:
    """Télécharge un partage public Nextcloud (fichier ou dossier compressé)."""
    base = url.split("?")[0].rstrip("/")
    try:
        r = requests.get(base + "/download", headers=ENTETE, timeout=120)
    except Exception:
        return None
    if not r.ok:
        return None
    nom = r.headers.get("Content-Disposition", "")
    if r.content[:2] == b"PK" and not nom.lower().endswith(".docx\""):
        try:
            z = zipfile.ZipFile(io.BytesIO(r.content))
            morceaux = [f"=== {n}\n" + texte_document(z.read(n), n) for n in z.namelist()
                        if n.lower().endswith((".pdf", ".docx", ".txt", ".md"))]
            if morceaux:
                return "\n\n".join(morceaux)
        except zipfile.BadZipFile:
            pass
    return texte_document(r.content, nom.strip('"; ').split("filename=")[-1])


def phrases_chiffrees(texte: str, maxi: int = 25) -> list[str]:
    phrases = re.split(r"(?<=[.!?])\s+|\n+", texte)
    garder = [p.strip() for p in phrases
              if re.search(r"\d", p) and 40 <= len(p.strip()) <= 400
              and re.search(r"%|€|km|vélis?|testeurs?|trajets?|véhicules?|personnes?|mois|ans", p)]
    vus, out = set(), []
    for p in garder:
        if p not in vus:
            vus.add(p)
            out.append(p)
    return out[:maxi]


def main():
    ressources = yaml.safe_load((RACINE / "data" / "ressources.yaml").read_text(encoding="utf-8"))
    SORTIE.mkdir(parents=True, exist_ok=True)
    candidates = []
    for r in ressources:
        url = r["url"]
        if "wiki" in url and "/wiki/" in url:
            txt = texte_wiki(url)
        elif "cloud.fabmob.io/s/" in url:
            txt = texte_cloud(url)
        else:
            continue
        if not txt:
            print(f"✗ {r['id']} : non récupéré ({url})")
            continue
        (SORTIE / f"{r['id']}.txt").write_text(txt, encoding="utf-8")
        trouve = phrases_chiffrees(txt)
        print(f"✓ {r['id']} : {len(txt):,} caractères, {len(trouve)} phrases chiffrées")
        for i, ph in enumerate(trouve, 1):
            candidates.append({
                "id": f"{r['id']}-{i:02d}", "titre": "À COMPLÉTER", "texte": ph,
                "source": r["id"].lower().replace("-", "_"), "page": "", "niveau": "terrain",
                "themes": r.get("themes", []), "a_valider": True,
                "source_a_declarer": {"titre": r["titre"], "url": url, "diffusion": "publique"},
            })
    (RACINE / "data" / "preuves_a_valider.yaml").write_text(
        "# Phrases repérées automatiquement : à relire, reformuler et copier dans preuves_complementaires.yaml\n"
        + yaml.safe_dump(candidates, allow_unicode=True, sort_keys=False, width=110), encoding="utf-8")
    print(f"\n{len(candidates)} preuves candidates écrites dans data/preuves_a_valider.yaml")


if __name__ == "__main__":
    sys.exit(main())
