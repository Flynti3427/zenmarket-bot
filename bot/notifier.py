"""Envoi des alertes sur Telegram."""
from __future__ import annotations

import html
import logging

import requests

from .filters import LIBELLES_ETAT
from .models import Article, Listing
from .pricing import Estimation

log = logging.getLogger(__name__)

NOMS_SOURCES = {"mercari": "Mercari", "mercari_shops": "Mercari Shops", "yahoo": "Yahoo Enchères"}


def eur(x: float | None) -> str:
    return "?" if x is None else f"{x:,.0f} €".replace(",", " ")


def fourchette(f) -> str:
    if not f:
        return "?"
    return eur(f[0]) if f[0] == f[1] else f"{f[0]:.0f}-{eur(f[1])}"


def signe(x: float) -> str:
    return f"+{eur(x)}" if x >= 0 else f"−{eur(-x)}"


def jpy(x: int | None) -> str:
    return "?" if x is None else f"{x:,} ¥".replace(",", " ")


def formater_alerte(article: Article, l: Listing, est: Estimation, etat: str, raison: str,
                    prix_max_jpy: int | None, baisse: bool = False) -> str:
    e = html.escape
    lignes = [
        f"{'📉 BAISSE DE PRIX' if baisse else '🔥 BONNE AFFAIRE'} — <b>{e(article.nom)}</b>",
        f"<i>{e(l.title[:120])}</i>",
        "",
        f"🏷 {NOMS_SOURCES.get(l.source, l.source)} : <b>{jpy(l.price_jpy)}</b> (≈ {eur(est.prix_article_eur)})",
    ]
    if l.is_auction:
        lignes.append("⏳ Enchère : prix actuel, il peut monter" + (f" — reste {e(l.time_left)}" if l.time_left else ""))
        if l.buy_now_jpy:
            lignes.append(f"⚡ Achat immédiat : {jpy(l.buy_now_jpy)}")
    statut = "🔥 SOUS ta fourchette" if est.sous_la_fourchette else "✅ dans ta fourchette"
    lignes += [
        f"📦 Coût rendu France : <b>{eur(est.cout_total_eur)}</b>",
        f"   (port {eur(est.port_eur)} · TVA {eur(est.tva_eur)} · douane {eur(est.droits_eur)} · ZenMarket {eur(est.frais_zenmarket_eur)})",
        f"🔎 État estimé : {LIBELLES_ETAT[etat]} ({e(raison)})",
        f"🎯 Prix d'achat du tableau : {fourchette(est.achat_vise)} → {statut}",
    ]
    if est.revente:
        bas, haut = est.profit
        lignes.append(f"💶 Revente du tableau : {fourchette(est.revente)} → marge estimée {signe(bas)} à {signe(haut)}"
                      if bas != haut else f"💶 Revente du tableau : {fourchette(est.revente)} → marge estimée {signe(bas)}")
    if prix_max_jpy:
        lignes.append(f"🧮 Prix affiché max à payer : {jpy(prix_max_jpy)}")
    lignes += [
        "",
        f'<a href="{e(l.url_zenmarket)}">👉 Ouvrir sur ZenMarket</a> · <a href="{e(l.url_original)}">annonce d\'origine</a>',
    ]
    if l.source == "mercari_shops":
        lignes.append("ℹ️ Article Mercari Shops : colle le lien d'origine dans ZenMarket (« Ajouter une URL »).")
    lignes.append("⚠️ Vérifie l'authenticité (photos, code date) avant d'acheter.")
    return "\n".join(lignes)


class Telegram:
    def __init__(self, token: str, chat_id: str):
        self.base = f"https://api.telegram.org/bot{token}"
        self.chat_id = chat_id

    def envoyer(self, texte: str, photo: str | None = None) -> bool:
        try:
            if photo and len(texte) <= 1024:
                r = requests.post(f"{self.base}/sendPhoto", timeout=20, data={
                    "chat_id": self.chat_id, "photo": photo, "caption": texte, "parse_mode": "HTML"})
                if r.ok:
                    return True
                log.debug("sendPhoto refusé (%s), envoi en texte", r.text[:200])
            r = requests.post(f"{self.base}/sendMessage", timeout=20, data={
                "chat_id": self.chat_id, "text": texte[:4096], "parse_mode": "HTML",
                "disable_web_page_preview": "false"})
            if not r.ok:
                log.error("Telegram a refusé le message : %s", r.text[:300])
            return r.ok
        except requests.RequestException as e:
            log.error("Telegram injoignable : %s", e)
            return False


class ConsoleNotifier:
    """Utilisé en mode test (--dry-run) : affiche les alertes au lieu de les envoyer."""

    def envoyer(self, texte: str, photo: str | None = None) -> bool:
        print("\n" + "=" * 60 + "\n" + texte + "\n" + "=" * 60)
        return True
