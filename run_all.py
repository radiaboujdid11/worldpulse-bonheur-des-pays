"""
Relance tout le projet WorldPulse, de la collecte des données aux modèles.

Exécute les scripts de src/ dans l'ordre (01 à 08) et s'arrête à la première erreur.

Utilisation :
    python run_all.py              # tout relancer (télécharge les données : ~10 min)
    python run_all.py --depuis 03  # repartir de l'étape 03, avec les données déjà téléchargées

Remarque : les étapes 01, 02 et 07 téléchargent des données (World Bank, Wikipedia).
Les sources peuvent avoir changé depuis novembre 2026 : en cas d'erreur, les données
téléchargées à l'époque sont conservées dans data/raw/ et on peut repartir de l'étape 03.
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path

DOSSIER_SRC = Path(__file__).resolve().parent / "src"


def main():
    parser = argparse.ArgumentParser(description="Relance les scripts de src/ dans l'ordre.")
    parser.add_argument("--depuis", default="01", help="numéro de la première étape à lancer (ex. 03)")
    args = parser.parse_args()

    # Les scripts sont numérotés (01_..., 02_...) : l'ordre alphabétique est le bon ordre
    scripts = sorted(s for s in DOSSIER_SRC.glob("[0-9][0-9]_*.py") if s.name[:2] >= args.depuis)

    debut_total = time.time()
    for script in scripts:
        print(f"\n=== {script.name} ===", flush=True)
        debut = time.time()
        # sys.executable = le Python actuel (celui du .venv s'il est activé)
        resultat = subprocess.run([sys.executable, str(script)], cwd=DOSSIER_SRC.parent)
        if resultat.returncode != 0:
            print(f"\nÉchec de {script.name} (code {resultat.returncode}). Arrêt.")
            sys.exit(resultat.returncode)
        print(f"--- {script.name} terminé en {time.time() - debut:.0f} s")

    print(f"\n{len(scripts)} étape(s) terminée(s) en {(time.time() - debut_total) / 60:.1f} min.")


if __name__ == "__main__":
    main()
