"""
Étape 7 — Modélisation : prédire le score de bonheur, avec une sélection de
variables justifiée par des critères chiffrés.

Démarche (chaque étape enregistre ses résultats dans reports/) :

  7.1  Diagnostic du modèle complet (7 variables, moindres carrés ordinaires) :
       R², R² ajusté, AIC, BIC, test F, coefficients avec p-valeurs, VIF.
  7.2  Hypothèses de la régression : normalité des résidus (Shapiro-Wilk,
       Jarque-Bera), homoscédasticité (Breusch-Pagan), pays influents (Cook).
  7.3  Sélection exhaustive : les 127 combinaisons de variables, évaluées
       - sur l'échantillon : R² ajusté, AIC, BIC, Cp de Mallows ;
       - hors échantillon : RMSE, MAE, R² en validation croisée.
  7.4  Contrôle par le Lasso : fréquence de sélection de chaque variable sur
       500 échantillons bootstrap (« stabilité »).
  7.5  Contrôle par la régression sur composantes principales (ACP, 1 à 7 axes).
  7.6  Validation croisée imbriquée : 5 PROCÉDURES de sélection (règle de
       l'écart-type, RMSE minimale, BIC minimal, Lasso, aucune sélection) sont
       refaites à l'intérieur de chaque pli d'entraînement, puis évaluées sur le
       pli de test. Choisir les variables ET mesurer l'erreur sur les mêmes données
       est optimiste : seule cette méthode mesure honnêtement chaque procédure.
  7.7  Décision : règle de l'écart-type (Hastie, Tibshirani & Friedman) appliquée
       aux procédures — parmi celles dont la RMSE imbriquée est à moins d'une
       erreur standard de la meilleure, la plus simple. Elle est ensuite appliquée
       aux 146 pays pour obtenir les variables du modèle final.
  7.8  Comparaison finale des modèles (références, régressions, Lasso, ACP,
       Random Forest, XGBoost), sur les mêmes 50 plis.
  7.9  Modèle final : coefficients (erreurs standard robustes si besoin),
       importance par permutation, valeurs SHAP du meilleur modèle d'arbres.

Données manquantes :
  - critères « sur l'échantillon » (statsmodels) : 134 pays complets ;
  - validation croisée (scikit-learn) : 146 pays, imputation par la médiane
    apprise sur les plis d'entraînement uniquement (pas de fuite de données).

Lancement (depuis la racine du projet, venv activé) :
    python src/05_modelisation.py          (≈ 5 minutes)
"""

from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd
import shap
import statsmodels.api as sm
from scipy.stats import shapiro
from sklearn.compose import ColumnTransformer
from sklearn.decomposition import PCA
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LassoCV, LinearRegression
from sklearn.model_selection import KFold, RepeatedKFold, cross_val_predict, cross_validate
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from statsmodels.stats.diagnostic import het_breuschpagan
from statsmodels.stats.outliers_influence import variance_inflation_factor
from statsmodels.stats.stattools import jarque_bera
from xgboost import XGBRegressor

# ---------------------------------------------------------------------------
# Paramètres
# ---------------------------------------------------------------------------

RACINE = Path(__file__).resolve().parent.parent
FICHIER_DONNEES = RACINE / "data" / "processed" / "worldpulse_2026.csv"
DOSSIER_REPORTS = RACINE / "reports"

GRAINE = 42
CIBLE = "score_bonheur"
VARIABLES = [
    "log_pib",                     # log10 du PIB par habitant (voir étape 6)
    "esperance_vie",
    "internet_pct",
    "urbanisation_pct",
    "depenses_sante_pct_pib",
    "depenses_education_pct_pib",
    "chomage_pct",
]

# Validation croisée commune à TOUTES les comparaisons : 5 plis × 10 répétitions
CV = RepeatedKFold(n_splits=5, n_repeats=10, random_state=GRAINE)
N_PLIS = 5
METRIQUES = {"MAE": "neg_mean_absolute_error", "RMSE": "neg_root_mean_squared_error", "R2": "r2"}

SEUIL_P = 0.05          # seuil des tests statistiques
N_BOOTSTRAP_LASSO = 500


# ---------------------------------------------------------------------------
# Outils
# ---------------------------------------------------------------------------

def imputer():
    return SimpleImputer(strategy="median")


