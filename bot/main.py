"""Boucle principale du bot ZenMarket (tourne 24h/24, 7j/7).

Usage :
    python -m bot.main               # mode normal (Telegram)
    python -m bot.main --dry-run     # affiche les alertes dans le terminal
    python -m bot.main --once        # un seul cycle puis arrêt (test)
"""
from __future__ import annotations

import argparse
import logging
import os
import random
import signal
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

from .alerte import construire
from .controle import controler
from .filters import correspond, estimer_etat
from .fx import TauxChange
from .http import nouvelle_session
from .models import Article, Listing, appliquer_seuil_unique
from .notifier import ConsoleNotifier, Telegram, eur, formater_alerte, jpy
from .pricing import cout_rendu_france, prix_max_jpy
from .sources.mercari import MercariSource
from .sources.yahoo import YahooSource
from .storage import Stockage

log = logging.getLogger("bot")
PARIS = ZoneInfo("Europe/Paris")
SEUIL_PANNE = 3  # cycles consécutifs sans résultat avant d'alerter

_arret = False


def _stop(*_):
    global _arret
    _arret = True
    log.info("Arrêt demandé, fin du cycle en cours…")


def charger_env(chemin: str = ".env"):
    """Charge un fichier .env simple (CLE=valeur) sans écraser les variables existantes."""
    if not Path(chemin).exists():
        return
    for ligne in Path(chemin).read_text(encoding="utf-8").splitlines():
        ligne = ligne.strip()
        if ligne and not ligne.startswith("#") and "=" in ligne:
            k, v = ligne.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def charger_config(chemin: str) -> dict:
    with open(chemin, encoding="utf-8") as f:
        return yaml.safe_load(f)


