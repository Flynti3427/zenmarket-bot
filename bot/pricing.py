"""Calcul du coût rendu en France.

Modèle (sources : grille ZenMarket + règles douane FR, oct. 2026) :
  article + frais service ZenMarket (800 ¥) + frais de dépôt (~1,5 %)
  + port international EMS
  + droits de douane (si valeur > 150 €) sur (article + port)
  + TVA 20 % sur (article + port + droits)
  + frais de dossier transporteur (si > 150 €) ou droit forfaitaire UE (si <= 150 €)

Règle d'alerte : coût rendu France <= prix d'achat visé dans le tableau (haut de la fourchette).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .models import Fourchette


@dataclass
class Estimation:
    prix_article_eur: float
    frais_zenmarket_eur: float
    port_eur: float
    droits_eur: float
    tva_eur: float
    frais_fixes_eur: float
    cout_total_eur: float
    achat_vise: Optional[Fourchette] = None
    revente: Optional[Fourchette] = None

    @property
    def dans_les_prix(self) -> bool:
        """True si le coût rendu est dans la fourchette d'achat du tableau ou en dessous."""
        return self.achat_vise is not None and self.cout_total_eur <= self.achat_vise[1]

    @property
    def sous_la_fourchette(self) -> bool:
        return self.achat_vise is not None and self.cout_total_eur < self.achat_vise[0]

    @property
    def profit(self) -> Optional[Fourchette]:
        if not self.revente:
            return None
        return (round(self.revente[0] - self.cout_total_eur), round(self.revente[1] - self.cout_total_eur))


def cout_rendu_france(prix_jpy: int, taux_jpy_eur: float, frais: dict, profil: dict) -> Estimation:
    article = prix_jpy * taux_jpy_eur
    service = frais["frais_service_zenmarket_jpy"] * taux_jpy_eur
    depot = (article + service) * frais["frais_depot_pct"] / 100
    port = float(profil["port_eur"])

    valeur_douane = article + port
    if valeur_douane > frais["seuil_droits_douane_eur"]:
        droits = valeur_douane * profil["droits_pct"] / 100
        fixes = frais["frais_dossier_transporteur_eur"]
    else:
        droits = 0.0
        fixes = frais["droit_forfaitaire_ue_eur"]
    tva = (valeur_douane + droits) * frais["tva_pct"] / 100

    total = article + service + depot + port + droits + tva + fixes
    return Estimation(
        prix_article_eur=round(article, 2),
        frais_zenmarket_eur=round(service + depot, 2),
        port_eur=round(port, 2),
        droits_eur=round(droits, 2),
        tva_eur=round(tva, 2),
        frais_fixes_eur=round(fixes, 2),
        cout_total_eur=round(total, 2),
    )


def prix_max_jpy(cout_cible_eur: float, taux_jpy_eur: float, frais: dict, profil: dict) -> int:
    """Prix affiché maximum (¥) pour que le coût rendu France reste <= cout_cible_eur.

    Renvoie 0 si même un article gratuit dépasse la cible (port + frais trop élevés).
    """
    lo, hi = 0, 5_000_000
    if cout_rendu_france(0, taux_jpy_eur, frais, profil).cout_total_eur > cout_cible_eur:
        return 0
    while hi - lo > 100:
        mid = (lo + hi) // 2
        if cout_rendu_france(mid, taux_jpy_eur, frais, profil).cout_total_eur <= cout_cible_eur:
            lo = mid
        else:
            hi = mid
    return lo
