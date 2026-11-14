"""
Étape 8 — Clustering : regrouper les pays aux profils similaires (K-Means).

Le clustering est « non supervisé » : on ne donne PAS le score de bonheur à
l'algorithme. Il regroupe les pays uniquement d'après leurs 7 indicateurs ; on
regarde ENSUITE si les groupes obtenus diffèrent en bonheur.

Ce script :
  1. prépare les données (imputation par la médiane, puis standardisation :
     K-Means mesure des distances, toutes les variables doivent avoir la même échelle) ;
  2. teste k = 2 à 8 groupes : inertie (méthode du coude) et score de silhouette ;
  3. applique K-Means avec K_CHOISI groupes et nomme chaque groupe d'après son profil ;
  4. calcule une projection en 2 dimensions (ACP) pour visualiser les groupes.

Sorties (dossier reports/) :
  clustering_choix_k.csv   inertie et silhouette pour chaque k
  clustering_pays.csv      groupe et coordonnées ACP de chaque pays
  clustering_profils.csv   moyenne de chaque indicateur et du score, par groupe

Lancement (depuis la racine du projet, venv activé) :
    python src/06_clustering.py
"""

from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.impute import SimpleImputer
from sklearn.metrics import silhouette_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

# ---------------------------------------------------------------------------
# Paramètres
# ---------------------------------------------------------------------------

RACINE = Path(__file__).resolve().parent.parent
FICHIER_DONNEES = RACINE / "data" / "processed" / "worldpulse_2026.csv"
DOSSIER_REPORTS = RACINE / "reports"

GRAINE = 42
VARIABLES = [
    "log_pib", "esperance_vie", "internet_pct", "urbanisation_pct",
    "depenses_sante_pct_pib", "depenses_education_pct_pib", "chomage_pct",
]
VALEURS_K = range(2, 9)

# Nombre de groupes retenu : meilleur score de silhouette (voir clustering_choix_k.csv)
K_CHOISI = 3


# ---------------------------------------------------------------------------
# Fonctions
# ---------------------------------------------------------------------------

def preparer(df):
    """Imputation (médiane) puis standardisation (moyenne 0, écart-type 1)."""
    preparation = make_pipeline(SimpleImputer(strategy="median"), StandardScaler())
    return preparation.fit_transform(df[VARIABLES])


def tester_k(X):
    """Inertie et silhouette pour chaque nombre de groupes k."""
    lignes = []
    for k in VALEURS_K:
        # n_init=50 : K-Means est relancé 50 fois avec des centres de départ différents,
        # et on garde la meilleure solution (le résultat dépend du point de départ)
        kmeans = KMeans(n_clusters=k, n_init=50, random_state=GRAINE).fit(X)
        lignes.append({"k": k, "inertie": kmeans.inertia_,
                       "silhouette": silhouette_score(X, kmeans.labels_)})
    return pd.DataFrame(lignes)


def nommer_groupes(profils):
    """
    Les numéros de K-Means sont arbitraires : on nomme chaque groupe d'après son profil
    (écrit pour K_CHOISI = 3, à adapter si on change de k).
      - le groupe au chômage le plus élevé       -> « Chômage élevé »
      - parmi les autres, le PIB le plus élevé   -> « Développés et émergents »
      - le dernier                                -> « En développement »
    """
    noms = {}
    chomage = profils["chomage_pct"].idxmax()
    noms[chomage] = "Chômage élevé"
    autres = profils.drop(index=chomage)
    noms[autres["log_pib"].idxmax()] = "Développés et émergents"
    noms[autres["log_pib"].idxmin()] = "En développement"
    return noms


# ---------------------------------------------------------------------------
# Programme principal
# ---------------------------------------------------------------------------

def main():
    DOSSIER_REPORTS.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(FICHIER_DONNEES)
    df["log_pib"] = np.log10(df["pib_par_habitant_ppa"])
    X = preparer(df)

    print("🔢 Choix du nombre de groupes :")
    choix = tester_k(X)
    choix.to_csv(DOSSIER_REPORTS / "clustering_choix_k.csv", index=False)
    print(choix.round(3).to_string(index=False))

    print(f"\n🧩 K-Means avec k = {K_CHOISI}")
    kmeans = KMeans(n_clusters=K_CHOISI, n_init=50, random_state=GRAINE).fit(X)
    df["groupe_num"] = kmeans.labels_

    # Profil moyen de chaque groupe (valeurs d'origine, plus lisibles que les valeurs standardisées)
    profils = df.groupby("groupe_num")[VARIABLES + ["score_bonheur"]].mean()
    profils["nb_pays"] = df["groupe_num"].value_counts()
    noms = nommer_groupes(profils)
    df["groupe"] = df["groupe_num"].map(noms)
    profils.index = profils.index.map(noms)
    profils.index.name = "groupe"
    profils = profils.sort_values("score_bonheur", ascending=False)
    profils.to_csv(DOSSIER_REPORTS / "clustering_profils.csv")
    print(profils.round(2).to_string())

    # ACP : résume les 7 variables en 2 axes, pour dessiner les pays sur un plan
    acp = PCA(n_components=2, random_state=GRAINE)
    coordonnees = acp.fit_transform(X)
    df["acp_1"], df["acp_2"] = coordonnees[:, 0], coordonnees[:, 1]
    part = acp.explained_variance_ratio_
    print(f"\n📐 ACP : les 2 axes résument {part.sum():.0%} de l'information "
          f"(axe 1 : {part[0]:.0%}, axe 2 : {part[1]:.0%})")
    # Contribution de chaque variable aux axes (pour les interpréter)
    print(pd.DataFrame(acp.components_.T, index=VARIABLES, columns=["axe_1", "axe_2"]).round(2).to_string())

    colonnes = ["iso3", "pays", "region", "score_bonheur", "groupe", "acp_1", "acp_2"]
    df[colonnes].to_csv(DOSSIER_REPORTS / "clustering_pays.csv", index=False)
    for nom in profils.index:
        print(f"\n{nom} : {', '.join(df.loc[df['groupe'] == nom, 'pays'].head(15))}…")

    print(f"\n✅ Résultats enregistrés dans {DOSSIER_REPORTS}")


if __name__ == "__main__":
    main()
