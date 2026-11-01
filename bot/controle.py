"""Contrôle anti-contrefaçon indicatif (titre, prix, vendeur). Ne remplace jamais l'examen des photos."""
from __future__ import annotations

import re
import unicodedata
from typing import Optional

from .models import Listing

# « ヴィトン風 » = « style Vuitton » ; N級 / ミラー / スーパーコピー = termes de contrefaçon
MARQUE_STYLE_RE = re.compile(r"(ヴィトン|シャネル|グッチ|ディオール|プラダ|セリーヌ|フェンディ|ボッテガ|クロエ|サンローラン)風")
MOTS_SUSPECTS = ["タイプ", "ノーブランド", "N級", "ミラー品", "スーパーコピー", "レプリカ", "偽物", "コピー品", "非正規", "ノベルティ"]


def controler(l: Listing, prix_habituel_jpy: Optional[int]) -> list[str]:
    """Renvoie la liste des signaux suspects (vide = contrôle passé)."""
    titre = unicodedata.normalize("NFKC", l.title or "")
    alertes = []
    if MARQUE_STYLE_RE.search(titre):
        alertes.append("le titre dit « style » de la marque (風)")
    for mot in MOTS_SUSPECTS:
        if mot in titre:
            alertes.append(f"mot suspect dans le titre : {mot}")
    if prix_habituel_jpy and l.price_jpy < 0.3 * prix_habituel_jpy:
        alertes.append("prix anormalement bas (moins de 30 % du prix habituel)")
    if l.vendeur_avis is not None and l.vendeur_avis < 5:
        alertes.append(f"vendeur très récent ({l.vendeur_avis} avis)")
    if l.vendeur_positif_pct is not None and l.vendeur_avis and l.vendeur_avis >= 5 and l.vendeur_positif_pct < 90:
        alertes.append(f"vendeur peu fiable ({l.vendeur_positif_pct} % d'avis positifs)")
    return alertes
