# Bot ZenMarket — chasse aux sacs de luxe 24h/24, 100 % gratuit

Le bot surveille les annonces des onglets **ENCHÈRES (JDirectItems / Yahoo)** et **MERCARI** de ZenMarket,
toutes les ~15 minutes, pour les **45 articles** de ton tableau
« Tableau prix sacs de luxe ». Pour chaque annonce il :

1. vérifie que c'est bien le bon article (pas un dustbag ou un cadenas vendu seul, pas une copie) ;
2. estime l'état : **8/10** (très bon) ou **5/10** (moyen), d'après l'état Mercari officiel, le rang
   « A/AB/B » des boutiques japonaises ou des mots comme 美品 / 使用感 / ジャンク ;
3. calcule le **coût rendu en France** : prix + 800 ¥ ZenMarket + frais de dépôt + port EMS + douane + TVA 20 % ;
4. **t'alerte sur Discord si ce coût est ≤ au haut de la fourchette d'achat 8/10 de ton tableau**
   (ou à son prix unique), quel que soit l'état du sac. En dessous du bas de la fourchette de son
   état, l'alerte dit « 🔥 SOUS ta fourchette ».

Il n'achète jamais rien tout seul : tu vérifies l'authenticité et tu achètes sur ZenMarket.
(Telegram reste possible : secrets `TELEGRAM_BOT_TOKEN` et `TELEGRAM_CHAT_ID` au lieu de `DISCORD_WEBHOOK_URL`.)

Exemple d'alerte :

```
🔥 BONNE AFFAIRE — LV Speedy
ルイヴィトン スピーディ30 美品
🏷 Mercari : 45 000 ¥ (≈ 257 €)
📦 Coût rendu France : 390 €
🔎 État estimé : très bon état (titre contient « 美品 »)
🎯 Prix d'achat du tableau : 400-450 € → 🔥 SOUS ta fourchette
💶 Revente du tableau : 500-550 € → marge estimée +110 € à +160 €
🧮 Prix affiché max à payer : 53 404 ¥
👉 Ouvrir sur ZenMarket · annonce d'origine
```

Chaque matin à 9 h tu reçois aussi un **récap** des annonces les moins chères des dernières 24 h,
y compris pour les articles sans prix dans le tableau (Dior Boston, Dior Trotter, Trouville,
Pochette Accessoires, Coach vintage…).

---

## Étape 1 — Créer le webhook Discord (1 min)

Dans l'appli Discord, sur ton serveur : appui long sur le salon des alertes → **Modifier le salon**
→ **Intégrations** → **Webhooks** → **Nouveau webhook** → nom `Zen Alertes` → **Copier l'URL du webhook**.
Cette URL est secrète : quiconque l'a peut écrire dans ton salon.

Chaque alerte arrive avec 3 photos, le prix en € et en ¥, l'écart avec le prix habituel, l'état,
les avis du vendeur, le détail du prix total livré en France, la marge, un contrôle anti-contrefaçon
et les boutons **🛒 Commander sur ZenMarket** et **🔎 Annonce d'origine**.

## Étape 2 — Le faire tourner 24h/24 avec GitHub Actions (gratuit)

Le bot tourne sur les serveurs de GitHub (aux États-Unis : Yahoo et Mercari accessibles),
un tour toutes les ~15 minutes, gratuit dans un dépôt **public**. L'URL du webhook reste secrète.

1. Le code est dans le dépôt GitHub `zenmarket-bot`.
2. Dans le dépôt : **Settings → Secrets and variables → Actions → New repository secret** :
   Name `DISCORD_WEBHOOK_URL`, Secret = l'URL copiée à l'étape 1.
3. Onglet **Actions** → **Bot ZenMarket** → **Run workflow** pour lancer un premier tour tout de suite.
4. « 🤖 Bot ZenMarket démarré » arrive dans ton salon. Ensuite le bot tourne tout seul.

Bon à savoir :
- GitHub peut décaler un tour de quelques minutes aux heures chargées.
- La mémoire du bot (annonces déjà signalées) est gardée dans le cache GitHub.
- Le bot fait un petit commit tous les 40 jours pour que GitHub ne le mette pas en pause.

### Option avancée : boutons Estimation / Favoris / Arnaque

Ces boutons ont besoin d'un bot Discord connecté en permanence, donc d'un serveur
(Oracle Cloud, Google Cloud…). Tout est prêt : `bot/discord_bot.py` et `deploy/oracle-zenmarket.sh`
(variables `DISCORD_BOT_TOKEN` et `DISCORD_CHANNEL_ID`).

## Étape 3 — Régler le bot (`config.yaml`)

Pour modifier la config : sur GitHub, ouvre `config.yaml` → crayon ✏️ → modifie → **Commit changes**. Le tour suivant utilise la nouvelle config.

- **Prix d'achat (`achat`)** : ce sont tes seuils d'alerte, en **coût rendu France**.
  `tres_bon` = colonne 8/10, `moyen` = colonne 5/10. Pour les modèles du 2e tableau
  (un seul « achat max visé »), le prix vaut pour les deux états.
- **Seuil unique (`seuil_unique_tous_etats: true`)** : chaque sac alerte sous le haut de sa
  fourchette 8/10 (ou son prix unique), **quel que soit l'état**, mauvais compris
  (Speedy 450 €, Keepall 350 €, Neverfull 450 €…). Mets `false` pour revenir aux limites par état.
  `achat_tous_etats: <prix>` sur un article force un autre seuil pour lui seul.
- **Prix de revente (`revente`)** : seulement affichés dans l'alerte pour estimer ta marge.
- `port_eur` dans `profils` : ajuste après ton premier colis réel (40 € pour un sac, 18 € pour un petit article).
- Voir à partir de quel prix japonais le bot alerte : `python -m bot.prix_max`

## Commandes utiles

Sur GitHub (depuis ton téléphone) :

| Action | Où |
|---|---|
| Lancer un tour tout de suite | Actions → Bot ZenMarket → Run workflow |
| Mettre le bot en pause | Actions → Bot ZenMarket → ⋯ → Disable workflow |
| Voir ce qu'il a trouvé | Actions → un tour → « Un tour de recherche » |
| Changer un prix ou un article | `config.yaml` → ✏️ → Commit changes |

Sur un ordinateur (pour tester) : `python -m bot.main --dry-run --once` (alertes affichées à l'écran),
`python -m bot.prix_max` (prix japonais max par article), `python -m pytest` (tests).

## Limites à connaître

- **Petits articles très bon marché** : avec ~18-40 € de port + TVA, un portefeuille LV visé à
  40-50 € ou un Saint-Germain 5/10 visé à 50-70 € doivent coûter presque rien au Japon pour déclencher
  une alerte. Si tu regroupes plusieurs achats dans un même colis ZenMarket, le port par article baisse :
  baisse alors `port_eur` dans `config.yaml`.
- **Enchères Yahoo** : le prix affiché est l'enchère actuelle, il va monter. Ne mise jamais
  au-dessus du « prix affiché max ».
- **Articles Mercari Shops** (boutiques pros) : ZenMarket n'a pas de lien direct, colle l'URL d'origine
  dans « Ajouter une URL » sur ZenMarket.
- L'**état** est une estimation à partir du titre. Regarde toujours les photos.
- Si Mercari ou Yahoo change son site, le bot t'envoie « ⚠️ aucun résultat depuis 3 cycles ».
  Le prompt Codex dans `PROMPT_CODEX.md` sert à le réparer.
- Les frais (douane 3 % sur les sacs, frais de dossier ~15 €) sont des estimations :
  compare avec ta première facture et ajuste `config.yaml`.
