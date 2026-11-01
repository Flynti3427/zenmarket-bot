"""Recherche Yahoo! Enchères Japon (appelé « JDirectItems Auction » sur ZenMarket).

⚠️ Yahoo Japan bloque les connexions venant d'Europe (UE/RU) depuis avril 2022 :
le bot doit tourner sur un serveur situé hors d'Europe (Japon, Singapour, USA).

Le parseur essaie trois méthodes, de la plus fiable à la plus générique,
pour résister aux changements de mise en page de Yahoo.
"""
from __future__ import annotations

import json
import logging
import re
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup

from ..http import requete
from ..models import Listing

log = logging.getLogger(__name__)

SEARCH_URL = (
    "https://auctions.yahoo.co.jp/search/search?p={q}&va={q}&exflg=1&b=1&n=100"
    "&s1=new&o1=d&aucminprice={min}"
)
ID_RE = re.compile(r"/jp/auction/([a-zA-Z]?\d{6,})")


def _entier(texte) -> int | None:
    if texte is None:
        return None
    chiffres = re.sub(r"[^\d]", "", str(texte))
    return int(chiffres) if chiffres else None


def _liens(item_id: str, langue: str) -> tuple[str, str]:
    return (
        f"https://auctions.yahoo.co.jp/jp/auction/{item_id}",
        f"https://zenmarket.jp/{langue}/auction.aspx?itemCode={item_id}",
    )


def _listing(item_id, titre, prix, langue, image=None, achat_immediat=None, temps=None) -> Listing | None:
    if not item_id or not titre or not prix:
        return None
    orig, zen = _liens(item_id, langue)
    return Listing(
        source="yahoo", item_id=item_id, title=titre.strip(), price_jpy=prix,
        url_original=orig, url_zenmarket=zen, image_url=image,
        is_auction=True, buy_now_jpy=achat_immediat or None, time_left=temps,
    )


def _par_attributs(soup: BeautifulSoup, langue: str) -> list[Listing]:
    """Méthode 1 : attributs data-auction-* (mise en page classique)."""
    res: dict[str, Listing] = {}
    for a in soup.select("[data-auction-id]"):
        item_id = a.get("data-auction-id")
        if item_id in res:
            continue
        produit = a.find_parent(class_=re.compile(r"Product\b")) or a.parent
        temps = produit.select_one(".Product__time") if produit else None
        l = _listing(
            item_id,
            a.get("data-auction-title") or a.get_text(" ", strip=True),
            _entier(a.get("data-auction-price")),
            langue,
            image=a.get("data-auction-img"),
            achat_immediat=_entier(a.get("data-auction-buynowprice")),
            temps=temps.get_text(strip=True) if temps else None,
        )
        if l:
            res[item_id] = l
    return list(res.values())


def _parcourir_json(noeud, trouves: list[dict]):
    if isinstance(noeud, dict):
        if ("auctionId" in noeud or "auction_id" in noeud) and "title" in noeud:
            trouves.append(noeud)
        for v in noeud.values():
            _parcourir_json(v, trouves)
    elif isinstance(noeud, list):
        for v in noeud:
            _parcourir_json(v, trouves)


def _par_json(soup: BeautifulSoup, langue: str) -> list[Listing]:
    """Méthode 2 : données JSON embarquées (__NEXT_DATA__ ou similaires)."""
    trouves: list[dict] = []
    for script in soup.find_all("script"):
        txt = script.string or ""
        if "auctionId" not in txt:
            continue
        debut = txt.find("{")
        try:
            _parcourir_json(json.loads(txt[debut:].rstrip(";\n ")), trouves)
        except (json.JSONDecodeError, ValueError):
            continue
    res: dict[str, Listing] = {}
    for d in trouves:
        item_id = str(d.get("auctionId") or d.get("auction_id"))
        prix = _entier(d.get("price") or d.get("currentPrice") or d.get("bidPrice"))
        img = d.get("imageUrl") or d.get("image") or d.get("thumbnail")
        if isinstance(img, dict):
            img = img.get("url")
        l = _listing(item_id, d.get("title"), prix, langue, image=img,
                     achat_immediat=_entier(d.get("buyNowPrice") or d.get("bidorbuy")))
        if l and item_id not in res:
            res[item_id] = l
    return list(res.values())


def _par_liens(soup: BeautifulSoup, langue: str) -> list[Listing]:
    """Méthode 3 (secours) : liens /jp/auction/<id> + prix le plus proche."""
    res: dict[str, Listing] = {}
    for a in soup.find_all("a", href=ID_RE):
        item_id = ID_RE.search(a["href"]).group(1)
        titre = a.get_text(" ", strip=True)
        if item_id in res or len(titre) < 6:
            continue
        bloc = a.find_parent("li") or a.find_parent("div")
        prix = None
        if bloc:
            m = re.search(r"([\d,]{3,})\s*円", bloc.get_text(" ", strip=True))
            prix = _entier(m.group(1)) if m else None
        l = _listing(item_id, titre, prix, langue)
        if l:
            res[item_id] = l
    return list(res.values())


def analyser_page(html: str, langue: str = "fr") -> list[Listing]:
    soup = BeautifulSoup(html, "html.parser")
    for methode in (_par_attributs, _par_json, _par_liens):
        res = methode(soup, langue)
        if res:
            return res
    return []


class YahooSource:
    nom = "yahoo"

    def __init__(self, session: requests.Session, langue: str = "fr"):
        self.session = session
        self.langue = langue

    def rechercher(self, mot_cle: str, prix_min: int = 0) -> list[Listing]:
        url = SEARCH_URL.format(q=quote(mot_cle), min=prix_min or "")
        r = requete(self.session, "GET", url)
        res = analyser_page(r.text, self.langue)
        log.debug("Yahoo « %s » : %d résultats", mot_cle, len(res))
        return res
