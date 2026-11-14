"""Tests de qualité des données fusionnées (data/processed/)."""

import pandas as pd
import pytest

from conftest import RACINE

POURCENTAGES = ["internet_pct", "urbanisation_pct", "chomage_pct",
                "depenses_sante_pct_pib", "depenses_education_pct_pib"]


def test_jeu_principal_146_pays_sans_doublon(df_2026):
    assert len(df_2026) == 146  # chiffre annoncé dans le README et le rapport
    assert df_2026["iso3"].is_unique
    assert (df_2026["rapport"] == 2026).all()


def test_panel_un_pays_par_rapport(df_panel):
    assert not df_panel.duplicated(["rapport", "iso3"]).any()
    assert sorted(df_panel["rapport"].unique()) == [2016, 2017, 2018, 2019, 2020, 2024, 2025, 2026]


@pytest.mark.parametrize("jeu", ["df_2026", "df_panel"])
def test_score_de_bonheur_entre_0_et_10(jeu, request):
    df = request.getfixturevalue(jeu)
    assert df["score_bonheur"].notna().all()
    assert df["score_bonheur"].between(0, 10).all()


def test_tous_les_pays_existent_dans_la_liste_world_bank(df_panel):
    pays_wb = pd.read_csv(RACINE / "data" / "raw" / "worldbank_pays.csv")
    # Jointure interne : aucun agrégat (World, Europe…) ni pays inconnu ne doit subsister
    assert set(df_panel["iso3"]) <= set(pays_wb["iso3"])
    assert df_panel["region"].notna().all()


def test_indicateurs_dans_des_bornes_plausibles(df_panel):
    for colonne in POURCENTAGES:
        assert df_panel[colonne].dropna().between(0, 100).all(), colonne
    # Borne basse à 30 ans : le minimum réel est le Soudan du Sud (37,3 ans, enquêtes 2015-2017,
    # pendant la guerre civile), valeur publiée par la World Bank et non erreur de traitement
    assert df_panel["esperance_vie"].dropna().between(30, 90).all()
    assert (df_panel["pib_par_habitant_ppa"].dropna() > 0).all()


def test_valeur_aberrante_somalie_retiree(df_2026):
    # Les dépenses d'éducation de la Somalie (≈ 0 % du PIB) sont traitées comme manquantes
    somalie = df_2026.loc[df_2026["iso3"] == "SOM", "depenses_education_pct_pib"]
    assert somalie.isna().all()
