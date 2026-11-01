import asyncio
import re

import yaml

from bot.controle import controler
from bot.discord_bot import (BoutonAlerte, ClientZen, construire_embeds, construire_estimation,
                             construire_vue, convertir_html)
from bot.main import Bot
from bot.models import Listing
from bot.sources.mercari import appliquer_details
from bot.storage import Stockage

TAUX = 0.0057


class FausseSource:
    nom = "mercari"

    def __init__(self, annonces, details=None):
        self.annonces, self._details = annonces, details or {}

    def rechercher(self, mot_cle, prix_min=0):
        return self.annonces if "スピーディ" in mot_cle else []

    def details(self, l):
        appliquer_details(l, self._details)


class NotifAlertes:
    def __init__(self):
        self.alertes, self.textes = [], []

    def envoyer_alerte(self, a):
        self.alertes.append(a)
        return True

    def envoyer(self, texte, photo=None):
        self.textes.append(texte)
        return True


DETAILS = {
    "photos": ["https://p/1.jpg", "https://p/2.jpg", "https://p/3.jpg", "https://p/4.jpg"],
    "seller": {"id": 777, "num_ratings": 942, "ratings": {"good": 942, "normal": 0, "bad": 0}},
}


def _bot(tmp_path, annonces, details=None):
    cfg = yaml.safe_load(open("config.yaml", encoding="utf-8"))
    cfg["reglages"]["pause_entre_requetes_s"] = [0, 0]
    notif = NotifAlertes()
    db = Stockage(tmp_path / "d.sqlite")
    bot = Bot(cfg, notif, db)
    bot.sources = [FausseSource(annonces, details)]
    bot.echecs = {"mercari": 0}
    bot.fx.jpy_eur = lambda: TAUX
    return bot, notif, db


def speedy(item_id="m42", prix=25000, titre="ルイヴィトン スピーディ30 美品", vendeur="777"):
    return Listing("mercari", item_id, titre, prix, "https://jp.mercari.com/item/" + item_id,
                   f"https://zenmarket.jp/fr/mercariproduct.aspx?itemCode={item_id}", seller_id=vendeur)


# ------------------------------------------------------------ alerte complète
def test_alerte_discord_contient_tout(tmp_path):
    bot, notif, db = _bot(tmp_path, [speedy()], DETAILS)
    assert bot.cycle() == 1
    a = notif.alertes[0]
    assert a["photos"] == DETAILS["photos"][:3]
    assert (a["vendeur_avis"], a["vendeur_positif_pct"]) == (942, 100)
    assert a["url_zenmarket"].startswith("https://zenmarket.jp/fr/")
    assert db.alerte("mercari:m42")["prix_jpy"] == 25000      # gardée pour les boutons

    embeds = construire_embeds(a)
    assert len(embeds) == 3                                     # galerie 3 photos
    assert all(e.url == a["url_zenmarket"] for e in embeds)    # même url = galerie Discord
    texte = embeds[0].description
    assert "25 000 ¥" in texte and "942 avis · 100 % positifs" in texte
    assert "Prix total livré en France" in texte
    assert embeds[0].fields[0].name.startswith("✅ Contrôle anti-contrefaçon passé")


def test_boutons_de_l_alerte(tmp_path):
    bot, notif, _ = _bot(tmp_path, [speedy()], DETAILS)
    bot.cycle()
    vue = construire_vue(notif.alertes[0])
    lien = [i for i in vue.children if getattr(i, "url", None)][0]
    assert lien.label == "Commander sur ZenMarket" and "zenmarket.jp" in lien.url
    ids = {i.custom_id for i in vue.children if getattr(i, "custom_id", None)}
    assert ids == {"zen:est:mercari:m42", "zen:fav:mercari:m42", "zen:arn:mercari:m42"}
    for cid in ids:  # les boutons sont retrouvés après un redémarrage du bot
        assert re.fullmatch(BoutonAlerte.__discord_ui_compiled_template__, cid)


def test_estimation_prix_total(tmp_path):
    bot, notif, _ = _bot(tmp_path, [speedy()], DETAILS)
    bot.cycle()
    e = construire_estimation(notif.alertes[0])
    assert "Total livré en France" in e.description and "TVA 20 %" in e.description
    assert "Prix affiché max à payer" in e.description


