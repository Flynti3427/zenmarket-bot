"""Alertes Discord avec boutons : Commander sur ZenMarket, Estimation prix total, Favoris, Arnaque.

Le bot Discord reste connecté en permanence (nécessaire pour que les boutons réagissent).
La recherche Mercari/Yahoo tourne à côté, dans un thread, toutes les N minutes.
"""
from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import tasks

from .alerte import ecart_prix_habituel

log = logging.getLogger(__name__)

VERT, BLEU, ROUGE, GRIS = 0x2ECC71, 0x5865F2, 0xE74C3C, 0x95A5A6


def eur(x) -> str:
    return "?" if x is None else f"{x:,.0f} €".replace(",", " ")


def jpy(x) -> str:
    return "?" if x is None else f"{x:,} ¥".replace(",", " ")


def fourchette(f) -> str:
    if not f:
        return "?"
    return eur(f[0]) if f[0] == f[1] else f"{f[0]:.0f}-{eur(f[1])}"


def signe(x) -> str:
    return f"+{eur(x)}" if x >= 0 else f"−{eur(-x)}"


# ------------------------------------------------------------------ affichage
def construire_embeds(a: dict) -> list[discord.Embed]:
    """L'alerte principale + jusqu'à 2 embeds de photos (Discord les affiche en galerie)."""
    statut = "🔥 SOUS ta fourchette" if a["sous_fourchette"] else "✅ dans ta fourchette"
    entete = ("📉 Baisse de prix · " if a["baisse"] else "") + f"{a['article']} · {statut}"
    couleur = ROUGE if a["signaux"] else (VERT if a["sous_fourchette"] else BLEU)

    dispo = "🟢 Enchère en cours" if a["enchere"] else "🟢 Disponible au Japon"
    lignes = [
        f"Prix de l'article au Japon · {dispo} · {a['source_nom']}",
        f"# {eur(a['prix_eur'])}  `{jpy(a['prix_jpy'])}`",
    ]
    ecart = ecart_prix_habituel(a)
    if ecart is not None:
        if ecart > 0:
            lignes.append(f"🔴 +{ecart} % au-dessus du prix habituel (≈ {eur(a['prix_habituel_eur'])})")
        else:
            lignes.append(f"🟢 {ecart} % sous le prix habituel (≈ {eur(a['prix_habituel_eur'])})")
    if a.get("taux_eur_jpy"):
        lignes.append(f"-# Vrai prix demandé par le vendeur, au taux du jour (1 € = {a['taux_eur_jpy']} ¥), sans les frais.")
    if a["enchere"]:
        lignes.append("⏳ Enchère : prix actuel, il peut monter"
                      + (f" · reste {a['temps_restant']}" if a.get("temps_restant") else ""))
        if a.get("achat_immediat_jpy"):
            lignes.append(f"⚡ Achat immédiat : {jpy(a['achat_immediat_jpy'])}")
    icone_etat = {"tres_bon": "🟢", "moyen": "🟠", "mauvais": "🔴"}[a["etat"]]
    lignes.append(f"{icone_etat} **État : {a['etat_libelle']}** ({a['etat_raison']})")
    if a.get("vendeur_avis"):
        lignes.append(f"👤 Vendeur : {a['vendeur_avis']} avis · {a['vendeur_positif_pct']} % positifs")
    lignes.append("")
    lignes.append(f"📦 **Prix total livré en France : {eur(a['cout']['total'])}** "
                  f"(ton prix d'achat : {fourchette(a['achat_vise'])})")
    if a.get("revente") and a.get("marge"):
        bas, haut = a["marge"]
        marge = signe(bas) if bas == haut else f"{signe(bas)} à {signe(haut)}"
        lignes.append(f"💶 Revente {fourchette(a['revente'])} → marge estimée **{marge}**")
    if a["source"] == "mercari_shops":
        lignes.append("ℹ️ Article Mercari Shops : colle le lien d'origine dans ZenMarket (« Ajouter une URL »).")

    e = discord.Embed(title=a["titre"][:250], url=a["url_zenmarket"], description="\n".join(lignes),
                      color=couleur, timestamp=datetime.fromtimestamp(a["horodatage"], timezone.utc))
    e.set_author(name=entete[:250])
    if a["signaux"]:
        e.add_field(name="⚠️ Contrôle anti-contrefaçon : à vérifier",
                    value="\n".join(f"• {s}" for s in a["signaux"])[:1000]
                    + "\nRegarde bien les photos avant d'acheter.", inline=False)
    else:
        e.add_field(name="✅ Contrôle anti-contrefaçon passé",
                    value="• Rien de suspect dans le titre, le prix et le vendeur\n"
                          "Indicatif : vérifie toujours les photos avant d'acheter.", inline=False)
    e.set_footer(text=f"✓ Tu commandes sur ZenMarket, qui achète au Japon et t'expédie le colis · 🔍 {a['source_nom']}")
    photos = a.get("photos") or []
    if photos:
        e.set_image(url=photos[0])
    embeds = [e]
    for p in photos[1:3]:  # même url que l'embed principal -> Discord regroupe en galerie
        embeds.append(discord.Embed(url=a["url_zenmarket"]).set_image(url=p))
    return embeds


