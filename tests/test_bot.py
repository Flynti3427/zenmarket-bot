import base64
import json

import pytest
import yaml
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature

from bot.filters import MAUVAIS, MOYEN, TRES_BON, correspond, estimer_etat
from bot.main import Bot
from bot.models import Article, Listing, appliquer_seuil_unique
from bot.pricing import cout_rendu_france, prix_max_jpy
from bot.sources import mercari, yahoo
from bot.storage import Stockage

CFG = yaml.safe_load(open("config.yaml", encoding="utf-8"))
FRAIS, PROFILS = CFG["frais"], CFG["profils"]
TAUX = 0.0057


def L(title, price=50000, **kw):
    return Listing(source="mercari", item_id="m1", title=title, price_jpy=price,
                   url_original="o", url_zenmarket="z", **kw)


def art(nom, unique=True):
    a = Article.from_dict(next(x for x in CFG["articles"] if x["nom"] == nom))
    if unique:
        appliquer_seuil_unique([a])
    return a


SPEEDY = art("LV Speedy")


# ----------------------------------------------------------------- filtres
def test_filtre_accepte_vrai_speedy():
    assert correspond(SPEEDY, L("ルイヴィトン モノグラム スピーディ30 ボストンバッグ"), CFG["exclusions_globales"])


@pytest.mark.parametrize("titre", [
    "ルイヴィトン スピーディ 保存袋のみ",      # dustbag seul
    "ルイヴィトン スピーディ カデナのみ",      # cadenas seul
    "ルイヴィトン キーポル 55",               # pas un speedy
])
def test_filtre_rejette(titre):
    assert not correspond(SPEEDY, L(titre), CFG["exclusions_globales"])


def test_filtre_prix_min():
    assert not correspond(SPEEDY, L("スピーディ30", price=3000), CFG["exclusions_globales"])


def test_filtre_pleine_chasse():
    assert correspond(SPEEDY, L("LOUIS VUITTON ＳＰＥＥＤＹ ３０"), CFG["exclusions_globales"])


# -------------------------------------------------------------------- état
@pytest.mark.parametrize("titre,cond,attendu", [
    ("スピーディ30 極美品", None, TRES_BON),
    ("スピーディ30 ジャンク 美品", None, MAUVAIS),       # le pire gagne
    ("スピーディ30 ABランク", None, TRES_BON),
    ("スピーディ30 Bランク", None, MOYEN),
    ("スピーディ30 Cランク", None, MAUVAIS),
    ("スピーディ30", "やや傷や汚れあり", MOYEN),
    ("スピーディ30", "未使用に近い", TRES_BON),
    ("スピーディ30", None, MOYEN),                     # inconnu -> prudent
])
def test_etat(titre, cond, attendu):
    assert estimer_etat(L(titre, condition_jp=cond))[0] == attendu


# ------------------------------------------------------------------- prix
def test_cout_sous_150_pas_de_droits():
    est = cout_rendu_france(10000, TAUX, FRAIS, PROFILS["sac"])  # 57 € + 40 € port = 97 €
    assert est.droits_eur == 0
    assert est.frais_fixes_eur == FRAIS["droit_forfaitaire_ue_eur"]
    assert est.tva_eur == pytest.approx(0.2 * 97, abs=0.01)


def test_cout_au_dessus_150():
    est = cout_rendu_france(40000, TAUX, FRAIS, PROFILS["sac"])  # 228 € + 40 €
    valeur = 228 + 40
    assert est.droits_eur == pytest.approx(valeur * 0.03, abs=0.01)
    assert est.tva_eur == pytest.approx((valeur + valeur * 0.03) * 0.2, abs=0.01)
    attendu = 228 + 800 * TAUX + (228 + 800 * TAUX) * 0.015 + 40 + est.droits_eur + est.tva_eur + 15
    assert est.cout_total_eur == pytest.approx(attendu, abs=0.02)


def test_prix_max_coherent_avec_cout():
    pmax = prix_max_jpy(450, TAUX, FRAIS, PROFILS["sac"])
    assert cout_rendu_france(pmax, TAUX, FRAIS, PROFILS["sac"]).cout_total_eur <= 450
    assert cout_rendu_france(pmax + 200, TAUX, FRAIS, PROFILS["sac"]).cout_total_eur > 450