def regression(variables):
    """Régression linéaire sur un sous-ensemble de colonnes (imputation puis standardisation)."""
    return make_pipeline(ColumnTransformer([("x", "passthrough", list(variables))]),
                         imputer(), StandardScaler(), LinearRegression())


def valider(modele, X, y, cv=CV, entrainement=False):
    """Validation croisée : renvoie les métriques de chaque pli (erreurs en positif)."""
    res = cross_validate(modele, X, y, cv=cv, scoring=METRIQUES, return_train_score=entrainement)
    sortie = pd.DataFrame({m: (-1 if m != "R2" else 1) * res[f"test_{m}"] for m in METRIQUES})
    if entrainement:
        for m in METRIQUES:
            sortie[f"{m}_entrainement"] = (-1 if m != "R2" else 1) * res[f"train_{m}"]
    return sortie


def regle_ecart_type(table, colonne_rmse="rmse_cv", colonne_es="rmse_cv_es"):
    """
    Règle de l'écart-type : parmi les modèles dont la RMSE est inférieure à
    (meilleure RMSE + son erreur standard), on garde celui qui a le MOINS de
    variables ; à égalité, la plus petite RMSE.
    """
    meilleur = table.loc[table[colonne_rmse].idxmin()]
    seuil = meilleur[colonne_rmse] + meilleur[colonne_es]
    candidats = table[table[colonne_rmse] <= seuil]
    return candidats.sort_values(["nb_variables", colonne_rmse]).iloc[0], seuil


def ols(df, variables, standardiser=False):
    """Régression des moindres carrés avec statsmodels (p-valeurs, AIC, BIC…)."""
    X = df[list(variables)]
    if standardiser:
        X = (X - X.mean()) / X.std()
    return sm.OLS(df[CIBLE], sm.add_constant(X)).fit()


# ---------------------------------------------------------------------------
# 7.1 et 7.2 — Diagnostic du modèle complet
# ---------------------------------------------------------------------------

def diagnostic_complet(complets):
    modele = ols(complets, VARIABLES)
    standard = ols(complets, VARIABLES, standardiser=True)
    ic = modele.conf_int()
    coefficients = pd.DataFrame({
        "coefficient": modele.params, "erreur_standard": modele.bse,
        "t": modele.tvalues, "p_valeur": modele.pvalues,
        "ic_bas": ic[0], "ic_haut": ic[1],
        "coefficient_standardise": standard.params,
    }).drop(index="const").rename_axis("variable").reset_index()

    exog = sm.add_constant(complets[VARIABLES])
    vif = pd.DataFrame({"variable": VARIABLES,
                        "vif": [variance_inflation_factor(exog.values, i + 1) for i in range(len(VARIABLES))]})

    # Tests sur les résidus
    _, p_shapiro = shapiro(modele.resid)
    _, p_jb, asymetrie, kurtosis = jarque_bera(modele.resid)
    _, p_bp, _, _ = het_breuschpagan(modele.resid, exog)
    metriques = pd.Series({
        "n": int(modele.nobs), "nb_variables": len(VARIABLES),
        "r2": modele.rsquared, "r2_ajuste": modele.rsquared_adj,
        "aic": modele.aic, "bic": modele.bic, "f": modele.fvalue, "p_f": modele.f_pvalue,
        "rmse_entrainement": np.sqrt(modele.mse_resid),
        "p_shapiro": p_shapiro, "p_jarque_bera": p_jb, "asymetrie": asymetrie, "kurtosis": kurtosis,
        "p_breusch_pagan": p_bp,
    })

    # Influence de chaque pays (distance de Cook ; seuil usuel 4/n)
    influence = modele.get_influence()
    pays = complets[["iso3", "pays"]].reset_index(drop=True).assign(
        prediction=modele.fittedvalues.values, residu=modele.resid.values,
        residu_studentise=influence.resid_studentized_external,
        levier=influence.hat_matrix_diag, distance_cook=influence.cooks_distance[0])
    return coefficients, vif, metriques, pays


# ---------------------------------------------------------------------------
# 7.3 — Les 127 combinaisons
# ---------------------------------------------------------------------------

