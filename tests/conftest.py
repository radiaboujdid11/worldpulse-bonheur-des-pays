"""
Outils partagés par les tests.

Les scripts de src/ commencent par un chiffre (03_nettoyage_fusion.py) : on ne peut pas
écrire « import 03_nettoyage_fusion ». On les charge donc avec importlib.
"""

import importlib.util
from pathlib import Path

import pandas as pd
import pytest

RACINE = Path(__file__).resolve().parent.parent


def charger_script(nom_fichier):
    """Importe un script de src/ comme un module, sans exécuter son main()."""
    chemin = RACINE / "src" / nom_fichier
    spec = importlib.util.spec_from_file_location(chemin.stem, chemin)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def fusion():
    """Le module src/03_nettoyage_fusion.py."""
    return charger_script("03_nettoyage_fusion.py")


@pytest.fixture(scope="session")
def df_2026():
    """Le jeu principal : rapport 2026, un pays par ligne."""
    return pd.read_csv(RACINE / "data" / "processed" / "worldpulse_2026.csv")


@pytest.fixture(scope="session")
def df_panel():
    """Le jeu panel : tous les rapports exploitables."""
    return pd.read_csv(RACINE / "data" / "processed" / "worldpulse_panel.csv")
