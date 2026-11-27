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


# ------------------------------------------------- relecture du 18/11/2026
@pytest.mark.parametrize("article,titre", [
    ("Bottega Veneta Cassette", "ボッテガ BOTTEGA VENETA カセット 二つ折り"),
    ("Bottega Veneta Cassette", "【限定品・IC】ボッテガ ヴェネタ カセット ネイビー ラウンドファスナー"),
    ("Chanel Cambon vintage", "CHANEL シャネル カンボンライン キーケース"),
    ("Chanel Cambon vintage", "【中古】 シャネル カンボンライン キーケース 6連キーケース ソフトカーフ  パテントレザー ブラック ピンク A26723 CHANEL Bランク"),
    ("Lady Dior classique", "Dior レディディオール カナージュ ロータスウォレット 三つ折り ベージュ クリスチャンディオール"),
    ("Lady Dior classique", "【美品】ディオール レディディオール カナージュ 4連キーケース 水色"),
    ("Lady Dior classique", "ディオール レディディオール カナージュ ウルトラマット カーフスキン ブラック カードケース S0011ONMJ DIOR Aランク 中古"),
    ("Lady Dior classique", "極美品/現行♡ディオール Lady Dior Hibiscus ウォレット 黒"),
    ("Gucci sac vintage toile GG", "まとめ売り GUCCI オールドグッチ バッグ 14点セット GGキャンバス シェリーライン レザー ボストン ショルダー 鞄 #140※0716-39/■g.k"),
    ("Sac Céline (autre modèle)", "CELINE セリーヌ デニム リボン バックストラップ サンダル 37.5 24.5cm程度 インディゴ レディース 古着 中古 USED"),
    ("Sac Céline (autre modèle)", "CELINE セリーヌ バッグ型 ピンブローチ ゴールドカラー"),
    ("Sac Céline (autre modèle)", "CELINE Macadam Monogram Clutch Bag y2k"),
    ("LV portefeuille (wallet)", "ルイヴィトン　6連　キーケース　正規品　長財布　モノグラム　レディース　メンズ"),
    ("Céline wallet", "【王道ブラック×艶やか金金具】セリーヌ CELINE ベルトバッグ ナノ Belt Bag Nano グレインドカーフスキン シボ革 レザー 本革 2WAY トップハンドル ハンドバッグ 財布"),
])
def test_relecture_18_11_rejette(article, titre):
    assert not correspond(ARTICLES[article], L(titre), EXCL)


@pytest.mark.parametrize("article,titre", [
    ("Bottega Veneta Cassette", "AD4192-127182◆ほぼ未使用【ボッテガ】マキシイントレ・パデットカセット・斜め掛け・ショルダーバッグ・ICチップあり◆ラムスキン・黒"),
    ("Chanel Cambon vintage", "CHANEL カンボンライン ショルダーバッグ"),
    ("Lady Dior classique", "Dior ディオール レディディオール カナージュ ハンドバッグ ゴールド金具"),
    ("Gucci sac vintage toile GG", "GUCCI オールドグッチ GGキャンバス ショルダーバッグ"),
    ("Céline Macadam vintage Boston", "CELINE Macadam Monogram Clutch Bag y2k"),
    ("Sac Céline (autre modèle)", "CELINE セリーヌ クラッチバッグ ブラウン"),
    ("LV portefeuille (wallet)", "LOUIS VUITTON ルイヴィトン ヴェルニ ポルトフォイユ サラ 長財布 アマラント　箱　袋付き"),
    ("Céline wallet", "CELINE セリーヌ ミディアム ストラップ ウォレット 財布　グレー U86"),
])
def test_relecture_18_11_garde(article, titre):
    assert correspond(ARTICLES[article], L(titre, price=60000), EXCL)


# ------------------------------------------------- relecture du 19/11/2026
@pytest.mark.parametrize("article,titre", [
    ("Chanel Cambon vintage", "CHANEL シャネル ノベリティ★カンボンライン ミディアムトートバッグ ブラック"),
    ("Céline Triomphe cuir", "CELINE　セリーヌ　スモールフラップウォレット トリオンフ　10D783BZG.04LU"),
    ("Lady Dior classique", "クリスチャンディオール CHRISTIAN DIOR 携帯・スマホアクセサリー ブラック ゴールド レディディオール カナージュ Call'in Dior"),
    ("LV Speedy", "LOUIS VUITTON　ルイヴィトン　ポルトクレBB　スピーディ　M66183"),
    ("Lot portefeuilles marques", "(まとめ) 新品 ちいかわ カードウォレット コインケース 2種"),
    ("Lot portefeuilles marques", "ちいかわ サガララゲッジタグ カードウォレット モモンガ まとめ売り"),
    ("Céline Macadam vintage Boston", "gr様専用　CELINE セリーヌ マカダム トリオンフ ベルト ゴールドバック"),
])
def test_relecture_19_11_rejette(article, titre):
    assert not correspond(ARTICLES[article], L(titre), EXCL)