def tous_les_sous_ensembles(df, complets):
    n = len(complets)
    sigma2_complet = ols(complets, VARIABLES).mse_resid  # pour le Cp de Mallows
    lignes = []
    for k in range(1, len(VARIABLES) + 1):
        for variables in combinations(VARIABLES, k):
            m = ols(complets, variables)
            cv = valider(regression(variables), df[VARIABLES], df[CIBLE])
            lignes.append({
                "variables": " + ".join(variables), "nb_variables": k,
                "r2": m.rsquared, "r2_ajuste": m.rsquared_adj, "aic": m.aic, "bic": m.bic,
                "cp_mallows": m.ssr / sigma2_complet - n + 2 * (k + 1),
                "rmse_cv": cv.RMSE.mean(), "rmse_cv_es": cv.RMSE.std() / np.sqrt(N_PLIS),
                "mae_cv": cv.MAE.mean(), "r2_cv": cv.R2.mean(),
            })
    return pd.DataFrame(lignes)


# ---------------------------------------------------------------------------
# 7.4 — Lasso : stabilité de la sélection
# ---------------------------------------------------------------------------

def lasso():
    return make_pipeline(imputer(), StandardScaler(),
                         LassoCV(cv=KFold(5, shuffle=True, random_state=GRAINE), random_state=GRAINE))


def stabilite_lasso(df):
    alea = np.random.default_rng(GRAINE)
    selections = []
    for _ in range(N_BOOTSTRAP_LASSO):
        indices = alea.integers(0, len(df), len(df))
        modele = lasso().fit(df[VARIABLES].iloc[indices], df[CIBLE].iloc[indices])
        selections.append(np.abs(modele[-1].coef_) > 1e-8)
    complet = lasso().fit(df[VARIABLES], df[CIBLE])
    return pd.DataFrame({"variable": VARIABLES,
                         "frequence_selection": np.mean(selections, axis=0),
                         "coefficient_lasso": complet[-1].coef_,
                         "alpha": complet[-1].alpha_})


# ---------------------------------------------------------------------------
# 7.5 — Régression sur composantes principales
# ---------------------------------------------------------------------------

def pcr(k):
    return make_pipeline(imputer(), StandardScaler(), PCA(n_components=k), LinearRegression())


def regression_composantes(df):
    lignes = []
    for k in range(1, len(VARIABLES) + 1):
        cv = valider(pcr(k), df[VARIABLES], df[CIBLE])
        lignes.append({"nb_composantes": k, "rmse_cv": cv.RMSE.mean(),
                       "rmse_cv_es": cv.RMSE.std() / np.sqrt(N_PLIS), "r2_cv": cv.R2.mean()})
    variance = PCA().fit(StandardScaler().fit_transform(imputer().fit_transform(df[VARIABLES])))
    resultat = pd.DataFrame(lignes)
    resultat["variance_expliquee_cumulee"] = np.cumsum(variance.explained_variance_ratio_)
    return resultat


# ---------------------------------------------------------------------------
# 7.7 — Validation croisée imbriquée
# ---------------------------------------------------------------------------

PROCEDURES = ["Règle de l'écart-type", "RMSE minimale", "BIC minimal", "Lasso", "Aucune sélection (7 variables)"]


def selections(X, y):
    """
    Applique chaque procédure de sélection à un jeu de données (un pli
    d'entraînement, ou tous les pays pour le modèle final).
    Renvoie {procédure: liste des variables retenues}.
    """
    # Validation croisée interne sur les 127 combinaisons
    cv_interne = RepeatedKFold(n_splits=5, n_repeats=2, random_state=GRAINE)
    complets = X.notna().all(axis=1)  # BIC calculé sur les pays complets, comme à l'étape 7.3
    lignes = []
    for k in range(1, len(VARIABLES) + 1):
        for variables in combinations(VARIABLES, k):
            rmse = -cross_validate(regression(variables), X, y, cv=cv_interne,
                                   scoring="neg_root_mean_squared_error")["test_score"]
            bic = sm.OLS(y[complets], sm.add_constant(X.loc[complets, list(variables)])).fit().bic
            lignes.append({"variables": variables, "nb_variables": k, "bic": bic,
                           "rmse_cv": rmse.mean(), "rmse_cv_es": rmse.std() / np.sqrt(N_PLIS)})
    table = pd.DataFrame(lignes)
    modele_lasso = lasso().fit(X, y)
    return {
        "Règle de l'écart-type": list(regle_ecart_type(table)[0]["variables"]),
        "RMSE minimale": list(table.loc[table.rmse_cv.idxmin(), "variables"]),
        "BIC minimal": list(table.loc[table.bic.idxmin(), "variables"]),
        "Lasso": [v for v, c in zip(VARIABLES, modele_lasso[-1].coef_) if abs(c) > 1e-8],
        "Aucune sélection (7 variables)": VARIABLES,
    }