class Bot:
    def __init__(self, config: dict, notifier, stockage: Stockage):
        self.cfg = config
        self.r = config["reglages"]
        self.frais = config["frais"]
        self.profils = config["profils"]
        self.exclusions = config.get("exclusions_globales", [])
        self.articles = [Article.from_dict(a) for a in config["articles"]]
        if self.r.get("seuil_unique_tous_etats"):
            appliquer_seuil_unique(self.articles)
        self.notifier = notifier
        self.db = stockage
        session = nouvelle_session()
        langue = self.r.get("langue_zenmarket", "fr")
        dispo = {"mercari": MercariSource(session, langue), "yahoo": YahooSource(session, langue)}
        self.sources = [dispo[s] for s in self.r.get("sources", dispo)]
        self.fx = TauxChange(self.frais["taux_jpy_eur_secours"], session)
        # compteurs de panne gardés en base : ils survivent d'une exécution à l'autre (GitHub Actions)
        self.echecs = {s.nom: int(self.db.meta_get(f"echecs_{s.nom}") or 0) for s in self.sources}

    def _source(self, nom: str):
        nom = "mercari" if nom.startswith("mercari") else nom
        return next((s for s in self.sources if s.nom == nom), None)

    def _pause(self):
        a, b = self.r.get("pause_entre_requetes_s", [3, 7])
        time.sleep(random.uniform(a, b))

    # ------------------------------------------------------------------ cycle
    def evaluer(self, article: Article, l: Listing, taux: float):
        etat, raison = estimer_etat(l)
        est = cout_rendu_france(l.price_jpy, taux, self.frais, self.profils[article.profil])
        est.achat_vise = article.seuil_achat(etat)
        est.revente = article.revente_pour(etat)
        return etat, raison, est

    def cycle(self) -> int:
        taux = self.fx.jpy_eur()
        candidats, libres, a_initialiser = [], [], set()
        for source in self.sources:
            total_source = 0
            for article in self.articles:
                for mot_cle in article.recherches:
                    if _arret:
                        return 0
                    try:
                        annonces = source.rechercher(mot_cle, article.prix_min_jpy)
                    except Exception as e:  # noqa: BLE001
                        log.error("%s « %s » : %s", source.nom, mot_cle, e)
                        annonces = []
                    total_source += len(annonces)
                    for l in annonces:
                        if not correspond(article, l, self.exclusions):
                            continue
                        if self.db.est_bloque(l.key, l.seller_id and f"vendeur:{l.source}:{l.seller_id}"):
                            continue  # signalé « Arnaque » sur Discord
                        etat, raison, est = self.evaluer(article, l, taux)
                        deja = self.db.get(l.key)
                        prix_alerte = deja[1] if deja else None
                        baisse_min = 1 - self.r["alerte_si_baisse_prix_pct"] / 100
                        nouveau = prix_alerte is None or l.price_jpy <= prix_alerte * baisse_min
                        if article.sans_limite:
                            if self.db.meta_get(f"init:{article.nom}") is None:
                                # 1er passage : on mémorise les annonces déjà en ligne sans alerter,
                                # pour ne recevoir ensuite que les nouvelles
                                self.db.enregistrer(l.key, article.nom, l.title, l.price_jpy,
                                                    est.cout_total_eur, None, l.url_zenmarket, True)
                                a_initialiser.add(article.nom)
                            elif nouveau:
                                libres.append((0, article, l, etat, raison, est, prix_alerte is not None))
                            continue
                        if est.dans_les_prix and nouveau:
                            # tri : la plus grosse économie sous le prix visé en premier
                            ecart = est.achat_vise[1] - est.cout_total_eur
                            candidats.append((ecart, article, l, etat, raison, est, prix_alerte is not None))
                        else:
                            self.db.enregistrer(l.key, article.nom, l.title, l.price_jpy,
                                                est.cout_total_eur, None, l.url_zenmarket, False)
                    self._pause()
            self._surveiller_panne(source.nom, total_source)

        for nom in a_initialiser:
            self.db.meta_set(f"init:{nom}", "1")
        candidats.sort(key=lambda c: c[0], reverse=True)
        vus = set()
        envoyees = self._envoyer(candidats, self.r["max_alertes_par_cycle"], taux, vus)
        envoyees += self._envoyer(libres, self.r.get("max_alertes_sans_limite_par_cycle", 20), taux, vus)
        log.info("Cycle terminé : %d alerte(s) envoyée(s), %d candidat(s)", envoyees, len(vus))
        return envoyees

    def _envoyer(self, candidats: list, maximum: int, taux: float, vus: set) -> int:
        envoyees = 0
        for _ecart, article, l, etat, raison, est, baisse in candidats:
            if l.key in vus:
                continue
            vus.add(l.key)
            if envoyees >= maximum:
                # Pas envoyée : on ne la marque pas comme alertée, elle repassera au prochain cycle
                self.db.enregistrer(l.key, article.nom, l.title, l.price_jpy,
                                    est.cout_total_eur, None, l.url_zenmarket, False)
                continue
            pmax = (prix_max_jpy(est.achat_vise[1], taux, self.frais, self.profils[article.profil])
                    if est.achat_vise else None)
            source = self._source(l.source)
            if source is not None and hasattr(source, "details"):
                source.details(l)  # photos + avis vendeur
                if self.db.est_bloque(l.seller_id and f"vendeur:{l.source}:{l.seller_id}"):
                    continue
            habituel = self.db.prix_habituel_jpy(article.nom)
            alerte = construire(article, l, est, etat, raison, pmax, baisse, habituel,
                                controler(l, habituel), taux)
            self.db.sauver_alerte(l.key, alerte)
            if hasattr(self.notifier, "envoyer_alerte"):
                ok = self.notifier.envoyer_alerte(alerte)
            else:
                ok = self.notifier.envoyer(formater_alerte(article, l, est, etat, raison, pmax, baisse), l.image_url)
            self.db.enregistrer(l.key, article.nom, l.title, l.price_jpy,
                                est.cout_total_eur, None, l.url_zenmarket, ok)
            envoyees += ok
        return envoyees

    # ------------------------------------------------------- rappels d'enchères
    def rappels_encheres(self) -> int:
        """Rappels dans le salon de l'alerte quand une enchère alertée se termine bientôt
        (par défaut 3 h puis 30 min avant la fin). Un seul message par seuil et par enchère."""
        seuils = self.r.get("rappel_enchere_heures", [3, 0.5])
        if not isinstance(seuils, list):
            seuils = [seuils]
        seuils = sorted((float(h) for h in seuils if h), reverse=True)
        if not seuils or not hasattr(self.notifier, "envoyer_rappel"):
            return 0
        from .discord_v2 import payload_rappel
        taux = self.fx.jpy_eur()
        maintenant = time.time()
        envoyes = 0
        for a in self.db.encheres_qui_finissent(maintenant + seuils[0] * 3600):
            reste = a["fin_ts"] - maintenant
            # seuils atteints, encore à envoyer, et pas déjà « couverts » par l'alerte elle-même
            a_faire = [h for h in seuils
                       if reste <= h * 3600
                       and a["fin_ts"] - a["horodatage"] > h * 3600
                       and not self.db.meta_get(f"rappel:{a['cle']}:{h:g}")]
            if not a_faire:
                continue
            for h in a_faire:  # on n'envoie que le plus urgent, les autres sont marqués comme faits
                self.db.meta_set(f"rappel:{a['cle']}:{h:g}", "couvert")
            h = min(a_faire)
            article = next((x for x in self.articles if x.nom == a["article"]), None)
            if self.db.est_bloque(a["cle"]) or article is None:
                continue
            vu = self.db.dernier_prix(a["cle"])
            prix, vu_ts, offres = (vu[0], vu[1], None) if vu else (a["prix_jpy"], None, None)
            source = self._source(a["source"])
            if source is not None and hasattr(source, "etat_enchere"):
                actuel, offres = source.etat_enchere(a["cle"].split(":", 1)[1])
                if actuel:
                    prix, vu_ts = actuel, time.time()
            est = cout_rendu_france(prix, taux, self.frais, self.profils[article.profil])
            vise = a.get("achat_vise")
            pmax = prix_max_jpy(vise[1], taux, self.frais, self.profils[article.profil]) if vise else None
            payload = payload_rappel(a, prix, est.prix_article_eur, est.cout_total_eur, pmax, vu_ts, offres,
                                     dernier=(h == seuils[-1] and len(seuils) > 1))
            if self.notifier.envoyer_rappel(a, payload):
                self.db.meta_set(f"rappel:{a['cle']}:{h:g}", "1")
                envoyes += 1
            else:
                self.db.meta_set(f"rappel:{a['cle']}:{h:g}", "")  # échec : on réessaiera au tour suivant
        if envoyes:
            log.info("%d rappel(s) d'enchère envoyé(s)", envoyes)
        return envoyes

    # ------------------------------------------------------------ surveillance
    def _surveiller_panne(self, source: str, total: int):
        if total > 0:
            if self.echecs[source] >= SEUIL_PANNE:
                self.notifier.envoyer(f"✅ {source} fonctionne de nouveau.")
            self.echecs[source] = 0
            self.db.meta_set(f"echecs_{source}", "0")
            return
        self.echecs[source] += 1
        self.db.meta_set(f"echecs_{source}", str(self.echecs[source]))
        if self.echecs[source] == SEUIL_PANNE:
            self.notifier.envoyer(
                f"⚠️ {source} : aucun résultat depuis {SEUIL_PANNE} cycles.\n"
                "Causes possibles : site bloqué depuis ce serveur (Yahoo bloque l'Europe), "
                "ou mise en page changée. Regarde les logs.")

    def recap_quotidien(self):
        maintenant = datetime.now(PARIS)
        cle = maintenant.strftime("%Y-%m-%d")
        if maintenant.hour < self.r.get("recap_quotidien_heure", 9) or self.db.meta_get("recap") == cle:
            return
        lignes = ["☀️ <b>Récap quotidien</b> — les moins chers des dernières 24 h (coût rendu France)"]
        for a in self.articles:
            top = self.db.moins_chers(a.nom, limite=3)
            if not top:
                continue
            tag = "" if a.a_des_prix else " <i>(pas de prix d'achat dans le tableau)</i>"
            lignes.append(f"\n<b>{a.nom}</b>{tag}")
            for titre, prix, cout, url in top:
                lignes.append(f'• {jpy(prix)} → {eur(cout)} — <a href="{url}">{titre[:45]}</a>')
        self.notifier.envoyer("\n".join(lignes)[:4096])
        self.db.meta_set("recap", cle)

    def annoncer_demarrage(self, une_fois: bool = False):
        # En mode --once (GitHub Actions), le message de démarrage n'est envoyé qu'au tout premier tour.
        if not une_fois or self.db.meta_get("demarrage_annonce") is None:
            self.notifier.envoyer(
                f"🤖 Bot ZenMarket démarré — {len(self.articles)} articles surveillés sur "
                f"{', '.join(s.nom for s in self.sources)}, toutes les {self.r['intervalle_minutes']} min.")
            self.db.meta_set("demarrage_annonce", "1")

    def tour(self):
        """Un tour complet : recherche, alertes, récap du matin. Ne lève jamais d'exception."""
        try:
            self.cycle()
            self.rappels_encheres()
            self.recap_quotidien()
        except Exception:  # noqa: BLE001 — le bot ne doit jamais mourir
            log.exception("Erreur inattendue pendant le cycle")
        battement = Path(os.environ.get("HEARTBEAT_FILE", "data/heartbeat"))
        battement.parent.mkdir(parents=True, exist_ok=True)
        battement.write_text(str(int(time.time())))

    def tourner(self, une_fois: bool = False):
        self.annoncer_demarrage(une_fois)
        while not _arret:
            debut = time.time()
            self.tour()
            if une_fois:
                break
            attente = max(30, self.r["intervalle_minutes"] * 60 - (time.time() - debut))
            attente += random.uniform(0, 60)
            log.info("Prochain cycle dans %.0f s", attente)
            while attente > 0 and not _arret:
                time.sleep(min(5, attente))
                attente -= 5


