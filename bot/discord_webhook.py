"""Alertes Discord par webhook (mode GitHub Actions : pas de bot connecté en permanence).

Même présentation que le bot Discord, avec les boutons-liens « Commander sur ZenMarket » et
« Annonce d'origine ». Le détail du prix total est affiché directement dans l'alerte.
"""
from __future__ import annotations

import logging
import time

import requests

from .discord_bot import construire_embeds, convertir_html, eur, fourchette, jpy
from .discord_v2 import est_meilleure_affaire, marque_de, payload_v2

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
    boutons = [{"type": 2, "style": 5, "label": "Commander sur ZenMarket", "emoji": {"name": "🛒"},
                "url": a["url_zenmarket"]}]
    if a.get("url_original"):
        boutons.append({"type": 2, "style": 5, "label": "Annonce d'origine", "emoji": {"name": "🔎"},
                        "url": a["url_original"]})
    return {"embeds": embeds, "components": [{"type": 1, "components": boutons}],
            "allowed_mentions": {"parse": []}}


class DiscordWebhook:
    def __init__(self, url: str, economie_min_pct: float = 25):
        self.url = url.strip()
        self.economie_min_pct = economie_min_pct

    def _poster(self, payload: dict) -> bool:
        for _ in range(3):
            payload = {"username": "ZenMarket Alertes", **payload}
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
        return self._poster(payload_v2(a, est_meilleure_affaire(a, self.economie_min_pct)))

    def envoyer(self, texte: str, photo: str | None = None) -> bool:
        return self._poster({"content": convertir_html(texte)[:2000], "allowed_mentions": {"parse": []}})


class DiscordWebhooks:
    """Un webhook par salon : {"louis-vuitton": url, ..., "meilleures-affaires": url}.

    Chaque alerte va dans le salon de sa marque ; les meilleures affaires sont aussi copiées
    dans « meilleures-affaires », qui reçoit aussi le démarrage, le récap et les pannes.
    """

    def __init__(self, salons: dict[str, str], economie_min_pct: float = 25, fils: dict | None = None):
        salons = dict(salons)
        # fils Discord déclarés dans config.yaml (« wallet/lots »: ID) : même webhook que le salon + thread_id
        for cle, fil_id in (fils or {}).items():
            base = salons.get(cle.split("/")[0])
            if base and fil_id and cle not in salons:
                salons[cle] = f"{base}{'&' if '?' in base else '?'}thread_id={fil_id}"
        self.salons = {k: DiscordWebhook(v, economie_min_pct) for k, v in salons.items() if v}
        self.economie_min_pct = economie_min_pct
        self.secours = self.salons.get("meilleures-affaires") or next(iter(self.salons.values()))

    def _webhook(self, salon: str) -> DiscordWebhook:
        return self.salons.get(salon) or self.secours

    def envoyer_alerte(self, a: dict) -> bool:
        meilleure = est_meilleure_affaire(a, self.economie_min_pct)
        payload = payload_v2(a, meilleure)
        salon = a.get("salon") or marque_de(a["article"])[1]
        ok = False
        if a.get("fil") and f"{salon}/{a['fil']}" in self.salons:
            # fil (ex. keepall dans louis-vuitton) ; si le fil est archivé ou supprimé, repli sur le salon
            ok = self.salons[f"{salon}/{a['fil']}"]._poster(payload)
        if not ok:
            ok = self._webhook(salon)._poster(payload)
        if meilleure and "meilleures-affaires" in self.salons:
            self.salons["meilleures-affaires"]._poster(payload)
        return ok

    def envoyer(self, texte: str, photo: str | None = None) -> bool:
        return self.secours.envoyer(texte)

