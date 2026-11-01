"""Affiche, pour chaque article, le prix affiché maximum (¥) à partir duquel le bot alerte.

Usage : python -m bot.prix_max
"""
from __future__ import annotations

from .filters import LIBELLES_ETAT
from .fx import TauxChange
from .main import charger_config
from .models import Article, appliquer_seuil_unique
from .notifier import fourchette
from .pricing import prix_max_jpy


def main():
    cfg = charger_config("config.yaml")
    taux = TauxChange(cfg["frais"]["taux_jpy_eur_secours"]).jpy_eur()
    print(f"Taux JPY->EUR : {taux:.6f}\n")
    print(f"{'Article':<34} {'État':<14} {'Achat visé':>12}   Prix affiché max")
    articles = [Article.from_dict(d) for d in cfg["articles"]]
    if cfg["reglages"].get("seuil_unique_tous_etats"):
        appliquer_seuil_unique(articles)
    for a in articles:
        if not a.a_des_prix:
            print(f"{a.nom:<34} {'—':<14} {'pas de prix':>12}   récap quotidien seulement")
            continue
        for etat in ("tres_bon", "moyen", "mauvais"):
            f = a.seuil_achat(etat)
            if not f:
                continue
            pmax = prix_max_jpy(f[1], taux, cfg["frais"], cfg["profils"][a.profil])
            info = f"{pmax:>9,} ¥".replace(",", " ") if pmax else "impossible (port + frais > prix visé)"
            print(f"{a.nom:<34} {LIBELLES_ETAT[etat]:<14} {fourchette(f):>12}   {info}")


if __name__ == "__main__":
    main()