def construire_estimation(a: dict) -> discord.Embed:
    c = a["cout"]
    lignes = [
        f"Article : {jpy(a['prix_jpy'])} → **{eur(c['article'])}**",
        f"Frais ZenMarket (800 ¥ + dépôt) : {eur(c['zenmarket'])}",
        f"Port international EMS (estimé) : {eur(c['port'])}",
        f"Droits de douane : {eur(c['douane'])}",
        f"TVA 20 % : {eur(c['tva'])}",
        f"Frais de dossier / forfait : {eur(c['fixes'])}",
        "",
        f"## Total livré en France : {eur(c['total'])}",
        f"Ton prix d'achat (tableau) : {fourchette(a['achat_vise'])}",
    ]
    if a.get("revente") and a.get("marge"):
        lignes.append(f"Revente (tableau) : {fourchette(a['revente'])} → marge "
                      f"{signe(a['marge'][0])} à {signe(a['marge'][1])}")
    if a.get("prix_max_jpy"):
        lignes.append(f"🧮 Prix affiché max à payer : **{jpy(a['prix_max_jpy'])}**")
    if a["enchere"]:
        lignes.append("⏳ Enchère : le prix va sûrement monter, ne mise pas au-dessus du prix max.")
    return discord.Embed(title=f"🧮 Estimation · {a['article']}", description="\n".join(lignes), color=BLEU)


# ------------------------------------------------------------------- boutons
class BoutonAlerte(discord.ui.DynamicItem[discord.ui.Button],
                   template=r"zen:(?P<action>est|fav|arn):(?P<cle>.+)"):
    """Bouton qui fonctionne encore après un redémarrage du bot (identifiant = action + annonce)."""

    STYLES = {
        "est": ("Estimation prix total", "🧮", discord.ButtonStyle.primary),
        "fav": ("Favoris", "🤍", discord.ButtonStyle.secondary),
        "arn": ("Arnaque", "🚫", discord.ButtonStyle.danger),
    }

    def __init__(self, action: str, cle: str):
        label, emoji, style = self.STYLES[action]
        super().__init__(discord.ui.Button(label=label, emoji=emoji, style=style,
                                           custom_id=f"zen:{action}:{cle}"[:100]))
        self.action, self.cle = action, cle

    @classmethod
    async def from_custom_id(cls, interaction, item, match: re.Match):
        return cls(match["action"], match["cle"])

    async def callback(self, interaction: discord.Interaction):
        await interaction.client.gerer_bouton(interaction, self.action, self.cle)


def construire_vue(a: dict) -> discord.ui.View:
    vue = discord.ui.View(timeout=None)
    vue.add_item(discord.ui.Button(label="Commander sur ZenMarket", emoji="🛒",
                                   style=discord.ButtonStyle.link, url=a["url_zenmarket"], row=0))
    vue.add_item(BoutonAlerte("est", a["cle"]))
    vue.add_item(BoutonAlerte("fav", a["cle"]))
    item = BoutonAlerte("arn", a["cle"])
    item.item.row = 1
    vue.add_item(item)
    return vue