@pytest.mark.parametrize("article,titre", [
    ("Céline Triomphe cuir", "【超美品】CELINE トリオンフチェーンショルダーバッグ"),
    ("Lady Dior classique", "Christian Dior レディディオール マットブラック"),
    ("LV Speedy", "LOUIS VUITTON モノグラム スピーディ35 ハンドバッグ"),
    ("Lot portefeuilles marques", "【17点まとめ売り】ブランド財布類まとめ ヴィトン セリーヌ　サンローラン他"),
    ("Céline Macadam vintage Boston", "CELINE セリーヌ マカダム柄 ショルダーバッグ オールドセリーヌ"),
    ("Chanel Cambon vintage", "CHANEL カンボンライン ショルダーバッグ"),
])
def test_relecture_19_11_garde(article, titre):
    assert correspond(ARTICLES[article], L(titre, price=60000), EXCL)


# ------------------------------------------------- relecture du 20/11/2026
@pytest.mark.parametrize("article,titre", [
    ("LV portefeuille (wallet)", "ルイ ヴィトン 保存袋 布袋 長財布用 LV LOUIS VUTTON"),
    ("Chanel wallet", "【新品】 CHANEL シャネル 袋 黒 財布入れ 保管袋"),
    ("LV Speedy", "1円～ 3ヶ月保証付き 磨き済み 美品 本物 人気 LOUIS VUITTON ルイヴィトン スピーディ デュオジェット GMT Q2371 メンズ 時計"),
    ("Fendi Mama Baguette vintage", "FENDI フェンディ【鑑定済み】レザーベルト｜FFロゴ｜シルバーバックル｜マンマ｜本革 110/125"),
    ("Céline Macadam vintage Boston", "CELINE セリーヌ ノエビア Cマカダム 馬車柄 トートバッグ ネイビー"),
    ("Lot portefeuilles marques", "日本正規品 ハローキティ 50周年 財布(まとめ売り)"),
])
def test_relecture_20_11_rejette(article, titre):
    assert not correspond(ARTICLES[article], L(titre), EXCL)


@pytest.mark.parametrize("article,titre", [
    ("LV portefeuille (wallet)", "LOUIS VUITTON ルイヴィトン ポルトフォイユ サラ モノグラム エトワール M66556 ブラウン 長財布"),
    ("Chanel wallet", "CHANEL シャネル マトラッセ キャビアスキン ラウンドファスナー 長財布 ロングジップウォレット 保存袋付き ブラック 黒"),
    ("LV Speedy", "★ LOUIS VUITTON モノグラム スピーディ40 M41522"),
    ("Céline Macadam vintage Boston", "CELINE ショルダーバッグ マカダム総柄 茶 ゴールド金具 2way M03"),
    ("Lot portefeuilles marques", "ブランド 財布 8点 まとめ売り カルティエ セリーヌ ジバンシィ サンローラン"),
    ("LV Keepall", "LOUIS VUITTON モノグラム キーポル ボストンバッグ45"),
])
def test_relecture_20_11_garde(article, titre):
    assert correspond(ARTICLES[article], L(titre, price=60000), EXCL)


# ------------------------------------------------- relecture du 21/11/2026
@pytest.mark.parametrize("article,titre", [
    ("LV Keepall", "LOUIS VUITTON ショルダーストラップ　110×2.5 キーポル用"),
    ("LV Keepall", "LOUIS VUITTON ルイヴィトン ヌメ革 ハンドルホルダー ポワニエ ゴールド金具 キーポル付属品 ハンドル固定用"),
    ("Bottega Veneta Cassette", "ボッテガヴェネタ カセット マキシイントレチャート キーリング付き コインパース"),
    ("Bottega Veneta Cassette", "未使用に近い✨ 現行 ボッテガヴェネタ ベルト 金具 カセット 編み込み 本革"),
    ("Sac Céline (autre modèle)", "【非売品】CELINE ナップサック ブラック"),
    ("Lot portefeuilles marques", "Il Bussetto イルブセット L字　財布 ミニ財布 レザー ブラウン"),
    ("Lot portefeuilles marques", "モンチッチ顔財布 まとめ売り"),
])
def test_relecture_21_11_rejette(article, titre):
    assert not correspond(ARTICLES[article], L(titre), EXCL)


