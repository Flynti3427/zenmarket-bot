"""Contenu d'une alerte, sous forme de dictionnaire (gardé en base pour les boutons Discord)."""
from __future__ import annotations

import time
from typing import Optional

from .filters import LIBELLES_ETAT
from .models import Article, Listing
from .pricing import Estimation

NOMS_SOURCES = {"mercari": "Mercari", "mercari_shops": "Mercari Shops", "yahoo": "Yahoo Enchères"}


def construire(article: Article, l: Listing, est: Estimation, etat: str, raison: str,
               prix_max_jpy: Optional[int], baisse: bool, prix_habituel_jpy: Optional[int],
               signaux: list[str], taux: float) -> dict:
    return {
        "cle": l.key,
        "article": article.nom,
        "titre": l.title,
        "source": l.source,
        "source_nom": NOMS_SOURCES.get(l.source, l.source),
        "prix_jpy": l.price_jpy,
        "prix_eur": est.prix_article_eur,
        "taux_eur_jpy": round(1 / taux) if taux else None,
        "enchere": l.is_auction,
        "achat_immediat_jpy": l.buy_now_jpy,
        "temps_restant": l.time_left,
        "fin_ts": l.fin_ts,
        "prix_habituel_jpy": prix_habituel_jpy,
        "prix_habituel_eur": round(prix_habituel_jpy * taux) if prix_habituel_jpy else None,
        "etat": etat,
        "etat_libelle": LIBELLES_ETAT[etat],
        "etat_raison": raison,
        "vendeur_id": l.seller_id,
        "vendeur_avis": l.vendeur_avis,
        "vendeur_positif_pct": l.vendeur_positif_pct,
        "photos": (l.photos or ([l.image_url] if l.image_url else []))[:3],
        "url_zenmarket": l.url_zenmarket,
        "url_original": l.url_original,
        "cout": {
            "article": est.prix_article_eur, "zenmarket": est.frais_zenmarket_eur, "port": est.port_eur,
            "douane": est.droits_eur, "tva": est.tva_eur, "fixes": est.frais_fixes_eur,
            "total": est.cout_total_eur,
        },
        "achat_vise": list(est.achat_vise) if est.achat_vise else None,
        "sous_fourchette": est.sous_la_fourchette,
        "revente": list(est.revente) if est.revente else None,
        "marge": list(est.profit) if est.profit else None,
        "prix_max_jpy": prix_max_jpy,
        "baisse": baisse,
        "signaux": signaux,
        "horodatage": time.time(),
        "salon": article.salon,
        "fil": article.fil,
        "sans_limite": article.sans_limite,
    }


def ecart_prix_habituel(a: dict) -> Optional[int]:
    """Écart en % entre le prix demandé et le prix habituel (+26 = 26 % plus cher)."""
    if not a.get("prix_habituel_jpy"):
        return None
    return round(100 * (a["prix_jpy"] - a["prix_habituel_jpy"]) / a["prix_habituel_jpy"])
