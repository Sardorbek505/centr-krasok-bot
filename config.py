"""
Конфигурация бота.
Все чувствительные данные загружаются из переменных окружения (.env).
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ─── Telegram ────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")

# ─── Groq AI ─────────────────────────────────────────────────
GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL: str = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")

# ─── Администратор ────────────────────────────────────────────
# Узнать свой Telegram ID можно у @userinfobot
_admin_raw = os.getenv("ADMIN_TELEGRAM_ID", "")
ADMIN_ID: int | None = int(_admin_raw) if _admin_raw.isdigit() else None

# ─── Настройки диалога ───────────────────────────────────────
MAX_HISTORY_MESSAGES: int = 10
MAX_TOKENS_RESPONSE: int = 800
TEMPERATURE: float = 0.4

# ─── Rate limiting ───────────────────────────────────────────
MAX_REQUESTS_PER_MINUTE: int = 15

# ─── Webhook (для Render / облачного хостинга) ───────────────
# Если WEBHOOK_URL задан — бот запускается в webhook-режиме.
# Иначе — polling (для локального запуска).
WEBHOOK_URL: str = os.getenv("WEBHOOK_URL", "")   # https://your-app.onrender.com
PORT: int = int(os.getenv("PORT", "8080"))


def validate_config() -> None:
    missing = []
    if not TELEGRAM_BOT_TOKEN:
        missing.append("TELEGRAM_BOT_TOKEN")
    if not GROQ_API_KEY:
        missing.append("GROQ_API_KEY")
    if missing:
        raise EnvironmentError(
            f"Отсутствуют переменные окружения: {', '.join(missing)}\n"
            f"Создайте .env файл на основе .env.example"
        )
