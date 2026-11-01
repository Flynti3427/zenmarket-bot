#!/usr/bin/env bash
# Installation complète du bot ZenMarket sur une VM Ubuntu (Google Cloud e2-micro).
# Usage : bash zenmarket-bot/installer.sh
set -euo pipefail
cd "$(dirname "$0")"
DOSSIER="$(pwd)"

echo "=== 1/5 Installation de Python ==="
sudo apt-get update -qq
sudo apt-get install -y -qq python3-venv curl >/dev/null

echo "=== 2/5 Installation des dépendances (1-2 min) ==="
python3 -m venv .venv
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r requirements.txt

echo "=== 3/5 Configuration Telegram ==="
if [ -f .env ] && grep -q "^TELEGRAM_BOT_TOKEN=[0-9]" .env && ! grep -q "ABCdef" .env; then
  echo "Fichier .env déjà rempli, je le garde."
else
  read -rp "Colle ton TOKEN Telegram (donné par @BotFather) : " TOKEN
  read -rp "Colle ton CHAT ID : " CHAT
  TOKEN="$(echo "$TOKEN" | tr -d '[:space:]')"
  CHAT="$(echo "$CHAT" | tr -d '[:space:]')"
  printf 'TELEGRAM_BOT_TOKEN=%s\nTELEGRAM_CHAT_ID=%s\n' "$TOKEN" "$CHAT" > .env
  chmod 600 .env
fi
# shellcheck disable=SC1091
source .env

echo "=== 4/5 Test d'envoi Telegram ==="
REPONSE="$(curl -s "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
  -d chat_id="${TELEGRAM_CHAT_ID}" -d text="✅ Test réussi : le serveur peut t'envoyer des messages.")"
if ! echo "$REPONSE" | grep -q '"ok":true'; then
  echo "❌ Telegram a refusé le test : $REPONSE"
  echo "   Vérifie le token et le chat ID (as-tu bien envoyé un message à ton bot avant ?)."
  echo "   Puis relance : rm .env && bash installer.sh"
  exit 1
fi
echo "Message de test envoyé, regarde ton téléphone."

echo "=== 5/5 Démarrage permanent du bot ==="
sudo tee /etc/systemd/system/zenmarket-bot.service >/dev/null <<EOF
[Unit]
Description=Bot ZenMarket (surveillance 24/7)
After=network-online.target
Wants=network-online.target

[Service]
User=${USER}
WorkingDirectory=${DOSSIER}
EnvironmentFile=${DOSSIER}/.env
ExecStart=${DOSSIER}/.venv/bin/python -m bot.main
Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload
sudo systemctl enable --now zenmarket-bot
sleep 5
if systemctl is-active --quiet zenmarket-bot; then
  echo ""
  echo "🎉 C'est fini ! Tu vas recevoir « 🤖 Bot ZenMarket démarré » sur Telegram."
  echo "   Le bot tourne 24h/24, même si tu fermes cette fenêtre."
  echo "   Voir ce qu'il fait : journalctl -u zenmarket-bot -f"
else
  echo "❌ Le bot ne démarre pas. Envoie-moi le résultat de : journalctl -u zenmarket-bot -n 50"
  exit 1
fi
