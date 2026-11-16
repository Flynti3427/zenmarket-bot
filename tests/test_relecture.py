"""Tests ajoutés par la relecture quotidienne : vrais titres d'annonces mal (ou bien) filtrées."""
import pytest
import yaml

from bot.filters import correspond
from bot.models import Article, Listing

CFG = yaml.safe_load(open("config.yaml", encoding="utf-8"))
EXCL = CFG["exclusions_globales"]
ARTICLES = {a["nom"]: Article.from_dict(a) for a in CFG["articles"]}


def L(title, price=50000):
    return Listing(source="mercari", item_id="m1", title=title, price_jpy=price,
                   url_original="o", url_zenmarket="z")


# ------------------------------------------------- relecture du 16/11/2026 : mauvaises alertes
@pytest.mark.parametrize("article,titre", [
    # wallets de marque : la marque doit figurer dans le titre
    ("Chanel wallet", "美品・限定 IL BISONTE イルビゾンテ 本革二つ折り財布 オールレザー"),
    ("Chanel wallet", "MIU MIU マテラッセ 二つ折り財布 ブラック"),
    ("Chanel wallet", "ヴィトン 長財布 グレー A-18644"),
    ("Chanel wallet", "三つ折り財布"),
    ("Gucci wallet", "新品　未使用　COACH コーチ 二つ折り財布 ブラック シンプルスリム"),
    ("Gucci wallet", "ロンシャン　レザー　LONGCHAMP 美品　未使用品　長財布"),
    ("Prada wallet", "ソフトルックスレザー財布　ダークブラウン"),
    ("Prada wallet", "正規品　MIU MIU ミュウミュウ　本物　 三つ折り財布 レザー PRADA ウォレット　ハイブランド　美品　レア　ミウッチャ　archive vintage"),
    ("Prada wallet", "【正規品 】 miumiu 二つ折り財布 RFID搭載"),
    ("Bottega Veneta wallet", "【新品未使用】羊革二つ折り財布　イントレチャート　小型財布　おしゃれ　黒　高見え"),
    ("Bottega Veneta wallet", "本革　ミニ財布　ラムレザー　編み込み　イントレチャート風　コンパクト　上品"),
    ("Chloé wallet", "ホロライブ　沙花叉クロヱ　飼育員　秘密結社holoX　長財布　ウォレット"),
    ("Chloé wallet", "未使用品　Salvatore Ferragamo 長財布　ガンチーニ　パープル"),
    ("Coach wallet", "MICHAEL KORS マイケルコース 35R4GTVT3V 長財布 レディース ブランド ピンク系"),
    ("LV portefeuille (wallet)", "【未使用級】ダンヒル dunhill 長財布 ブラック レザー 折り財布"),
    ("Dior wallet", "ほぼ未使用✨️ Dior HOMME ディオールオム ウォレットチェーン 4連"),
    # Céline Macadam : motif Macadam sur autre chose qu'un sac
    ("Céline Macadam vintage Boston", "CECINE レディース ダウンポンチョ F ベージュ マカダム柄 秋冬"),
    ("Céline Macadam vintage Boston", "セリーヌ　CELINE　マカダム　ロゴ　カフス　カフリンクス　シルバーカラー×ゴールドカラー　YMA-615"),
    ("Céline Macadam vintage Boston", "CELINE セリーヌ コインケース 小銭入れ マカダム トライアングル"),
    ("Céline Macadam vintage Boston", "美品 CELINE マカダム柄 ダウンベスト ブラウン"),
    ("Céline Macadam vintage Boston", "CELINE セリーヌ マカダム柄 ブランケット 綿毛布"),
    # Sac Céline : vêtements et dustbag
    ("Sac Céline (autre modèle)", "1311⭐️オールドセリーヌ ツイードスカート フレア　総柄 ウール ブラウン"),
    ("Sac Céline (autre modèle)", "CELINE セリーヌ ブラウス ヴィンテージ 金具ロゴ総柄 シルク プルオーバートップス 半袖"),
    ("Sac Céline (autre modèle)", "CELINE セリーヌ 巾着 保存袋"),
    # sacs : petite maroquinerie, ceintures, coques, lots
    ("Bottega Veneta Cassette", "ボッテガヴェネタ カセット カードケース パスケース ブラウン レザー 定期"),
    ("Bottega Veneta Cassette", "【新着】BOTTEGA VENETA カセット レザー グリーン ジップアラウンドウォレット シルバー"),
    ("Bottega Veneta Cassette", "✨未使用級　RFID✨ボッテガ　コインケース　小銭入れ　カセット　パラキート"),
    ("Chanel Cambon vintage", "CHANEL シガレットケース　カンボンライン　タバコケース シャネル"),
    ("Chanel Cambon vintage", "CHANEL◆長サイフ_カンボンライン_カーフスキン_ココマーク_BLK/牛革/BLK/レディース"),
    ("Chanel Cambon vintage", "CHANEL シャネル カンボンライン カードケース ココマーク マトラッセ"),
    ("Lady Dior classique", "DIOR レディディオール iPhone16ケース ブラック"),
    ("Lady Dior classique", "クリスチャンディオール レディ ディオール S0478ONMJ コインケース"),
    ("Lady Dior classique", "美品✨ レディディオール カナージュ フォンホルダー レッド"),
    ("LV Ellipse", "【C0025】 LOUIS VUITTON ルイヴィトン サンチュール エリプス M6919 ベルト モノグラム 定番 ブラウン 90/36 ゴールドバックル メンズ"),
    ("LV Speedy", "￥1〜 全5品 LOUIS VUITTON モノグラム キーポル スピーディ ボストンバッグ ショルダーバッグ クラッチ バッグ ヴィンテージ まとめ"),
])
def test_relecture_rejette(article, titre):
    assert not correspond(ARTICLES[article], L(titre), EXCL)


