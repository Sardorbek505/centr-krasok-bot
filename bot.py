"""
AI Telegram-бот «Центр Красок #1» — Enhanced Version.

Возможности:
  - Текстовые и голосовые сообщения (Groq Whisper)
  - Контекст диалога на пользователя
  - 👍👎 Inline-кнопки оценки ответа
  - Быстрые вопросы на /start
  - /stats — аналитика для администратора
  - SQLite логирование пользователей и оценок
  - Rate limiting

Запуск: python bot.py
"""

import logging
import time
import os
import tempfile
from collections import defaultdict

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatAction, ParseMode
from telegram.ext import (
    Application, MessageHandler, CommandHandler,
    CallbackQueryHandler, ContextTypes, filters,
)
from telegram.error import TelegramError
from groq import AsyncGroq

from config import TELEGRAM_BOT_TOKEN, MAX_REQUESTS_PER_MINUTE, GROQ_API_KEY, ADMIN_ID, validate_config
from ai_handler import ai_handler
from database import init_db, upsert_user, increment_message, save_feedback, get_stats

# ─── Логирование ──────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    level=logging.INFO,
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ─── Groq клиент для Whisper ──────────────────────────────────────────────────
groq_client = AsyncGroq(api_key=GROQ_API_KEY)

# ─── Rate limiter ─────────────────────────────────────────────────────────────
_user_request_times: dict[int, list[float]] = defaultdict(list)

def is_rate_limited(user_id: int) -> bool:
    now = time.time()
    _user_request_times[user_id] = [t for t in _user_request_times[user_id] if now - t < 60.0]
    if len(_user_request_times[user_id]) >= MAX_REQUESTS_PER_MINUTE:
        return True
    _user_request_times[user_id].append(now)
    return False

# ─── Хранилище последних Q&A для фидбека ─────────────────────────────────────
# message_id → (question, answer)
_last_qa: dict[int, tuple[str, str]] = {}

# ─── Клавиатуры ───────────────────────────────────────────────────────────────
QUICK_QUESTIONS_KEYBOARD = InlineKeyboardMarkup([
    [
        InlineKeyboardButton("🎨 Какие краски есть?", callback_data="q_paints"),
        InlineKeyboardButton("📍 Где магазин?",       callback_data="q_address"),
    ],
    [
        InlineKeyboardButton("🚚 Как заказать?",      callback_data="q_order"),
        InlineKeyboardButton("💰 Есть акции?",        callback_data="q_promo"),
    ],
    [
        InlineKeyboardButton("🏷️ Какие бренды?",     callback_data="q_brands"),
        InlineKeyboardButton("📞 Контакты",           callback_data="q_contacts"),
    ],
])

def feedback_keyboard(msg_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("👍 Помогло",     callback_data=f"fb_up_{msg_id}"),
        InlineKeyboardButton("👎 Не помогло",  callback_data=f"fb_down_{msg_id}"),
    ]])

# ─── Быстрые вопросы (callback_data → текст вопроса) ─────────────────────────
QUICK_Q_MAP = {
    "q_paints":   "Какие категории красок и материалов у вас есть?",
    "q_address":  "Где находятся ваши магазины? Адреса и часы работы.",
    "q_order":    "Как оформить заказ и доставку?",
    "q_promo":    "Есть ли сейчас акции или скидки?",
    "q_brands":   "Какие бренды красок представлены в магазине?",
    "q_contacts": "Какие контакты компании? Телефоны и email.",
}

# ─── Тексты ───────────────────────────────────────────────────────────────────
WELCOME_TEXT = (
    "👋 Привет! Я AI-ассистент магазина **«Центр Красок #1»**.\n\n"
    "Отвечаю на вопросы о компании, красках, доставке и многом другом.\n"
    "Пишите текстом или отправьте **голосовое сообщение** 🎙️\n\n"
    "Выберите вопрос или напишите свой 👇"
)

RATE_LIMIT_TEXT = "⏳ Слишком много сообщений. Подождите немного."
ERROR_TEXT = (
    "😔 Произошла ошибка. Попробуйте ещё раз.\n"
    "📞 По срочным вопросам: +7 778 061 5000"
)


