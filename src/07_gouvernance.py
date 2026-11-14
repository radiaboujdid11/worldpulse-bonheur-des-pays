"""
Étape 8b — Gouvernance : la qualité des institutions explique-t-elle une partie
du bonheur que le modèle final de l'étape 7 ne capte pas ?

Hypothèse testée :
  « Ajouter des indicateurs de gouvernance augmente le R² du modèle, et réduit
  l'erreur sur des pays mal prédits comme le Liban et l'Afghanistan. »

Données : Worldwide Governance Indicators (WGI) de la World Bank.
  ⚠️ En novembre 2026, ces indicateurs sont classés « archivés » par l'API
  (source « WDI Database Archives ») : seul le téléchargement groupé (ZIP)
  fonctionne, et les données s'arrêtent en 2023. 2023 est comprise dans la période
  d'enquête du rapport 2026 (2023-2025), et la gouvernance évolue lentement :
  on utilise donc la valeur 2023.
  ⚠️ Anomalie du fichier archivé : les valeurs ne sont PAS sur l'échelle officielle
  (−2,5 à +2,5), et leur échelle change d'une année à l'autre (en 2023, environ la
  moitié de 2020 pour tous les pays). Le classement des pays reste cohérent
  (corrélation de rang 2020-2023 : 0,98 ; Danemark et Finlande en tête, Soudan du
  Sud et Syrie en bas). On n'utilise donc qu'UNE seule année (2023), sans repli
  sur d'autres années : les valeurs sont comparables entre pays, et les modèles
  standardisent les variables (régression) ou ne dépendent que de leur ordre (arbres).

Comparaison : les MÊMES plis de validation croisée (5 plis × 10 répétitions) pour
le modèle sans et avec gouvernance, afin que la différence ne vienne que des variables.

Sorties :
  data/raw/wgi_indicateurs.csv                  WGI bruts (format long)
  data/processed/worldpulse_2026_gouvernance.csv   jeu 2026 + 3 colonnes WGI
  reports/gouvernance_scores_cv.csv             R², MAE, RMSE par modèle et par pli
  reports/gouvernance_predictions.csv           prédictions hors échantillon par pays
  reports/gouvernance_coefficients.csv          coefficients standardisés (modèle complet)

Lancement (depuis la racine du projet, venv activé) :
    python src/07_gouvernance.py
"""

import io
import time
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import requests
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import KFold, RepeatedKFold, cross_val_predict, cross_validate
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

# ---------------------------------------------------------------------------
# Paramètres
# ---------------------------------------------------------------------------

RACINE = Path(__file__).resolve().parent.parent
DOSSIER_RAW = RACINE / "data" / "raw"
DOSSIER_PROCESSED = RACINE / "data" / "processed"
DOSSIER_REPORTS = RACINE / "reports"

URL_API = "https://api.worldbank.org/v2"
ENTETES = {"User-Agent": "WorldPulse-EducationalProject/0.1 (student data science project)"}
PAUSE = 1.0
GRAINE = 42

# Indicateurs de gouvernance retenus (3 sur les 6 WGI, ceux suggérés par l'hypothèse)
WGI = {
    "CC.EST": "controle_corruption",   # contrôle de la corruption
    "PV.EST": "stabilite_politique",   # stabilité politique et absence de violence
    "RL.EST": "etat_de_droit",         # État de droit (justice, police, contrats)
}

ANNEE_WGI = 2023            # seule année disponible dans la période d'enquête 2023-2025
ANNEES_TELECHARGEES = range(2020, 2024)  # gardées dans le fichier brut pour la traçabilité

CIBLE = "score_bonheur"
# Variables du modèle final, choisies à l'étape 7 (fichier écrit par src/05_modelisation.py)
VARIABLES_BASE = pd.read_csv(DOSSIER_REPORTS / "modele_decision.csv")["variables"][0].split(" + ")
VARIABLES_GOUV = list(WGI.values())

PAYS_SUIVIS = ["LBN", "AFG"]  # pays cités dans l'hypothèse


# ---------------------------------------------------------------------------
# 1. Extraction
# ---------------------------------------------------------------------------