def test_prix_max_impossible_si_port_trop_cher():
    assert prix_max_jpy(20, TAUX, FRAIS, PROFILS["petit"]) == 0


# ------------------------------------------------------ règle du tableau
def test_fourchettes_par_etat():
    keepall = art("LV Keepall", unique=False)
    assert keepall.seuil_achat("tres_bon") == (300, 350)
    assert keepall.seuil_achat("moyen") == (220, 250)
    assert keepall.seuil_achat("mauvais") is None


def test_speedy_450_tous_etats():
    assert SPEEDY.seuil_achat("tres_bon") == (400, 450)
    assert SPEEDY.seuil_achat("moyen") == (200, 450)
    assert SPEEDY.seuil_achat("mauvais") == (200, 450)


def test_prix_unique_vaut_pour_tres_bon():
    jackie = Article.from_dict(next(a for a in CFG["articles"] if a["nom"] == "Gucci Jackie vintage"))
    assert jackie.seuil_achat("tres_bon") == jackie.seuil_achat("moyen") == (400, 400)


def test_tous_les_articles_du_tableau_presents():
    noms = {a["nom"] for a in CFG["articles"]}
    assert len(CFG["articles"]) == 57  # 45 du tableau + 10 wallets + 2 lots
    for n in ["LV Saint-Germain", "LV Alma", "LV Ellipse", "Chanel Wallet on Chain (WOC)",
              "Lady Dior classique", "Bottega Veneta Jodie mini", "Chloé Nile Bracelet Bag"]:
        assert n in noms
    for a in CFG["articles"]:
        Article.from_dict(a)  # chaque ligne se lit sans erreur
        assert a["profil"] in PROFILS


# ---------------------------------------------------------------- mercari
def test_dpop_signature_valide():
    cle = ec.generate_private_key(ec.SECP256R1())
    jeton = mercari.creer_dpop(mercari.SEARCH_URL, "POST", cle)
    h, p, s = jeton.split(".")
    dec = lambda x: base64.urlsafe_b64decode(x + "=" * (-len(x) % 4))
    header, payload = json.loads(dec(h)), json.loads(dec(p))
    assert header["typ"] == "dpop+jwt" and header["alg"] == "ES256"
    assert payload["htm"] == "POST" and payload["htu"] == mercari.SEARCH_URL
    sig = dec(s)
    der = encode_dss_signature(int.from_bytes(sig[:32], "big"), int.from_bytes(sig[32:], "big"))
    cle.public_key().verify(der, f"{h}.{p}".encode(), ec.ECDSA(hashes.SHA256()))  # lève si invalide


def test_mercari_conversion():
    items = [
        {"id": "m123456789", "name": "スピーディ30", "price": "45000", "itemConditionId": "3",
         "thumbnails": ["https://img/1.jpg"], "itemType": "ITEM_TYPE_MERCARI"},
        {"id": "2AbCdEf", "name": "スピーディ25", "price": "38000", "itemConditionId": "2",
         "itemType": "ITEM_TYPE_BEYOND"},
    ]
    a, b = mercari.convertir(items)
    assert a.url_zenmarket == "https://zenmarket.jp/fr/mercariproduct.aspx?itemCode=m123456789"
    assert a.price_jpy == 45000 and a.condition_jp == "目立った傷や汚れなし" and a.image_url
    assert b.source == "mercari_shops" and "shops/product/2AbCdEf" in b.url_original


# ------------------------------------------------------------------ yahoo
HTML_ATTRS = """
<ul><li class="Product">
  <a class="Product__imageLink" data-auction-id="x123456789" data-auction-title="ルイヴィトン スピーディ30 美品"
     data-auction-price="32000" data-auction-buynowprice="45000" data-auction-img="https://img/y.jpg"
     href="https://auctions.yahoo.co.jp/jp/auction/x123456789"></a>
  <span class="Product__time">3日</span>
</li></ul>"""

HTML_JSON = """<script id="__NEXT_DATA__" type="application/json">
{"props":{"pageProps":{"items":[{"auctionId":"k987654321","title":"ルイヴィトン ノエ","price":28000,
"imageUrl":"https://img/k.jpg"}]}}}</script>"""