# ------------------------------------------------------- favoris et arnaques
class FausseReponse:
    def __init__(self):
        self.envoye, self.edite = [], []

    async def send_message(self, *a, **k):
        self.envoye.append((a, k))

    async def edit_message(self, **k):
        self.edite.append(k)


class FausseInteraction:
    def __init__(self):
        self.response = FausseReponse()


def test_boutons_favori_et_arnaque(tmp_path):
    bot, notif, db = _bot(tmp_path, [speedy()], DETAILS)
    bot.cycle()
    client = ClientZen(123, db, 15)

    i = FausseInteraction()
    asyncio.run(client.gerer_bouton(i, "fav", "mercari:m42"))
    assert "Ajouté" in i.response.envoye[0][0][0]
    assert db.favoris()[0]["cle"] == "mercari:m42"

    i = FausseInteraction()
    asyncio.run(client.gerer_bouton(i, "est", "mercari:m42"))
    assert i.response.envoye[0][1]["ephemeral"] is True

    i = FausseInteraction()
    asyncio.run(client.gerer_bouton(i, "arn", "mercari:m42"))
    assert "arnaque" in i.response.edite[0]["content"]

    # Une autre annonce du même vendeur n'est plus signalée
    bot.sources = [FausseSource([speedy("m99", 24000)], DETAILS)]
    assert bot.cycle() == 0


def test_alerte_inconnue(tmp_path):
    db = Stockage(tmp_path / "x.sqlite")
    i = FausseInteraction()
    asyncio.run(ClientZen(1, db, 15).gerer_bouton(i, "est", "mercari:inconnu"))
    assert "trop ancienne" in i.response.envoye[0][0][0]


# ------------------------------------------------------ anti-contrefaçon
def test_controle_suspects():
    l = Listing("mercari", "m1", "ヴィトン風 スピーディ タイプ", 2000, "o", "z", vendeur_avis=2)
    signaux = controler(l, prix_habituel_jpy=40000)
    assert len(signaux) == 4  # « style », « タイプ », prix trop bas, vendeur récent
    assert controler(speedy(), 30000) == []


def test_prix_habituel(tmp_path):
    db = Stockage(tmp_path / "h.sqlite")
    for i, prix in enumerate([30000, 35000, 40000, 45000, 50000, 55000, 60000, 65000]):
        db.enregistrer(f"k{i}", "LV Speedy", "t", prix, 0, None, "u", False)
    assert db.prix_habituel_jpy("LV Speedy") == 47500
    assert db.prix_habituel_jpy("LV Noé") is None  # pas assez de données


def test_conversion_texte():
    assert convertir_html('<b>Récap</b> <a href="https://x">lien</a>') == "**Récap** [lien](https://x)"


# ------------------------------------------------------- webhook (GitHub Actions)
def test_webhook_payload(tmp_path, monkeypatch):
    from bot import discord_webhook
    envois = []

    class R:
        status_code, ok, text = 200, True, ""

    monkeypatch.setattr(discord_webhook.requests, "post",
                        lambda url, params, json, timeout: envois.append((params, json)) or R())
    monkeypatch.setattr(discord_webhook.time, "sleep", lambda s: None)
    bot, _, _ = _bot(tmp_path, [speedy()], DETAILS)
    bot.notifier = discord_webhook.DiscordWebhook("https://discord.com/api/webhooks/1/abc")
    assert bot.cycle() == 1
    params, payload = envois[0]
    assert params["with_components"] == "true"
    assert len(payload["embeds"]) == 3
    assert payload["embeds"][0]["fields"][0]["name"] == "🧮 Estimation prix total"
    boutons = payload["components"][0]["components"]
    assert [b["label"] for b in boutons] == ["Commander sur ZenMarket", "Annonce d'origine"]
    assert all(b["style"] == 5 and b["url"].startswith("https://") for b in boutons)


def test_webhook_attend_si_limite(monkeypatch):
    from bot import discord_webhook
    reponses = iter([(429, {"retry_after": 0.1}), (200, {})])

    class R:
        def __init__(self, code, data):
            self.status_code, self.ok, self.text, self._d = code, code == 200, "", data

        def json(self):
            return self._d

    monkeypatch.setattr(discord_webhook.requests, "post", lambda *a, **k: R(*next(reponses)))
    monkeypatch.setattr(discord_webhook.time, "sleep", lambda s: None)
    assert discord_webhook.DiscordWebhook("https://x").envoyer("<b>Récap</b>") is True
