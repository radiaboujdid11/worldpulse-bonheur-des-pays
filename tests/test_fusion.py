"""Tests des fonctions de nettoyage et de fusion (src/03_nettoyage_fusion.py)."""

import pandas as pd


def test_moyenne_sur_la_periode_sinon_repli_sinon_manquant(fusion):
    # Petit jeu inventé, au format long de worldbank_indicateurs.csv
    df_wb = pd.DataFrame({
        "iso3":       ["AAA", "AAA", "AAA", "BBB", "BBB"],
        "indicateur": ["chomage_pct"] * 3 + ["chomage_pct", "internet_pct"],
        "annee":      [2023, 2024, 2019, 2021, 2024],
        "valeur":     [4.0, 6.0, 99.0, 8.0, 50.0],
    })
    resultat, origine = fusion.resumer_indicateurs(df_wb, debut=2023, fin=2025)
    resultat = resultat.set_index("iso3")

    # AAA : moyenne de 2023 et 2024 ; la valeur de 2019 (hors période et hors repli) est ignorée
    assert resultat.loc["AAA", "chomage_pct"] == 5.0
    assert origine.loc["AAA", "chomage_pct"] == "periode"
    # BBB : rien en 2023-2025 -> repli sur 2021 (dans les 3 années précédentes)
    assert resultat.loc["BBB", "chomage_pct"] == 8.0
    assert origine.loc["BBB", "chomage_pct"] == "repli"
    # AAA n'a aucune valeur d'internet -> manquant, sans valeur inventée
    assert pd.isna(resultat.loc["AAA", "internet_pct"])
    assert origine.loc["AAA", "internet_pct"] == "manquant"


def test_conversion_iso3_sans_doublon_ni_territoire_exclu(fusion):
    bonheur = fusion.preparer_bonheur()

    # Chaque pays a un code ISO3 valide (3 lettres majuscules)
    assert bonheur["iso3"].str.fullmatch(r"[A-Z]{3}").all()
    # Un pays n'apparaît qu'une fois par rapport (Chypre du Nord n'est pas confondue avec Chypre)
    assert not bonheur.duplicated(["rapport", "iso3"]).any()
    # Le rapport 2013 (85 premiers pays seulement) est exclu
    assert 2013 not in bonheur["rapport"].unique()


def test_corrections_manuelles_excluent_les_agregats(fusion):
    for nom in ["World", "Europe", "Northern Cyprus", "Somaliland region"]:
        assert fusion.CORRECTIONS_MANUELLES[nom] is None