HTML_LIENS = """<li><a href="https://auctions.yahoo.co.jp/jp/auction/w111222333">ルイヴィトン キーポル 55 ボストン</a>
<span>現在 41,000円</span></li>"""


def test_yahoo_attributs():
    (l,) = yahoo.analyser_page(HTML_ATTRS)
    assert (l.item_id, l.price_jpy, l.buy_now_jpy, l.time_left) == ("x123456789", 32000, 45000, "3日")
    assert l.url_zenmarket == "https://zenmarket.jp/fr/auction.aspx?itemCode=x123456789"


def test_yahoo_json():
    (l,) = yahoo.analyser_page(HTML_JSON)
    assert (l.item_id, l.price_jpy) == ("k987654321", 28000)


def test_yahoo_liens_secours():
    (l,) = yahoo.analyser_page(HTML_LIENS)
    assert (l.item_id, l.price_jpy) == ("w111222333", 41000)


# ------------------------------------------------------- cycle complet
class FausseSource:
    nom = "mercari"

    def __init__(self, annonces):
        self.annonces = annonces

    def rechercher(self, mot_cle, prix_min=0):
        return self.annonces if "スピーディ" in mot_cle else []


class Capture:
    def __init__(self):
        self.messages = []

    def envoyer(self, texte, photo=None):
        self.messages.append(texte)
        return True


def _bot(tmp_path, annonces):
    cfg = yaml.safe_load(open("config.yaml", encoding="utf-8"))
    cfg["reglages"]["pause_entre_requetes_s"] = [0, 0]
    cap = Capture()
    bot = Bot(cfg, cap, Stockage(tmp_path / "t.sqlite"))
    bot.sources = [FausseSource(annonces)]
    bot.echecs = {"mercari": 0}
    bot.fx.jpy_eur = lambda: TAUX
    return bot, cap


def test_cycle_alerte_selon_tableau(tmp_path):
    # Speedy très bon état : alerte si coût rendu <= 450 €
    pmax = prix_max_jpy(450, TAUX, FRAIS, PROFILS["sac"])
    ok = Listing("mercari", "m42", "ルイヴィトン スピーディ30 美品", pmax - 500, "o", "z")
    trop = Listing("mercari", "m43", "ルイヴィトン スピーディ30 美品", pmax + 3000, "o", "z")
    # Speedy : seuil 450 € quel que soit l'état -> le 5/10 et le mauvais état alertent aussi
    moyen = Listing("mercari", "m44", "ルイヴィトン スピーディ30 使用感", pmax - 500, "o", "z")
    junk = Listing("mercari", "m45", "ルイヴィトン スピーディ30 ジャンク", pmax - 500, "o", "z")
    bot, cap = _bot(tmp_path, [ok, trop, moyen, junk])
    assert bot.cycle() == 3
    assert "LV Speedy" in cap.messages[0] and "dans ta fourchette" in cap.messages[0]
    assert bot.cycle() == 0   # déjà alertée -> pas de doublon


def test_cycle_sous_la_fourchette(tmp_path):
    bot, cap = _bot(tmp_path, [Listing("mercari", "m42", "スピーディ30 美品", 20000, "o", "z")])
    assert bot.cycle() == 1 and "SOUS ta fourchette" in cap.messages[0]


def test_cycle_realerte_si_baisse(tmp_path):
    bot, cap = _bot(tmp_path, [Listing("mercari", "m42", "スピーディ30 美品", 25000, "o", "z")])
    bot.cycle()
    bot.sources = [FausseSource([Listing("mercari", "m42", "スピーディ30 美品", 21000, "o", "z")])]
    assert bot.cycle() == 1 and "BAISSE" in cap.messages[-1]


def test_seuil_unique_tous_les_sacs():
    assert CFG["reglages"]["seuil_unique_tous_etats"] is True
    keepall = art("LV Keepall")
    assert keepall.seuil_achat("moyen") == (220, 350) and keepall.seuil_achat("mauvais") == (220, 350)
    jackie = art("Gucci Jackie vintage")
    assert jackie.seuil_achat("mauvais") == (400, 400)
    assert art("Dior Boston").seuil_achat("moyen") is None   # pas de prix -> pas d'alerte


