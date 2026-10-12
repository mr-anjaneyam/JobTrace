#!/usr/bin/env bash
# JobTrace - Runner script for Linux / macOS
set -euo pipefail
cd "$(dirname "$0")"

# Export your keys here (or store in a .env file)
export TELEGRAM_BOT_TOKEN="your-telegram-bot-token"
export TELEGRAM_CHAT_ID="your-telegram-chat-id"
export XKIRO_API_KEY="your-xkiro-or-openai-key"

exec python3 -m jobtrace.main "${@:-run}"
