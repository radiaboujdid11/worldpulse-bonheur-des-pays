"""
Étape 2 — Extraction des indicateurs de la World Bank (API publique, sans clé).

Ce script utilise DEUX façons d'interroger l'API :
  1. la liste des pays, en JSON paginé (pour écarter les « agrégats » comme « World ») ;
  2. les indicateurs, en téléchargement groupé : un fichier ZIP (contenant un CSV)
     par indicateur, avec tous les pays et toutes les années.

Pourquoi le téléchargement groupé pour les indicateurs ?
  En novembre 2026, les requêtes JSON de données renvoyaient très souvent une
  erreur 502 (panne côté World Bank). Le téléchargement groupé fonctionnait, et
  ne demande que 7 requêtes au lieu de plusieurs dizaines : c'est aussi plus
  respectueux du serveur.

On garde TOUTES les années de ANNEE_DEBUT à ANNEE_FIN (format « long ») :
le choix de l'agrégation (moyenne sur 3 ans…) sera fait à l'étape 4.

Lancement (depuis la racine du projet, venv activé) :
    python src/01_extraction_api.py
"""

import io
import time
import zipfile
from pathlib import Path

import pandas as pd
import requests

# ---------------------------------------------------------------------------
# Paramètres
# ---------------------------------------------------------------------------

# Dossier où ranger les fichiers bruts (chemin construit à partir de ce script,
# pour que le script marche quel que soit le dossier d'où on le lance)
DOSSIER_RAW = Path(__file__).resolve().parent.parent / "data" / "raw"

URL_API = "https://api.worldbank.org/v2"

# On s'identifie clairement auprès du serveur (bonne pratique)
ENTETES = {"User-Agent": "WorldPulse-EducationalProject/0.1 (student data science project)"}

# Indicateurs à récupérer : code World Bank -> nom court qu'on utilisera dans le projet
INDICATEURS = {
    "NY.GDP.PCAP.PP.KD": "pib_par_habitant_ppa",  # PIB/hab. en parité de pouvoir d'achat ($ constants 2021)
    "SP.DYN.LE00.IN": "esperance_vie",            # espérance de vie à la naissance (années)
    "IT.NET.USER.ZS": "internet_pct",             # % de la population utilisant internet
    "SL.UEM.TOTL.ZS": "chomage_pct",              # chômage, % de la population active (estimation OIT)
    "SE.XPD.TOTL.GD.ZS": "depenses_education_pct_pib",  # dépenses publiques d'éducation, % du PIB
    "SH.XPD.CHEX.GD.ZS": "depenses_sante_pct_pib",      # dépenses de santé courantes, % du PIB
    "SP.URB.TOTL.IN.ZS": "urbanisation_pct",      # % de la population vivant en ville
}

# Années couvertes : 2013 = premier rapport du bonheur sur Wikipedia
ANNEE_DEBUT = 2013
ANNEE_FIN = 2025

# Nombre de lignes par page : l'API est lente si on en demande trop d'un coup
LIGNES_PAR_PAGE = 1000

# Pause (en secondes) entre deux requêtes, pour ne pas surcharger le serveur
PAUSE = 1.0


# ---------------------------------------------------------------------------
# Fonctions
# ---------------------------------------------------------------------------

def requete_get(url, parametres, essais=3):
    """Envoie une requête GET et renvoie la réponse. Réessaie en cas d'échec."""
    for essai in range(1, essais + 1):
        try:
            reponse = requests.get(url, params=parametres, headers=ENTETES, timeout=60)
            reponse.raise_for_status()  # déclenche une erreur si le code HTTP n'est pas 200
            return reponse
        except requests.RequestException as erreur:
            print(f"   ⚠️  essai {essai}/{essais} échoué : {erreur}")
            if essai == essais:
                raise  # après le dernier essai, on abandonne et on affiche l'erreur
            time.sleep(5 * essai)  # on attend un peu plus à chaque nouvel essai


def appeler_api(url, parametres):
    """Envoie une requête GET et renvoie le contenu JSON (converti en listes/dictionnaires Python)."""
    return requete_get(url, parametres).json()


