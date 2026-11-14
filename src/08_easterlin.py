"""
Étape 8c — Le paradoxe d'Easterlin : le bonheur suit-il la croissance dans le temps ?

Le paradoxe (Richard Easterlin, 1974) :
  - ENTRE pays, à un moment donné, les pays riches sont plus heureux (étape 6 :
    +1,8 point quand le PIB est multiplié par 10) ;
  - mais DANS le temps, quand un pays s'enrichit, son bonheur n'augmenterait
    presque pas.

Question : dans nos données, la pente « dans le temps » est-elle aussi forte
que la pente « entre pays » ?

Trois mesures de la pente (points de bonheur par unité de log10 du PIB,
c'est-à-dire pour un PIB multiplié par 10) :
  1. Entre pays : régression score ~ log PIB, rapport 2016 puis 2026.
  2. Dans le temps (différences longues) : pour chaque pays, variation du score
     entre 2016 et 2026 en fonction de la variation de son log PIB.
  3. Dans le temps (panel à effets fixes) : les 8 rapports, avec un terme par pays
     (ce qui retire les différences permanentes entre pays) et un terme par rapport
     (ce qui retire les évolutions communes à tous les pays, ex. Covid).
     Seules les variations propres à chaque pays sont alors utilisées.

Incertitude : intervalle de confiance à 95 % par bootstrap (on tire des pays au
hasard avec remise, 1 000 fois, et on recalcule la pente).

Sorties (dossier reports/) :
  easterlin_variations.csv   variation du score et du PIB de chaque pays, 2016 → 2026
  easterlin_pentes.csv       les pentes et leurs intervalles de confiance

Lancement (depuis la racine du projet, venv activé) :
    python src/08_easterlin.py
"""

from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import theilslopes

# ---------------------------------------------------------------------------
# Paramètres
# ---------------------------------------------------------------------------

RACINE = Path(__file__).resolve().parent.parent
FICHIER_PANEL = RACINE / "data" / "processed" / "worldpulse_panel.csv"
DOSSIER_REPORTS = RACINE / "reports"

DEBUT, FIN = 2016, 2026     # premier et dernier rapport complets du panel
N_BOOTSTRAP = 1000
GRAINE = 42


# ---------------------------------------------------------------------------
# Fonctions
# ---------------------------------------------------------------------------

def pente(x, y):
    """Pente de la droite des moindres carrés y = a + b·x (renvoie b)."""
    return np.polyfit(x, y, 1)[0]


def bootstrap(fonction, donnees, groupe, n=N_BOOTSTRAP):
    """
    Intervalle de confiance à 95 % : on tire des pays avec remise (un pays tiré
    deux fois compte comme deux pays distincts), puis on recalcule la statistique.
    """
    alea = np.random.default_rng(GRAINE)
    pays = donnees[groupe].unique()
    par_pays = dict(tuple(donnees.groupby(groupe)))
    valeurs = []
    for _ in range(n):
        tirage = alea.choice(pays, size=len(pays), replace=True)
        echantillon = pd.concat([par_pays[p].assign(**{groupe: f"{p}_{i}"}) for i, p in enumerate(tirage)])
        valeurs.append(fonction(echantillon))
    return np.percentile(valeurs, [2.5, 97.5])


def pente_effets_fixes(panel):
    """
    Régression score ~ log_pib + un terme par pays + un terme par rapport.
    Les variables indicatrices (0/1) de pays et de rapport absorbent les écarts
    permanents entre pays et les chocs communs à une année.
    """
    X = pd.concat([panel[["log_pib"]],
                   pd.get_dummies(panel["iso3"], dtype=float),
                   pd.get_dummies(panel["rapport"], dtype=float, drop_first=True)], axis=1)
    coefficients, *_ = np.linalg.lstsq(X.to_numpy(), panel["score_bonheur"].to_numpy(), rcond=None)
    return coefficients[0]


def charger_panel():
    panel = pd.read_csv(FICHIER_PANEL).dropna(subset=["score_bonheur", "pib_par_habitant_ppa"])
    panel["log_pib"] = np.log10(panel["pib_par_habitant_ppa"])
    return panel


def variations(panel):
    """Une ligne par pays présent en 2016 ET en 2026 : niveaux et variations."""
    debut = panel.query("rapport == @DEBUT").set_index("iso3")
    fin = panel.query("rapport == @FIN").set_index("iso3")
    communs = debut.index.intersection(fin.index)
    df = pd.DataFrame({
        "pays": fin.loc[communs, "pays"],
        "region": fin.loc[communs, "region"],
        f"score_{DEBUT}": debut.loc[communs, "score_bonheur"],
        f"score_{FIN}": fin.loc[communs, "score_bonheur"],
        f"log_pib_{DEBUT}": debut.loc[communs, "log_pib"],
        f"log_pib_{FIN}": fin.loc[communs, "log_pib"],
    })
    df["delta_score"] = df[f"score_{FIN}"] - df[f"score_{DEBUT}"]
    df["delta_log_pib"] = df[f"log_pib_{FIN}"] - df[f"log_pib_{DEBUT}"]
    df["croissance_pib_pct"] = (10 ** df["delta_log_pib"] - 1) * 100
    return df.reset_index()


