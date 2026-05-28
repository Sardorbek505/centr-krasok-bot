"""
AI-обработчик: интеграция с Groq API.
- Управление контекстом диалога на пользователя
- Строгий system prompt для ограничения галлюцинаций
- Обработка ошибок API
"""

import logging
from collections import defaultdict, deque
from typing import Optional

from groq import AsyncGroq, APIError, RateLimitError

from config import GROQ_API_KEY, GROQ_MODEL, MAX_HISTORY_MESSAGES, MAX_TOKENS_RESPONSE, TEMPERATURE
from knowledge_base import COMPANY_KNOWLEDGE

logger = logging.getLogger(__name__)

# ─── System prompt ───────────────────────────────────────────────────────────
SYSTEM_PROMPT = f"""Ты — умный AI-ассистент интернет-магазина «Центр Красок #1» (centr-krasok.kz).
Твоя задача — помогать клиентам и отвечать на их вопросы о компании.

СТРОГИЕ ПРАВИЛА:
1. Отвечай ТОЛЬКО на основе базы знаний, представленной ниже. Не придумывай информацию.
2. Если в базе знаний нет ответа на вопрос — честно скажи об этом и предложи связаться с менеджерами.
3. Отвечай на том языке, на котором пишет пользователь (русский, казахский, английский).
4. Будь дружелюбным, вежливым и профессиональным. Используй живой, естественный язык.
5. Не отвечай на вопросы, не связанные с компанией или её продукцией. Вежливо перенаправь к теме.
6. Не упоминай конкурентов и не сравнивай компанию с другими магазинами.
7. Если вопрос о ценах — указывай, что цены могут меняться, и рекомендуй уточнять на сайте.
8. При вопросах о наличии товара — отправляй на сайт или рекомендуй позвонить.
9. Отвечай кратко и по делу. Не пиши длинных списков без необходимости.
10. Если клиент интересуется покупкой — укажи на сайт и контакты магазина.

КОНТАКТЫ ДЛЯ ПЕРЕНАПРАВЛЕНИЯ:
- Сайт: https://centr-krasok.kz/
- Телефон Алматы: +7 778 061 5000
- Телефон Астана: +7 701 943 5000
- Email: info@centr-krasok.kz

━━━━━━━━━━━━━━━━━━━━━━━━
БАЗА ЗНАНИЙ О КОМПАНИИ:
━━━━━━━━━━━━━━━━━━━━━━━━
{COMPANY_KNOWLEDGE}
━━━━━━━━━━━━━━━━━━━━━━━━
"""

# ─── Хранилище контекста диалогов ────────────────────────────────────────────
# user_id → deque из {"role": ..., "content": ...}
_conversation_history: dict[int, deque] = defaultdict(
    lambda: deque(maxlen=MAX_HISTORY_MESSAGES)
)


class AIHandler:
    """Обёртка над Groq API с управлением контекстом и защитой от галлюцинаций."""

    def __init__(self) -> None:
        self.client = AsyncGroq(api_key=GROQ_API_KEY)

    def add_user_message(self, user_id: int, text: str) -> None:
        """Добавляет сообщение пользователя в историю."""
        _conversation_history[user_id].append({"role": "user", "content": text})

    def add_assistant_message(self, user_id: int, text: str) -> None:
        """Добавляет ответ ассистента в историю."""
        _conversation_history[user_id].append({"role": "assistant", "content": text})

    def clear_history(self, user_id: int) -> None:
        """Очищает историю диалога пользователя."""
        _conversation_history[user_id].clear()

    def get_history(self, user_id: int) -> list[dict]:
        """Возвращает историю диалога в формате для API."""
        return list(_conversation_history[user_id])

    async def get_response(self, user_id: int, user_message: str) -> Optional[str]:
        """
        Отправляет сообщение в Groq и возвращает ответ.
        Возвращает None при критической ошибке.
        """
        # Добавляем сообщение пользователя в историю
        self.add_user_message(user_id, user_message)

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            *self.get_history(user_id),
        ]

        try:
            response = await self.client.chat.completions.create(
                model=GROQ_MODEL,
                messages=messages,
                max_tokens=MAX_TOKENS_RESPONSE,
                temperature=TEMPERATURE,
                stream=False,
            )
            answer = response.choices[0].message.content.strip()

            # Сохраняем ответ в историю
            self.add_assistant_message(user_id, answer)
            return answer

        except RateLimitError:
            logger.warning("Groq rate limit exceeded for user %d", user_id)
            # Убираем последнее сообщение пользователя, т.к. не получили ответ
            _conversation_history[user_id].pop()
            return (
                "⚠️ Сейчас слишком много запросов. Пожалуйста, подождите немного и попробуйте снова."
            )

        except APIError as e:
            logger.error("Groq API error for user %d: %s", user_id, e)
            _conversation_history[user_id].pop()
            return (
                "⚠️ Возникла проблема с AI-сервисом. Попробуйте чуть позже.\n"
                "Или свяжитесь с нами напрямую: +7 778 061 5000"
            )

        except Exception as e:
            logger.exception("Unexpected error in AIHandler.get_response: %s", e)
            _conversation_history[user_id].pop()
            return None


# Синглтон — один экземпляр на всё приложение
ai_handler = AIHandler()
