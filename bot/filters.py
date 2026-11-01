"""Filtrage des annonces et estimation de l'état (très bon / moyen / mauvais)."""
from __future__ import annotations

import re
import unicodedata

from .models import Article, Listing

TRES_BON = "tres_bon"
MOYEN = "moyen"
MAUVAIS = "mauvais"

LIBELLES_ETAT = {TRES_BON: "très bon état", MOYEN: "état moyen", MAUVAIS: "mauvais état"}

# États officiels Mercari (itemConditionId)
MERCARI_CONDITIONS = {
    "1": ("新品、未使用", TRES_BON),
    "2": ("未使用に近い", TRES_BON),
    "3": ("目立った傷や汚れなし", TRES_BON),
    "4": ("やや傷や汚れあり", MOYEN),
    "5": ("傷や汚れあり", MOYEN),
    "6": ("全体的に状態が悪い", MAUVAIS),
}

# Mots-clés dans les titres japonais (ordre = priorité : le pire gagne)
MOTS_MAUVAIS = ["ジャンク", "難あり", "訳あり", "破れ", "ベタつき", "ベタ有", "劣化", "穴あき", "全体的に状態が悪い"]
MOTS_MOYEN = ["使用感", "汚れあり", "傷あり", "スレあり", "角スレ", "ヤケ"]
MOTS_TRES_BON = ["極美品", "超美品", "美品", "未使用", "新品", "良品", "美中古"]

# Rangs utilisés par les boutiques d'occasion japonaises (Aランク, ABランク...)
RANG_RE = re.compile(r"(S|SA|A|AB|B|BC|C|D)\s*ランク", re.IGNORECASE)
RANG_ETAT = {"S": TRES_BON, "SA": TRES_BON, "A": TRES_BON, "AB": TRES_BON,
             "B": MOYEN, "BC": MOYEN, "C": MAUVAIS, "D": MAUVAIS}


def normaliser(texte: str) -> str:
    """Minuscules + caractères pleine chasse convertis (ＳＰＥＥＤＹ -> speedy)."""
    return unicodedata.normalize("NFKC", texte or "").lower()


def correspond(article: Article, listing: Listing, exclusions_globales: list[str]) -> bool:
    """True si l'annonce correspond bien à l'article recherché."""
    titre = normaliser(listing.title)
    if listing.price_jpy < article.prix_min_jpy:
        return False
    if article.doit_contenir and not any(normaliser(m) in titre for m in article.doit_contenir):
        return False
    for mot in [str(m) for m in exclusions_globales] + article.exclure:
        if normaliser(mot) in titre:
            return False
    return True


def estimer_etat(listing: Listing) -> tuple[str, str]:
    """Retourne (catégorie d'état, explication). Par défaut : moyen (prudent)."""
    titre = normaliser(listing.title)

    for mot in MOTS_MAUVAIS:
        if normaliser(mot) in titre:
            return MAUVAIS, f"titre contient « {mot} »"

    if listing.condition_jp:
        for _cid, (libelle, etat) in MERCARI_CONDITIONS.items():
            if listing.condition_jp == libelle:
                return etat, f"état Mercari : {libelle}"

    rang = RANG_RE.search(unicodedata.normalize("NFKC", listing.title or ""))
    if rang:
        r = rang.group(1).upper()
        return RANG_ETAT.get(r, MOYEN), f"rang {r}"

    for mot in MOTS_MOYEN:
        if normaliser(mot) in titre:
            return MOYEN, f"titre contient « {mot} »"
    for mot in MOTS_TRES_BON:
        if normaliser(mot) in titre:
            return TRES_BON, f"titre contient « {mot} »"

    return MOYEN, "état non précisé (hypothèse prudente)"
