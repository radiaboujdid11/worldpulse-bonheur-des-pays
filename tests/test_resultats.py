"""Tests de cohérence des résultats de la modélisation (reports/)."""

import pandas as pd

from conftest import RACINE

REPORTS = RACINE / "reports"


def test_modele_final_correspond_a_la_decision():
    decision = pd.read_csv(REPORTS / "modele_decision.csv").iloc[0]
    final = pd.read_csv(REPORTS / "modele_final_coefficients.csv")
    assert set(decision["variables"].split(" + ")) == set(final["variable"])


def test_score_hors_echantillon_plus_faible_que_sur_echantillon():
    # Un modèle est toujours meilleur sur les données qui ont servi à l'ajuster :
    # si ce n'était pas le cas, il y aurait une erreur (ou une fuite de données).
    metriques = pd.read_csv(REPORTS / "modele_final_metriques.csv", index_col=0)["valeur"]
    scores = pd.read_csv(REPORTS / "modele_scores_cv.csv")
    r2_test = scores.loc[scores["modele"] == "Régression — variables retenues", "R2"].mean()
    assert 0 < r2_test < metriques["r2"]


def test_validation_croisee_imbriquee_plus_prudente():
    # La validation croisée imbriquée refait la sélection dans chaque pli :
    # elle doit donner un score inférieur ou égal à celui obtenu après sélection sur tous les pays.
    imbriquee = pd.read_csv(REPORTS / "modele_cv_imbriquee.csv")
    decision = pd.read_csv(REPORTS / "modele_decision.csv").iloc[0]
    scores = pd.read_csv(REPORTS / "modele_scores_cv.csv")
    r2_honnete = imbriquee.loc[imbriquee["procedure"] == decision["procedure"], "R2"].mean()
    r2_optimiste = scores.loc[scores["modele"] == "Régression — variables retenues", "R2"].mean()
    assert r2_honnete <= r2_optimiste
