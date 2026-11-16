import json
from datetime import datetime
from urllib.parse import parse_qs, urlparse

import yaml

from bot import rapport
from bot.discord_v2 import payload_v2
from bot.main import Bot
from bot.models import Listing
from bot.storage import Stockage

TAUX = 0.0057


class Notif:
    def __init__(self):
        self.alertes, self.textes = [], []

    def envoyer_alerte(self, a):
        self.alertes.append(a)
        return True

    def envoyer(self, texte, photo=None):
        self.textes.append(texte)
        return True


class Source:
    nom = "mercari"

    def __init__(self, annonces):
        self.annonces = annonces

    def rechercher(self, mot_cle, prix_min=0):
        return self.annonces if "スピーディ" in mot_cle else []


def _bot(tmp_path):
    cfg = yaml.safe_load(open("config.yaml", encoding="utf-8"))
    cfg["reglages"]["pause_entre_requetes_s"] = [0, 0]
    notif = Notif()
    bot = Bot(cfg, notif, Stockage(tmp_path / "r.sqlite"))
    bot.sources = [Source([
        Listing("mercari", "m1", "ルイヴィトン スピーディ30 美品", 25000, "https://jp.mercari.com/item/m1", "z"),
        Listing("mercari", "m2", "ルイヴィトン スピーディ30 美品", 95000, "o", "z"),
    ])]
    bot.echecs = {"mercari": 0}
    bot.fx.jpy_eur = lambda: TAUX
    return bot, notif


def test_bouton_erreur(tmp_path):
    bot, notif = _bot(tmp_path)
    bot.cycle()
    a = notif.alertes[0]
    url = a["url_erreur"]
    assert url.startswith("https://github.com/Flynti3427/zenmarket-bot/issues/new?")
    q = parse_qs(urlparse(url).query)
    assert q["labels"] == ["erreur"] and "mercari:m1" in q["title"][0] and "スピーディ30" in q["body"][0]
    boutons = [c for c in payload_v2(a)["components"][0]["components"] if c["type"] == 1][0]["components"]
    assert boutons[-1]["label"] == "Erreur" and boutons[-1]["url"] == url


def test_contenu_du_rapport(tmp_path):
    bot, notif = _bot(tmp_path)
    bot.cycle()
    r = rapport.construire_rapport(bot.db, bot.articles, "2026-11-16")
    assert r["nb_alertes"] == 1 and r["alertes"][0]["cle"] == "mercari:m1"
    s = r["stats"]["LV Speedy"]
    assert s["annonces_vues_24h"] == 2 and s["alertes_24h"] == 1 and s["ton_prix_max"] == 450
    assert s["cout_livre_min_30j"] < s["cout_livre_median_30j"]
    json.dumps(r, ensure_ascii=False)  # sérialisable


class FauxGithub:
    def __init__(self):
        self.fichiers = {}

    def lire(self, chemin):
        return self.fichiers.get(chemin)

    def ecrire(self, chemin, contenu, message):
        self.fichiers[chemin] = contenu


def test_tache_du_soir(tmp_path, monkeypatch):
    bot, notif = _bot(tmp_path)
    bot.cycle()
    gh = FauxGithub()
    monkeypatch.setattr(rapport, "depuis_env", lambda depot: gh)

    class Heure:
        h = 18

        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 11, 16, cls.h, 5, tzinfo=tz)

    monkeypatch.setattr(rapport, "datetime", Heure)
    rapport.tache_du_soir(bot)
    assert gh.fichiers == {}                                   # avant 19 h : rien
    Heure.h = 19
    rapport.tache_du_soir(bot)
    assert "rapports/2026-11-16.json" in gh.fichiers
    assert notif.textes == []                                  # pas encore de bilan
    gh.fichiers.clear()
    rapport.tache_du_soir(bot)
    assert gh.fichiers == {}                                   # exporté une seule fois par jour
    gh.fichiers["bilans/2026-11-16.md"] = "📊 **Bilan du 16/11**\n" + "ligne\n" * 500
    rapport.tache_du_soir(bot)
    assert notif.textes[0].startswith("📊 **Bilan du 16/11**")
    assert all(len(t) <= 2000 for t in notif.textes) and len(notif.textes) > 1
    n = len(notif.textes)
    rapport.tache_du_soir(bot)
    assert len(notif.textes) == n                              # publié une seule fois


def test_decouper():
    morceaux = rapport.decouper("a" * 4500, 1900)
    assert [len(m) for m in morceaux] == [1900, 1900, 700]
