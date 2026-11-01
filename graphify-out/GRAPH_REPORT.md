# Graph Report - zenmarket-bot  (2026-11-01)

## Corpus Check
- 25 files · ~13,206 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 4 file(s) not represented in the graph (top: (none) 2, .example 1, .service 1)

## Summary
- 384 nodes · 799 edges · 20 communities (11 shown, 9 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 61 edges (avg confidence: 0.9)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- main.py
- Réseau, change et Mercari
- Config articles et frais
- beautifulsoup4>=4.12
- test_discord.py
- Parseur Yahoo et annonces
- Stockage
- steps
- test_bot.py
- ClientZen
- storage.py
- Bot ZenMarket — chasse aux sacs de luxe 24h/24, 100 % gratuit
- PROMPT_CODEX.md
- cryptography>=42
- PyYAML>=6.0
- requests>=2.31
- tzdata>=2024.1
- oracle-zenmarket.sh
- installer.sh

## God Nodes (most connected - your core abstractions)
1. `Listing` - 37 edges
2. `Stockage` - 27 edges
3. `Bot` - 24 edges
4. `Article` - 22 edges
5. `ClientZen` - 18 edges
6. `construire_embeds()` - 12 edges
7. `correspond()` - 12 edges
8. `formater_alerte()` - 12 edges
9. `prix_max_jpy()` - 12 edges
10. `requete()` - 11 edges

## Surprising Connections (you probably didn't know these)
- `test_boutons_de_l_alerte()` --uses--> `BoutonAlerte`  [INFERRED]
  tests/test_discord.py → bot/discord_bot.py
- `test_alerte_inconnue()` --calls--> `ClientZen`  [EXTRACTED]
  tests/test_discord.py → bot/discord_bot.py
- `test_boutons_favori_et_arnaque()` --calls--> `ClientZen`  [EXTRACTED]
  tests/test_discord.py → bot/discord_bot.py
- `test_conversion_texte()` --calls--> `convertir_html()`  [EXTRACTED]
  tests/test_discord.py → bot/discord_bot.py
- `_bot()` --calls--> `Bot`  [EXTRACTED]
  tests/test_bot.py → bot/main.py

## Import Cycles
- None detected.

## Communities (20 total, 9 thin omitted)

### Community 0 - "main.py"
Cohesion: 0.07
Nodes (15): construire(), TauxChange, charger_config(), charger_env(), main(), _stop(), ConsoleNotifier, eur() (+7 more)

### Community 1 - "Réseau, change et Mercari"
Cohesion: 0.10
Nodes (10): nouvelle_session(), requete(), appliquer_details(), _b64url(), convertir(), corps_recherche(), creer_dpop(), MercariSource (+2 more)

### Community 2 - "Config articles et frais"
Cohesion: 0.05
Nodes (41): moyen, tres_bon, articles, achat, doit_contenir, exclure, nom, prix_min_jpy (+33 more)

### Community 4 - "test_discord.py"
Cohesion: 0.08
Nodes (22): ecart_prix_habituel(), BoutonAlerte, construire_embeds(), construire_estimation(), construire_vue(), convertir_html(), eur(), fourchette() (+14 more)

### Community 5 - "Parseur Yahoo et annonces"
Cohesion: 0.15
Nodes (12): analyser_page(), _entier(), _liens(), _listing(), _par_attributs(), _par_json(), _par_liens(), _parcourir_json() (+4 more)

### Community 6 - "Stockage"
Cohesion: 0.14
Nodes (4): Bot, Stockage, test_compteur_panne_persiste(), test_prix_habituel()

### Community 7 - "steps"
Cohesion: 0.07
Nodes (28): concurrency, cancel-in-progress, group, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, jobs, recherche, name (+20 more)

### Community 8 - "test_bot.py"
Cohesion: 0.06
Nodes (35): controler(), correspond(), estimer_etat(), normaliser(), appliquer_seuil_unique(), Article, lire_fourchette(), lire_par_etat() (+27 more)

### Community 10 - "ClientZen"
Cohesion: 0.13
Nodes (6): ClientZen, favoris(), NotifDiscord, lancer_discord(), demarrage(), principal()

### Community 11 - "storage.py"
Cohesion: 0.19
Nodes (3): ajouter(), main(), sans_docstrings()

### Community 12 - "Bot ZenMarket — chasse aux sacs de luxe 24h/24, 100 % gratuit"
Cohesion: 0.29
Nodes (6): Bot ZenMarket — chasse aux sacs de luxe 24h/24, 100 % gratuit, Commandes utiles, Limites à connaître, Étape 1 — Créer ton bot Discord (10 min), Étape 2 — L'héberger 24h/24 sur Oracle Cloud (gratuit), Étape 3 — Régler le bot (`config.yaml`)

## Knowledge Gaps
- **6 isolated node(s):** `DEBIAN_FRONTEND`, `cryptography>=42`, `PyYAML>=6.0`, `requests>=2.31`, `tzdata>=2024.1` (+1 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 155 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **9 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Listing` connect `test_bot.py` to `main.py`, `Réseau, change et Mercari`, `test_discord.py`, `Parseur Yahoo et annonces`, `Stockage`?**
  _High betweenness centrality (0.073) - this node is a cross-community bridge._
- **Are the 13 inferred relationships involving `Listing` (e.g. with `construire()` and `controler()`) actually correct?**
  _`Listing` has 13 INFERRED edges - model-reasoned connections that need verification._
- **What connects `DEBIAN_FRONTEND`, `cryptography>=42`, `PyYAML>=6.0` to the rest of the system?**
  _6 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `main.py` be split into smaller, more focused modules?**
  _Cohesion score 0.07183673469387755 - nodes in this community are weakly interconnected._
- **Why does `Stockage` connect `Stockage` to `main.py`, `test_discord.py`, `test_bot.py`, `ClientZen`, `storage.py`?**
  _High betweenness centrality (0.065) - this node is a cross-community bridge._
- **Are the 2 inferred relationships involving `Stockage` (e.g. with `Bot` and `lancer_discord()`) actually correct?**
  _`Stockage` has 2 INFERRED edges - model-reasoned connections that need verification._
- **Should `Réseau, change et Mercari` be split into smaller, more focused modules?**
  _Cohesion score 0.09848484848484848 - nodes in this community are weakly interconnected._