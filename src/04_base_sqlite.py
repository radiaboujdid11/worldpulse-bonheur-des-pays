"""
Étape 5 — Base de données SQLite.

Ce script :
  1. enregistre les données brutes et fusionnées dans db/worldpulse.db ;
  2. crée une vue (requête enregistrée) pour le rapport principal ;
  3. exécute quelques requêtes SQL d'exemple et affiche leurs résultats.

Tables créées :
  pays                  <- data/raw/worldbank_pays.csv
  indicateurs_wb        <- data/raw/worldbank_indicateurs.csv
  bonheur_wikipedia     <- data/raw/wikipedia_bonheur.csv
  worldpulse            <- data/processed/worldpulse_panel.csv
Vue :
  worldpulse_2026       = worldpulse filtrée sur le rapport 2026

Lancement (depuis la racine du projet, venv activé) :
    python src/04_base_sqlite.py
"""

import sqlite3
from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# Paramètres
# ---------------------------------------------------------------------------

RACINE = Path(__file__).resolve().parent.parent
CHEMIN_BASE = RACINE / "db" / "worldpulse.db"

# Nom de la table SQL -> fichier CSV source
TABLES = {
    "pays": RACINE / "data" / "raw" / "worldbank_pays.csv",
    "indicateurs_wb": RACINE / "data" / "raw" / "worldbank_indicateurs.csv",
    "bonheur_wikipedia": RACINE / "data" / "raw" / "wikipedia_bonheur.csv",
    "worldpulse": RACINE / "data" / "processed" / "worldpulse_panel.csv",
}

# Requêtes d'exemple : (question posée, requête SQL)
REQUETES = [
    (
        "Les 10 pays les plus heureux (rapport 2026)",
        """
        SELECT pays, region, ROUND(score_bonheur, 2) AS score
        FROM worldpulse_2026
        ORDER BY score_bonheur DESC
        LIMIT 10
        """,
    ),
    (
        "Score moyen par niveau de revenu (rapport 2026)",
        """
        SELECT niveau_revenu,
               COUNT(*)                     AS nb_pays,
               ROUND(AVG(score_bonheur), 2) AS score_moyen
        FROM worldpulse_2026
        GROUP BY niveau_revenu
        ORDER BY score_moyen DESC
        """,
    ),
    (
        "Score moyen et espérance de vie moyenne par région (rapport 2026)",
        """
        SELECT region,
               COUNT(*)                     AS nb_pays,
               ROUND(AVG(score_bonheur), 2) AS score_moyen,
               ROUND(AVG(esperance_vie), 1) AS esperance_vie_moy
        FROM worldpulse_2026
        GROUP BY region
        ORDER BY score_moyen DESC
        """,
    ),
    (
        "Plus fortes variations du bonheur entre les rapports 2016 et 2026",
        # Auto-jointure : on joint la table à elle-même pour mettre
        # le score 2016 et le score 2026 d'un même pays sur une seule ligne
        """
        SELECT a.pays,
               ROUND(a.score_bonheur, 2)                   AS score_2016,
               ROUND(b.score_bonheur, 2)                   AS score_2026,
               ROUND(b.score_bonheur - a.score_bonheur, 2) AS variation
        FROM worldpulse AS a
        JOIN worldpulse AS b ON a.iso3 = b.iso3
        WHERE a.rapport = 2016 AND b.rapport = 2026
        ORDER BY ABS(b.score_bonheur - a.score_bonheur) DESC
        LIMIT 10
        """,
    ),
    (
        "Pays très connectés (internet > 90 %) mais peu heureux (score < 6)",
        """
        SELECT pays, ROUND(internet_pct, 1) AS internet_pct, ROUND(score_bonheur, 2) AS score
        FROM worldpulse_2026
        WHERE internet_pct > 90 AND score_bonheur < 6
        ORDER BY score_bonheur
        """,
    ),
]


# ---------------------------------------------------------------------------
# Programme principal
# ---------------------------------------------------------------------------

def main():
    CHEMIN_BASE.parent.mkdir(parents=True, exist_ok=True)

    # Connexion à la base (le fichier est créé s'il n'existe pas).
    # Le bloc « with » valide automatiquement les modifications (commit).
    with sqlite3.connect(CHEMIN_BASE) as connexion:

        # 1. Chargement des tables (if_exists="replace" : on recrée la table à chaque exécution)
        print("💾 Enregistrement des tables…")
        for nom_table, chemin_csv in TABLES.items():
            df = pd.read_csv(chemin_csv)
            df.to_sql(nom_table, connexion, if_exists="replace", index=False)
            print(f"   {nom_table:18} {df.shape[0]:>6} lignes × {df.shape[1]} colonnes")

        # 2. Vue : une requête enregistrée qu'on interroge comme une table
        connexion.execute("DROP VIEW IF EXISTS worldpulse_2026")
        connexion.execute("CREATE VIEW worldpulse_2026 AS SELECT * FROM worldpulse WHERE rapport = 2026")
        print("   vue worldpulse_2026 créée")

        # 3. Requêtes d'exemple (pd.read_sql renvoie directement un DataFrame)
        for question, requete in REQUETES:
            print(f"\n🔎 {question}")
            print(pd.read_sql(requete, connexion).to_string(index=False))

    print(f"\n✅ Base enregistrée : {CHEMIN_BASE}")


if __name__ == "__main__":
    main()