def test_keepall_moyen_alerte_sous_350(tmp_path):
    pmax_tb = prix_max_jpy(350, TAUX, FRAIS, PROFILS["sac"])
    moyen = Listing("mercari", "m50", "ルイヴィトン キーポル55 使用感", pmax_tb - 500, "o", "z")
    bot, cap = _bot(tmp_path, [])
    bot.sources = [type("S", (), {"nom": "mercari", "rechercher": lambda self, m, p=0: [moyen] if "キーポル" in m else []})()]
    assert bot.cycle() == 1


def test_mode_once_annonce_demarrage_une_seule_fois(tmp_path):
    bot, cap = _bot(tmp_path, [])
    bot.cycle = lambda: 0
    bot.tourner(une_fois=True)
    bot.tourner(une_fois=True)
    assert sum("démarré" in m for m in cap.messages) == 1


def test_compteur_panne_persiste(tmp_path):
    db = Stockage(tmp_path / "p.sqlite")
    cfg = yaml.safe_load(open("config.yaml", encoding="utf-8"))
    for _ in range(3):  # 3 exécutions séparées (comme sur GitHub), chacune sans résultat
        cap = Capture()
        bot = Bot(cfg, cap, db)
        bot._surveiller_panne("mercari", 0)
    assert any("aucun résultat" in m for m in cap.messages)


def test_triomphe_cuir_rejette_pochette_macadam():
    triomphe = art("Céline Triomphe cuir", unique=False)
    titre = "オールド CELINE セリーヌ トリオンフ マカダム柄 ハンドバッグ ホーボー PVCレザー ブラウン ヴィンテージ ポーチ 6681"
    assert not correspond(triomphe, L(titre, price=36081), CFG["exclusions_globales"])
    assert correspond(triomphe, L("セリーヌ トリオンフ レザー ショルダーバッグ", price=90000), CFG["exclusions_globales"])


def test_yahoo_heure_de_fin():
    import json as _json
    import time as _time
    from datetime import datetime, timedelta, timezone
    jst = timezone(timedelta(hours=9))
    fin = (datetime.now(jst) + timedelta(days=2)).replace(microsecond=0)
    passe = (datetime.now(jst) - timedelta(hours=1)).replace(microsecond=0)
    data = {"props": {"items": [
        {"auctionId": "n1", "title": "ルイヴィトン スピーディ25", "price": 49800, "endTime": fin.isoformat()},
        {"auctionId": "n2", "title": "ルイヴィトン スピーディ30", "price": 39800, "endTime": passe.isoformat()},
    ]}}
    html = f'<script id="__NEXT_DATA__" type="application/json">{_json.dumps(data)}</script>'
    annonces = yahoo.analyser_page(html)
    assert [a.item_id for a in annonces] == ["n1"]           # l'enchère terminée est ignorée
    assert annonces[0].fin_ts == fin.timestamp()
    assert abs(annonces[0].fin_ts - _time.time() - 2 * 86400) < 5


def test_lots_de_portefeuilles():
    lot_lv = art("Lot portefeuilles LV", unique=False)
    lot = art("Lot portefeuilles marques", unique=False)
    wallet_gucci = art("Gucci wallet", unique=False)
    ex = CFG["exclusions_globales"]
    assert correspond(lot_lv, L("ルイヴィトン 財布 5点 まとめ売り モノグラム", price=20000), ex)
    assert not correspond(lot_lv, L("ルイヴィトン 長財布 モノグラム", price=20000), ex)       # un seul wallet
    assert not correspond(lot_lv, L("ルイヴィトン バッグ まとめ売り", price=20000), ex)       # pas des wallets
    assert correspond(lot, L("ブランド財布 まとめ売り 10点 グッチ プラダ", price=15000), ex)
    assert not correspond(wallet_gucci, L("グッチ 財布 まとめ 3点", price=15000), ex)        # le lot ne va pas dans #wallet
    assert correspond(wallet_gucci, L("グッチ 長財布 GG", price=15000), ex)


def test_cravate_exclue():
    macadam = art("Céline Macadam vintage Boston", unique=False)
    assert not correspond(macadam, L("セリーヌ ネクタイ シルク マカダム トリオンフ ブラゾン グレー", price=7200),
                          CFG["exclusions_globales"])