def validation_imbriquee(df):
    """
    Pour chacun des 50 plis externes : on applique chaque procédure de sélection
    au pli d'entraînement SEULEMENT, puis on évalue le modèle obtenu sur le pli de
    test. On mesure ainsi la performance de la PROCÉDURE complète (choisir puis
    entraîner), sans biais d'optimisme.
    """
    X, y = df[VARIABLES], df[CIBLE]
    lignes = []
    for pli, (i_train, i_test) in enumerate(CV.split(X)):
        X_train, y_train, X_test, y_test = X.iloc[i_train], y.iloc[i_train], X.iloc[i_test], y.iloc[i_test]
        for procedure, variables in selections(X_train, y_train).items():
            modele = lasso() if procedure == "Lasso" else regression(variables)
            erreur = y_test - modele.fit(X_train, y_train).predict(X_test)
            lignes.append({"pli": pli, "procedure": procedure, "variables": " + ".join(variables),
                           "nb_variables": len(variables), "MAE": erreur.abs().mean(),
                           "RMSE": np.sqrt((erreur ** 2).mean()),
                           "R2": 1 - (erreur ** 2).sum() / ((y_test - y_test.mean()) ** 2).sum()})
        if pli % 10 == 9:
            print(f"   {pli + 1}/50 plis")
    return pd.DataFrame(lignes)


def choisir_procedure(imbriquee):
    """
    Même logique que la règle de l'écart-type, appliquée aux procédures :
    parmi celles dont la RMSE imbriquée est à moins d'une erreur standard de la
    meilleure, on garde la plus simple (le moins de variables en moyenne).
    """
    resume = imbriquee.groupby("procedure").agg(
        rmse_cv=("RMSE", "mean"), rmse_cv_es=("RMSE", lambda r: r.std() / np.sqrt(N_PLIS)),
        mae=("MAE", "mean"), r2=("R2", "mean"), nb_variables=("nb_variables", "mean")).loc[PROCEDURES]
    choix, seuil = regle_ecart_type(resume.reset_index())
    return choix["procedure"], resume, seuil


# ---------------------------------------------------------------------------
# 7.8 et 7.9 — Comparaison finale et interprétation
# ---------------------------------------------------------------------------

def modeles_finaux(variables_retenues, k_pcr):
    return {
        "Référence (moyenne)": make_pipeline(imputer(), DummyRegressor(strategy="mean")),
        "Régression — PIB seul": regression(["log_pib"]),
        "Régression — 7 variables": regression(VARIABLES),
        "Régression — variables retenues": regression(variables_retenues),
        "Lasso": lasso(),
        f"Régression sur {k_pcr} composantes (ACP)": pcr(k_pcr),
        "Random Forest": make_pipeline(
            imputer(), RandomForestRegressor(n_estimators=500, min_samples_leaf=3, random_state=GRAINE)),
        "XGBoost": make_pipeline(
            imputer(), XGBRegressor(n_estimators=300, max_depth=3, learning_rate=0.05, subsample=0.8,
                                    colsample_bytree=0.8, random_state=GRAINE, n_jobs=-1)),
    }


def comparer(modeles, df):
    morceaux = []
    for nom, modele in modeles.items():
        res = valider(modele, df[VARIABLES], df[CIBLE], entrainement=True)
        res.insert(0, "modele", nom)
        res.insert(1, "pli", range(len(res)))
        morceaux.append(res)
        print(f"   {nom:34} RMSE {res.RMSE.mean():.3f}   MAE {res.MAE.mean():.3f}   "
              f"R² {res.R2.mean():.3f}   (R² entraînement {res.R2_entrainement.mean():.2f})")
    return pd.concat(morceaux, ignore_index=True)