def lancer_discord(config: dict, stockage: Stockage, token: str, salon_id: str):
    from .discord_bot import ClientZen, NotifDiscord

    client = ClientZen(int(salon_id), stockage, config["reglages"]["intervalle_minutes"])
    bot = Bot(config, NotifDiscord(client), stockage)
    client.bot = bot

    async def demarrage():
        await client.wait_until_ready()
        await client.loop.run_in_executor(None, bot.annoncer_demarrage)

    async def principal():
        async with client:
            client.loop.create_task(demarrage())
            await client.start(token)

    import asyncio
    asyncio.run(principal())


def main():
    p = argparse.ArgumentParser(description="Bot de surveillance ZenMarket")
    p.add_argument("--config", default=os.environ.get("BOT_CONFIG", "config.yaml"))
    p.add_argument("--db", default=os.environ.get("BOT_DB", "data/bot.sqlite"))
    p.add_argument("--dry-run", action="store_true", help="affiche les alertes au lieu de les envoyer")
    p.add_argument("--once", action="store_true", help="un seul cycle puis arrêt")
    p.add_argument("--debug", action="store_true")
    args = p.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)

    charger_env()
    Path(args.db).parent.mkdir(parents=True, exist_ok=True)
    discord_token, salon = os.environ.get("DISCORD_BOT_TOKEN"), os.environ.get("DISCORD_CHANNEL_ID")
    serveur = os.environ.get("DISCORD_GUILD_ID")
    config = charger_config(args.config)
    economie = config["reglages"].get("meilleure_affaire_economie_pct", 25)
    if discord_token and serveur and not args.dry_run:
        # GitHub Actions : le bot crée les salons et poste par marque (API REST, un tour puis arrêt)
        from .discord_serveur import DiscordServeur
        notif = DiscordServeur(discord_token, serveur, [a["nom"] for a in config["articles"]], economie)
        notif.preparer()
        Bot(config, notif, Stockage(args.db)).tourner(une_fois=args.once)
        return
    if discord_token and not args.dry_run:
        if not salon:
            raise SystemExit("DISCORD_CHANNEL_ID doit être défini (ID du salon où envoyer les alertes)")
        lancer_discord(config, Stockage(args.db), discord_token, salon)
        return
    webhook = os.environ.get("DISCORD_WEBHOOK_URL")
    webhooks = os.environ.get("DISCORD_WEBHOOKS")  # JSON {salon: url}, un webhook par salon
    if args.dry_run:
        notifier = ConsoleNotifier()
    elif webhooks:
        import json

        from .discord_webhook import DiscordWebhooks
        notifier = DiscordWebhooks(json.loads(webhooks), economie,
                                   fils=config["reglages"].get("fils_discord"))
    elif webhook:
        from .discord_webhook import DiscordWebhook
        notifier = DiscordWebhook(webhook, economie)
    else:
        token, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
        if not token or not chat:
            raise SystemExit("Définis DISCORD_WEBHOOK_URL, ou DISCORD_BOT_TOKEN + DISCORD_CHANNEL_ID, "
                             "ou TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID")
        notifier = Telegram(token, chat)

    Bot(config, notifier, Stockage(args.db)).tourner(une_fois=args.once)


if __name__ == "__main__":
    main()
