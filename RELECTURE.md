# Relecture quotidienne du bot ZenMarket (tâche planifiée, chaque soir vers 19 h 35)

Ce fichier est la consigne exacte donnée chaque soir à Claude. Il sert aussi de référence si tu veux la modifier.

## Objectif
Faire progresser le bot chaque jour : repérer les mauvaises alertes de la journée (et celles signalées par
Flavio avec le bouton « ❌ Erreur »), corriger les filtres, vérifier avec les tests, puis écrire le bilan
du soir que le bot publie sur Discord vers 20 h.

## Étapes
1. Attacher le dépôt `Flynti3427/zenmarket-bot` avec accès en écriture (outil add_repo, access « push »),
   le cloner, puis `pip install -r requirements.txt pytest`.
2. Date du jour à l'heure de Paris (`TZ=Europe/Paris date +%F`). Lire le rapport :
   `git fetch origin rapports && git show origin/rapports:rapports/<DATE>.json`.
   S'il n'existe pas, regarder `gh run list -R Flynti3427/zenmarket-bot --workflow bot.yml --limit 10`
   et le signaler dans le bilan.
3. Lire les signalements ouverts : `gh issue list -R Flynti3427/zenmarket-bot --label erreur --state open --json number,title,body`.
4. Pour chaque alerte du rapport, vérifier avec le titre japonais que l'annonce est bien l'article annoncé :
   bonne marque, bon modèle, bon type d'objet (sac / portefeuille / lot), pas un accessoire vendu seul
   (pochette, sangle, cadenas, boîte, cravate…), pas une copie ou un objet « style » (風, タイプ, ノーブランド).
5. Pour chaque erreur trouvée et chaque signalement : faire la plus petite correction possible dans
   `config.yaml` (`exclure`, `doit_contenir`, `doit_contenir_aussi`, `exclusions_globales`), et ajouter un test
   dans `tests/test_relecture.py` avec le vrai titre (la mauvaise annonce ne doit plus correspondre).
   Vérifier aussi que les bonnes alertes du rapport correspondent toujours à leur article.
6. Lancer `python -m pytest -q`. Si une correction casse un test, l'annuler et la noter dans le bilan.
7. `git pull --rebase origin main`, commit, push sur `main`. Fermer chaque signalement corrigé avec un
   commentaire en français qui explique la correction.
8. Écrire le bilan sur la branche `rapports`, fichier `bilans/<DATE>.md`, en français, en Markdown Discord,
   1 800 caractères au plus :
   - `📊 **Bilan du JJ/MM**` : nombre d'alertes, par salon ou par article ;
   - `✅ Corrections` : ce qui a été corrigé, en une ligne chacune ;
   - `⚠️ À voir` : signalements non corrigés, source en panne, rapport manquant ;
   - `📈 Prix observés (30 j)` : pour les articles avec au moins 5 annonces vues, prix livré médian et
     minimum comparés au prix max de Flavio. Montrer les chiffres seulement : **ne jamais proposer de
     changer ses prix**, c'est son choix.
   Commit et push sur `rapports` (`git push origin HEAD:rapports`). Le bot le publie dans les 15 minutes.

## Interdits
- Ne jamais modifier les prix (`achat`, `revente`, `achat_tous_etats`), les réglages autres que les filtres,
  le workflow GitHub, les secrets, ni supprimer d'article.
- Ne jamais envoyer de message Discord soi-même (le bot publie le bilan).
- Ne pas créer d'autre tâche planifiée. Ne pas contourner de protection anti-bot.
- En cas de doute sur une correction, ne pas l'appliquer : la mettre dans « ⚠️ À voir ».