def modele_final_ols(complets, variables, robuste):
    """Coefficients du modèle final ; erreurs standard robustes HC3 si l'homoscédasticité est rejetée."""
    covariance = "HC3" if robuste else "nonrobust"
    m = sm.OLS(complets[CIBLE], sm.add_constant(complets[list(variables)])).fit(cov_type=covariance)
    z = complets[list(variables)]
    s = sm.OLS(complets[CIBLE], sm.add_constant((z - z.mean()) / z.std())).fit(cov_type=covariance)
    ic = m.conf_int()
    coefs = pd.DataFrame({"coefficient": m.params, "erreur_standard": m.bse, "p_valeur": m.pvalues,
                          "ic_bas": ic[0], "ic_haut": ic[1], "coefficient_standardise": s.params,
                          "ic_bas_standardise": s.conf_int()[0], "ic_haut_standardise": s.conf_int()[1]})
    coefs = coefs.drop(index="const").rename_axis("variable").reset_index()
    coefs["erreurs_standard"] = covariance
    metriques = pd.Series({"n": int(m.nobs), "nb_variables": len(variables), "r2": m.rsquared,
                           "r2_ajuste": m.rsquared_adj, "aic": m.aic, "bic": m.bic,
                           "f": m.fvalue, "p_f": m.f_pvalue})
    return coefs, metriques


def importance_permutation(modeles, df, noms):
    X, y = df[VARIABLES], df[CIBLE]
    lignes = []
    for pli, (i_train, i_test) in enumerate(KFold(5, shuffle=True, random_state=GRAINE).split(X)):
        for nom in noms:
            modele = modeles[nom].fit(X.iloc[i_train], y.iloc[i_train])
            perm = permutation_importance(modele, X.iloc[i_test], y.iloc[i_test], n_repeats=30,
                                          scoring="neg_root_mean_squared_error", random_state=GRAINE)
            for var, valeur in zip(VARIABLES, perm.importances_mean):
                lignes.append({"modele": nom, "pli": pli, "variable": var, "importance": valeur})
    return pd.DataFrame(lignes)


def valeurs_shap(modele, df):
    modele.fit(df[VARIABLES], df[CIBLE])
    X_impute = pd.DataFrame(modele[0].transform(df[VARIABLES]), columns=VARIABLES)
    explicateur = shap.TreeExplainer(modele[-1])
    valeurs = pd.DataFrame(explicateur.shap_values(X_impute), columns=[f"shap_{v}" for v in VARIABLES])
    resultat = pd.concat([df[["iso3", "pays", CIBLE]].reset_index(drop=True), X_impute, valeurs], axis=1)
    resultat["valeur_de_base"] = float(np.ravel(explicateur.expected_value)[0])
    return resultat


# ---------------------------------------------------------------------------
# Programme principal
# ---------------------------------------------------------------------------

