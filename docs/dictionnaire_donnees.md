# Dictionnaire des données — WorldPulse

## `data/raw/worldbank_pays.csv` — 217 pays et territoires (agrégats régionaux exclus)

| Colonne | Description |
|---|---|
| `iso3` | Code pays ISO 3166-1 alpha-3 (clé de fusion) |
| `pays` | Nom du pays (anglais, World Bank) |
| `region` | Région World Bank (ex. *Sub-Saharan Africa*) |
| `niveau_revenu` | Catégorie de revenu World Bank (*Low* → *High income*) |

## `data/raw/worldbank_indicateurs.csv` — format long : une ligne par (pays, indicateur, année)

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

## `data/raw/wikipedia_bonheur.csv` — une ligne par (rapport, pays)

| Colonne | Description |
|---|---|
| `rapport` | Année de publication du World Happiness Report |
| `enquete_debut`, `enquete_fin` | Années d'enquête couvertes par le score (rapport − 3 à rapport − 1) |
| `rang` | Rang du pays dans le rapport |
| `pays` | Nom du pays, tel qu'écrit sur Wikipedia |
| `score_bonheur` | **Variable cible.** Moyenne nationale de l'échelle de Cantril, de 0 (pire vie possible) à 10 (meilleure vie possible), sur 3 ans d'enquêtes Gallup |

`data/raw/wikipedia_whr.html` : copie de la page Wikipedia au moment du scraping, conservée pour la traçabilité.

## `data/processed/worldpulse_2026.csv` (146 × 13) et `worldpulse_panel.csv` (1 200 × 13)

Une ligne par (rapport, pays). Le fichier `_2026` contient le rapport 2026 seul (modèle principal). Le fichier `_panel` contient tous les rapports exploitables (2016–2020, 2024–2026).

| Colonne | Description |
|---|---|
| `rapport` | Année du rapport |
| `iso3`, `pays`, `region`, `niveau_revenu` | Identifiants et infos pays (World Bank) |
| `score_bonheur` | Variable cible (voir plus haut) |
| 7 indicateurs | Mêmes noms et unités que dans `worldbank_indicateurs.csv`. Valeur = moyenne sur les années d'enquête du rapport ; à défaut, dernière valeur des 3 années précédentes. `NaN` si aucune des deux n'existe |

## `data/processed/qualite_indicateurs_2026.csv` — origine des valeurs, par indicateur (146 pays)

| Colonne | Description |
|---|---|
| `indicateur` | Nom court de l'indicateur |
| `periode` | Nombre de pays dont la valeur est une moyenne sur 2023–2025 |
| `repli` | Nombre de pays dont la valeur est la dernière disponible sur 2020–2022 |
| `manquant` | Nombre de pays sans valeur |

## Gouvernance : `data/raw/wgi_indicateurs.csv` et `data/processed/worldpulse_2026_gouvernance.csv`

Le premier fichier est au format long, comme `worldbank_indicateurs.csv`, pour les années 2020–2023. Le second reprend `worldpulse_2026.csv` et y ajoute 3 colonnes, avec les valeurs de 2023 uniquement (seule année disponible sur la période d'enquête 2023–2025). Plus la valeur est haute, meilleure est la gouvernance.

⚠️ Dans le fichier archivé, l'échelle n'est pas l'échelle officielle (−2,5 à +2,5) et elle change d'une année à l'autre ; le classement des pays reste cohérent. Les valeurs ne sont donc comparables **qu'au sein d'une même année**.

| Colonne | Code WB | Définition |
|---|---|---|
| `controle_corruption` | CC.EST | Contrôle de la corruption |
| `stabilite_politique` | PV.EST | Stabilité politique et absence de violence |
| `etat_de_droit` | RL.EST | État de droit (justice, police, respect des contrats) |

## `db/worldpulse.db` (SQLite)

| Table / vue | Contenu |
|---|---|
| `pays` | = `data/raw/worldbank_pays.csv` |
| `indicateurs_wb` | = `data/raw/worldbank_indicateurs.csv` |
| `bonheur_wikipedia` | = `data/raw/wikipedia_bonheur.csv` |
| `worldpulse` | = `data/processed/worldpulse_panel.csv` |
| `worldpulse_2026` (vue) | `worldpulse` filtrée sur `rapport = 2026` |

Des requêtes d'exemple (classement, moyennes par région et par revenu, évolution 2016 → 2026) se trouvent dans `src/04_base_sqlite.py`.

## `reports/` — résultats de la modélisation (rapport 2026)

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

[← Retour au README](../README.md)