# ------------------------------------------------- bonnes alertes qui doivent rester
@pytest.mark.parametrize("article,titre", [
    ("Chanel wallet", "CHANEシャネル キャビアスキン 二つ折り財布 ブラック ココマーク"),
    ("Chanel wallet", "新品未使用に近いボーイシャネル三つ折り財布"),
    ("Gucci wallet", "GGマーモント コンパクトウォレット"),
    ("Gucci wallet", "GUCCI × BALENCIAGA 二つ折り財布 限定 美品 未使用 箱付"),
    ("Prada wallet", "プラダ 三角ロゴ テスート ナイロン 2つ折り 長財布 ブラック 黒 レザー"),
    ("Saint Laurent wallet", "【YVES SAINT LAURENT】イヴサンローラン カサンドラ YSLロゴ 総柄 長財布 モノグラム 二つ折り ロングウォレット 箱 保存袋付き ブラウン"),
    ("Saint Laurent wallet", "イヴ・サンローラン Saint Laurent カードウォレット/財布 ゴールド 正規品 S級 (鑑定O)"),
    ("Bottega Veneta wallet", "美品✨ボッテガヴェネタ 長財布 イントレチャート 編み込み ブルー系"),
    ("Céline wallet", "フラットジップウォレットトリオンフ スタンプ / サプル グレインドカーフスキン"),
    ("Chloé wallet", "Chloé クロエ INDY 長財布 レザー ピンクベージュ 付属品多数あり"),
    ("LV portefeuille (wallet)", "LOUIS VUITTON モノグラム 二つ折り財布"),
    ("Céline Macadam vintage Boston", "CELINE マカダム柄 クラッチバッグ ブラウン"),
    ("Céline Macadam vintage Boston", "セリーヌ　マカダムセカンドバック"),
    ("Céline Macadam vintage Boston", "CELINE セリーヌ Cサルキー Cマカダム キャンバス レザー ショルダー"),
    ("Sac Céline (autre modèle)", "CELINE セリーヌ ナップサック 巾着 バッグ　Celine"),
    ("Sac Céline (autre modèle)", "★CELINE*セリーヌ★バッグ"),
    ("Bottega Veneta Cassette", "ボッテガヴェネタ ショルダーバッグ キャンディカセット パラキート IC内蔵"),
    ("Chanel Cambon vintage", "CHANEL シャネル カンボンライン ミディアムトートバッグ ブラック"),
    ("Lady Dior classique", "Christian Dior レディディオール ハンドバッグ"),
    ("LV Speedy", "ルイヴィトン モノグラム スピーディ30 ハンドバッグ"),
    ("Chanel Wallet on Chain (WOC)", "CHANEL マトラッセ チェーンウォレット ブラック"),
])
def test_relecture_garde(article, titre):
    assert correspond(ARTICLES[article], L(titre, price=60000), EXCL)