def main():
    DOSSIER_REPORTS.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(FICHIER_DONNEES)
    df["log_pib"] = np.log10(df["pib_par_habitant_ppa"])
    complets = df.dropna(subset=VARIABLES).reset_index(drop=True)
    print(f"📦 {len(df)} pays ({len(complets)} sans valeur manquante), {len(VARIABLES)} variables candidates\n")

    print("7.1-7.2  Diagnostic du modèle complet")
    coefs, vif, metriques, pays = diagnostic_complet(complets)
    coefs.to_csv(DOSSIER_REPORTS / "modele_complet_coefficients.csv", index=False)
    vif.to_csv(DOSSIER_REPORTS / "modele_vif.csv", index=False)
    metriques.to_frame("valeur").to_csv(DOSSIER_REPORTS / "modele_complet_metriques.csv")
    pays.to_csv(DOSSIER_REPORTS / "modele_complet_diagnostics_pays.csv", index=False)
    print(metriques.round(3).to_string())
    print(coefs[["variable", "coefficient", "p_valeur", "coefficient_standardise"]].round(3).to_string(index=False))
    print(vif.round(2).to_string(index=False))
    print("   pays influents (Cook > 4/n) :",
          pays.loc[pays.distance_cook > 4 / len(pays), "pays"].tolist())

    print("\n7.3  Les 127 combinaisons de variables…")
    sous_ensembles = tous_les_sous_ensembles(df, complets)
    sous_ensembles.to_csv(DOSSIER_REPORTS / "modele_sous_ensembles.csv", index=False)
    for critere, sens in [("r2_ajuste", False), ("aic", True), ("bic", True), ("cp_mallows", True), ("rmse_cv", True)]:
        meilleur = sous_ensembles.sort_values(critere, ascending=sens).iloc[0]
        print(f"   meilleur selon {critere:10} : {meilleur['variables']}  ({meilleur[critere]:.3f})")

    print("\n7.4  Stabilité du Lasso (500 bootstraps)…")
    stabilite = stabilite_lasso(df)
    stabilite.to_csv(DOSSIER_REPORTS / "modele_lasso_stabilite.csv", index=False)
    print(stabilite.round(3).to_string(index=False))

    print("\n7.5  Régression sur composantes principales…")
    composantes = regression_composantes(df)
    composantes.to_csv(DOSSIER_REPORTS / "modele_pcr.csv", index=False)
    print(composantes.round(3).to_string(index=False))
    composantes["nb_variables"] = composantes["nb_composantes"]
    k_pcr = int(regle_ecart_type(composantes)[0]["nb_composantes"])

    choix_1es, seuil = regle_ecart_type(sous_ensembles)
    print(f"   règle de l'écart-type sur tous les pays (seuil RMSE {seuil:.3f}) : {choix_1es['variables']}")
    print(f"   ACP : {k_pcr} composante(s) retenue(s) par la même règle")

    print("\n7.6  Validation croisée imbriquée : chaque procédure de sélection refaite dans chaque pli…")
    imbriquee = validation_imbriquee(df)
    imbriquee.to_csv(DOSSIER_REPORTS / "modele_cv_imbriquee.csv", index=False)
    procedure, resume, seuil = choisir_procedure(imbriquee)
    print(resume.round(3).to_string())
    for p in PROCEDURES[:3]:
        print(f"   {p} — combinaisons les plus choisies :",
              imbriquee.query("procedure == @p")["variables"].value_counts().head(3).to_dict())

    print("\n7.7  Décision")
    variables_retenues = selections(df[VARIABLES], df[CIBLE])[procedure]
    print(f"   seuil RMSE {seuil:.3f} → procédure retenue : {procedure}")
    print(f"   appliquée aux 146 pays, elle retient : {' + '.join(variables_retenues)}")
    pd.DataFrame({"procedure": [procedure], "variables": [" + ".join(variables_retenues)]}).to_csv(
        DOSSIER_REPORTS / "modele_decision.csv", index=False)

    print("\n7.8  Comparaison finale (5 plis × 10 répétitions, mêmes plis pour tous)")
    modeles = modeles_finaux(variables_retenues, k_pcr)
    scores = comparer(modeles, df)
    scores.to_csv(DOSSIER_REPORTS / "modele_scores_cv.csv", index=False)

    print("\n7.9  Modèle final et interprétation")
    robuste = metriques["p_breusch_pagan"] < SEUIL_P
    coefs_final, metriques_final = modele_final_ols(complets, variables_retenues, robuste)
    coefs_final.to_csv(DOSSIER_REPORTS / "modele_final_coefficients.csv", index=False)
    metriques_final.to_frame("valeur").to_csv(DOSSIER_REPORTS / "modele_final_metriques.csv")
    print(metriques_final.round(3).to_string())
    print(coefs_final[["variable", "coefficient", "p_valeur", "coefficient_standardise"]].round(3).to_string(index=False))

    # Prédictions hors échantillon (une découpe 5 plis)
    cv5 = KFold(5, shuffle=True, random_state=GRAINE)
    predictions = df[["iso3", "pays", "region", CIBLE]].copy()
    predictions["prediction_regression_finale"] = cross_val_predict(
        modeles["Régression — variables retenues"], df[VARIABLES], df[CIBLE], cv=cv5)
    predictions["prediction_random_forest"] = cross_val_predict(
        modeles["Random Forest"], df[VARIABLES], df[CIBLE], cv=cv5)
    predictions.to_csv(DOSSIER_REPORTS / "modele_predictions.csv", index=False)

    importance = importance_permutation(modeles, df, ["Régression — variables retenues", "Random Forest"])
    importance.to_csv(DOSSIER_REPORTS / "modele_importance.csv", index=False)

    shap_df = valeurs_shap(modeles["Random Forest"], df)
    shap_df["modele"] = "Random Forest"
    shap_df.to_csv(DOSSIER_REPORTS / "modele_shap.csv", index=False)

    print(f"\n✅ Résultats enregistrés dans {DOSSIER_REPORTS}")


if __name__ == "__main__":
    main()
