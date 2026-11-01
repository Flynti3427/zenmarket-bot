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


log = logging.getLogger(__name__)

VERT, BLEU, ROUGE, ORANGE = 0x2ECC71, 0x5865F2, 0xE74C3C, 0xE67E22


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
    """Alerte courte et lisible : le modèle en français, le coût total en gros, 3 infos clés, les photos."""
    c = a["cout"]
    vise = a["achat_vise"]
    if a["baisse"]:
        badge = "📉 BAISSE DE PRIX"
    elif a["sous_fourchette"]:
        badge = "🔥 TRÈS BONNE AFFAIRE"
    else:
        badge = "✅ BONNE AFFAIRE"
    couleur = ORANGE if a["signaux"] else (VERT if a["sous_fourchette"] else BLEU)

    lignes = [f"## 📦 {eur(c['total'])} livré en France",
              f"Ton prix max : **{eur(vise[1]) if vise else '?'}**"
              + (f" → tu économises **{eur(vise[1] - c['total'])}**" if vise else "")]
    if a.get("revente") and a.get("marge"):
        bas, haut = a["marge"]
        marge = signe(bas) if bas == haut else f"{signe(bas)} à {signe(haut)}"
        lignes.append(f"💶 Revente {fourchette(a['revente'])} → marge **{marge}**")
    lignes.append(f"-# Détail : article {eur(c['article'])} + ZenMarket {eur(c['zenmarket'])} + port {eur(c['port'])}"
                  f" + douane {eur(c['douane'])} + TVA {eur(c['tva'])} + frais {eur(c['fixes'])}")

    e = discord.Embed(title=f"{a['article']}", url=a["url_zenmarket"], description="\n".join(lignes),
                      color=couleur, timestamp=datetime.fromtimestamp(a["horodatage"], timezone.utc))
    e.set_author(name=badge)

    icone_etat = {"tres_bon": "🟢", "moyen": "🟠", "mauvais": "🔴"}[a["etat"]]
    e.add_field(name="Prix au Japon", value=f"{jpy(a['prix_jpy'])}\n≈ {eur(a['prix_eur'])}", inline=True)
    e.add_field(name="État", value=f"{icone_etat} {a['etat_libelle'].capitalize()}", inline=True)
    source = a["source_nom"] + ("\n⏳ enchère" if a["enchere"] else "\n🛒 achat direct")
    e.add_field(name="Site", value=source, inline=True)

    if a["enchere"]:
        infos = []
        if a.get("temps_restant"):
            infos.append(f"Fin dans {a['temps_restant']}")
        if a.get("achat_immediat_jpy"):
            infos.append(f"Achat immédiat possible : {jpy(a['achat_immediat_jpy'])}")
        if a.get("prix_max_jpy"):
            infos.append(f"**Ne mise pas plus de {jpy(a['prix_max_jpy'])}**")
        e.add_field(name="⏳ Enchère : le prix peut encore monter", value="\n".join(infos) or "—", inline=False)
    if a.get("vendeur_avis"):
        e.add_field(name="👤 Vendeur", value=f"{a['vendeur_avis']} avis · {a['vendeur_positif_pct']} % positifs",
                    inline=False)
    if a["signaux"]:
        e.add_field(name="⚠️ À vérifier avant d'acheter",
                    value="\n".join(f"• {s}" for s in a["signaux"])[:1000], inline=False)
    if a["source"] == "mercari_shops":
        e.add_field(name="ℹ️ Mercari Shops",
                    value="Colle le lien « Annonce d'origine » dans ZenMarket (« Ajouter une URL »).", inline=False)

    e.set_footer(text=f"🇯🇵 {a['titre'][:150]}")
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
