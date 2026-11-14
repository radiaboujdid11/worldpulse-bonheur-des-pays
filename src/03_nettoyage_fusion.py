"""
Étape 4 — Nettoyage et fusion des deux sources.

Ce script :
  1. convertit les noms de pays Wikipedia en codes ISO3 (country_converter
     + corrections manuelles) ;
  2. résume les indicateurs World Bank en UNE valeur par pays et par rapport :
       - moyenne sur les années d'enquête du rapport (ex. 2023-2025 pour 2026) ;
       - sinon (donnée absente), dernière valeur des 3 années précédentes ;
  3. fusionne bonheur + indicateurs + infos pays sur la clé iso3 ;
  4. enregistre :
       - data/processed/worldpulse_panel.csv : tous les rapports (analyse de l'évolution) ;
       - data/processed/worldpulse_2026.csv  : rapport 2026 seul (modèle principal).

Les valeurs manquantes restantes sont CONSERVÉES (NaN) : elles seront imputées
à l'étape 7, à l'intérieur de la validation croisée, pour éviter toute fuite
d'information entre données d'entraînement et de test.

Lancement (depuis la racine du projet, venv activé) :
    python src/03_nettoyage_fusion.py
"""

import logging
from pathlib import Path

import country_converter as coco
import numpy as np
import pandas as pd

# country_converter affiche un avertissement pour chaque nom inconnu :
# on les masque, car on fait notre propre liste plus lisible
logging.getLogger("country_converter").setLevel(logging.ERROR)

# ---------------------------------------------------------------------------
# Paramètres
# ---------------------------------------------------------------------------

RACINE = Path(__file__).resolve().parent.parent
DOSSIER_RAW = RACINE / "data" / "raw"
DOSSIER_PROCESSED = RACINE / "data" / "processed"

# Rapport utilisé pour le modèle principal
RAPPORT_PRINCIPAL = 2026

# Rapports exclus : 2013 ne contient que les 85 premiers pays (classement tronqué)
RAPPORTS_EXCLUS = [2013]

# Nombre d'années avant la période d'enquête où l'on accepte d'aller
# chercher une valeur de repli (ex. 2020-2022 pour le rapport 2026)
ANNEES_REPLI = 3

# Corrections manuelles : nom Wikipedia -> code ISO3 (None = ligne exclue)
CORRECTIONS_MANUELLES = {
    "Northern Cyprus": None,    # territoire sans code ISO ; sinon confondu avec Chypre (CYP)
    "Somaliland region": None,  # territoire sans code ISO ; sinon confondu avec la Somalie (SOM)
    "World": None,              # moyenne mondiale (rapport 2017), pas un pays
    "Europe": None,             # moyenne européenne (rapport 2017), pas un pays
}


# ---------------------------------------------------------------------------
# 1. Scores de bonheur : noms de pays -> ISO3
# ---------------------------------------------------------------------------

def preparer_bonheur():
    """Charge les scores Wikipedia, ajoute le code ISO3 et retire les lignes inutilisables."""
    df = pd.read_csv(DOSSIER_RAW / "wikipedia_bonheur.csv")
    df = df[~df["rapport"].isin(RAPPORTS_EXCLUS)].copy()

    # Conversion automatique des noms uniques (plus rapide que ligne par ligne)
    noms = sorted(df["pays"].unique())
    codes = coco.convert(noms, to="ISO3", not_found=None)
    correspondance = dict(zip(noms, codes))

    # Les corrections manuelles remplacent la conversion automatique
    correspondance.update(CORRECTIONS_MANUELLES)

    df["iso3"] = df["pays"].map(correspondance)

    # Liste des noms écartés (non reconnus ou exclus volontairement)
    exclus = sorted(df.loc[df["iso3"].isna(), "pays"].unique())
    print(f"   noms exclus : {exclus}")
    df = df.dropna(subset=["iso3"])

    # Vérification : un pays ne doit apparaître qu'une fois par rapport
    doublons = df[df.duplicated(["rapport", "iso3"], keep=False)]
    if not doublons.empty:
        raise ValueError(f"Doublons après conversion ISO3 :\n{doublons}")

    return df[["rapport", "iso3", "score_bonheur"]]


# ---------------------------------------------------------------------------
# 2. Indicateurs World Bank : une valeur par pays pour une période donnée
# ---------------------------------------------------------------------------

