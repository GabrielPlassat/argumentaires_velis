"""Générateur d'argumentaires XD — application Streamlit.

Lancer en local :  streamlit run app.py
Déployer : voir README.md (Streamlit Community Cloud, depuis un dépôt GitHub).
"""
from __future__ import annotations

import datetime as dt
import re

import pandas as pd
import streamlit as st

from xd import catalogue as cat_mod
from xd import stats as st_mod
from xd.donnees import charger
from xd.export import vers_docx
from xd.generateur import NIVEAUX, TERRITOIRES, Contexte, generer, vers_markdown

st.set_page_config(page_title="Générateur d'argumentaires XD", page_icon="🚲", layout="wide")


# ───────────────────────── Accès protégé (facultatif) ─────────────────────────
def _secret(nom, defaut=None):
    try:
        return st.secrets.get(nom, defaut)
    except Exception:
        return defaut


mot_de_passe = _secret("APP_PASSWORD")
if mot_de_passe and not st.session_state.get("acces_ok"):
    st.title("Générateur d'argumentaires XD")
    saisie = st.text_input("Mot de passe", type="password")
    if saisie and saisie == mot_de_passe:
        st.session_state["acces_ok"] = True
        st.rerun()
    elif saisie:
        st.error("Mot de passe incorrect.")
    st.stop()


@st.cache_resource
def base_donnees():
    return charger()


base = base_donnees()
exp = st_mod.preparer(base.experiences)

st.title("Générateur d'argumentaires XD")
st.caption("Argumentaires sourcés pour convaincre les acteurs de s'engager avec les vélis — "
           "à partir des expérimentations, du catalogue des vélis à la vente et des rapports du programme eXtrême Défi.")

if base.anomalies:
    with st.expander(f"⚠️ {len(base.anomalies)} incohérence(s) dans les fichiers de données"):
        for a in base.anomalies:
            st.write("- " + a)

onglet_gen, onglet_ia, onglet_donnees, onglet_preuves, onglet_aide = st.tabs(
    ["✍️ Argumentaire", "🤖 Rédaction assistée", "📊 Données terrain", "📚 Base de preuves", "❓ Mode d'emploi"])

