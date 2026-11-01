"""Alerte Discord au nouveau format (« Components V2 ») : un bloc avec barre de couleur,
galerie de photos en haut, prix, état, vendeur, total livré, boutons, contrôle anti-contrefaçon.
Le même message est envoyé par webhook ou par le bot (API REST).
"""
from __future__ import annotations

from .alerte import ecart_prix_habituel
from .discord_bot import eur, fourchette, jpy, signe

FLAG_COMPONENTS_V2 = 1 << 15
VERT, BLEU, ORANGE, ROUGE = 0x2ECC71, 0x5865F2, 0xE67E22, 0xE74C3C

# Marque affichée et salon Discord, déduits du nom de l'article
MARQUES = [
    ("LV ", "Louis Vuitton", "louis-vuitton"),
    ("Chanel", "Chanel", "chanel"),
    ("Lady Dior", "Dior", "dior"),
    ("Dior", "Dior", "dior"),
    ("Gucci", "Gucci", "gucci"),
    ("Prada", "Prada", "prada"),
    ("Saint Laurent", "Saint Laurent", "saint-laurent"),
    ("Fendi", "Fendi", "fendi"),
    ("Bottega", "Bottega Veneta", "bottega-veneta"),
    ("Céline", "Céline", "celine"),
    ("Sac Céline", "Céline", "celine"),
    ("Chloé", "Chloé", "chloe"),
    ("Coach", "Coach", "coach"),
    ("Jacquemus", "Jacquemus", "jacquemus"),
    ("Burberry", "Burberry", "burberry"),
]


def marque_de(article: str) -> tuple[str, str]:
    """(« Louis Vuitton », « louis-vuitton ») pour « LV Speedy »."""
    for prefixe, nom, salon in MARQUES:
        if article.startswith(prefixe):
            return nom, salon
    return "Autres", "autres-marques"


def est_meilleure_affaire(a: dict, economie_min_pct: float) -> bool:
    """Coût livré au moins X % sous ton prix max, et rien de suspect."""
    vise = a.get("achat_vise")
    if not vise or a.get("signaux"):
        return False
    return (vise[1] - a["cout"]["total"]) / vise[1] * 100 >= economie_min_pct


def _texte(contenu: str) -> dict:
    return {"type": 10, "content": contenu[:3900]}


def _separateur() -> dict:
    return {"type": 14, "divider": True, "spacing": 1}


def payload_v2(a: dict, meilleure: bool = False) -> dict:
    c, vise = a["cout"], a.get("achat_vise")
    if a.get("sans_limite"):
        entete = f"🆕 **{a['article']}** · nouvelle annonce"
    elif a["baisse"]:
        entete = f"📉 **{a['article']}** · baisse de prix"
    elif meilleure:
        entete = f"🔥 **{a['article']}** · meilleure affaire"
    else:
        entete = f"🟢 **{a['article']}** · sous ton prix"
    couleur = ORANGE if a["signaux"] else (ROUGE if meilleure else (VERT if a["sous_fourchette"] else BLEU))

    blocs = [_texte(entete)]
    photos = [p for p in (a.get("photos") or []) if p][:3]
    if photos:
        blocs.append({"type": 12, "items": [{"media": {"url": p}} for p in photos]})
    blocs.append(_separateur())

    dispo = "🟢 Enchère en cours" if a["enchere"] else "🟢 Disponible au Japon"
    lignes = [f"Prix de l'article au Japon · {dispo} · {a['source_nom']}",
              f"# {eur(a['prix_eur'])}  `{jpy(a['prix_jpy'])}`"]
    ecart = ecart_prix_habituel(a)
    if ecart is not None:
        rond = "🔴" if ecart > 0 else "🟢"
        signe_pct = f"+{ecart}" if ecart > 0 else f"{ecart}"
        sens = "au-dessus du" if ecart > 0 else "sous le"
        lignes.append(f"{rond} {signe_pct} % {sens} prix habituel (≈ {eur(a['prix_habituel_eur'])})")
    if a.get("taux_eur_jpy"):
        lignes.append(f"-# Vrai prix demandé par le vendeur, au taux du jour (1 € = {a['taux_eur_jpy']} ¥), sans les frais.")
    icone = {"tres_bon": "🟢", "moyen": "🟠", "mauvais": "🔴"}[a["etat"]]
    lignes.append(f"{icone} **État : {a['etat_libelle'].capitalize()}**")
    if a.get("vendeur_avis"):
        lignes.append(f"👤 Vendeur : {a['vendeur_avis']} avis · {a['vendeur_positif_pct']} % positifs")
    lignes.append("")
    total = f"📦 **Total livré en France : {eur(c['total'])}**"
    if vise:
        ecart = vise[1] - c["total"]
        total += (f" · **{eur(ecart)} sous ton max** ({eur(vise[1])})" if ecart >= 0
                  else f" · {eur(-ecart)} au-dessus de ton max ({eur(vise[1])})")
    lignes.append(total)
    lignes.append(f"-# Article {eur(c['article'])} + ZenMarket {eur(c['zenmarket'])} + port {eur(c['port'])}"
                  f" + douane {eur(c['douane'])} + TVA {eur(c['tva'])} + frais {eur(c['fixes'])}")
    if a.get("revente") and a.get("marge"):
        bas, haut = a["marge"]
        marge = signe(bas) if bas == haut else f"{signe(bas)} à {signe(haut)}"
        lignes.append(f"💶 Revente {fourchette(a['revente'])} → marge estimée **{marge}**")
    if a["enchere"]:
        infos = []
        if a.get("prix_max_jpy"):
            infos.append(f"ne mise pas plus de **{jpy(a['prix_max_jpy'])}**")
        if a.get("temps_restant"):
            infos.append(f"fin dans {a['temps_restant']}")
        if a.get("achat_immediat_jpy"):
            infos.append(f"achat immédiat {jpy(a['achat_immediat_jpy'])}")
        lignes.append("⏳ Enchère : " + " · ".join(infos) if infos else "⏳ Enchère : le prix peut monter")
    if a["source"] == "mercari_shops":
        lignes.append("ℹ️ Mercari Shops : colle le lien « Annonce d'origine » dans ZenMarket (« Ajouter une URL »).")
    blocs.append(_texte("\n".join(lignes)))

    boutons = [{"type": 2, "style": 5, "label": "Commander sur ZenMarket", "emoji": {"name": "🛒"},
                "url": a["url_zenmarket"]}]
    if a.get("url_original"):
        boutons.append({"type": 2, "style": 5, "label": "Annonce d'origine", "emoji": {"name": "🔎"},
                        "url": a["url_original"]})
    blocs.append({"type": 1, "components": boutons})
    blocs.append(_separateur())

    if a["signaux"]:
        controle = "⚠️ **Contrôle anti-contrefaçon : à vérifier**\n" + "\n".join(f"• {s}" for s in a["signaux"])
    else:
        controle = "✅ **Contrôle anti-contrefaçon passé**\n• Rien de suspect dans le titre et le prix"
    blocs.append(_texte(controle + "\nIndicatif : vérifie toujours les photos avant d'acheter."))
    ts = int(a["horodatage"])
    blocs.append(_texte(f"-# 🇯🇵 {a['titre'][:180]}\n"
                        f"-# ✓ Tu commandes sur ZenMarket, qui achète au Japon et t'expédie le colis"
                        f" · 🔍 {a['article']} ({a['source_nom']}) · <t:{ts}:R>"))

    return {"flags": FLAG_COMPONENTS_V2,
            "components": [{"type": 17, "accent_color": couleur, "components": blocs}],
            "allowed_mentions": {"parse": []}}