def telecharger_wgi(code):
    """Télécharge le ZIP d'un indicateur WGI et renvoie un tableau long (iso3, annee, valeur)."""
    for essai in range(1, 4):
        try:
            reponse = requests.get(f"{URL_API}/en/indicator/{code}", params={"downloadformat": "csv"},
                                   headers=ENTETES, timeout=60)
            reponse.raise_for_status()
            break
        except requests.RequestException as erreur:
            print(f"   ⚠️  essai {essai}/3 échoué : {erreur}")
            if essai == 3:
                raise
            time.sleep(5 * essai)

    archive = zipfile.ZipFile(io.BytesIO(reponse.content))
    nom_csv = [nom for nom in archive.namelist() if nom.startswith("API_")][0]
    with archive.open(nom_csv) as fichier:
        df_large = pd.read_csv(fichier, skiprows=4)

    annees = [str(a) for a in ANNEES_TELECHARGEES if str(a) in df_large.columns]
    df_long = df_large[["Country Code"] + annees].melt(id_vars="Country Code", var_name="annee",
                                                       value_name="valeur")
    df_long = df_long.rename(columns={"Country Code": "iso3"}).dropna(subset=["valeur"])
    df_long["annee"] = df_long["annee"].astype(int)
    df_long["indicateur"] = WGI[code]
    df_long["code_wb"] = code
    return df_long[["iso3", "indicateur", "code_wb", "annee", "valeur"]]


def extraire_wgi():
    pays = pd.read_csv(DOSSIER_RAW / "worldbank_pays.csv")
    morceaux = []
    for code, nom in WGI.items():
        print(f"📥 {nom} ({code})…")
        morceau = telecharger_wgi(code)
        derniere = morceau["annee"].max()
        print(f"   dernière année disponible : {derniere} "
              f"({morceau.query('annee == @derniere')['iso3'].nunique()} pays et agrégats)")
        morceaux.append(morceau)
        time.sleep(PAUSE)
    df = pd.concat(morceaux, ignore_index=True)
    df = df[df["iso3"].isin(pays["iso3"])].reset_index(drop=True)  # on retire les agrégats
    df.to_csv(DOSSIER_RAW / "wgi_indicateurs.csv", index=False)
    return df


# ---------------------------------------------------------------------------
# 2. Résumé par pays et fusion
# ---------------------------------------------------------------------------

def resumer_wgi(df_wgi):
    """
    Une colonne par indicateur, valeurs de 2023 uniquement.
    Pas de repli sur d'autres années : l'échelle du fichier archivé change d'une
    année à l'autre, mélanger les années rendrait les pays incomparables.
    """
    resultat = (df_wgi.query("annee == @ANNEE_WGI")
                .pivot(index="iso3", columns="indicateur", values="valeur"))[VARIABLES_GOUV]
    # Contrôle de l'anomalie d'échelle (l'échelle officielle va d'environ −2,5 à +2,5)
    print(f"   écart-type des valeurs {ANNEE_WGI} : "
          + ", ".join(f"{c} {resultat[c].std():.1f}" for c in VARIABLES_GOUV)
          + "  (≈ 1 attendu sur l'échelle officielle)")
    return resultat


def fusionner(wgi_par_pays):
    df = pd.read_csv(DOSSIER_PROCESSED / "worldpulse_2026.csv")
    df["log_pib"] = np.log10(df["pib_par_habitant_ppa"])
    df = df.merge(wgi_par_pays, left_on="iso3", right_index=True, how="left")
    sans_wgi = df[df[VARIABLES_GOUV].isna().any(axis=1)]["pays"].tolist()
    print(f"\n🔗 {len(df)} pays ; sans donnée de gouvernance : {sans_wgi or 'aucun'}")
    df.drop(columns="log_pib").to_csv(DOSSIER_PROCESSED / "worldpulse_2026_gouvernance.csv", index=False)
    return df


# ---------------------------------------------------------------------------
# 3. Comparaison des modèles
# ---------------------------------------------------------------------------

def creer_modeles():
    imputer = lambda: SimpleImputer(strategy="median")
    return {
        "Régression linéaire": lambda: make_pipeline(imputer(), StandardScaler(), LinearRegression()),
        "Random Forest": lambda: make_pipeline(
            imputer(), RandomForestRegressor(n_estimators=500, min_samples_leaf=3, random_state=GRAINE)),
    }


JEUX_DE_VARIABLES = {
    "Modèle final": VARIABLES_BASE,
    "Modèle final + gouvernance": VARIABLES_BASE + VARIABLES_GOUV,
    "PIB + gouvernance": ["log_pib"] + VARIABLES_GOUV,
}