# ───────────────────────────────── Génération ─────────────────────────────────
with onglet_gen:
    col_g, col_d = st.columns([1, 1.4], gap="large")
    with col_g:
        st.subheader("1. À qui s'adresse l'argumentaire ?")
        selection = []
        for fam_id, fam in base.cibles.items():
            with st.expander(fam["label"], expanded=(fam_id == "collectivite")):
                for obj_id, obj in fam["objectifs"].items():
                    if st.checkbox(obj["label"], key=f"c_{fam_id}_{obj_id}"):
                        selection.append((fam_id, obj_id))

        st.subheader("2. Contexte")
        structure = st.text_input("Nom de la structure destinataire (facultatif)",
                                  placeholder="ex. la Communauté de communes du Clunisois")
        types = st.multiselect("Type de territoire", options=list(TERRITOIRES),
                               format_func=lambda k: TERRITOIRES[k][0], placeholder="Choisir...")
        territoires_ref = st.multiselect(
            "Territoires d'expérimentation à mettre en avant (facultatif)",
            options=sorted(exp["territoire"].dropna().unique()) if not exp.empty else [],
            help="Les statistiques terrain seront calculées sur ces seuls territoires (comparables au destinataire).", placeholder="Choisir...")

        with st.expander("Vélis à présenter"):
            familles_v = st.multiselect("Familles de vélis", list(cat_mod.FAMILLES), placeholder="Choisir...")
            prix_max = st.number_input("Prix d'achat maximum (€ HT, 0 = sans limite)", min_value=0, step=1000, value=0)
            location = st.checkbox("Uniquement les modèles proposés en location")

        st.subheader("3. Options")
        diffusion_externe = st.toggle("Mode diffusion externe (sources publiques uniquement)", value=True,
                                      help="Écarte automatiquement les chiffres issus de documents internes.")
        c1, c2 = st.columns(2)
        objections = c1.checkbox("Réponses aux objections", value=True)
        relativiser = c1.checkbox("Ordres de grandeur (comparaison automobile)", value=False)
        catalogue = c2.checkbox("Tableau des vélis disponibles", value=True)
        niveaux = c2.checkbox("Afficher les niveaux de preuve", value=True)
        conseils = st.checkbox("Ajouter des conseils de présentation (note interne)", value=True)
        max_preuves = st.slider("Nombre d'arguments clés", 4, 15, 9)

        if st.button("Générer l'argumentaire", type="primary", disabled=not selection, width="stretch"):
            ctx = Contexte(selection=selection, structure=structure, types_territoire=types,
                           territoires_30veli=territoires_ref, diffusion_externe=diffusion_externe,
                           inclure_objections=objections, inclure_relativiser=relativiser,
                           inclure_conseils=conseils, inclure_catalogue=catalogue, max_preuves=max_preuves,
                           familles_vehicules=familles_v, prix_max=prix_max or None, location_seulement=location)
            st.session_state["arg"] = generer(base, ctx)
            st.session_state["ctx"] = ctx
            st.session_state["niveaux"] = niveaux
        if not selection:
            st.info("Cochez au moins un objectif pour générer un argumentaire.")

    with col_d:
        arg = st.session_state.get("arg")
        if arg:
            for a in arg.avertissements:
                st.warning(a)
            md_complet = vers_markdown(arg, base, st.session_state.get("niveaux", True), inclure_notes=True)
            md_diffusion = vers_markdown(arg, base, st.session_state.get("niveaux", True), inclure_notes=False)
            nom = f"argumentaire_xd_{dt.date.today().isoformat()}"
            b1, b2 = st.columns(2)
            b1.download_button("Télécharger en Word (.docx)",
                               vers_docx(arg, base, st.session_state.get("niveaux", True)),
                               file_name=f"{nom}.docx", width="stretch",
                               mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
            b2.download_button("Télécharger en Markdown (.md)", md_diffusion, file_name=f"{nom}.md",
                               width="stretch")
            st.caption("Les fichiers téléchargés n'incluent pas la note interne de conseils.")
            st.markdown(re.sub(r"^(#{1,2}) ", lambda m: "#" * (len(m.group(1)) + 2) + " ", md_complet, flags=re.M))
        else:
            st.markdown("#### L'argumentaire apparaîtra ici")
            st.write("Chaque argument est relié à sa source (numéro entre crochets), avec son niveau de preuve. "
                     "Les statistiques terrain sont recalculées à partir des carnets de bord 30 vélis.")

# ───────────────────────────── Rédaction assistée ─────────────────────────────
with onglet_ia:
    st.subheader("Reformuler l'argumentaire avec l'IA")
    st.write("Étape facultative : l'IA reformule l'argumentaire en texte suivi, **uniquement** à partir des preuves "
             "sélectionnées. Un contrôle signale ensuite tout nombre absent du dossier de preuves.")
    arg = st.session_state.get("arg")
    from xd.ia import FOURNISSEURS, ErreurIA, choisir_fournisseur, rediger, verifier_nombres

    choix_ia = choisir_fournisseur({k: _secret(k) for k in ("ALBERT_API_KEY", "ANTHROPIC_API_KEY")})
    if not arg:
        st.info("Générez d'abord un argumentaire dans l'onglet « Argumentaire ».")
    elif not choix_ia:
        st.info("Aucune clé d'API n'est configurée. Ajoutez ALBERT_API_KEY (API de l'État) ou ANTHROPIC_API_KEY "
                "dans les secrets de l'application (voir le mode d'emploi). "
                "L'argumentaire de l'onglet principal reste utilisable sans IA.")
    else:
        fournisseur, cle = choix_ia
        modele = _secret("MODELE") or FOURNISSEURS[fournisseur]["modele"]
        if fournisseur == "albert" and modele.startswith("claude"):
            modele = FOURNISSEURS["albert"]["modele"]
        st.caption(f"IA utilisée : {FOURNISSEURS[fournisseur]['nom']} — modèle « {modele} »")
        consignes = st.text_area("Précisez la cible et la situation (rendez-vous, courrier, réunion publique...)",
                                 placeholder="ex. Courrier au président de l'intercommunalité, qui doit renouveler 6 véhicules de service en 2027.")
        c1, c2 = st.columns(2)
        longueur = c1.selectbox("Longueur", ["1 page", "2 pages", "4 pages", "un courriel de 15 lignes"], index=1)
        ton = c2.selectbox("Ton", ["institutionnel", "direct et concret", "pédagogique", "convaincant pour des élus"])
        if st.button("Rédiger", type="primary"):
            texte = None
            with st.spinner("Rédaction en cours..."):
                try:
                    texte = rediger(arg, base, cle, consignes or "voir dossier", longueur, ton, modele, fournisseur)
                except ErreurIA as e:
                    st.error(str(e))
            if texte:
                st.session_state["texte_ia"] = texte
                st.session_state["suspects"] = verifier_nombres(texte, arg, base, consignes + " " + st.session_state["ctx"].structure)
        if st.session_state.get("texte_ia"):
            suspects = st.session_state.get("suspects", [])
            if suspects:
                st.error("Nombres absents du dossier de preuves, à vérifier ou supprimer : " + ", ".join(suspects))
            else:
                st.success("Contrôle : tous les nombres du texte figurent dans le dossier de preuves.")
            st.download_button("Télécharger le texte (.md)", st.session_state["texte_ia"],
                               file_name="argumentaire_xd_redige.md")
            st.markdown(st.session_state["texte_ia"])

# ───────────────────────────────── Données ─────────────────────────────────
with onglet_donnees:
    st.subheader("Carnets de bord de l'expérimentation 30 vélis")
    if exp.empty:
        st.info("Aucune donnée d'expérimentation chargée (data/experiences_30veli.csv).")
    else:
        f1, f2, f3 = st.columns(3)
        motifs = f1.multiselect("Motifs de trajet", list(st_mod.LIBELLES_MOTIFS),
                                format_func=lambda k: st_mod.LIBELLES_MOTIFS[k], placeholder="Choisir...")
        terr = f2.multiselect("Territoires", sorted(exp["territoire"].dropna().unique()), placeholder="Choisir...")
        veh = f3.multiselect("Vélis", sorted(exp["vehicule"].dropna().unique()), placeholder="Choisir...")
        sel = st_mod.filtrer(exp, motifs or None, terr or None, veh or None)
        renseignes = sel[sel["bilan_renseigne"]]
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Carnets (hors gestion de l'expé)", st_mod.fmt_nb(len(sel)))
        m2.metric("Bilan positif ou très positif",
                  st_mod.fmt_pct(renseignes["bilan_positif"].mean()) if len(renseignes) else "—")
        m3.metric("Territoires", sel["territoire"].nunique())
        m4.metric("Modèles de vélis", sel["vehicule"].nunique())
        for p in st_mod.preuves_calculees(exp, motifs or None, terr or None, veh or None):
            st.markdown(f"- {p['texte']}")
        c1, c2 = st.columns(2)
        c1.markdown("**Par territoire**")
        c1.dataframe(st_mod.tableau_territoires(sel), width="stretch")
        c2.markdown("**Par véli (10 carnets ou plus)**")
        c2.dataframe(st_mod.tableau_vehicules(sel), width="stretch")
        with st.expander("Répartition des motifs de trajet (classement automatique)"):
            st.dataframe(exp["categorie_motif"].value_counts().rename("carnets"))
        with st.expander("Lire les commentaires des testeurs"):
            st.dataframe(sel[["territoire", "vehicule", "motif", "bilan", "commentaires", "difficultes_details"]]
                         .dropna(subset=["commentaires"]), width="stretch", hide_index=True)

    st.subheader("Vélis à la vente")
    if not base.catalogue.empty:
        u = st.multiselect("Cas d'usage", cat_mod.USAGES, placeholder="Choisir...")
        fam = st.multiselect("Familles", list(cat_mod.FAMILLES), key="fam_cat", placeholder="Choisir...")
        selc = cat_mod.filtrer(base.catalogue, u or None, fam or None)
        p = cat_mod.preuve_synthese(selc, u)
        if p:
            st.markdown(p["texte"])
        st.dataframe(cat_mod.tableau(selc), width="stretch", hide_index=True)

    if base.deploiement:
        st.subheader("Questionnaire « Déploiement 2026 » (indicateurs agrégés, document interne)")
        d = base.deploiement
        a, b, c = st.columns(3)
        a.metric("Réponses", d["nb_reponses"])
        b.metric("Vélis envisagés (médiane par projet)", f"{d['velis_envisages_mediane']:.0f}")
        c.metric("Ont contacté leur territoire", d["contact_territoire_oui"])
        x, y = st.columns(2)
        x.dataframe(pd.Series(d["profils"], name="réponses"))
        y.dataframe(pd.Series(d["types_projet"], name="réponses"))

# ─────────────────────────────── Base de preuves ───────────────────────────────
with onglet_preuves:
    st.subheader("Base de preuves")
    lignes = []
    for p in base.preuves.values():
        src = base.sources.get(p["source"], {})
        lignes.append({"id": p["id"], "titre": p.get("titre", ""), "niveau": NIVEAUX.get(p["niveau"], p["niveau"]),
                       "source": src.get("titre", p["source"]), "page": p.get("page", ""),
                       "diffusion": src.get("diffusion", "?"), "thèmes": ", ".join(p.get("themes", [])),
                       "texte": p["texte"], "précaution": p.get("limite", "")})
    df_p = pd.DataFrame(lignes)
    q = st.text_input("Rechercher (mot, chiffre, thème)")
    if q:
        masque = df_p.apply(lambda r: q.lower() in " ".join(map(str, r.values)).lower(), axis=1)
        df_p = df_p[masque]
    st.caption(f"{len(df_p)} preuve(s). Pour ajouter ou corriger une preuve : modifier data/preuves.yaml sur GitHub.")
    st.dataframe(df_p, width="stretch", hide_index=True)
    with st.expander("Registre des sources"):
        st.dataframe(pd.DataFrame(base.sources).T[["titre", "auteur", "date", "diffusion"]], width="stretch")

# ─────────────────────────────── Mode d'emploi ───────────────────────────────
with onglet_aide:
    st.markdown("""
### Comment ça marche
1. **Cochez une ou plusieurs cibles** (collectivité, entreprise, financeur, partenaire, laboratoire, école, association)
   et l'objectif visé. La liste reprend le document « Générateur d'argumentaires XD ».
2. **Précisez le contexte** : nom du destinataire, type de territoire, territoires d'expérimentation comparables.
3. **Générez** : l'outil assemble les arguments les plus pertinents, recalcule les statistiques terrain,
   sélectionne les vélis du catalogue adaptés, ajoute les objections fréquentes et les étapes pour s'engager.
4. **Téléchargez** en Word pour retoucher, ou passez par l'onglet *Rédaction assistée* pour un texte suivi.

### Garanties
- Aucun chiffre n'est inventé : chaque argument vient de `data/preuves.yaml` (avec source et page)
  ou d'un calcul sur les données (`data/experiences_30veli.csv`, `data/catalogue_velis.csv`).
- Le **niveau de preuve** distingue mesures, retours de terrain, textes en vigueur, estimations, projections et objectifs.
- Le **mode diffusion externe** écarte les documents internes (Bilan XD 2022-2025, notes de travail...).
- La rédaction IA (Albert ou Claude) est contrôlée : tout nombre absent du dossier de preuves est signalé.

### Mettre à jour les contenus
- Corriger ou ajouter un argument : éditer `data/preuves.yaml` directement sur GitHub (bouton crayon).
- Changer le statut d'une source (interne / publique) : `data/sources.yaml`.
- Ajuster les cibles, objectifs, objections, étapes : `data/cibles.yaml` et `data/objections.yaml`.
- Rafraîchir les données 30 vélis ou le catalogue : `outils/preparer_donnees.py` (voir README).
""")
