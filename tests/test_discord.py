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
    e = embeds[0]
    assert e.title == "LV Speedy"                               # modèle en français, pas le titre japonais
    assert "livré en France" in e.description and "Ton prix max : **450 €**" in e.description
    champs = {f.name: f.value for f in e.fields}
    assert champs["Prix au Japon"].startswith("25 000 ¥")
    assert champs["👤 Vendeur"] == "942 avis · 100 % positifs"
    assert not any("vérifier" in n for n in champs)            # rien de suspect -> pas d'avertissement
    assert "スピーディ" in e.footer.text                         # titre japonais en petit


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
    assert payload["flags"] == 1 << 15 and payload["components"][0]["type"] == 17


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


def test_alerte_enchere_affiche_mise_max(tmp_path):
    from bot.discord_bot import construire_embeds
    bot, notif, _ = _bot(tmp_path, [], DETAILS)
    l = speedy()
    l.source, l.is_auction, l.time_left = "yahoo", True, "2 jours"
    bot.sources = [FausseSource([l])]
    bot.cycle()
    champs = {f.name: f.value for f in construire_embeds(notif.alertes[0])[0].fields}
    assert "Ne mise pas plus de" in champs["⏳ Enchère : le prix peut encore monter"]


# ------------------------------------------------- format de la capture (V2)
def _alerte(tmp_path, details=DETAILS, annonces=None):
    bot, notif, _ = _bot(tmp_path, annonces or [speedy()], details)
    bot.cycle()
    return notif.alertes[0]


def _textes(bloc):
    return "\n".join(c["content"] for c in bloc["components"] if c["type"] == 10)


def test_format_comme_la_capture(tmp_path):
    from bot.discord_v2 import payload_v2
    p = payload_v2(_alerte(tmp_path), meilleure=True)
    bloc = p["components"][0]
    types = [c["type"] for c in bloc["components"]]
    # en-tête, galerie de photos, séparateur, prix, boutons, séparateur, contrôle, pied
    assert types == [10, 12, 14, 10, 1, 14, 10, 10]
    assert len(bloc["components"][1]["items"]) == 3
    texte = _textes(bloc)
    assert "🔥 **LV Speedy** · meilleure affaire" in texte
    assert "Prix de l'article au Japon · 🟢 Disponible au Japon · Mercari" in texte
    assert "`25 000 ¥`" in texte and "942 avis · 100 % positifs" in texte
    assert "Total livré en France" in texte and "Contrôle anti-contrefaçon passé" in texte
    assert "<t:" in texte  # « il y a X minutes »
    boutons = bloc["components"][4]["components"]
    assert boutons[0]["label"] == "Commander sur ZenMarket" and boutons[0]["style"] == 5
    assert len(texte) < 4000


def test_marques_de_tous_les_articles():
    from bot.discord_v2 import marque_de
    cfg = yaml.safe_load(open("config.yaml", encoding="utf-8"))
    marques = {a["nom"]: marque_de(a["nom"]) for a in cfg["articles"]}
    assert all(m[0] != "Autres" for m in marques.values()), marques
    assert marques["Lady Dior classique"] == ("Dior", "dior")
    assert marques["Sac Céline (autre modèle)"] == ("Céline", "celine")
    assert len({m[1] for m in marques.values()}) == 13


def test_meilleure_affaire():
    from bot.discord_v2 import est_meilleure_affaire
    a = {"achat_vise": [400, 450], "cout": {"total": 300}, "signaux": []}
    assert est_meilleure_affaire(a, 25)           # 33 % sous le max
    a["cout"]["total"] = 400
    assert not est_meilleure_affaire(a, 25)       # 11 % seulement
    a["cout"]["total"], a["signaux"] = 300, ["prix anormalement bas"]
    assert not est_meilleure_affaire(a, 25)       # suspect -> jamais « meilleure »


class FausseApiDiscord:
    def __init__(self, existants):
        self.salons = list(existants)
        self.messages = []
        self.prochain = 1000

    def request(self, methode, url, timeout=None, json=None):
        import types
        chemin = url.split("/api/v10")[1]
        if methode == "GET":
            data = self.salons
        elif chemin.endswith("/channels"):
            self.prochain += 1
            data = {"id": str(self.prochain), **json}
            self.salons.append(data)
        else:
            self.messages.append((chemin.split("/")[2], json))
            data = {"id": "m"}
        return types.SimpleNamespace(status_code=200, ok=True, content=b"x", json=lambda: data, text="")


def test_salons_crees_et_routage(tmp_path, monkeypatch):
    from bot import discord_serveur
    from bot.discord_serveur import DiscordServeur, SALON_MEILLEURES, nom_salon
    monkeypatch.setattr(discord_serveur.time, "sleep", lambda s: None)
    cfg = yaml.safe_load(open("config.yaml", encoding="utf-8"))
    api = FausseApiDiscord([{"id": "1", "type": 0, "name": "général"},
                            {"id": "2", "type": 0, "name": nom_salon("chanel")}])  # existe déjà
    d = DiscordServeur("tok", "999", [a["nom"] for a in cfg["articles"]], 25)
    d.session = api
    d.preparer()
    noms = [s["name"] for s in api.salons]
    assert "ZenMarket" in noms and SALON_MEILLEURES in noms and nom_salon("louis-vuitton") in noms
    assert noms.count(nom_salon("chanel")) == 1            # pas de doublon
    assert len(d.salons) == 14                              # 13 marques + meilleures affaires
    d.preparer()                                            # 2e tour : rien de recréé
    assert len(api.salons) == len(noms)

    a = _alerte(tmp_path)                                   # Speedy 25 000 ¥ : très sous 450 €
    assert d.envoyer_alerte(a)
    cibles = [cid for cid, _ in api.messages]
    assert cibles == [d.salons[nom_salon("louis-vuitton")], d.salons[SALON_MEILLEURES]]
