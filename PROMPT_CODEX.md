# Prompt Codex — maintenir et faire évoluer le bot ZenMarket

Ouvre le dossier `zenmarket-bot` dans Codex, remplace `[TÂCHE]` par ce que tu veux
(ex. « Yahoo ne renvoie plus aucun résultat, voici les logs : … » ou
« ajoute Rakuma comme source »), puis colle le bloc ci-dessous.

```
## Objectif
[TÂCHE]

## Contexte (à respecter)
- Projet : bot Python 3.12 qui tourne 24/7 (alertes Discord avec boutons via bot/discord_bot.py : Commander sur ZenMarket, Estimation prix total, Favoris, Arnaque ; /favoris) et surveille Mercari Japon + Yahoo Enchères pour des sacs de luxe d'occasion achetés via ZenMarket, puis revendus sur Vinted. Il n'achète jamais : il envoie des alertes Telegram.
- Avant de modifier quoi que ce soit, lis graphify-out/GRAPH_REPORT.md (carte du code) puis README.md.
- Architecture figée :
  - bot/sources/mercari.py : API api.mercari.jp/v2/entities:search signée par DPoP ES256.
  - bot/sources/yahoo.py : parseur HTML à 3 méthodes de secours (data-auction-*, JSON embarqué, liens /jp/auction/<id>).
  - bot/filters.py : correspondance titre/article et estimation d'état (tres_bon / moyen / mauvais).
  - bot/pricing.py : coût rendu France (800 ¥ ZenMarket, dépôt, port EMS, douane si > 150 €, TVA 20 %).
  - bot/main.py : classe Bot (cycle, déduplication SQLite via bot/storage.py, alertes, récap quotidien, détection de panne).
  - config.yaml : 45 articles, prix d'achat (`achat`) et de revente (`revente`) par état, frais. Tout réglage métier va ici, jamais en dur dans le code.
- Règle d'alerte figée : alerte si le coût rendu France <= haut de la fourchette `achat` la plus haute de l'article (8/10 ou prix unique), quel que soit l'état (réglage `seuil_unique_tous_etats: true`). tres_bon = 8/10, moyen = 5/10.
- Hébergement : GitHub Actions, alertes via DISCORD_WEBHOOK_URL (bot/discord_webhook.py, boutons-liens uniquement). Alternative serveur (boutons interactifs) : deploy/oracle-zenmarket.sh, à regénérer avec deploy/generer_oracle.py. GitHub Actions (dépôt public, .github/workflows/bot.yml, un tour `python -m bot.main --once` toutes les 15 min, mémoire SQLite dans le cache GitHub). Le bot doit rester gratuit : cron >= 15 min, un tour < 25 min, pas de service payant.
- Chaque source renvoie des objets Listing (bot/models.py). Toute nouvelle source DOIT exposer `nom` et `rechercher(mot_cle, prix_min) -> list[Listing]` et construire un lien ZenMarket.
- Les serveurs GitHub sont aux États-Unis (Yahoo Japan bloque l'UE). Ne propose jamais un hébergement en Europe. Ne contourne jamais une protection anti-bot (Cloudflare, CAPTCHA) : la recherche directe sur zenmarket.jp est protégée, le bot lit donc Mercari et Yahoo et renvoie vers ZenMarket.
- Langue du code, des messages et des commentaires : français.

## Périmètre
- Modifie uniquement ce qu'il faut pour la tâche, dans bot/, tests/ et config.yaml.
- Pas de refactorisation, pas de nouvelle fonctionnalité, pas de nouvelle abstraction au-delà de la tâche.
- Ne change pas les formules de bot/pricing.py ni les prix d'achat/revente de config.yaml sauf si la tâche le demande.

## Demande-moi avant de
- ajouter une dépendance à requirements.txt ;
- supprimer un fichier ou changer le schéma SQLite (bot/storage.py) ;
- ajouter un achat, une enchère ou une connexion à un compte (interdit sans mon accord écrit) ;
- envoyer quoi que ce soit sur Discord/Telegram ou lancer le bot sans --dry-run.

## Terminé quand
- `python -m pytest -q` passe entièrement, avec au moins un nouveau test qui couvre la modification (pour un parseur : un extrait HTML/JSON réel en fixture) ;
- `python -m bot.main --dry-run --once` s'exécute sans exception ;
- tu me rends : la liste des fichiers modifiés, la raison de chaque changement en une ligne, la sortie des tests, et ce qui reste à vérifier sur le serveur.
```

🎯 Cible : Codex (GPT-5.6 Sol ou Terra), 💡 Le prompt fige l'architecture et le contrat des sources, et bloque achats, dépendances et envois Telegram derrière ta validation, pour que Codex répare sans casser le reste.

> Ce prompt est pour un outil agentique qui a un vrai accès à ton système. Relis le périmètre, les actions interdites et les conditions d'arrêt avant de le coller, et vérifie que les chemins correspondent bien à ton projet.