# ---------------------------------------------------------------------------
# Programme principal
# ---------------------------------------------------------------------------

def main():
    DOSSIER_REPORTS.mkdir(parents=True, exist_ok=True)
    panel = charger_panel()
    var = variations(panel)
    var.to_csv(DOSSIER_REPORTS / "easterlin_variations.csv", index=False)
    print(f"📦 Panel : {len(panel)} lignes ; {len(var)} pays présents en {DEBUT} et {FIN}")
    print(f"   croissance médiane du PIB/hab. : {var.croissance_pib_pct.median():+.0f} % ; "
          f"variation médiane du score : {var.delta_score.median():+.2f} point")

    resultats = []

    # 1. Entre pays
    for annee in (DEBUT, FIN):
        coupe = panel.query("rapport == @annee")
        b = pente(coupe.log_pib, coupe.score_bonheur)
        ic = bootstrap(lambda d: pente(d.log_pib, d.score_bonheur), coupe, "iso3")
        resultats.append({"approche": f"Entre pays ({annee})", "pente": b, "ic_bas": ic[0], "ic_haut": ic[1],
                          "n_pays": coupe.iso3.nunique()})

    # 2. Dans le temps : différences longues
    b = pente(var.delta_log_pib, var.delta_score)
    ic = bootstrap(lambda d: pente(d.delta_log_pib, d.delta_score), var, "iso3")
    resultats.append({"approche": f"Dans le temps ({DEBUT} → {FIN})", "pente": b, "ic_bas": ic[0], "ic_haut": ic[1],
                      "n_pays": len(var)})

    # 3. Dans le temps : panel à effets fixes (pays présents dans au moins 2 rapports)
    multi = panel[panel.groupby("iso3")["rapport"].transform("count") >= 2]
    b = pente_effets_fixes(multi)
    ic = bootstrap(pente_effets_fixes, multi, "iso3", n=300)  # plus lent : 300 tirages
    resultats.append({"approche": "Dans le temps (panel, effets fixes)", "pente": b, "ic_bas": ic[0],
                      "ic_haut": ic[1], "n_pays": multi.iso3.nunique()})

    # 4. Robustesse de la pente « dans le temps » (sans intervalle de confiance)
    sans_baisse = var[var.delta_log_pib > 0]
    pays_par_pays = [pente(var.drop(i).delta_log_pib, var.drop(i).delta_score) for i in var.index]
    robustesse = {
        "Robustesse : PIB en hausse seulement": (pente(sans_baisse.delta_log_pib, sans_baisse.delta_score),
                                                 len(sans_baisse)),
        "Robustesse : Theil-Sen (peu sensible aux extrêmes)": (theilslopes(var.delta_score, var.delta_log_pib)[0],
                                                               len(var)),
        "Robustesse : retrait d'un pays (minimum)": (min(pays_par_pays), len(var) - 1),
        "Robustesse : retrait d'un pays (maximum)": (max(pays_par_pays), len(var) - 1),
    }
    for nom, (b, n) in robustesse.items():
        resultats.append({"approche": nom, "pente": b, "ic_bas": np.nan, "ic_haut": np.nan, "n_pays": n})

    pentes = pd.DataFrame(resultats)
    pentes.to_csv(DOSSIER_REPORTS / "easterlin_pentes.csv", index=False)
    print("\n📐 Pente : points de bonheur pour un PIB multiplié par 10 (IC à 95 % par bootstrap)")
    print(pentes.round(2).to_string(index=False))

    # Corrélation des variations, et comparaison des pays selon leur croissance
    print(f"\n🔗 Corrélation entre variation du log PIB et variation du score : "
          f"{var.delta_log_pib.corr(var.delta_score):.2f}")
    var["croissance"] = pd.qcut(var.croissance_pib_pct, 3, labels=["faible ou négative", "moyenne", "forte"])
    print(var.groupby("croissance", observed=True).agg(
        n=("pays", "size"), croissance_mediane_pct=("croissance_pib_pct", "median"),
        delta_score_median=("delta_score", "median")).round(2).to_string())

    print(f"\n✅ Résultats enregistrés dans {DOSSIER_REPORTS}")


if __name__ == "__main__":
    main()
