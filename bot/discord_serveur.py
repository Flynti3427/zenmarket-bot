"""Bot Discord utilisé depuis GitHub Actions (API REST, pas de connexion permanente).

À chaque tour : crée la catégorie « ZenMarket » et les salons manquants (un par marque
+ « meilleures-affaires »), puis poste chaque alerte dans le salon de sa marque.
Les meilleures affaires sont aussi copiées dans le salon « meilleures-affaires ».
"""
from __future__ import annotations

import logging
import time

import requests

from .discord_bot import convertir_html
from .discord_v2 import est_meilleure_affaire, marque_de, payload_v2

log = logging.getLogger(__name__)

API = "https://discord.com/api/v10"
CATEGORIE = "ZenMarket"
SALON_MEILLEURES = "🔥┃meilleures-affaires"


def nom_salon(slug: str) -> str:
    return f"👜┃{slug}"


class DiscordServeur:
    def __init__(self, token: str, serveur_id: str, articles: list[str], economie_min_pct: float = 25):
        self.serveur_id = serveur_id.strip()
        self.economie_min_pct = economie_min_pct
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bot {token.strip()}",
            "User-Agent": "DiscordBot (https://github.com/Flynti3427/zenmarket-bot, 1.0)",
        })
        self.salons_voulus = [SALON_MEILLEURES] + sorted({nom_salon(marque_de(a)[1]) for a in articles})
        self.salons: dict[str, str] = {}

    # ------------------------------------------------------------------ API
    def _api(self, methode: str, chemin: str, **kwargs):
        for _ in range(4):
            try:
                r = self.session.request(methode, API + chemin, timeout=20, **kwargs)
            except requests.RequestException as e:
                log.error("Discord injoignable : %s", e)
                time.sleep(3)
                continue
            if r.status_code == 429:  # limite de Discord : il indique combien de temps attendre
                time.sleep(float(r.json().get("retry_after", 2)) + 0.5)
                continue
            if not r.ok:
                log.error("Discord a refusé %s %s (%s) : %s", methode, chemin, r.status_code, r.text[:300])
                if r.status_code in (401, 403):
                    raise PermissionError(
                        "Le bot Discord n'a pas les droits : vérifie le token et qu'il a la permission "
                        "« Gérer les salons » sur ton serveur.")
                return None
            return r.json() if r.content else {}
        return None

    def preparer(self):
        """Crée la catégorie et les salons qui manquent (rien n'est modifié ni supprimé)."""
        existants = self._api("GET", f"/guilds/{self.serveur_id}/channels") or []
        categorie = next((c for c in existants if c.get("type") == 4 and c.get("name") == CATEGORIE), None)
        if categorie is None:
            categorie = self._api("POST", f"/guilds/{self.serveur_id}/channels",
                                  json={"name": CATEGORIE, "type": 4})
            log.info("Catégorie « %s » créée", CATEGORIE)
        par_nom = {c["name"]: c["id"] for c in existants if c.get("type") == 0}
        for nom in self.salons_voulus:
            if nom not in par_nom:
                cree = self._api("POST", f"/guilds/{self.serveur_id}/channels",
                                 json={"name": nom, "type": 0, "parent_id": categorie["id"] if categorie else None})
                if cree:
                    par_nom[nom] = cree["id"]
                    log.info("Salon « %s » créé", nom)
        self.salons = {n: par_nom[n] for n in self.salons_voulus if n in par_nom}

    def _poster(self, salon: str, payload: dict) -> bool:
        if not self.salons:
            self.preparer()
        salon_id = self.salons.get(salon) or self.salons.get(SALON_MEILLEURES)
        if not salon_id:
            log.error("Salon « %s » introuvable", salon)
            return False
        ok = self._api("POST", f"/channels/{salon_id}/messages", json=payload) is not None
        time.sleep(1)  # reste sous la limite de Discord
        return ok

    # ---------------------------------------------------- interface du Bot
    def envoyer_alerte(self, a: dict) -> bool:
        meilleure = est_meilleure_affaire(a, self.economie_min_pct)
        payload = payload_v2(a, meilleure)
        ok = self._poster(nom_salon(a.get("salon") or marque_de(a["article"])[1]), payload)
        if meilleure:
            self._poster(SALON_MEILLEURES, payload)
        return ok

    def envoyer(self, texte: str, photo: str | None = None) -> bool:
        return self._poster(SALON_MEILLEURES, {"content": convertir_html(texte)[:2000],
                                               "allowed_mentions": {"parse": []}})