# ─── Утилиты ──────────────────────────────────────────────────────────────────
async def transcribe_voice(file_path: str) -> str | None:
    """Распознаёт голосовое через Groq Whisper."""
    try:
        with open(file_path, "rb") as f:
            result = await groq_client.audio.transcriptions.create(
                file=("voice.ogg", f, "audio/ogg"),
                model="whisper-large-v3-turbo",
                language="ru",
                response_format="text",
            )
        return result.strip() if result else None
    except Exception as e:
        logger.error("Whisper error: %s", e)
        return None


async def send_ai_reply(update: Update, user_id: int, question: str) -> None:
    """Получает ответ от AI и отправляет с кнопками оценки."""
    await update.effective_chat.send_action(ChatAction.TYPING)
    answer = await ai_handler.get_response(user_id, question)

    if answer is None:
        await update.effective_message.reply_text(ERROR_TEXT)
        return

    # Отправляем ответ с кнопками оценки
    try:
        sent = await update.effective_message.reply_text(
            answer,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=feedback_keyboard(update.effective_message.message_id),
        )
    except TelegramError:
        sent = await update.effective_message.reply_text(
            answer,
            reply_markup=feedback_keyboard(update.effective_message.message_id),
        )

    # Сохраняем Q&A для возможного фидбека
    _last_qa[update.effective_message.message_id] = (question, answer)


# ─── Команды ──────────────────────────────────────────────────────────────────
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    upsert_user(user.id, user.username, user.first_name)
    ai_handler.clear_history(user.id)
    logger.info("User %d started", user.id)
    # Send welcome image if it exists
    from pathlib import Path as _Path
    welcome_img = _Path(__file__).parent / "welcome.png"
    if welcome_img.exists():
        await update.message.reply_photo(
            photo=welcome_img.open("rb"),
            caption=WELCOME_TEXT,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=QUICK_QUESTIONS_KEYBOARD,
        )
    else:
        await update.message.reply_text(
            WELCOME_TEXT,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=QUICK_QUESTIONS_KEYBOARD,
        )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "ℹ️ **Как пользоваться:**\n\n"
        "Просто напишите вопрос или отправьте голосовое 🎙️\n\n"
        "Например:\n"
        "— Какие краски есть для ванной?\n"
        "— Есть ли краски Dulux?\n"
        "— Как оформить доставку в Шымкент?\n\n"
        "**Команды:**\n"
        "/start — начать заново\n"
        "/reset — сбросить историю диалога\n",
        parse_mode=ParseMode.MARKDOWN,
    )