@pytest.mark.parametrize("article,titre", [
    ("LV Keepall", "Louis Vuitton モノグラム キーポル50 ボストンバッグ"),
    ("LV Keepall", "LOUIS VUITTON　ルイヴィトン　モノグラム　キーポル45　M41428　ボストンバッグ　旅行用バッグ　旅行かばん　鑑定済　正規品　正規品"),
    ("Bottega Veneta Cassette", "1円■ボッテガヴェネタ キャンディカセット ショルダーバッグ グリーン系 レザー BOTTEGA VENETA ■K.Cem.tI-31"),
    ("Sac Céline (autre modèle)", "CELINE セリーヌ クラッチバッグ/セカンドバッグ ボルドー/ワインレッド系 馬車ロゴ 型押し ゴールド金具[OL03479]"),
    ("Lot portefeuilles marques", "コーチ カルティエ 等 ブランド 財布 6点 まとめ売り 長財布 折り財布 本革"),
])
def test_relecture_21_11_garde(article, titre):
    assert correspond(ARTICLES[article], L(titre, price=60000), EXCL)


# ------------------------------------------------- relecture du 22/11/2026
@pytest.mark.parametrize("article,titre", [
    ("LV Neverfull", "ルイヴィトン ネヴァーフルmm用 オーガナイザー LV パース オーガナイザー バッグ シェイパー インサート 海外 即決"),
    ("LV Speedy", "ルイ・ヴィトン　ブレスレット・スピーディ"),
    ("LV portefeuille (wallet)", "LOUIS VUITTON ルイヴィトン カードケース カード入れ パスケース 定期入れ 名刺入れ ブラウン系 ウォレット ファッション小物 普段使い 中古 DM3599"),
    ("LV portefeuille (wallet)", "【230点以上送料込み】LOUIS VUITTON　CHANEL　HERMES　GUCCI　COACH　CELINE　GIVENCHY　FENDI　Tiffany＆Co.等　財布小物類【約29kg】"),
    ("Prada wallet", "★PRADA★ロングウォレット用箱★カード等付属品★"),
    ("Prada Tessuto vintage nylon", "PRADA プラダ テスートナイロン 6連 キーケース 鍵入れ メンズ レディース ブラック系 DR0782"),
    ("Chanel Cambon vintage", "CHANEL Cambon Line　Card Case"),
    ("Chloé Marcie petit format", "Chloe クロエ MARCIE マーシー 二つ折りスクエアウォレット グリーン"),
    ("Chloé Paddington vintage", "Chloe パディントン コイン、カード"),
    ("Sac Céline (autre modèle)", "CELINE セリーヌ ヴィンテージ 馬車金具 のみ ベルトバックル ベルト金具 メンズ レディース ゴールド系 DQ9154"),
    ("Sac Céline (autre modèle)", "CELINE セリーヌ ナップサック　巾着　保存袋"),
    ("Sac Céline (autre modèle)", "CELINE ガーメントバッグ ガーメントケース"),
])
def test_relecture_22_11_rejette(article, titre):
    assert not correspond(ARTICLES[article], L(titre), EXCL)


@pytest.mark.parametrize("article,titre", [
    ("LV Neverfull", "LOUIS VUITTON モノグラム ネヴァーフルMM"),
    ("LV Speedy", "ルイヴィトン M41526 スピーディ30 モノグラム"),
    ("LV portefeuille (wallet)", "【訳あり・リペア用】ルイヴィトン エピ ジッピーウォレット 長財布 ノワール 黒"),
    ("Gucci wallet", "GUCCI グッチ GG柄 フラップ長財布 ダークネイビー レザー 専用箱付き"),
    ("Prada Tessuto vintage nylon", "PRADA プラダ テスート ナイロン 三角ロゴ トートバッグ ショルダーバッグ"),
    ("Chanel Cambon vintage", "CHANEL カンボンライン トートバッグ シルバー"),
    ("Sac Céline (autre modèle)", "CELINE ホワイト ショルダーバッグ"),
])
def test_relecture_22_11_garde(article, titre):
    assert correspond(ARTICLES[article], L(titre, price=60000), EXCL)


# ------------------------------------------------- relecture du 23/11/2026
@pytest.mark.parametrize("article,titre", [
    ("Gucci Jackie vintage", "グッチ グッチシマ ニュージャッキー コンチネンタルウォレット 黒 ゴールド金具"),
    ("Sac Céline (autre modèle)", "CELINE ショルダーストラップ ベージュ ヴィンテージ 当時物"),
    ("Coach wallet", "COACH 財布ストラップ ブラウン　巾着袋付"),
    ("Lot portefeuilles marques", "MONSTA X(モンスタエックス・モネク) ミニョク(MINHYUK) ネクサス アンコン ストラップ カード 財布 トレカ まとめ"),
])
def test_relecture_23_11_rejette(article, titre):
    assert not correspond(ARTICLES[article], L(titre), EXCL)


