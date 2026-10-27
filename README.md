# Générateur d'argumentaires XD

Application web (Streamlit) qui produit des **argumentaires sourcés** pour convaincre les acteurs de s'engager
avec les vélis : collectivités, entreprises avec flotte, financeurs, partenaires, laboratoires, écoles, associations.

Chaque argumentaire assemble, pour la ou les cibles cochées :

- les **arguments clés** tirés d'une base de preuves sourcées (`data/preuves.yaml`, 100+ faits avec source, page et niveau de preuve) ;
- des **statistiques recalculées** sur les 1 824 carnets de bord de l'expérimentation 30 vélis (bilan, bénéfices, difficultés, pluie, distances), filtrables par motif de trajet et par territoire, avec des verbatims de testeurs ;
- les **vélis à la vente** adaptés aux usages visés (prix, location, délais) ;
- les **réponses aux objections** fréquentes, avec ce qu'il faut honnêtement reconnaître ;
- les **étapes pour s'engager** et les ressources du wiki XD ;
- une liste de **sources numérotées**, avec le statut public / interne de chacune.

Aucun chiffre n'est généré par une IA. Une étape de **rédaction assistée** (facultative, API Albert de l'État ou API Claude) reformule le texte
à partir des seules preuves sélectionnées, puis signale tout nombre absent du dossier de preuves.

---

## Mettre l'outil en ligne (sans rien installer sur votre ordinateur)

### 1. Créer le dépôt GitHub
1. Sur github.com : **New repository** → nom `xd-argumentaires` → cocher **Private** (recommandé : la base contient des éléments issus de documents internes) → *Create repository*.
2. Dans le dépôt vide : **Add file → Upload files**, puis glisser **le contenu** du dossier décompressé
   (`app.py`, `requirements.txt`, les dossiers `data`, `xd`, `outils`, `tests`, `exemples`, `.streamlit`).
   Les dossiers commençant par un point peuvent être masqués par votre explorateur : vérifiez que `.streamlit/config.toml` est bien envoyé (sinon le créer via *Add file → Create new file*).
3. **Commit changes**.

> Le dossier `brut/` (données sources avec coordonnées personnelles) n'est pas dans l'archive et ne doit jamais être publié.

### 2. Déployer sur Streamlit Community Cloud
1. Aller sur https://share.streamlit.io, se connecter avec GitHub.
2. **Create app** → choisir le dépôt `xd-argumentaires`, branche `main`, fichier `app.py` → **Deploy**.
3. Dans **Settings → Secrets**, coller (en adaptant) le contenu de `.streamlit/secrets.toml.example` :
   - `APP_PASSWORD` : protège l'accès par un mot de passe (conseillé si le dépôt contient des éléments internes) ;
   - `ALBERT_API_KEY` : active l'onglet *Rédaction assistée* avec Albert, l'API IA de l'État (facultatif) ;
   - ou `ANTHROPIC_API_KEY` pour utiliser Claude à la place (clé commençant par `sk-ant-`) ;
   - `MODELE` : modèle utilisé (facultatif ; par défaut `openweight-large` pour Albert, voir
     https://guides.ia.numerique.gouv.fr/albert-api/modeles/available-models).
4. Dans **Settings → Sharing**, restreindre les personnes autorisées si besoin.

À chaque modification d'un fichier sur GitHub, l'application se met à jour automatiquement.

---

## Faire évoluer les contenus (directement sur GitHub, bouton ✏️)

| Je veux... | Fichier |
|---|---|
| Corriger ou ajouter un argument chiffré | `data/preuves.yaml` |
| Passer une source de « interne » à « publique » | `data/sources.yaml` (ligne `diffusion`) |
| Modifier les cibles, accroches, enjeux, étapes, arguments retenus par cible | `data/cibles.yaml` |
| Modifier les objections et réponses | `data/objections.yaml` |
| Ajouter des liens « pour aller plus loin » | `data/ressources.yaml` |

Format d'une preuve :

```yaml
- id: ECO-12
  titre: "Titre court"
  texte: "Phrase prête à l'emploi, avec le chiffre exact."
  source: bilan_thematique_2025      # identifiant déclaré dans data/sources.yaml
  page: "p. 12"
  niveau: mesure                     # mesure | terrain | reglementaire | estimation | projection | objectif
  limite: "Précaution éventuelle"    # facultatif
  themes: [economie, flotte]
```

Puis l'ajouter à la liste `preuves:` des objectifs concernés dans `data/cibles.yaml`.
L'application signale en haut de page toute référence incohérente (preuve ou source inconnue).

## Rafraîchir les données (Google Colab)

```python
!git clone https://github.com/<compte>/xd-argumentaires.git
%cd xd-argumentaires
!pip install -q pandas pyyaml openpyxl
# déposer dans brut/ : 30veli_export_experiences.csv (https://30veli.fabmob.io/export),
#                      velis_a_la_vente.csv, deploiement_reponses.xlsx
!python outils/preparer_donnees.py
```

Puis renvoyer sur GitHub les fichiers mis à jour de `data/` (`experiences_30veli.csv`, `catalogue_velis.csv`, `deploiement_agrege.json`).
Le script retire les noms, prénoms et e-mails des contacts constructeurs et n'agrège que des indicateurs anonymes du questionnaire déploiement.

## Intégrer les pages du wiki XD et les fiches du cloud FabMob

Ces pages n'étaient pas accessibles lors de la construction de l'outil. Le script `outils/importer_wiki.py`
(à lancer dans Colab, voir l'en-tête du fichier) récupère les pages listées dans `data/ressources.yaml`
et propose des phrases chiffrées dans `data/preuves_a_valider.yaml`. Après relecture, copier les preuves
validées dans `data/preuves_complementaires.yaml` (chargé automatiquement) et déclarer leurs sources.

## Lancer les contrôles

```
pip install -r requirements.txt pytest
python -m pytest -q
```

## Structure

```
app.py                  interface Streamlit
xd/donnees.py           chargement et contrôle de cohérence des données
xd/stats.py             statistiques sur les carnets 30 vélis (classement des motifs, verbatims)
xd/catalogue.py         sélection des vélis à la vente
xd/generateur.py        assemblage de l'argumentaire et rendu Markdown
xd/export.py            export Word
xd/ia.py                rédaction assistée et vérification des nombres
data/                   base de preuves, sources, cibles, objections, ressources, données préparées
outils/                 préparation des données, import du wiki
exemples/               exemple d'argumentaire généré
```