def comparer(df):
    """Validation croisée répétée, mêmes plis pour toutes les combinaisons."""
    cv = RepeatedKFold(n_splits=5, n_repeats=10, random_state=GRAINE)
    metriques = {"MAE": "neg_mean_absolute_error", "RMSE": "neg_root_mean_squared_error", "R2": "r2"}
    lignes = []
    print("\n🔁 Validation croisée (5 plis × 10 répétitions), moyenne sur les plis de test :")
    for nom_modele, fabrique in creer_modeles().items():
        for nom_jeu, variables in JEUX_DE_VARIABLES.items():
            res = cross_validate(fabrique(), df[variables], df[CIBLE], cv=cv, scoring=metriques)
            for i in range(len(res["fit_time"])):
                for m in metriques:
                    signe = -1 if m in ("MAE", "RMSE") else 1
                    lignes.append({"modele": nom_modele, "variables": nom_jeu, "pli": i,
                                   "metrique": m, "test": signe * res[f"test_{m}"][i]})
            r2 = res["test_R2"].mean()
            mae = -res["test_MAE"].mean()
            print(f"   {nom_modele:20} | {nom_jeu:28} R² {r2:.3f}   MAE {mae:.3f}")
    return pd.DataFrame(lignes)


def predictions_hors_echantillon(df, n_repetitions=10):
    """
    Prédiction de chaque pays par un modèle qui ne l'a pas vu, moyennée sur
    10 découpages différents (une seule découpe donne un résultat trop dépendant du hasard).
    """
    sortie = df[["iso3", "pays", "region", CIBLE]].copy()
    fabrique = creer_modeles()["Régression linéaire"]
    for nom_jeu in ["Modèle final", "Modèle final + gouvernance"]:
        variables = JEUX_DE_VARIABLES[nom_jeu]
        preds = [cross_val_predict(fabrique(), df[variables], df[CIBLE],
                                   cv=KFold(n_splits=5, shuffle=True, random_state=GRAINE + r))
                 for r in range(n_repetitions)]
        sortie[f"prediction_{nom_jeu}"] = np.mean(preds, axis=0)
        sortie[f"residu_{nom_jeu}"] = sortie[CIBLE] - sortie[f"prediction_{nom_jeu}"]
    return sortie


def coefficients(df):
    """Coefficients standardisés de la régression complète (entraînée sur tous les pays)."""
    variables = JEUX_DE_VARIABLES["Modèle final + gouvernance"]
    modele = creer_modeles()["Régression linéaire"]().fit(df[variables], df[CIBLE])
    return pd.DataFrame({"variable": variables, "coefficient": modele[-1].coef_})


# ---------------------------------------------------------------------------
# Programme principal
# ---------------------------------------------------------------------------

def main():
    DOSSIER_REPORTS.mkdir(parents=True, exist_ok=True)
    df_wgi = extraire_wgi()
    print(f"   {len(df_wgi)} lignes (pays × indicateur × année)")

    df = fusionner(resumer_wgi(df_wgi))

    print("\n📈 Corrélations (Pearson) avec le score et avec le log du PIB :")
    corr = df[[CIBLE, "log_pib"] + VARIABLES_GOUV].corr().loc[VARIABLES_GOUV, [CIBLE, "log_pib"]]
    print(corr.round(2).to_string())

    scores = comparer(df)
    scores.to_csv(DOSSIER_REPORTS / "gouvernance_scores_cv.csv", index=False)

    # Comparaison pli par pli (régression linéaire) : dans combien de plis la gouvernance aide-t-elle ?
    r2 = (scores.query("modele == 'Régression linéaire' and metrique == 'R2'")
          .pivot(index="pli", columns="variables", values="test"))
    gain = r2["Modèle final + gouvernance"] - r2["Modèle final"]
    print(f"\n⚖️  Gain de R² (régression linéaire) : moyenne {gain.mean():+.3f}, "
          f"positif dans {(gain > 0).sum()} plis sur {len(gain)}")

    preds = predictions_hors_echantillon(df)
    preds.to_csv(DOSSIER_REPORTS / "gouvernance_predictions.csv", index=False)
    print("\n🎯 Résidus (score réel − prédit) des pays suivis :")
    print(preds[preds["iso3"].isin(PAYS_SUIVIS)][["pays", CIBLE, "residu_Modèle final",
                                                  "residu_Modèle final + gouvernance"]]
          .round(2).to_string(index=False))

    coefs = coefficients(df)
    coefs.to_csv(DOSSIER_REPORTS / "gouvernance_coefficients.csv", index=False)
    print("\n📐 Coefficients standardisés (régression avec gouvernance) :")
    print(coefs.round(3).to_string(index=False))

    print(f"\n✅ Résultats enregistrés dans {DOSSIER_REPORTS}")


if __name__ == "__main__":
    main()
