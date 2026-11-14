# WorldPulse — Qu'est-ce qui rend un pays heureux ?

Quels facteurs (richesse, santé, éducation, internet, emploi, urbanisation) expliquent le mieux le score de bonheur d'un pays ? Ce projet combine les indicateurs de la World Bank et les scores du World Happiness Report pour répondre à cette question, puis les analyse et les modélise.

> Projet en cours. Ce document est complété à chaque étape.
>
> 📓 **Résultats et graphiques de chaque étape : [`notebooks/rapport_worldpulse.ipynb`](notebooks/rapport_worldpulse.ipynb)** (avec le code)
>
> 📄 **Version lecteur, sans code : [`reports/rapport_worldpulse.html`](reports/rapport_worldpulse.html)**, à ouvrir dans un navigateur.

## Sources

| Source | Méthode | Contenu |
|---|---|---|
| [World Bank — World Development Indicators](https://data.worldbank.org/) | API publique : JSON pour la liste des pays, ZIP/CSV (`?downloadformat=csv`) pour les indicateurs | 7 indicateurs, 2013–2025 |
| [Wikipedia — World Happiness Report](https://en.wikipedia.org/wiki/World_Happiness_Report) | Scraping (`requests` + `pd.read_html`) | Score de bonheur par pays et par rapport |

## Avancement

| # | Étape | Script | Sortie | État |
|---|---|---|---|---|
| 1 | Environnement | — | `.venv/`, `requirements.txt` | ✅ |
| 2 | Extraction World Bank | `src/01_extraction_api.py` | `data/raw/worldbank_*.csv` | ✅ |
| 3 | Scraping Wikipedia | `src/02_scraping_wikipedia.py` | `data/raw/wikipedia_*` | ✅ |
| 4 | Nettoyage + fusion | `src/03_nettoyage_fusion.py` | `data/processed/worldpulse_*.csv` | ✅ |
| 5 | Base SQLite | `src/04_base_sqlite.py` | `db/worldpulse.db` | ✅ |
| 6 | Analyse exploratoire | `notebooks/rapport_worldpulse.ipynb` | — | ✅ |
| 7 | Modélisation et sélection des variables | `src/05_modelisation.py` | `reports/modele_*.csv` | ✅ |
| 8 | Clustering | `src/06_clustering.py` | `reports/clustering_*.csv` | ✅ |
| 8b | Test : gouvernance (WGI) | `src/07_gouvernance.py` | `reports/gouvernance_*.csv` | ✅ |
| 8c | Test : paradoxe d'Easterlin | `src/08_easterlin.py` | `reports/easterlin_*.csv` | ✅ |
| 9 | Conclusion | `README.md` | — | ⏳ |

## Utilisation (Windows / PowerShell)

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Tout relancer : scripts src/01 à src/08 dans l'ordre (~15 min, téléchargements compris)
python run_all.py
# ou repartir des données déjà présentes dans data/raw/ (sans téléchargement des étapes 01-02)
python run_all.py --depuis 03

# Rapport : exécuter le notebook, puis exporter la version sans code
jupyter nbconvert --to notebook --execute --inplace notebooks/rapport_worldpulse.ipynb
jupyter nbconvert --to html --no-input --output-dir reports --output rapport_worldpulse notebooks/rapport_worldpulse.ipynb
```

## Dictionnaire des données

### `data/raw/worldbank_pays.csv` — 217 pays et territoires (agrégats régionaux exclus)

| Colonne | Description |
|---|---|
| `iso3` | Code pays ISO 3166-1 alpha-3 (clé de fusion) |
| `pays` | Nom du pays (anglais, World Bank) |
| `region` | Région World Bank (ex. *Sub-Saharan Africa*) |
| `niveau_revenu` | Catégorie de revenu World Bank (*Low* → *High income*) |

### `data/raw/worldbank_indicateurs.csv` — format long : une ligne par (pays, indicateur, année)

| Colonne | Description |
|---|---|
| `iso3` | Code pays ISO3 |
| `indicateur` | Nom court de l'indicateur (voir tableau ci-dessous) |
| `code_wb` | Code officiel World Bank |
| `annee` | Année de la mesure (2013–2025) |
| `valeur` | Valeur ; les lignes sans valeur sont supprimées |

| `indicateur` | Code WB | Définition | Unité |
|---|---|---|---|
| `pib_par_habitant_ppa` | NY.GDP.PCAP.PP.KD | PIB par habitant en parité de pouvoir d'achat | $ internationaux constants 2021 |
| `esperance_vie` | SP.DYN.LE00.IN | Espérance de vie à la naissance | années |
| `internet_pct` | IT.NET.USER.ZS | Personnes utilisant internet | % de la population |
| `chomage_pct` | SL.UEM.TOTL.ZS | Chômage (estimation modélisée OIT) | % de la population active |
| `depenses_education_pct_pib` | SE.XPD.TOTL.GD.ZS | Dépenses publiques d'éducation | % du PIB |
| `depenses_sante_pct_pib` | SH.XPD.CHEX.GD.ZS | Dépenses courantes de santé, publiques et privées | % du PIB |
| `urbanisation_pct` | SP.URB.TOTL.IN.ZS | Population urbaine | % de la population |

### `data/raw/wikipedia_bonheur.csv` — une ligne par (rapport, pays)

| Colonne | Description |
|---|---|
| `rapport` | Année de publication du World Happiness Report |
| `enquete_debut`, `enquete_fin` | Années d'enquête couvertes par le score (rapport − 3 à rapport − 1) |
| `rang` | Rang du pays dans le rapport |
| `pays` | Nom du pays, tel qu'écrit sur Wikipedia |
| `score_bonheur` | **Variable cible.** Moyenne nationale de l'échelle de Cantril, de 0 (pire vie possible) à 10 (meilleure vie possible), sur 3 ans d'enquêtes Gallup |

`data/raw/wikipedia_whr.html` : copie de la page Wikipedia au moment du scraping, conservée pour la traçabilité.

### `data/processed/worldpulse_2026.csv` (146 × 13) et `worldpulse_panel.csv` (1 200 × 13)

Une ligne par (rapport, pays). Le fichier `_2026` contient le rapport 2026 seul (modèle principal). Le fichier `_panel` contient tous les rapports exploitables (2016–2020, 2024–2026).

| Colonne | Description |
|---|---|
| `rapport` | Année du rapport |
| `iso3`, `pays`, `region`, `niveau_revenu` | Identifiants et infos pays (World Bank) |
| `score_bonheur` | Variable cible (voir plus haut) |
| 7 indicateurs | Mêmes noms et unités que dans `worldbank_indicateurs.csv`. Valeur = moyenne sur les années d'enquête du rapport ; à défaut, dernière valeur des 3 années précédentes. `NaN` si aucune des deux n'existe |

### `data/processed/qualite_indicateurs_2026.csv` — origine des valeurs, par indicateur (146 pays)

| Colonne | Description |
|---|---|
| `indicateur` | Nom court de l'indicateur |
| `periode` | Nombre de pays dont la valeur est une moyenne sur 2023–2025 |
| `repli` | Nombre de pays dont la valeur est la dernière disponible sur 2020–2022 |
| `manquant` | Nombre de pays sans valeur |

### Gouvernance : `data/raw/wgi_indicateurs.csv` et `data/processed/worldpulse_2026_gouvernance.csv`

Le premier fichier est au format long, comme `worldbank_indicateurs.csv`, pour les années 2020–2023. Le second reprend `worldpulse_2026.csv` et y ajoute 3 colonnes, avec les valeurs de 2023 uniquement (seule année disponible sur la période d'enquête 2023–2025). Plus la valeur est haute, meilleure est la gouvernance.

⚠️ Dans le fichier archivé, l'échelle n'est pas l'échelle officielle (−2,5 à +2,5) et elle change d'une année à l'autre ; le classement des pays reste cohérent. Les valeurs ne sont donc comparables **qu'au sein d'une même année**.

| Colonne | Code WB | Définition |
|---|---|---|
| `controle_corruption` | CC.EST | Contrôle de la corruption |
| `stabilite_politique` | PV.EST | Stabilité politique et absence de violence |
| `etat_de_droit` | RL.EST | État de droit (justice, police, respect des contrats) |

### `db/worldpulse.db` (SQLite)

| Table / vue | Contenu |
|---|---|
| `pays` | = `data/raw/worldbank_pays.csv` |
| `indicateurs_wb` | = `data/raw/worldbank_indicateurs.csv` |
| `bonheur_wikipedia` | = `data/raw/wikipedia_bonheur.csv` |
| `worldpulse` | = `data/processed/worldpulse_panel.csv` |
| `worldpulse_2026` (vue) | `worldpulse` filtrée sur `rapport = 2026` |

Des requêtes d'exemple (classement, moyennes par région et par revenu, évolution 2016 → 2026) se trouvent dans `src/04_base_sqlite.py`.

### `reports/` — résultats de la modélisation (rapport 2026)

| Fichier | Contenu |
|---|---|
| `modele_complet_metriques.csv` | Modèle à 7 variables : n, R², R² ajusté, AIC, BIC, F, p-valeurs des tests de Shapiro-Wilk, Jarque-Bera et Breusch-Pagan |
| `modele_complet_coefficients.csv` | Modèle à 7 variables : coefficient, erreur standard, t, p-valeur, IC à 95 %, coefficient standardisé |
| `modele_vif.csv` | VIF (facteur d'inflation de la variance) de chaque variable |
| `modele_complet_diagnostics_pays.csv` | Par pays : prédiction, résidu, résidu studentisé, levier, distance de Cook |
| `modele_sous_ensembles.csv` | Les 127 combinaisons : R², R² ajusté, AIC, BIC, Cp de Mallows, RMSE / MAE / R² en validation croisée (`rmse_cv_es` = erreur standard) |
| `modele_lasso_stabilite.csv` | Fréquence de sélection de chaque variable par le Lasso (500 bootstraps) et coefficient Lasso |
| `modele_pcr.csv` | Régression sur k composantes principales : RMSE, R² en validation croisée, variance conservée |
| `modele_cv_imbriquee.csv` | Validation croisée imbriquée : pour chaque pli externe et chaque procédure, variables choisies et erreurs de test |
| `modele_decision.csv` | Procédure retenue et variables du modèle final (lu par `src/07_gouvernance.py`) |
| `modele_final_coefficients.csv` / `modele_final_metriques.csv` | Modèle final : coefficients (bruts et standardisés, IC à 95 %, p-valeurs) et métriques |
| `modele_scores_cv.csv` | MAE, RMSE, R² par modèle et par pli (5 plis × 10 répétitions), en test et en entraînement |
| `modele_predictions.csv` | Score prédit hors échantillon pour chaque pays (régression finale, Random Forest) |
| `modele_importance.csv` | Importance par permutation : hausse de la RMSE quand la variable est mélangée, par modèle et par pli |
| `modele_shap.csv` | Valeurs SHAP du Random Forest : contribution de chaque variable au score prédit de chaque pays (`valeur_de_base` = score moyen) |
| `clustering_choix_k.csv` | Inertie et score de silhouette de K-Means pour k = 2 à 8 |
| `clustering_pays.csv` | Groupe de chaque pays (`groupe`) et ses coordonnées sur les 2 axes de l'ACP (`acp_1`, `acp_2`) |
| `clustering_profils.csv` | Moyenne de chaque indicateur et du score de bonheur par groupe, nombre de pays (`nb_pays`) |
| `gouvernance_scores_cv.csv` | MAE, RMSE, R² par modèle, par jeu de variables (avec ou sans gouvernance) et par pli. Les plis sont identiques pour tous les jeux |
| `gouvernance_predictions.csv` | Prédiction et résidu (score réel − prédit) de chaque pays, sans et avec gouvernance, moyennés sur 10 découpages |
| `gouvernance_coefficients.csv` | Coefficients standardisés de la régression avec gouvernance, entraînée sur tous les pays |
| `easterlin_variations.csv` | Pour chaque pays présent dans les rapports 2016 et 2026 : scores, log PIB, variations (`delta_score`, `delta_log_pib`) et croissance du PIB en % |
| `easterlin_pentes.csv` | Pente du bonheur en fonction du log10 du PIB (points pour un PIB ×10) selon l'approche, avec IC à 95 % par bootstrap (`ic_bas`, `ic_haut`) et tests de robustesse |

## Choix méthodologiques

- **Modèle principal : rapport 2026**, enquêtes 2023–2025. Les indicateurs World Bank seront moyennés sur ces mêmes années.
- **Pas de colonnes « facteurs » du WHR.** Les colonnes *GDP per capita*, *Social support*… des tableaux Wikipedia sont des décompositions du score lui-même. Les utiliser pour prédire le score serait une fuite de données.
- **Indicateurs récupérés en ZIP/CSV.** En novembre 2026, l'API JSON de données renvoyait des erreurs 502. Le téléchargement groupé donne les mêmes données officielles en 7 requêtes.
- **Rapports exploitables :** 2016–2020 et 2024–2026. Sur Wikipedia, les rapports 2022–2023 n'ont pas de score, 2021 et 2014–2015 sont absents, et 2013 ne couvre que les 85 premiers pays.
- **Données brutes jamais modifiées.** Tout le nettoyage se fait à l'étape 4.
- **Pays → ISO3** avec `country_converter`. Corrections manuelles : *Northern Cyprus* et *Somaliland region* (sinon confondus avec Chypre et la Somalie), *World* et *Europe* exclus.
- **Agrégation des indicateurs.** Moyenne sur les années d'enquête du rapport ; sinon, dernière valeur des 3 années précédentes. Pour 2026, le repli concerne surtout les dépenses d'éducation (54 pays sur 146). Le détail par indicateur est dans `data/processed/qualite_indicateurs_2026.csv`.
- **Valeur aberrante.** Les dépenses d'éducation de la Somalie (≈ 0 % du PIB) sont traitées comme manquantes.
- **Valeurs manquantes conservées.** Il en reste 19, réparties sur 12 pays ; 134 pays sur 146 sont complets. Elles seront imputées à l'étape 7, à l'intérieur de la validation croisée, pour éviter une fuite de données.
- **pandas < 3** : `country_converter` 1.3.2 est incompatible avec pandas 3.
- **`log_pib` = log10(PIB par habitant)** remplace le PIB brut pour la modélisation : la distribution du PIB est très asymétrique (asymétrie 1,54 → −0,37 après le log), et son lien avec le bonheur est linéaire en échelle logarithmique.

## Premiers résultats (analyse exploratoire, rapport 2026)

- Le PIB (log, r = 0,79), internet (0,76) et l'espérance de vie (0,74) sont les indicateurs les plus liés au bonheur. Le PIB explique à lui seul 62 % des écarts entre pays.
- Ces trois indicateurs sont très corrélés entre eux (0,84–0,89) : leur effet est à lire comme un bloc « développement ».
- Les dépenses de santé et d'éducation (% du PIB) et le chômage sont faiblement liés au bonheur.
- Plusieurs pays d'Amérique latine sont bien plus heureux que leur PIB ne le prévoit, et l'Afghanistan, le Liban, l'Égypte ou le Botswana bien moins. Les explications avancées (liens sociaux selon le WHR 2018, chapitre 6 ; inégalités ; crises) restent des hypothèses.
- Le score médian progresse de 5,31 (2016) à 5,94 (2026).

## Modélisation et sélection des variables (rapport 2026)

Démarche complète dans la section 7 du notebook. Règles de décision fixées avant de voir les résultats.

**1. Modèle complet (7 variables, 134 pays complets).** R² 0,764, R² ajusté 0,751, AIC 223,7, BIC 246,9, test F p ≈ 10⁻³⁶. L'espérance de vie (p = 0,92) et l'urbanisation (p = 0,95) ne sont pas significatives. Multicolinéarité notable mais pas critique : VIF max 7,2 (PIB), 6,1 (internet), 5,3 (espérance de vie).

**2. Hypothèses vérifiées.** Résidus normaux (Shapiro-Wilk p = 0,94 ; Jarque-Bera p = 0,98), variance constante (Breusch-Pagan p = 0,12), aucun pays dominant (distance de Cook max 0,22 < 1, Botswana).

**3. Sélection des variables.**

| Méthode | Résultat |
|---|---|
| 127 combinaisons, sur l'échantillon (R² ajusté, AIC, BIC, Cp) | les 4 critères retiennent le même modèle à 5 variables |
| 127 combinaisons, validation croisée | RMSE quasi identique de 3 à 7 variables (0,645 à 0,660, ± 0,04) |
| Lasso, 500 bootstraps | chômage 100 %, PIB 99 %, éducation 98 %, internet 98 % ; espérance de vie la moins stable (65 %) |
| ACP (1 à 7 composantes) | pas mieux que la sélection (meilleure RMSE 0,651), et coefficients illisibles |
| Validation croisée imbriquée de 5 procédures | règle de l'écart-type écartée (R² 0,57) ; RMSE min, BIC, Lasso et aucune sélection à égalité → la plus simple : **BIC** |

**Modèle retenu : PIB (log), internet, chômage, dépenses de santé, dépenses d'éducation.** Il écarte l'espérance de vie et l'urbanisation. R² ajusté 0,755 (contre 0,751), BIC 237,1 (contre 246,9).

**4. Performance hors échantillon** (5 plis × 10, mêmes plis pour tous les modèles)

| Modèle | MAE | RMSE | R² test | R² entraînement |
|---|---|---|---|---|
| Référence (moyenne) | 0,96 | 1,14 | −0,03 | 0,00 |
| Régression — PIB seul | 0,54 | 0,72 | 0,58 | 0,61 |
| Régression — 7 variables | 0,50 | 0,66 | 0,64 | 0,72 |
| **Régression — 5 variables retenues** | **0,48** | **0,65** | **0,65** | 0,71 |
| Lasso | 0,49 | 0,66 | 0,64 | 0,72 |
| Régression sur 2 composantes (ACP) | 0,51 | 0,68 | 0,62 | 0,66 |
| Random Forest | 0,50 | 0,67 | 0,63 | 0,88 |
| XGBoost | 0,54 | 0,70 | 0,60 | 0,99 |

Estimation honnête, qui inclut l'étape de sélection (validation croisée imbriquée) : **R² ≈ 0,63, RMSE ≈ 0,67**. Les modèles d'arbres surapprennent sans mieux généraliser.

**5. Effets estimés** (à autres variables égales, IC à 95 %)
- PIB × 2 → +0,30 point (coefficient +1,01 [0,58 ; 1,44] par log10) ;
- +5 points de chômage → −0,30 point ;
- +10 points d'accès à internet → +0,12 point ;
- +1 point de PIB en dépenses d'éducation → +0,10 ; en dépenses de santé → +0,06.

Environ 35 % des écarts restent inexpliqués. *Hypothèse* : conflits, liens sociaux. La gouvernance a été testée et n'explique presque rien de plus (voir plus bas).

## Clustering (K-Means, k = 3, silhouette 0,38)

Les groupes sont formés sur les 7 indicateurs standardisés, sans utiliser le score de bonheur.

| Groupe | Pays | Profil | Bonheur (médiane) |
|---|---|---|---|
| Développés et émergents | 87 | PIB ≈ 35 000 $, 89 % sur internet | 6,4 |
| En développement | 44 | PIB ≈ 4 900 $, 45 % sur internet, chômage 3,9 % | 4,5 |
| Chômage élevé | 15 | PIB ≈ 7 400 $, chômage 20 % | 4,5 |

Le groupe « Chômage élevé » est 50 % plus riche que le groupe « En développement », mais pas plus heureux. Les groupes ont des frontières floues : ils servent à orienter des actions par profil de pays, pas à classer chaque pays avec certitude.

## Test : la gouvernance explique-t-elle le reste ?

Hypothèse testée : les indicateurs de gouvernance (corruption, stabilité politique, État de droit) augmenteraient le R² et amélioreraient la prédiction du Liban et de l'Afghanistan.

| R² test (mêmes 50 plis) | Modèle final (5 variables) | + gouvernance | PIB + gouvernance |
|---|---|---|---|
| Régression linéaire | **0,651** | 0,642 | 0,581 |
| Random Forest | 0,616 | 0,617 | 0,578 |

- **Hypothèse rejetée.** Le R² ne monte ni pour la régression (la gouvernance n'aide que dans 24 plis sur 50), ni pour le Random Forest.
- **Pourquoi** : la gouvernance est très corrélée au PIB (jusqu'à 0,80) et ses indicateurs sont corrélés entre eux (corruption et État de droit : 0,96). Elle mesure surtout la même chose que le développement.
- **Résidus** : le Liban s'améliore un peu (−1,32 → −1,22), l'Afghanistan pas du tout (−2,71 → −2,71), et le Botswana, bien gouverné mais peu heureux, se dégrade (−1,67 → −2,09).
- Limites : les WGI sont archivés par l'API World Bank, leurs données s'arrêtent en 2023, et le fichier archivé n'est pas sur l'échelle officielle. Les modèles n'en sont pas affectés, puisqu'une seule année est utilisée, mais les valeurs brutes ne sont pas interprétables telles quelles.

## Test : le paradoxe d'Easterlin (2016 → 2026)

Le paradoxe d'Easterlin dit que les pays riches sont plus heureux que les pays pauvres, mais que le bonheur d'un pays augmente à peine quand il s'enrichit. Nos données ne le confirment pas.

Pente = points de bonheur gagnés quand le PIB par habitant est multiplié par 10 :

| Approche | Pente | IC 95 % (bootstrap) |
|---|---|---|
| Entre pays (rapport 2016 / 2026) | 1,9 / 1,8 | [1,7 ; 2,1] / [1,6 ; 2,0] |
| Dans le temps, variations 2016 → 2026 (139 pays) | **3,8** | [2,5 ; 5,2] |
| Dans le temps, panel à effets fixes pays et année (8 rapports) | **3,5** | [1,6 ; 5,2] |

- Dans le temps, le bonheur suit la croissance, et même plus fortement qu'entre pays. La corrélation entre les deux variations est de 0,50.
- Résultat robuste : sans un pays au choix, la pente reste entre 3,4 et 4,0. Avec la méthode Theil-Sen, peu sensible aux valeurs extrêmes, elle vaut 4,1. Avec les seuls pays dont le PIB a augmenté, elle vaut 5,0.
- *Hypothèses*, non testées ici :
  - 10 ans reste un horizon court ; Easterlin et al., *PNAS* 2010, situent le paradoxe sur le long terme ;
  - la croissance s'accompagne d'autres changements, comme la sortie de crise ;
  - les pays qui ont le plus progressé (Kosovo, Viet Nam, Chine) sont en rattrapage.
- L'Irlande (PIB +78 %, bonheur inchangé) rappelle que le PIB irlandais est gonflé par les multinationales.

## Limites

- Environ 140 pays seulement : peu de données pour du machine learning.
- Corrélation ≠ causalité : le modèle identifie des associations, pas des leviers d'action garantis.
- Les statistiques World Bank des années récentes sont incomplètes (dépenses d'éducation et de santé surtout).
- Taiwan est exclu, faute de données World Bank.
- Les dépenses d'éducation sont peu comparables d'un pays à l'autre ; par exemple, celles du Nigeria ne couvrent que le budget fédéral (≈ 0,3 % du PIB).
