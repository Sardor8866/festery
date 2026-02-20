import logging
from datetime import datetime, timedelta
from aiogram import Router, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.enums import ParseMode

leaders_router = Router()

# ── ID кастомных эмодзи (из main.py) ──────────────────────────────────────────
EMOJI_LEADERS    = "5440539497383087970"
EMOJI_BACK       = "5906771962734057347"
EMOJI_TROPHY     = "5440539497383087970"   # 🏆  — заменишь на нужный
EMOJI_TURNOVER   = "5197288647275071607"   # оборот
EMOJI_WIN        = "5278467510604160626"   # выигрыш
EMOJI_DEPOSIT    = "5443127283898405358"   # депозит
EMOJI_WITHDRAW   = "5445355530111437729"   # вывод
EMOJI_COIN       = "5197434882321567830"   # монета (USDT)

# ── Типы и периоды ────────────────────────────────────────────────────────────
LEADER_TYPES    = ["turnover", "wins", "deposits", "withdrawals"]
LEADER_PERIODS  = ["today", "yesterday", "week", "month"]

TYPE_LABELS = {
    "turnover":    ("Оборот",    EMOJI_TURNOVER),
    "wins":        ("Выигрыш",   EMOJI_WIN),
    "deposits":    ("Депозиты",  EMOJI_DEPOSIT),
    "withdrawals": ("Выводы",    EMOJI_WITHDRAW),
}

PERIOD_LABELS = {
    "today":     "Сегодня",
    "yesterday": "Вчера",
    "week":      "Неделя",
    "month":     "Месяц",
}

# Медальки для топ-3
MEDALS = {1: "🥇", 2: "🥈", 3: "🥉"}


# ── Хелпер: диапазон дат для периода ─────────────────────────────────────────
def _period_range(period: str):
    now   = datetime.utcnow()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if period == "today":
        return today, now
    elif period == "yesterday":
        return today - timedelta(days=1), today
    elif period == "week":
        return today - timedelta(days=7), now
    elif period == "month":
        return today - timedelta(days=30), now
    return today, now


# ── Получение топ-10 из storage ───────────────────────────────────────────────
def get_top10(storage, leader_type: str, period: str) -> list[dict]:
    """
    Возвращает список из ≤10 записей:
    [{"user_id": int, "name": str, "value": float}, ...]
    отсортированных по убыванию value.

    Адаптируй логику под свою реальную БД / storage.
    Сейчас читаем из storage.users (словарь user_id -> данные пользователя).
    """
    try:
        users_data = storage.users  # dict {user_id: {...}}
    except AttributeError:
        return []

    start_dt, end_dt = _period_range(period)

    results = []
    for uid, data in users_data.items():
        # Определяем нужное поле
        if leader_type == "turnover":
            # Сумма всех ставок за период — если есть история, иначе total
            value = float(data.get("total_bets", 0) or 0)
        elif leader_type == "wins":
            value = float(data.get("total_wins", 0) or 0)
        elif leader_type == "deposits":
            value = float(data.get("total_deposits", 0) or 0)
        elif leader_type == "withdrawals":
            value = float(data.get("total_withdrawals", 0) or 0)
        else:
            value = 0.0

        if value <= 0:
            continue

        name = data.get("first_name") or data.get("username") or f"User {uid}"
        results.append({"user_id": uid, "name": str(name), "value": value})

    results.sort(key=lambda x: x["value"], reverse=True)
    return results[:10]


# ── Клавиатура лидеров ────────────────────────────────────────────────────────
def get_leaders_keyboard(active_type: str, active_period: str) -> InlineKeyboardMarkup:
    def type_btn(t_id: str):
        label, emoji_id = TYPE_LABELS[t_id]
        mark  = "✦ " if t_id == active_type else ""
        return InlineKeyboardButton(
            text=f"{mark}{label}",
            callback_data=f"leaders:{t_id}:{active_period}",
            icon_custom_emoji_id=emoji_id
        )

    def period_btn(p_id: str):
        label = PERIOD_LABELS[p_id]
        mark  = "✦ " if p_id == active_period else ""
        return InlineKeyboardButton(
            text=f"{mark}{label}",
            callback_data=f"leaders:{active_type}:{p_id}"
        )

    return InlineKeyboardMarkup(inline_keyboard=[
        # Ряд 1: типы
        [type_btn("turnover"), type_btn("wins"), type_btn("deposits"), type_btn("withdrawals")],
        # Ряд 2: периоды
        [period_btn("today"), period_btn("yesterday"), period_btn("week"), period_btn("month")],
        # Ряд 3: назад
        [InlineKeyboardButton(
            text="Назад",
            callback_data="back_to_main",
            icon_custom_emoji_id=EMOJI_BACK
        )]
    ])


# ── Текст лидеров ─────────────────────────────────────────────────────────────
def build_leaders_text(storage, leader_type: str, period: str) -> str:
    type_label, type_emoji_id = TYPE_LABELS[leader_type]
    period_label = PERIOD_LABELS[period]
    top = get_top10(storage, leader_type, period)

    header = (
        f'<tg-emoji emoji-id="{EMOJI_LEADERS}">🏆</tg-emoji> '
        f'<b>Таблица лидеров</b>\n'
        f'<blockquote>'
        f'<tg-emoji emoji-id="{type_emoji_id}">⭐</tg-emoji> <b>{type_label}</b> · {period_label}'
        f'</blockquote>\n\n'
    )

    if not top:
        body = '<i>Пока нет данных за выбранный период.</i>\n'
    else:
        lines = []
        for i, entry in enumerate(top, start=1):
            medal = MEDALS.get(i, f"<b>{i}.</b>")
            name  = entry["name"]
            value = entry["value"]
            lines.append(
                f'{medal} <b>{name}</b> — '
                f'<code>{value:,.2f}</code>'
                f'<tg-emoji emoji-id="{EMOJI_COIN}">💰</tg-emoji>'
            )
        body = "\n".join(lines) + "\n"

    return header + body


# ── Хендлер: первый вход (callback_data="leaders") ────────────────────────────
async def show_leaders(callback: CallbackQuery, storage_obj):
    default_type   = "turnover"
    default_period = "today"
    text = build_leaders_text(storage_obj, default_type, default_period)
    kb   = get_leaders_keyboard(default_type, default_period)
    await callback.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)
    await callback.answer()


# ── Хендлер: переключение ─────────────────────────────────────────────────────
@leaders_router.callback_query(F.data.startswith("leaders:"))
async def leaders_switch(callback: CallbackQuery):
    # callback_data = "leaders:{type}:{period}"
    parts = callback.data.split(":")
    if len(parts) != 3:
        await callback.answer()
        return

    _, leader_type, period = parts

    if leader_type not in LEADER_TYPES or period not in LEADER_PERIODS:
        await callback.answer("Неверные параметры", show_alert=True)
        return

    # Импортируем storage из payments (как в main.py)
    try:
        from payments import storage as payment_storage
    except ImportError:
        await callback.answer("Ошибка загрузки данных", show_alert=True)
        return

    try:
        text = build_leaders_text(payment_storage, leader_type, period)
        kb   = get_leaders_keyboard(leader_type, period)
        await callback.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)
    except Exception as e:
        logging.error(f"Leaders error: {e}")

    await callback.answer()
