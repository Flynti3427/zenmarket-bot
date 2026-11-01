"""Alertes Discord par webhook (mode GitHub Actions : pas de bot connecté en permanence).

Même présentation que le bot Discord, avec les boutons-liens « Commander sur ZenMarket » et
« Annonce d'origine ». Le détail du prix total est affiché directement dans l'alerte.
"""
from __future__ import annotations

import logging
import time

import requests

from .discord_bot import construire_embeds, convertir_html, eur, fourchette, jpy

log = logging.getLogger(__name__)


def champ_estimation(a: dict) -> dict:
    c = a["cout"]
    lignes = [
        f"Article {eur(c['article'])} · ZenMarket {eur(c['zenmarket'])} · Port {eur(c['port'])}",
        f"Douane {eur(c['douane'])} · TVA {eur(c['tva'])} · Frais fixes {eur(c['fixes'])}",
        f"**= {eur(c['total'])} livré** (ton prix : {fourchette(a['achat_vise'])})",
    ]
    if a.get("prix_max_jpy"):
        lignes.append(f"Prix affiché max à payer : **{jpy(a['prix_max_jpy'])}**")
    return {"name": "🧮 Estimation prix total", "value": "\n".join(lignes)[:1024], "inline": False}


def payload_alerte(a: dict) -> dict:
    embeds = [e.to_dict() for e in construire_embeds(a)]
    embeds[0].setdefault("fields", []).insert(0, champ_estimation(a))
    boutons = [{"type": 2, "style": 5, "label": "Commander sur ZenMarket", "emoji": {"name": "🛒"},
                "url": a["url_zenmarket"]}]
    if a.get("url_original"):
        boutons.append({"type": 2, "style": 5, "label": "Annonce d'origine", "emoji": {"name": "🔎"},
                        "url": a["url_original"]})
    return {"embeds": embeds, "components": [{"type": 1, "components": boutons}],
            "allowed_mentions": {"parse": []}}


class DiscordWebhook:
    def __init__(self, url: str):
        self.url = url.strip()

    def _poster(self, payload: dict) -> bool:
        for _ in range(3):
            try:
                r = requests.post(self.url, params={"with_components": "true", "wait": "true"},
                                  json=payload, timeout=20)
            except requests.RequestException as e:
                log.error("Discord injoignable : %s", e)
                time.sleep(3)
                continue
            if r.status_code == 429:  # trop de messages d'un coup : Discord dit combien attendre
                time.sleep(float(r.json().get("retry_after", 2)) + 0.5)
                continue
            if r.ok:
                time.sleep(1)  # reste sous la limite de Discord (5 messages / 2 s)
                return True
            log.error("Discord a refusé le message (%s) : %s", r.status_code, r.text[:300])
            return False
        return False

    def envoyer_alerte(self, a: dict) -> bool:
        return self._poster(payload_alerte(a))

    def envoyer(self, texte: str, photo: str | None = None) -> bool:
        return self._poster({"content": convertir_html(texte)[:2000], "allowed_mentions": {"parse": []}})