@pytest.mark.parametrize("article,titre", [
    ("Gucci Jackie vintage", "GUCCI グッチ ジャッキー GGキャンバス ショルダーバッグ ブラック 黒"),
    ("Sac Céline (autre modèle)", "CELINE セリーヌ ショルダーバッグ 馬車金具 クロスボディ 斜め掛け"),
    ("Coach wallet", "COACH 長財布 ブラウン レザー ストラップ付き"),
    ("Lot portefeuilles marques", "PRADA Dior マイケルコース 印傳屋 財布 4点 まとめ売り 訳あり"),
])
def test_relecture_23_11_garde(article, titre):
    assert correspond(ARTICLES[article], L(titre, price=60000), EXCL)


# ------------------------------------------------- relecture du 24/11/2026
@pytest.mark.parametrize("article,titre", [
    ("Lot portefeuilles marques", "BOTTEGA VENETA カセット 二つ折りウォレット ブラック　極美品"),
    ("LV portefeuille (wallet)", "LOUIS VUITTON　お財布空き箱　限定品　リボン付き"),
    ("Gucci wallet", "GUCCI 長財布の箱　付属品あり"),
    ("Gucci wallet", "濱野⭐️長財布 レッド ゴールド金具大収納 グッチプラダ"),
    ("Prada wallet", "濱野⭐️長財布 レッド ゴールド金具大収納 グッチプラダ"),
    ("Bottega Veneta wallet", "BOTTEGA VENETA イントレチャート 風の長財布 ブラック"),
    ("Céline wallet", "セリーヌ 黒マカダム クラッチバッグ セカンドバッグ 長財布収納可能 ブラック"),
])
def test_relecture_24_11_rejette(article, titre):
    assert not correspond(ARTICLES[article], L(titre), EXCL)


@pytest.mark.parametrize("article,titre", [
    ("Lot portefeuilles marques", "FURLA フルラ など 財布 2点 セット 長財布 二つ折り ピンク レザー"),
    ("LV portefeuille (wallet)", "LOUIS VUITTON ルイヴィトン M61734 モノグラム ポルトフォイユ サラ 二つ折り 長財布 ウォレット 小銭入れ 札入れ ブラウン系 DR1759"),
    ("Gucci wallet", "【極美品・箱付き】GUCCI グッチ GGキャンバス 長財布 ベージュ ブラウン"),
    ("Prada wallet", "【未使用保管品・箱付】PRADA プラダ 長財布 サフィアーノレザー ラウンドファスナー ブラック 黒 ジップアラウンド"),
    ("Bottega Veneta wallet", "BOTTEGA VENETA イントレチャート ラウンドファスナー 長財布"),
    ("Céline wallet", "CELINE M8 マカダム柄 がま口 長財布 ロングウォレット フラップ"),
    ("Sac Céline (autre modèle)", "CELINE レザー クラッチバッグ ブラック"),
])
def test_relecture_24_11_garde(article, titre):
    assert correspond(ARTICLES[article], L(titre, price=60000), EXCL)


# ------------------------------------------------- relecture du 25/11/2026
@pytest.mark.parametrize("article,titre", [
    ("Céline Triomphe cuir", "CELINE トリオンフ ベルト ブラック 85 定価95700円"),
    ("Céline Triomphe cuir", "極美品✨【鑑定済み】セリーヌ｜ダブルブレスレット｜トリオンフ｜レザー｜ゴールド"),
    ("LV Keepall", "〔COLOURS〕 未使用・長期保管・展示品■キーポルバンドリエール用■ロングストラップ＋肩当て■ヌメ革■Louis Vuitton"),
    ("LV Neverfull", "ウール大判ショール　マイ　ネヴァーフル　ジグネチャーモチーフ"),
    ("Gucci sac vintage toile GG", "GUCCI グッチ GGキャンバス シェリーライン コインケース 訳あり"),
    ("Fendi Mama Baguette vintage", "A1136【希少】FENDI フェンディ ズッカ柄 ショルダーバッグ ハンドバッグ ブラウン シルバー金具 ヴィンテージ 現状品 マンマバケット風"),
    ("Chanel wallet", "【確認用ページ】CHANEL キャビアスキン ラウンドファスナー 長財布"),
    ("Chanel wallet", "シャネル CHANEL 名刺入れ AP0214 マトラッセ ラムスキン イエロー ゴールド金具 財布"),
    ("Gucci wallet", "グッチ GUCCI ペンケース 662129 GGスプリーム ベージュ×ダークブラウン×ピンク デイジー/ディズニーコラボ 美品 財布"),
    ("Gucci wallet", "Wallet #5 GUCCI アートブック　マガジン ノルウェー"),
    ("Lot portefeuilles marques", "バッグ 財布 ペンライト 雑貨 まとめ売り"),
])
def test_relecture_25_11_rejette(article, titre):
    assert not correspond(ARTICLES[article], L(titre), EXCL)


