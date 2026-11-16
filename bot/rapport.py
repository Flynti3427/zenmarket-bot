"""Rapport du jour et bilan du soir.

Vers 19 h (heure de Paris), le bot écrit le rapport de la journée (alertes envoyées, annonces vues,
prix observés) sur la branche « rapports » du dépôt GitHub. La relecture quotidienne le lit, corrige
les filtres si besoin et écrit un bilan (bilans/AAAA-MM-JJ.md) que le bot publie ensuite sur Discord.
"""
from __future__ import annotations

import base64
import json
import logging
import os
import statistics
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import requests

log = logging.getLogger(__name__)
PARIS = ZoneInfo("Europe/Paris")
BRANCHE = "rapports"
API = "https://api.github.com"


def construire_rapport(db, articles: list, jour: str) -> dict:
    maintenant = time.time()
    alertes = []
    for a in db.alertes_depuis(maintenant - 86400):
        alertes.append({
            "cle": a["cle"], "article": a["article"], "titre": a["titre"], "source": a["source"],
            "prix_jpy": a["prix_jpy"], "cout_total_eur": a["cout"]["total"], "etat": a["etat"],
            "etat_raison": a.get("etat_raison"), "signaux": a.get("signaux", []),
            "enchere": a.get("enchere"), "sans_limite": a.get("sans_limite", False),
            "url_original": a.get("url_original"),
        })
    stats = {}
    for art in articles:
        vues_24h = db.compter_vues(art.nom, maintenant - 86400)
        couts = db.couts(art.nom, maintenant - 30 * 86400)
        seuil = max((f[1] for f in art.achat.values() if f), default=None)
        if art.achat_tous_etats:
            seuil = art.achat_tous_etats
        stats[art.nom] = {
            "annonces_vues_24h": vues_24h,
            "annonces_vues_30j": len(couts),
            "cout_livre_median_30j": round(statistics.median(couts)) if couts else None,
            "cout_livre_min_30j": round(min(couts)) if couts else None,
            "ton_prix_max": seuil,
            "alertes_24h": sum(1 for a in alertes if a["article"] == art.nom),
        }
    return {"date": jour, "genere_le": datetime.now(PARIS).isoformat(timespec="minutes"),
            "nb_alertes": len(alertes), "alertes": alertes, "stats": stats}


class Github:
    """Lecture / écriture de fichiers sur la branche « rapports » (API contents de GitHub)."""

    def __init__(self, depot: str, jeton: str):
        self.depot = depot
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {jeton}",
                                     "Accept": "application/vnd.github+json"})

    def lire(self, chemin: str) -> str | None:
        r = self.session.get(f"{API}/repos/{self.depot}/contents/{chemin}", params={"ref": BRANCHE}, timeout=20)
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return base64.b64decode(r.json()["content"]).decode("utf-8")

    def ecrire(self, chemin: str, contenu: str, message: str) -> None:
        url = f"{API}/repos/{self.depot}/contents/{chemin}"
        existant = self.session.get(url, params={"ref": BRANCHE}, timeout=20)
        data = {"message": message, "branch": BRANCHE,
                "content": base64.b64encode(contenu.encode("utf-8")).decode()}
        if existant.status_code == 200:
            data["sha"] = existant.json()["sha"]
        r = self.session.put(url, json=data, timeout=30)
        r.raise_for_status()


def depuis_env(depot: str | None) -> Github | None:
    jeton = os.environ.get("GITHUB_TOKEN")
    depot = os.environ.get("GITHUB_REPOSITORY") or depot
    return Github(depot, jeton) if jeton and depot else None


def tache_du_soir(bot, heure_rapport: int | None = None) -> None:
    """Appelée à chaque tour : exporte le rapport (une fois par jour, à partir de 19 h),
    puis publie le bilan du jour dès que la relecture l'a écrit."""
    if heure_rapport is None:
        valeur = os.environ.get("RAPPORT_HEURE") or "19"
        heure_rapport = 0 if valeur == "maintenant" else int(valeur)
    gh = depuis_env(bot.r.get("depot_github"))
    if gh is None:
        return
    maintenant = datetime.now(PARIS)
    jour = maintenant.strftime("%Y-%m-%d")
    if maintenant.hour < heure_rapport:
        return
    if bot.db.meta_get("rapport_exporte") != jour:
        rapport = construire_rapport(bot.db, bot.articles, jour)
        gh.ecrire(f"rapports/{jour}.json", json.dumps(rapport, ensure_ascii=False, indent=1),
                  f"Rapport du {jour} ({rapport['nb_alertes']} alertes)")
        bot.db.meta_set("rapport_exporte", jour)
        log.info("Rapport du %s exporté (%d alertes)", jour, rapport["nb_alertes"])
    if bot.db.meta_get("bilan_publie") != jour:
        bilan = gh.lire(f"bilans/{jour}.md")
        if bilan:
            for morceau in decouper(bilan, 1900):
                bot.notifier.envoyer(morceau)
            bot.db.meta_set("bilan_publie", jour)
            log.info("Bilan du %s publié sur Discord", jour)


def decouper(texte: str, taille: int) -> list[str]:
    """Coupe un texte en messages Discord (2000 caractères max), de préférence entre les lignes."""
    morceaux, courant = [], ""
    for ligne in texte.splitlines(keepends=True):
        while len(ligne) > taille:
            morceaux.append(courant + ligne[: taille - len(courant)])
            ligne, courant = ligne[taille - len(courant):], ""
        if len(courant) + len(ligne) > taille:
            morceaux.append(courant)
            courant = ""
        courant += ligne
    if courant.strip():
        morceaux.append(courant)
    return morceaux