async def cmd_reset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    ai_handler.clear_history(update.effective_user.id)
    await update.message.reply_text(
        "🔄 История сброшена. Задайте новый вопрос!",
        reply_markup=QUICK_QUESTIONS_KEYBOARD,
    )


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Статистика — только для администратора."""
    user_id = update.effective_user.id
    if ADMIN_ID and user_id != ADMIN_ID:
        await update.message.reply_text("⛔ Нет доступа.")
        return

    s = get_stats()
    total_fb = s["thumbs_up"] + s["thumbs_down"]
    text = (
        "📊 **Статистика бота**\n\n"
        f"👥 Всего пользователей: `{s['total_users']}`\n"
        f"🟢 Активны сегодня: `{s['active_today']}`\n"
        f"💬 Всего сообщений: `{s['total_messages']}`\n"
        f"🎙️ Голосовых: `{s['total_voice']}`\n\n"
        f"**Оценки ответов:**\n"
        f"👍 Полезно: `{s['thumbs_up']}`\n"
        f"👎 Не полезно: `{s['thumbs_down']}`\n"
        f"✅ Удовлетворённость: `{s['satisfaction']}%` "
        f"({'из ' + str(total_fb) + ' оценок' if total_fb else 'нет оценок'})\n"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


# ─── Обработчики сообщений ────────────────────────────────────────────────────
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    text = (update.message.text or "").strip()
    if not text:
        return

    if is_rate_limited(user.id):
        await update.message.reply_text(RATE_LIMIT_TEXT)
        return

    upsert_user(user.id, user.username, user.first_name)
    increment_message(user.id, is_voice=False)
    logger.info("Text user %d: %.80s", user.id, text)
    await send_ai_reply(update, user.id, text)


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user

    if is_rate_limited(user.id):
        await update.message.reply_text(RATE_LIMIT_TEXT)
        return

    logger.info("Voice user %d, %ds", user.id, update.message.voice.duration)
    await update.message.chat.send_action(ChatAction.TYPING)
    status_msg = await update.message.reply_text("🎙️ Распознаю голосовое...")

    tmp_path = None
    try:
        voice_file = await update.message.voice.get_file()
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
            tmp_path = tmp.name
        await voice_file.download_to_drive(tmp_path)

        transcribed = await transcribe_voice(tmp_path)

        if not transcribed:
            await status_msg.edit_text(
                "😔 Не удалось распознать. Попробуйте говорить чётче или напишите текстом."
            )
            return

        logger.info("Whisper user %d: %s", user.id, transcribed)
        await status_msg.edit_text(f"🗣️ _Вы сказали: {transcribed}_",
                                   parse_mode=ParseMode.MARKDOWN)

        upsert_user(user.id, user.username, user.first_name)
        increment_message(user.id, is_voice=True)
        await send_ai_reply(update, user.id, transcribed)

    except Exception as e:
        logger.exception("Voice error user %d: %s", user.id, e)
        await update.message.reply_text(ERROR_TEXT)
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


async def handle_unsupported(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "📝 Отправьте текст или голосовое сообщение 🎙️\n"
        "Спросите о красках, адресах, доставке — помогу!"
    )


# ─── Callback обработчики ─────────────────────────────────────────────────────
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает нажатия на inline-кнопки."""
    query = update.callback_query
    await query.answer()  # Убираем «часики» на кнопке

    user = query.from_user
    data = query.data

    # ── Быстрые вопросы ──
    if data in QUICK_Q_MAP:
        question = QUICK_Q_MAP[data]
        upsert_user(user.id, user.username, user.first_name)
        increment_message(user.id)

        # Показываем выбранный вопрос как сообщение
        await query.message.reply_text(f"❓ {question}")
        await send_ai_reply(update, user.id, question)
        return

    # ── Оценка ответа ──
    if data.startswith("fb_"):
        parts = data.split("_")           # fb_up_12345 или fb_down_12345
        rating = parts[1]                 # 'up' | 'down'
        orig_msg_id = int(parts[2])

        qa = _last_qa.get(orig_msg_id)
        if qa:
            save_feedback(user.id, rating, qa[0], qa[1])

        emoji = "👍" if rating == "up" else "👎"
        thank_text = "Спасибо за оценку!" if rating == "up" else "Спасибо! Постараемся улучшиться."

        # Убираем кнопки оценки после нажатия
        try:
            await query.message.edit_reply_markup(reply_markup=None)
        except TelegramError:
            pass

        await query.message.reply_text(f"{emoji} {thank_text}")


# ─── Глобальный обработчик ошибок ─────────────────────────────────────────────
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Error: %s", context.error, exc_info=context.error)


# ─── Точка входа ──────────────────────────────────────────────────────────────
def main() -> None:
    validate_config()
    init_db()
    logger.info("Starting «Центр Красок #1» AI bot (Enhanced)...")

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Команды
    app.add_handler(CommandHandler("start",  cmd_start))
    app.add_handler(CommandHandler("help",   cmd_help))
    app.add_handler(CommandHandler("reset",  cmd_reset))
    app.add_handler(CommandHandler("stats",  cmd_stats))

    # Сообщения
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.add_handler(MessageHandler(
        filters.PHOTO | filters.Document.ALL | filters.VIDEO |
        filters.Sticker.ALL | filters.AUDIO,
        handle_unsupported,
    ))

    # Inline кнопки
    app.add_handler(CallbackQueryHandler(handle_callback))

    app.add_error_handler(error_handler)

    logger.info("Bot is running. Press Ctrl+C to stop.")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)


if __name__ == "__main__":
    main()