def telecharger_toutes_les_pages(url, parametres):
    """
    L'API renvoie les résultats par pages.
    Sa réponse JSON est une liste de 2 éléments :
      [0] = informations sur la pagination (page, nombre total de pages…)
      [1] = les données elles-mêmes (liste de dictionnaires)
    Cette fonction parcourt toutes les pages et renvoie la liste complète des données.
    """
    toutes_les_donnees = []
    page = 1
    while True:
        parametres_page = {**parametres, "format": "json", "per_page": LIGNES_PAR_PAGE, "page": page}
        json_recu = appeler_api(url, parametres_page)

        # Si l'API renvoie une erreur (ex. code invalide), elle n'a qu'un seul élément
        if len(json_recu) < 2:
            raise ValueError(f"Réponse inattendue de l'API : {json_recu}")

        infos, donnees = json_recu
        toutes_les_donnees.extend(donnees or [])

        if page >= infos["pages"]:
            break
        page += 1
        time.sleep(PAUSE)
    return toutes_les_donnees


def recuperer_pays():
    """Récupère la liste des pays avec leur région et leur niveau de revenu."""
    donnees = telecharger_toutes_les_pages(f"{URL_API}/country", {})
    lignes = []
    for pays in donnees:
        lignes.append({
            "iso3": pays["id"],
            "pays": pays["name"],
            "region": pays["region"]["value"],
            "niveau_revenu": pays["incomeLevel"]["value"],
        })
    df = pd.DataFrame(lignes)
    # Les agrégats (« World », « Euro area »…) ont la région « Aggregates » : on les retire
    df = df[df["region"] != "Aggregates"].reset_index(drop=True)
    return df


def recuperer_indicateur(code):
    """
    Télécharge le fichier ZIP d'un indicateur et renvoie un DataFrame au format long.

    Le ZIP contient 3 CSV ; celui des données commence par « API_ ».
    Ce CSV est au format « large » : une ligne par pays, une colonne par année.
    """
    url = f"{URL_API}/en/indicator/{code}"
    reponse = requete_get(url, {"downloadformat": "csv"})

    # On ouvre le ZIP directement en mémoire, sans l'écrire sur le disque
    archive = zipfile.ZipFile(io.BytesIO(reponse.content))
    nom_csv = [nom for nom in archive.namelist() if nom.startswith("API_")][0]

    # Les 4 premières lignes du CSV sont des informations (source, date de mise à jour) : on les saute
    with archive.open(nom_csv) as fichier:
        df_large = pd.read_csv(fichier, skiprows=4)

    # On ne garde que le code pays et les colonnes des années qui nous intéressent
    colonnes_annees = [str(annee) for annee in range(ANNEE_DEBUT, ANNEE_FIN + 1)
                       if str(annee) in df_large.columns]
    df_large = df_large[["Country Code"] + colonnes_annees]

    # Format « large » -> format « long » : une ligne par (pays, année)
    #   avant : iso3 | 2013 | 2014 | …
    #   après : iso3 | annee | valeur
    df_long = df_large.melt(id_vars="Country Code", var_name="annee", value_name="valeur")
    df_long = df_long.rename(columns={"Country Code": "iso3"})
    df_long["annee"] = df_long["annee"].astype(int)
    df_long["indicateur"] = INDICATEURS[code]
    df_long["code_wb"] = code

    # On remet les colonnes dans le même ordre pour tous les indicateurs
    return df_long[["iso3", "indicateur", "code_wb", "annee", "valeur"]]


# ---------------------------------------------------------------------------
# Programme principal
# ---------------------------------------------------------------------------

def main():
    DOSSIER_RAW.mkdir(parents=True, exist_ok=True)

    # 1. Liste des pays
    print("📋 Récupération de la liste des pays…")
    df_pays = recuperer_pays()
    df_pays.to_csv(DOSSIER_RAW / "worldbank_pays.csv", index=False)
    print(f"   {len(df_pays)} pays (agrégats exclus)\n")

    # 2. Chaque indicateur, l'un après l'autre
    morceaux = []
    for code, nom in INDICATEURS.items():
        print(f"📥 {nom} ({code})…")
        df_ind = recuperer_indicateur(code)
        print(f"   {len(df_ind)} lignes, dont {df_ind['valeur'].notna().sum()} avec une valeur")
        morceaux.append(df_ind)
        time.sleep(PAUSE)

    # 3. On empile tous les indicateurs dans un seul tableau (format long)
    df = pd.concat(morceaux, ignore_index=True)

    # On ne garde que les vrais pays (on retire les agrégats régionaux)
    df = df[df["iso3"].isin(df_pays["iso3"])]

    # On retire les lignes sans valeur : elles n'apportent aucune information
    df = df.dropna(subset=["valeur"]).reset_index(drop=True)

    chemin = DOSSIER_RAW / "worldbank_indicateurs.csv"
    df.to_csv(chemin, index=False)
    print(f"\n✅ Enregistré : {chemin}")
    print(f"   {df.shape[0]} lignes × {df.shape[1]} colonnes")


if __name__ == "__main__":
    main()