def resumer_indicateurs(df_wb, debut, fin):
    """
    Renvoie un tableau large (une ligne par pays, une colonne par indicateur)
    et un tableau de même forme indiquant l'origine de chaque valeur.
    """
    # a) Moyenne sur la période d'enquête [debut, fin]
    periode = df_wb[df_wb["annee"].between(debut, fin)]
    moyenne = periode.groupby(["iso3", "indicateur"])["valeur"].mean()

    # b) Repli : dernière valeur disponible dans les années juste avant
    avant = df_wb[df_wb["annee"].between(debut - ANNEES_REPLI, debut - 1)]
    repli = avant.sort_values("annee").groupby(["iso3", "indicateur"])["valeur"].last()

    # c) On prend la moyenne si elle existe, sinon le repli
    #    (unstack : format long -> format large, une colonne par indicateur)
    moyenne = moyenne.unstack("indicateur")
    repli = repli.unstack("indicateur")
    resultat = moyenne.combine_first(repli)

    # Origine de chaque valeur (pour la transparence) : « periode », « repli » ou « manquant »
    moyenne = moyenne.reindex_like(resultat)
    origine = pd.DataFrame(
        np.where(moyenne.notna(), "periode", np.where(resultat.notna(), "repli", "manquant")),
        index=resultat.index,
        columns=resultat.columns,
    )

    return resultat.reset_index(), origine


# ---------------------------------------------------------------------------
# Programme principal
# ---------------------------------------------------------------------------

def main():
    DOSSIER_PROCESSED.mkdir(parents=True, exist_ok=True)

    print("🏷️  Conversion des pays en ISO3…")
    df_bonheur = preparer_bonheur()

    df_wb = pd.read_csv(DOSSIER_RAW / "worldbank_indicateurs.csv")
    df_pays = pd.read_csv(DOSSIER_RAW / "worldbank_pays.csv")

    # Valeur aberrante : dépenses d'éducation de la Somalie publiées à ~0,000008 % du PIB
    # (2018-2023), statistique inutilisable -> considérée comme manquante
    aberrant = (df_wb["iso3"] == "SOM") & (df_wb["indicateur"] == "depenses_education_pct_pib")
    df_wb = df_wb[~aberrant]

    # Fusion rapport par rapport : chaque rapport a sa propre période d'enquête
    morceaux = []
    for rapport in sorted(df_bonheur["rapport"].unique()):
        debut, fin = rapport - 3, rapport - 1
        indicateurs, origine = resumer_indicateurs(df_wb, debut, fin)

        scores = df_bonheur[df_bonheur["rapport"] == rapport]
        # Jointure interne : on ne garde que les pays présents dans les deux sources
        fusion = scores.merge(indicateurs, on="iso3", how="inner")
        morceaux.append(fusion)

        perdus = sorted(set(scores["iso3"]) - set(fusion["iso3"]))
        print(f"\n🔗 Rapport {rapport} (enquêtes {debut}-{fin}) : "
              f"{len(scores)} pays -> {len(fusion)} après fusion ; sans données World Bank : {perdus}")
        if rapport == RAPPORT_PRINCIPAL:
            # Bilan, pour les pays retenus : combien de valeurs viennent de la période,
            # du repli, ou manquent, par indicateur
            qualite = origine.loc[fusion["iso3"]].apply(pd.Series.value_counts).T
            qualite = qualite.reindex(columns=["periode", "repli", "manquant"]).fillna(0).astype(int)
            qualite.index.name = "indicateur"
            qualite.to_csv(DOSSIER_PROCESSED / f"qualite_indicateurs_{RAPPORT_PRINCIPAL}.csv")
            print("   origine des valeurs :\n" + qualite.to_string())

    df_panel = pd.concat(morceaux, ignore_index=True)

    # Ajout du nom, de la région et du niveau de revenu (World Bank)
    df_panel = df_panel.merge(df_pays, on="iso3", how="left")

    # Ordre des colonnes : identifiants, cible, puis variables explicatives
    indicateurs = sorted(df_wb["indicateur"].unique())
    colonnes = ["rapport", "iso3", "pays", "region", "niveau_revenu", "score_bonheur"] + indicateurs
    df_panel = df_panel[colonnes].sort_values(["rapport", "score_bonheur"], ascending=[True, False])

    df_principal = df_panel[df_panel["rapport"] == RAPPORT_PRINCIPAL]

    # Bilan des valeurs manquantes du jeu principal
    print(f"\n❓ Valeurs manquantes (rapport {RAPPORT_PRINCIPAL}) :")
    print(df_principal[indicateurs].isna().sum().to_string())
    print(f"   pays complets : {df_principal[indicateurs].notna().all(axis=1).sum()} / {len(df_principal)}")

    df_panel.to_csv(DOSSIER_PROCESSED / "worldpulse_panel.csv", index=False)
    df_principal.to_csv(DOSSIER_PROCESSED / f"worldpulse_{RAPPORT_PRINCIPAL}.csv", index=False)
    print(f"\n✅ worldpulse_panel.csv : {df_panel.shape}")
    print(f"✅ worldpulse_{RAPPORT_PRINCIPAL}.csv  : {df_principal.shape}")


if __name__ == "__main__":
    main()
