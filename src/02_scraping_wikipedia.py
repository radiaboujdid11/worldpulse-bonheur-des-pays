"""
Étape 3 — Scraping des scores de bonheur sur Wikipedia (page « World Happiness Report »).

La section « International rankings » de la page contient un tableau par rapport
annuel. Ce script :
  1. télécharge la page UNE seule fois (avec un User-Agent identifiable) ;
  2. garde une copie du HTML dans data/raw/ (la page évolue : on garde une trace
     exacte de ce qu'on a lu) ;
  3. repère chaque tableau et l'année du rapport auquel il appartient ;
  4. ne garde que le rang, le pays et le score de bonheur ;
  5. empile tous les rapports dans un seul fichier CSV.

⚠️ Les colonnes « GDP per capita », « Social support »… des tableaux ne sont PAS
des données brutes : ce sont les parts du score attribuées à chaque facteur par
le rapport. Les utiliser pour prédire le score serait une fuite de données
(data leakage). On les ignore volontairement.

Lancement (depuis la racine du projet, venv activé) :
    python src/02_scraping_wikipedia.py
"""

import re
from io import StringIO
from pathlib import Path

import pandas as pd
import requests
from lxml import html

# ---------------------------------------------------------------------------
# Paramètres
# ---------------------------------------------------------------------------

DOSSIER_RAW = Path(__file__).resolve().parent.parent / "data" / "raw"

URL_PAGE = "https://en.wikipedia.org/wiki/World_Happiness_Report"

# On s'identifie clairement auprès de Wikipedia (c'est demandé dans leurs règles)
ENTETES = {"User-Agent": "WorldPulse-EducationalProject/0.1 (student data science project)"}

# Seuls les tableaux de cette section nous intéressent
SECTION_CLASSEMENTS = "International rankings"


# ---------------------------------------------------------------------------
# Fonctions
# ---------------------------------------------------------------------------

def telecharger_page():
    """Télécharge la page Wikipedia et renvoie son code HTML (texte)."""
    reponse = requests.get(URL_PAGE, headers=ENTETES, timeout=30)
    reponse.raise_for_status()  # erreur si la page n'a pas pu être récupérée
    return reponse.text


def enlever_notes(texte):
    """Retire les appels de notes Wikipedia, ex. 'Europe[a]' -> 'Europe', '5.305[b]' -> '5.305'."""
    return re.sub(r"\[.*?\]", "", str(texte)).strip()


def trouver_colonne(df, noms_possibles):
    """Renvoie le nom de la première colonne du tableau qui figure dans noms_possibles (ou None)."""
    for nom in noms_possibles:
        if nom in df.columns:
            return nom
    return None


def extraire_tableaux(code_html):
    """
    Parcourt les tableaux de la page et renvoie :
      - une liste de DataFrames propres (rapport, rang, pays, score) ;
      - une liste de messages sur les tableaux ignorés.
    """
    arbre = html.fromstring(code_html)
    tableaux_propres = []
    ignores = []

    # Sur Wikipedia, les tableaux de données ont la classe CSS « wikitable »
    for tableau in arbre.xpath("//table[contains(@class, 'wikitable')]"):

        # Titre de section (h2) et sous-section (h3) qui précèdent le tableau
        h2 = tableau.xpath("preceding::h2[1]")[0].text_content().strip()
        h3 = tableau.xpath("preceding::h3[1]")[0].text_content().strip()

        # On ignore les tableaux qui ne sont pas dans « International rankings »
        if h2 != SECTION_CLASSEMENTS:
            continue

        # L'année du rapport se trouve dans le titre, ex. « 2026 report »
        annee_trouvee = re.search(r"(\d{4}) report", h3)
        if annee_trouvee is None:
            ignores.append(f"section « {h3} » : année introuvable")
            continue
        rapport = int(annee_trouvee.group(1))

        # pd.read_html transforme le HTML d'un tableau en DataFrame
        # (il renvoie une liste, d'où le [0])
        code_tableau = html.tostring(tableau, encoding="unicode")
        df = pd.read_html(StringIO(code_tableau))[0]

        # Les noms de colonnes changent selon les années : on cherche la bonne
        col_rang = trouver_colonne(df, ["Rank", "Overall rank", "Rank[30]"])
        col_pays = trouver_colonne(df, ["Country or region", "Country"])
        col_score = trouver_colonne(df, ["Life evaluation", "Score", "Happiness score"])

        if col_pays is None or col_score is None:
            ignores.append(f"rapport {rapport} : pas de colonne de score ({len(df)} lignes)")
            continue

        # On ne garde que les 3 colonnes utiles, avec des noms en français
        df = df[[col_rang, col_pays, col_score]].copy()
        df.columns = ["rang", "pays", "score_bonheur"]

        # Nettoyage : notes de bas de page, puis conversion en nombres
        df["pays"] = df["pays"].apply(enlever_notes)
        df["score_bonheur"] = pd.to_numeric(df["score_bonheur"].apply(enlever_notes), errors="coerce")
        df["rang"] = pd.to_numeric(df["rang"].apply(enlever_notes), errors="coerce")

        # Le score d'un rapport = moyenne des enquêtes des 3 années précédentes
        # (ex. rapport 2026 -> enquêtes 2023, 2024, 2025)
        df.insert(0, "rapport", rapport)
        df.insert(1, "enquete_debut", rapport - 3)
        df.insert(2, "enquete_fin", rapport - 1)

        tableaux_propres.append(df)

    return tableaux_propres, ignores


# ---------------------------------------------------------------------------
# Programme principal
# ---------------------------------------------------------------------------

def main():
    DOSSIER_RAW.mkdir(parents=True, exist_ok=True)

    # 1. Téléchargement (une seule requête)
    print("🌐 Téléchargement de la page Wikipedia…")
    code_html = telecharger_page()

    # 2. Copie du HTML brut, pour la traçabilité
    chemin_html = DOSSIER_RAW / "wikipedia_whr.html"
    chemin_html.write_text(code_html, encoding="utf-8")
    print(f"   page enregistrée : {chemin_html.name} ({len(code_html) // 1024} Ko)\n")

    # 3. Extraction des tableaux
    tableaux, ignores = extraire_tableaux(code_html)

    if not tableaux:
        # Si la page a changé de structure, on s'arrête avec un message clair
        raise RuntimeError("Aucun tableau de score trouvé : la structure de la page a peut-être changé.")

    print("📊 Tableaux retenus :")
    for df in tableaux:
        print(f"   rapport {df['rapport'].iloc[0]} : {len(df)} lignes")
    print("\n🚫 Tableaux ignorés :")
    for message in ignores:
        print(f"   {message}")

    # 4. On empile tous les rapports dans un seul tableau
    df_final = pd.concat(tableaux, ignore_index=True)

    chemin_csv = DOSSIER_RAW / "wikipedia_bonheur.csv"
    df_final.to_csv(chemin_csv, index=False)
    print(f"\n✅ Enregistré : {chemin_csv}")
    print(f"   {df_final.shape[0]} lignes × {df_final.shape[1]} colonnes")


if __name__ == "__main__":
    main()
