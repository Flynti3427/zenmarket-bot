"""Recherche Mercari Japon via l'API publique du site web (jp.mercari.com).

Le site web signe chaque appel avec une preuve DPoP (RFC 9449) : un petit JWT
ES256 contenant une clé publique générée par le client. On fait pareil.
Les liens renvoyés pointent vers ZenMarket, qui achète l'article pour toi.
"""
from __future__ import annotations

import base64
import json
import logging
import secrets
import time
import uuid

import requests
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature

from ..filters import MERCARI_CONDITIONS
from ..http import requete
from ..models import Listing

log = logging.getLogger(__name__)

SEARCH_URL = "https://api.mercari.jp/v2/entities:search"
DETAIL_URL = "https://api.mercari.jp/items/get"


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def creer_dpop(url: str, methode: str, cle: ec.EllipticCurvePrivateKey) -> str:
    pub = cle.public_key().public_numbers()
    header = {
        "typ": "dpop+jwt",
        "alg": "ES256",
        "jwk": {
            "crv": "P-256",
            "kty": "EC",
            "x": _b64url(pub.x.to_bytes(32, "big")),
            "y": _b64url(pub.y.to_bytes(32, "big")),
        },
    }
    payload = {
        "iat": int(time.time()),
        "jti": str(uuid.uuid4()),
        "htu": url,
        "htm": methode.upper(),
        "uuid": str(uuid.uuid4()),
    }
    entree = (
        _b64url(json.dumps(header, separators=(",", ":")).encode())
        + "."
        + _b64url(json.dumps(payload, separators=(",", ":")).encode())
    )
    der = cle.sign(entree.encode(), ec.ECDSA(hashes.SHA256()))
    r, s = decode_dss_signature(der)
    return entree + "." + _b64url(r.to_bytes(32, "big") + s.to_bytes(32, "big"))


def corps_recherche(mot_cle: str, prix_min: int = 0, taille_page: int = 120) -> dict:
    return {
        "userId": "",
        "pageSize": taille_page,
        "pageToken": "",
        "searchSessionId": secrets.token_hex(16),
        "indexRouting": "INDEX_ROUTING_UNSPECIFIED",
        "thumbnailTypes": [],
        "searchCondition": {
            "keyword": mot_cle,
            "excludeKeyword": "",
            "sort": "SORT_CREATED_TIME",
            "order": "ORDER_DESC",
            "status": ["STATUS_ON_SALE"],
            "sizeId": [], "categoryId": [], "brandId": [], "sellerId": [],
            "priceMin": prix_min, "priceMax": 0,
            "itemConditionId": [], "shippingPayerId": [], "shippingFromArea": [],
            "shippingMethod": [], "colorId": [], "hasCoupon": False,
            "attributes": [], "itemTypes": [], "skuIds": [],
        },
        "defaultDatasets": ["DATASET_TYPE_MERCARI", "DATASET_TYPE_BEYOND"],
        "serviceFrom": "suruga",
        "withItemBrand": True,
        "withItemSize": False,
        "withItemPromotions": True,
        "withItemSizes": True,
        "withShopname": False,
    }


def appliquer_details(l: Listing, data: dict) -> None:
    """Complète une annonce avec la réponse de items/get : photos, vendeur, avis."""
    photos = [p for p in (data.get("photos") or []) if isinstance(p, str)]
    if photos:
        l.photos = photos[:3]
        l.image_url = photos[0]
    vendeur = data.get("seller") or {}
    if vendeur.get("id"):
        l.seller_id = str(vendeur["id"])
    notes = vendeur.get("ratings") or {}
    bons = int(notes.get("good") or 0)
    total = int(vendeur.get("num_ratings") or 0) or bons + int(notes.get("normal") or 0) + int(notes.get("bad") or 0)
    if total:
        l.vendeur_avis = total
        l.vendeur_positif_pct = round(100 * bons / total)
    etat = (data.get("item_condition") or {}).get("name")
    if etat and not l.condition_jp:
        l.condition_jp = etat


def convertir(items: list[dict], langue: str = "fr") -> list[Listing]:
    resultats = []
    for it in items:
        try:
            item_id = str(it["id"])
            prix = int(it.get("price") or 0)
        except (KeyError, ValueError):
            continue
        boutique = it.get("itemType") == "ITEM_TYPE_BEYOND" or not item_id.startswith("m")
        if boutique:
            url_orig = f"https://jp.mercari.com/shops/product/{item_id}"
            # Les articles Mercari Shops s'ajoutent sur ZenMarket via "Ajouter une URL"
            url_zen = f"https://zenmarket.jp/{langue}/"
        else:
            url_orig = f"https://jp.mercari.com/item/{item_id}"
            url_zen = f"https://zenmarket.jp/{langue}/mercariproduct.aspx?itemCode={item_id}"
        cond = MERCARI_CONDITIONS.get(str(it.get("itemConditionId", "")))
        thumbs = it.get("thumbnails") or []
        resultats.append(Listing(
            source="mercari_shops" if boutique else "mercari",
            item_id=item_id,
            title=it.get("name", ""),
            price_jpy=prix,
            url_original=url_orig,
            url_zenmarket=url_zen,
            image_url=thumbs[0] if thumbs else None,
            condition_jp=cond[0] if cond else None,
            seller_id=str(it["sellerId"]) if it.get("sellerId") else None,
        ))
    return resultats


class MercariSource:
    nom = "mercari"

    def __init__(self, session: requests.Session, langue: str = "fr"):
        self.session = session
        self.langue = langue
        self.cle = ec.generate_private_key(ec.SECP256R1())

    def rechercher(self, mot_cle: str, prix_min: int = 0) -> list[Listing]:
        headers = {
            "DPoP": creer_dpop(SEARCH_URL, "POST", self.cle),
            "X-Platform": "web",
            "Content-Type": "application/json; charset=utf-8",
            "Accept": "application/json",
            "Origin": "https://jp.mercari.com",
            "Referer": "https://jp.mercari.com/",
        }
        r = requete(self.session, "POST", SEARCH_URL, headers=headers,
                    data=json.dumps(corps_recherche(mot_cle, prix_min)))
        items = r.json().get("items", [])
        log.debug("Mercari « %s » : %d résultats", mot_cle, len(items))
        return convertir(items, self.langue)

    def details(self, l: Listing) -> None:
        """Ajoute 3 photos et les avis du vendeur (annonces Mercari de particuliers seulement)."""
        if l.source != "mercari":
            return
        headers = {
            "DPoP": creer_dpop(DETAIL_URL, "GET", self.cle),
            "X-Platform": "web",
            "Accept": "application/json",
            "Origin": "https://jp.mercari.com",
            "Referer": "https://jp.mercari.com/",
        }
        try:
            r = requete(self.session, "GET", DETAIL_URL, essais=2, headers=headers,
                        params={"id": l.item_id, "include_item_attributes": "true"})
            appliquer_details(l, r.json().get("data") or {})
        except Exception as e:  # noqa: BLE001 — l'alerte part quand même, avec moins d'infos
            log.warning("Détails Mercari indisponibles pour %s : %s", l.item_id, e)