@pytest.mark.parametrize("article,titre", [
    ("Céline Triomphe cuir", "✨良品✨ CELINE セリーヌ トリオンフ トートバッグ レザー ブラウン"),
    ("LV Keepall", "LOUIS VUITTON ルイヴィトン キーポル バンドリエール 50 M41416 ボストンバッグ 鑑定済み"),
    ("LV Neverfull", "LOUIS VUITTON ルイヴィトン Neverfull ネヴァーフルMM M40156 トートバッグ 鑑定済み"),
    ("Gucci sac vintage toile GG", "OLD GUCCI GGキャンバス 137396 シェリーライン グッチ ハンドバッグ ショルダーバッグ 100円スタート"),
    ("Fendi Mama Baguette vintage", "1円 美品 FENDI フェンディ ズッキーノ マンマバケット ショルダーバッグ ワンショルダー ブラウン"),
    ("Chanel wallet", "D4216◆極美品【シャネル】ロングジップウォレット 長財布 カメリア ラムスキン◆シール有 ラウンドファスナー 黒"),
    ("Gucci wallet", "美品　GUCCI グッチDisney ディズニーミッキー 二つ折り財布"),
    ("Lot portefeuilles marques", "COACH コーチ 財布 3点 セット 長財布 二つ折り 花柄 レザー まとめ売"),
])
def test_relecture_25_11_garde(article, titre):
    assert correspond(ARTICLES[article], L(titre, price=60000), EXCL)


# ------------------------------------------------- relecture du 27/11/2026
@pytest.mark.parametrize("article,titre", [
    ("LV Alma", "■美品■ LOUIS VUITTON ルイヴィトン M99370 アルマ 2009年限定 スノードーム オブジェ 置物 インテリア クリア×レッド系 飾り ディスプレイ 中古 HE2452"),
    ("LV Neverfull", "極美品 ルイヴィトン バンドーBB マイネヴァーフル M98330 箱付き"),
    ("LV Keepall", "Louis Vuitton バッグ 4点セット ルイヴィトン クロワッサンGM ミュゼット ランドネPM キーポル45 モノグラム ブランド まとめ売り"),
    ("Sac Céline (autre modèle)", "リバティ セリーヌ × 国産高級ボア フリルトートバッグ ベージュ｜マチ15cm"),
    ("Sac Céline (autre modèle)", "ヴィンテージ セリーヌ 馬車金具 レザー リバーシブル ベルト 2WAY ゴールド バックル ファッション レディース EIE ET37-7【中古】"),
    ("Chanel wallet", "CHANEL シャネル マトラッセ チェーンフォンケースウォレット ショルダーバッグ"),
    ("Dior wallet", "Christian Dior Samantha Thavasa 財布2点"),
])
def test_relecture_27_11_rejette(article, titre):
    assert not correspond(ARTICLES[article], L(titre), EXCL)


@pytest.mark.parametrize("article,titre", [
    ("LV Alma", "1円スタート！【美品】ルイ・ヴィトン モノグラム アルマPM M51130 カデナ(キーなし) LOUIS VUITTON ハンドバッグ"),
    ("LV Neverfull", "加420 LOUIS VUITTON ルイ ヴィトン モノグラム ネヴァーフルMM トートバッグ ショルダートート ショルダーバッグ セミショルダー M40156"),
    ("LV Keepall", "■大人気【LOUIS VUITTON ルイヴィトン モノグラム・キャンバス M41414 キーポル・バンドリエール 55 ショルダーストラップ付 旅行用ボスト"),
    ("Sac Céline (autre modèle)", "CELINE セリーヌ ベルトバッグ ベージュ"),
    ("Chanel wallet", "【箱・Gカード付】CHANEL シャネルキャビアスキン がま口 三つ折り財布 黒"),
    ("Dior wallet", "Dior カナージュ 三つ折り財布　箱・リボン付き"),
])
def test_relecture_27_11_garde(article, titre):
    assert correspond(ARTICLES[article], L(titre, price=60000), EXCL)
