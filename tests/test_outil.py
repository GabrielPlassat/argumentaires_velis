"""Tests de non-régression. Lancer : python -m pytest -q"""
import itertools
import re

from xd import stats as st_mod
from xd.donnees import charger
from xd.export import vers_docx
from xd.generateur import Contexte, generer, vers_markdown
from xd.ia import verifier_nombres

BASE = charger()


def tous_les_objectifs():
    return [(f, o) for f, fam in BASE.cibles.items() for o in fam["objectifs"]]


def test_donnees_coherentes():
    assert BASE.anomalies == []


def test_chaque_objectif_genere_un_argumentaire():
    for sel in tous_les_objectifs():
        for externe in (True, False):
            arg = generer(BASE, Contexte(selection=[sel], diffusion_externe=externe, inclure_relativiser=True))
            md = vers_markdown(arg, BASE)
            assert "## Sources" in md
            assert len(arg.preuves_utilisees) >= 3, sel
            vers_docx(arg, BASE)


def test_mode_externe_sans_source_interne():
    for sel in tous_les_objectifs():
        arg = generer(BASE, Contexte(selection=[sel], diffusion_externe=True, inclure_relativiser=True))
        for _, sid in arg.references:
            assert BASE.sources[sid]["diffusion"] == "publique", (sel, sid)


def test_combinaisons_et_territoires():
    objs = tous_les_objectifs()
    for a, b in itertools.islice(itertools.combinations(objs, 2), 0, 60):
        generer(BASE, Contexte(selection=[a, b], types_territoire=["rural", "montagne"],
                               territoires_30veli=["Le Mans", "CC Clunisois"]))


def test_citations_numerotees_existent():
    arg = generer(BASE, Contexte(selection=tous_les_objectifs()[:4], diffusion_externe=False))
    md = vers_markdown(arg, BASE)
    nums = {int(n) for n in re.findall(r"\[(\d+)[,\]]", md)}
    assert nums <= {n for n, _ in arg.references}


def test_classement_motifs():
    assert st_mod.categoriser_motif("Domicile / travail") == "domicile_travail"
    assert st_mod.categoriser_motif("Trajet pro") == "professionnel"
    assert st_mod.categoriser_motif("Récupération du véhicule") == "gestion_expe"
    assert st_mod.categoriser_motif("Rdv médical") == "sante"
    assert st_mod.categoriser_motif("Ecole (enfants)") == "ecole"


def test_verification_ia_repere_un_chiffre_invente():
    arg = generer(BASE, Contexte(selection=[("collectivite", "flotte")], diffusion_externe=False))
    texte = "Les vélis coûtent 1 € aux 100 km [1] et réduisent les coûts de 87,3 %."
    suspects = verifier_nombres(texte, arg, BASE)
    assert "87,3" in suspects and "1" not in suspects


def test_choix_fournisseur_ia():
    from xd.ia import choisir_fournisseur
    assert choisir_fournisseur({"ALBERT_API_KEY": "abc"}) == ("albert", "abc")
    assert choisir_fournisseur({"ANTHROPIC_API_KEY": "sk-ant-x"}) == ("anthropic", "sk-ant-x")
    # clé Albert rangée par erreur sous ANTHROPIC_API_KEY : reconnue comme Albert
    assert choisir_fournisseur({"ANTHROPIC_API_KEY": "cle-albert"}) == ("albert", "cle-albert")
    assert choisir_fournisseur({}) is None


def test_redaction_albert_simulee(monkeypatch):
    import sys, types
    from xd import ia
    appels = {}

    class FauxClient:
        def __init__(self, base_url, api_key):
            appels["url"] = base_url
            self.chat = types.SimpleNamespace(completions=types.SimpleNamespace(create=self.create))

        def create(self, **kw):
            appels["modele"] = kw["model"]
            msg = types.SimpleNamespace(content="Texte rédigé [1].")
            return types.SimpleNamespace(choices=[types.SimpleNamespace(message=msg)])

    monkeypatch.setitem(sys.modules, "openai", types.SimpleNamespace(OpenAI=FauxClient))
    arg = generer(BASE, Contexte(selection=[("collectivite", "flotte")]))
    texte = ia.rediger(arg, BASE, "cle", "test", fournisseur="albert", modele="claude-sonnet-5-5")
    assert texte == "Texte rédigé [1]."
    assert appels["url"] == "https://albert.api.etalab.gouv.fr/v1"
    assert appels["modele"] == "openweight-large"