# -------------------------------------------------------------------- client
class ClientZen(discord.Client):
    def __init__(self, salon_id: int, stockage, intervalle_min: float):
        super().__init__(intents=discord.Intents.default())
        self.salon_id = salon_id
        self.db = stockage
        self.intervalle_min = intervalle_min
        self.bot = None  # Bot de recherche, branché par lancer()
        self.tree = app_commands.CommandTree(self)
        self._enregistrer_commandes()

    def _enregistrer_commandes(self):
        @self.tree.command(name="favoris", description="Affiche tes annonces mises en favoris")
        async def favoris(interaction: discord.Interaction):
            favs = self.db.favoris()
            if not favs:
                await interaction.response.send_message("Aucun favori pour l'instant. Appuie sur 🤍 sous une alerte.",
                                                        ephemeral=True)
                return
            lignes = [f"• [{a['article']} — {eur(a['cout']['total'])} livré]({a['url_zenmarket']})" for a in favs]
            await interaction.response.send_message(
                embed=discord.Embed(title="❤️ Tes favoris", description="\n".join(lignes)[:4000], color=BLEU),
                ephemeral=True)

    async def setup_hook(self):
        self.add_dynamic_items(BoutonAlerte)
        try:
            await self.tree.sync()
        except discord.HTTPException as e:
            log.warning("Commande /favoris non enregistrée : %s", e)
        self.boucle.change_interval(minutes=self.intervalle_min)
        self.boucle.start()

    async def on_ready(self):
        log.info("Connecté à Discord en tant que %s", self.user)

    @tasks.loop(minutes=15)
    async def boucle(self):
        # La recherche est bloquante (requêtes HTTP) : elle tourne dans un thread à part.
        await asyncio.get_running_loop().run_in_executor(None, self.bot.tour)

    @boucle.before_loop
    async def _attendre_connexion(self):
        await self.wait_until_ready()

    # --------------------------------------------------- envoi depuis le thread
    def _depuis_thread(self, coro) -> bool:
        try:
            return asyncio.run_coroutine_threadsafe(coro, self.loop).result(timeout=60)
        except Exception as e:  # noqa: BLE001
            log.error("Envoi Discord impossible : %s", e)
            return False

    async def _salon(self):
        return self.get_channel(self.salon_id) or await self.fetch_channel(self.salon_id)

    async def _envoyer_alerte(self, a: dict) -> bool:
        salon = await self._salon()
        await salon.send(embeds=construire_embeds(a), view=construire_vue(a))
        return True

    async def _envoyer_texte(self, texte: str) -> bool:
        salon = await self._salon()
        await salon.send(convertir_html(texte)[:2000])
        return True

    # ---------------------------------------------------------------- boutons
    async def gerer_bouton(self, interaction: discord.Interaction, action: str, cle: str):
        a = self.db.alerte(cle)
        if a is None:
            await interaction.response.send_message("Cette alerte est trop ancienne, je n'ai plus ses détails.",
                                                    ephemeral=True)
            return
        if action == "est":
            await interaction.response.send_message(embed=construire_estimation(a), ephemeral=True)
        elif action == "fav":
            ajoute = self.db.basculer_favori(cle)
            msg = ("❤️ Ajouté à tes favoris. Tape **/favoris** pour les revoir." if ajoute
                   else "🤍 Retiré de tes favoris.")
            await interaction.response.send_message(msg, ephemeral=True)
        elif action == "arn":
            self.db.bloquer(cle, "arnaque")
            vendeur = a.get("vendeur_id")
            if vendeur:
                self.db.bloquer(f"vendeur:{a['source']}:{vendeur}", "arnaque")
            await interaction.response.edit_message(
                content="🚫 **Signalé comme arnaque.** "
                        + ("Ce vendeur ne t'enverra plus d'alertes." if vendeur else "Cette annonce est ignorée."))


class NotifDiscord:
    """Interface utilisée par le Bot de recherche (qui tourne dans un autre thread)."""

    def __init__(self, client: ClientZen):
        self.client = client

    def envoyer_alerte(self, a: dict) -> bool:
        return self.client._depuis_thread(self.client._envoyer_alerte(a))

    def envoyer(self, texte: str, photo: str | None = None) -> bool:
        return self.client._depuis_thread(self.client._envoyer_texte(texte))


def convertir_html(texte: str) -> str:
    """Les messages texte du bot sont écrits pour Telegram (HTML) : conversion en Markdown Discord."""
    texte = re.sub(r'<a href="([^"]+)">([^<]+)</a>', r"[\2](\1)", texte)
    texte = re.sub(r"</?b>", "**", texte)
    texte = re.sub(r"</?i>", "*", texte)
    return texte.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"')
