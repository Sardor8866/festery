import json
import logging
import os
from datetime import datetime
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.enums import ParseMode

# ──────────────────────────────────────────────
#  НАСТРОЙКИ
# ──────────────────────────────────────────────
REFERRAL_PERCENT   = 2        # % от ставки реферала
MIN_REF_WITHDRAWAL = 1.0      # минимальная сумма вывода с реф-баланса (USDT)
REFERRALS_FILE     = "referrals.json"

# Кастомные эмодзи
EMOJI_REF_LINK   = "5906986955911993888"   # 🤝 партнёры
EMOJI_WALLET     = "5443127283898405358"   # 💰
EMOJI_STATS      = "5197288647275071607"   # 📊
EMOJI_USERS      = "5197269100878907942"   # 👥
EMOJI_COIN       = "5197434882321567830"   # 💎 (монета)
EMOJI_BACK       = "5906771962734057347"   # ◀️
EMOJI_SUCCESS    = "5368324170671202286"   # ✅
EMOJI_ERROR      = "5210952531676504517"   # ❌
EMOJI_WITHDRAWAL = "5445355530111437729"   # 📤
EMOJI_GIFT       = "5213452215527677637"   # 🎁
EMOJI_CROWN      = "5440539497383087970"   # 👑
EMOJI_PERCENT    = "5197288647275071607"   # %


# ──────────────────────────────────────────────
#  FSM
# ──────────────────────────────────────────────
class ReferralWithdraw(StatesGroup):
    entering_amount = State()


# ──────────────────────────────────────────────
#  ХРАНИЛИЩЕ РЕФЕРАЛОВ
# ──────────────────────────────────────────────
class ReferralStorage:
    """
    Структура JSON:
    {
      "user_id": {
        "referrer_id": int | null,          ← кто пригласил
        "referrals": [int, ...],            ← кого пригласил
        "ref_balance": float,               ← накопленный реф-баланс
        "total_earned": float,              ← суммарно заработано за всё время
        "total_withdrawn": float,           ← суммарно выведено
        "join_date": "YYYY-MM-DD"
      }
    }
    """

    def __init__(self, filepath: str = REFERRALS_FILE):
        self.filepath = filepath
        self._data: dict = {}
        self._load()

    # ---------- I/O ----------
    def _load(self):
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
            except Exception as e:
                logging.error(f"[ReferralStorage] Ошибка загрузки: {e}")
                self._data = {}

    def _save(self):
        try:
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logging.error(f"[ReferralStorage] Ошибка сохранения: {e}")

    # ---------- Получить / создать запись ----------
    def _get(self, user_id: int) -> dict:
        key = str(user_id)
        if key not in self._data:
            self._data[key] = {
                "referrer_id":     None,
                "referrals":       [],
                "ref_balance":     0.0,
                "total_earned":    0.0,
                "total_withdrawn": 0.0,
                "join_date":       datetime.now().strftime("%Y-%m-%d"),
            }
            self._save()
        return self._data[key]

    # ---------- Публичные методы ----------
    def register_referral(self, new_user_id: int, referrer_id: int) -> bool:
        """
        Привязать нового пользователя к рефереру.
        Возвращает True, если привязка успешна, иначе False.
        """
        if new_user_id == referrer_id:
            return False
        record = self._get(new_user_id)
        if record["referrer_id"] is not None:
            return False          # уже привязан
        referrer_record = self._get(referrer_id)
        if new_user_id in referrer_record["referrals"]:
            return False

        record["referrer_id"] = referrer_id
        referrer_record["referrals"].append(new_user_id)
        self._save()
        logging.info(f"[Referral] {new_user_id} → реферал {referrer_id}")
        return True

    def accrue_commission(self, referral_user_id: int, bet_amount: float) -> float:
        """
        Начислить реферреру {REFERRAL_PERCENT}% от ставки реферала.
        Возвращает начисленную сумму (0.0, если реферрера нет).
        """
        record = self._get(referral_user_id)
        referrer_id = record["referrer_id"]
        if referrer_id is None:
            return 0.0

        commission = round(bet_amount * REFERRAL_PERCENT / 100, 4)
        ref_record = self._get(referrer_id)
        ref_record["ref_balance"]  = round(ref_record["ref_balance"]  + commission, 4)
        ref_record["total_earned"] = round(ref_record["total_earned"] + commission, 4)
        self._save()
        logging.info(f"[Referral] Комиссия {commission} USDT → {referrer_id} (за ставку {referral_user_id})")
        return commission

    def get_ref_balance(self, user_id: int) -> float:
        return self._get(user_id)["ref_balance"]

    def get_stats(self, user_id: int) -> dict:
        r = self._get(user_id)
        return {
            "referrer_id":     r["referrer_id"],
            "referrals_count": len(r["referrals"]),
            "referrals_list":  r["referrals"],
            "ref_balance":     r["ref_balance"],
            "total_earned":    r["total_earned"],
            "total_withdrawn": r["total_withdrawn"],
        }

    def withdraw_ref_balance(self, user_id: int, amount: float) -> bool:
        """Списать сумму с реф-баланса. Возвращает True при успехе."""
        record = self._get(user_id)
        if record["ref_balance"] < amount:
            return False
        record["ref_balance"]     = round(record["ref_balance"]     - amount, 4)
        record["total_withdrawn"] = round(record["total_withdrawn"] + amount, 4)
        self._save()
        return True

    def get_referrer_id(self, user_id: int) -> int | None:
        return self._get(user_id)["referrer_id"]


# ──────────────────────────────────────────────
#  ГЛОБАЛЬНЫЙ ЭКЗЕМПЛЯР  (импортируется везде)
# ──────────────────────────────────────────────
referral_storage = ReferralStorage()

# Бот (устанавливается через setup_referrals)
_bot: Bot | None = None


def setup_referrals(bot: Bot):
    global _bot
    _bot = bot


# ──────────────────────────────────────────────
#  ВСПОМОГАТЕЛЬНЫЕ УТИЛИТЫ
# ──────────────────────────────────────────────
def get_referral_link(user_id: int) -> str:
    """Генерирует реферальную ссылку для бота."""
    # BOT_USERNAME можно задать как переменную окружения или жёстко
    bot_username = os.getenv("BOT_USERNAME", "YourBotUsername")
    return f"https://t.me/{bot_username}?start=ref_{user_id}"


def emoji(eid: str, fallback: str = "•") -> str:
    return f'<tg-emoji emoji-id="{eid}">{fallback}</tg-emoji>'


# ──────────────────────────────────────────────
#  КЛАВИАТУРЫ
# ──────────────────────────────────────────────
def kb_referrals_main(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="📊 Статистика",
                callback_data="ref_stats"
            ),
            InlineKeyboardButton(
                text="💰 Вывести",
                callback_data="ref_withdraw"
            ),
        ],
        [
            InlineKeyboardButton(
                text="🔗 Моя ссылка",
                callback_data="ref_link"
            ),
        ],
        [
            InlineKeyboardButton(
                text="◀️ Назад",
                callback_data="back_to_main",
                icon_custom_emoji_id=EMOJI_BACK
            ),
        ],
    ])


def kb_ref_back() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text="◀️ В реферальный раздел",
            callback_data="referrals",
            icon_custom_emoji_id=EMOJI_BACK
        )
    ]])


def kb_ref_cancel() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text="✖️ Отмена",
            callback_data="referrals",
            icon_custom_emoji_id=EMOJI_BACK
        )
    ]])


# ──────────────────────────────────────────────
#  ТЕКСТЫ
# ──────────────────────────────────────────────
def text_referrals_main(user_id: int) -> str:
    stats = referral_storage.get_stats(user_id)
    link  = get_referral_link(user_id)

    ref_count = stats["referrals_count"]
    if 11 <= ref_count % 100 <= 19:
        ref_word = "рефералов"
    elif ref_count % 10 == 1:
        ref_word = "реферал"
    elif ref_count % 10 in (2, 3, 4):
        ref_word = "реферала"
    else:
        ref_word = "рефералов"

    return (
        f"{emoji(EMOJI_REF_LINK,'🤝')} <b>Реферальная программа</b>\n\n"

        f"<blockquote>"
        f"{emoji(EMOJI_PERCENT,'%')} <b>Ваша комиссия:</b> <code>{REFERRAL_PERCENT}%</code> от каждой ставки реферала\n"
        f"{emoji(EMOJI_USERS,'👥')} <b>Приглашено:</b> <code>{ref_count} {ref_word}</code>\n"
        f"{emoji(EMOJI_WALLET,'💰')} <b>Реф-баланс:</b> <code>{stats['ref_balance']:.4f}</code> {emoji(EMOJI_COIN,'💎')} USDT\n"
        f"{emoji(EMOJI_CROWN,'👑')} <b>Заработано всего:</b> <code>{stats['total_earned']:.4f}</code> {emoji(EMOJI_COIN,'💎')} USDT\n"
        f"{emoji(EMOJI_WITHDRAWAL,'📤')} <b>Выведено:</b> <code>{stats['total_withdrawn']:.4f}</code> {emoji(EMOJI_COIN,'💎')} USDT\n"
        f"</blockquote>\n\n"

        f"<blockquote>"
        f"{emoji(EMOJI_GIFT,'🎁')} <b>Минимальный вывод:</b> <code>{MIN_REF_WITHDRAWAL:.2f} USDT</code>\n"
        f"</blockquote>\n\n"

        f"<blockquote>"
        f"🔗 <b>Ваша ссылка:</b>\n"
        f"<code>{link}</code>"
        f"</blockquote>"
    )


def text_ref_stats(user_id: int) -> str:
    stats = referral_storage.get_stats(user_id)
    refs  = stats["referrals_list"]

    lines = []
    for i, uid in enumerate(refs[:20], 1):          # показываем до 20
        lines.append(f"  <code>{i:02d}.</code> <code>{uid}</code>")

    refs_block = "\n".join(lines) if lines else f"  <i>Рефералов пока нет</i>"
    more = f"\n  <i>... и ещё {len(refs) - 20}</i>" if len(refs) > 20 else ""

    return (
        f"{emoji(EMOJI_STATS,'📊')} <b>Детальная статистика</b>\n\n"

        f"<blockquote>"
        f"{emoji(EMOJI_WALLET,'💰')} Реф-баланс:  <code>{stats['ref_balance']:.4f} USDT</code>\n"
        f"{emoji(EMOJI_CROWN,'👑')} Всего заработано:  <code>{stats['total_earned']:.4f} USDT</code>\n"
        f"{emoji(EMOJI_WITHDRAWAL,'📤')} Всего выведено:  <code>{stats['total_withdrawn']:.4f} USDT</code>\n"
        f"{emoji(EMOJI_USERS,'👥')} Рефералов: <code>{stats['referrals_count']}</code>\n"
        f"</blockquote>\n\n"

        f"<blockquote>"
        f"<b>Список рефералов (ID):</b>\n"
        f"{refs_block}{more}"
        f"</blockquote>"
    )


# ──────────────────────────────────────────────
#  РОУТЕР И ХЭНДЛЕРЫ
# ──────────────────────────────────────────────
referral_router = Router()


# ---------- Главная страница рефералов ----------
@referral_router.callback_query(F.data == "referrals")
async def referrals_main(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        text_referrals_main(callback.from_user.id),
        parse_mode=ParseMode.HTML,
        reply_markup=kb_referrals_main(callback.from_user.id),
        disable_web_page_preview=True
    )
    await callback.answer()


# ---------- Статистика ----------
@referral_router.callback_query(F.data == "ref_stats")
async def ref_stats(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        text_ref_stats(callback.from_user.id),
        parse_mode=ParseMode.HTML,
        reply_markup=kb_ref_back()
    )
    await callback.answer()


# ---------- Ссылка ----------
@referral_router.callback_query(F.data == "ref_link")
async def ref_link(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    link = get_referral_link(callback.from_user.id)
    await callback.message.edit_text(
        f"{emoji(EMOJI_REF_LINK,'🤝')} <b>Ваша реферальная ссылка</b>\n\n"
        f"<blockquote>"
        f"Отправьте эту ссылку друзьям — и получайте <b>{REFERRAL_PERCENT}%</b> "
        f"с каждой их ставки автоматически!\n\n"
        f"🔗 <code>{link}</code>"
        f"</blockquote>\n\n"
        f"<blockquote>"
        f"{emoji(EMOJI_GIFT,'🎁')} <b>Чем больше рефералов — тем больше пассивный доход</b>"
        f"</blockquote>",
        parse_mode=ParseMode.HTML,
        reply_markup=kb_ref_back(),
        disable_web_page_preview=True
    )
    await callback.answer()


# ---------- Запрос суммы вывода ----------
@referral_router.callback_query(F.data == "ref_withdraw")
async def ref_withdraw_start(callback: CallbackQuery, state: FSMContext):
    ref_balance = referral_storage.get_ref_balance(callback.from_user.id)

    if ref_balance < MIN_REF_WITHDRAWAL:
        await callback.answer(
            f"❌ Минимум для вывода: {MIN_REF_WITHDRAWAL} USDT\n"
            f"Ваш баланс: {ref_balance:.4f} USDT",
            show_alert=True
        )
        return

    await state.set_state(ReferralWithdraw.entering_amount)
    await callback.message.edit_text(
        f"{emoji(EMOJI_WITHDRAWAL,'📤')} <b>Вывод реферального баланса</b>\n\n"
        f"<blockquote>"
        f"{emoji(EMOJI_WALLET,'💰')} Доступно: <code>{ref_balance:.4f} USDT</code>\n"
        f"{emoji(EMOJI_GIFT,'🎁')} Минимум: <code>{MIN_REF_WITHDRAWAL:.2f} USDT</code>"
        f"</blockquote>\n\n"
        f"<i>Введите сумму для вывода:</i>",
        parse_mode=ParseMode.HTML,
        reply_markup=kb_ref_cancel()
    )
    await callback.answer()


# ---------- Обработка суммы вывода ----------
@referral_router.message(ReferralWithdraw.entering_amount, F.text)
async def ref_withdraw_amount(message: Message, state: FSMContext):
    try:
        amount = float(message.text.replace(",", ".").strip())
    except ValueError:
        await message.answer(
            f"{emoji(EMOJI_ERROR,'❌')} <b>Неверный формат.</b> Введите число, например: <code>5.00</code>",
            parse_mode=ParseMode.HTML,
            reply_markup=kb_ref_cancel()
        )
        return

    if amount < MIN_REF_WITHDRAWAL:
        await message.answer(
            f"{emoji(EMOJI_ERROR,'❌')} <b>Минимальная сумма вывода:</b> <code>{MIN_REF_WITHDRAWAL:.2f} USDT</code>",
            parse_mode=ParseMode.HTML,
            reply_markup=kb_ref_cancel()
        )
        return

    ref_balance = referral_storage.get_ref_balance(message.from_user.id)
    if amount > ref_balance:
        await message.answer(
            f"{emoji(EMOJI_ERROR,'❌')} <b>Недостаточно средств.</b>\n"
            f"Ваш реф-баланс: <code>{ref_balance:.4f} USDT</code>",
            parse_mode=ParseMode.HTML,
            reply_markup=kb_ref_cancel()
        )
        return

    # Перевод на основной баланс
    success = referral_storage.withdraw_ref_balance(message.from_user.id, amount)
    if not success:
        await message.answer(
            f"{emoji(EMOJI_ERROR,'❌')} Ошибка при выводе. Попробуйте позже.",
            parse_mode=ParseMode.HTML,
            reply_markup=kb_ref_cancel()
        )
        return

    # Зачисляем на основной баланс через payment storage
    try:
        from payments import storage as pay_storage
        pay_storage.add_balance(message.from_user.id, amount)
        new_pay_balance = pay_storage.get_balance(message.from_user.id)

        # Синхронизируем с игровым балансом если доступен
        try:
            from main import betting_game
            if betting_game:
                betting_game.user_balances[message.from_user.id] = new_pay_balance
                betting_game.save_balances()
        except Exception:
            pass

    except Exception as e:
        logging.error(f"[Referral] Ошибка зачисления на основной баланс: {e}")

    await state.clear()
    new_ref_balance = referral_storage.get_ref_balance(message.from_user.id)

    await message.answer(
        f"{emoji(EMOJI_SUCCESS,'✅')} <b>Успешно выведено!</b>\n\n"
        f"<blockquote>"
        f"➕ Переведено на игровой баланс: <code>{amount:.4f} USDT</code>\n"
        f"{emoji(EMOJI_WALLET,'💰')} Остаток реф-баланса: <code>{new_ref_balance:.4f} USDT</code>"
        f"</blockquote>",
        parse_mode=ParseMode.HTML,
        reply_markup=kb_ref_back()
    )

    logging.info(f"[Referral] Пользователь {message.from_user.id} вывел {amount} USDT с реф-баланса")


# ──────────────────────────────────────────────
#  ХЭЛПЕР ДЛЯ НАЧИСЛЕНИЯ КОМИССИИ (вызывается из game.py)
# ──────────────────────────────────────────────
async def notify_referrer_commission(referral_user_id: int, bet_amount: float):
    """
    Начислить комиссию реферреру и уведомить его в ЛС.
    Вызывать после каждой ставки реферала.
    """
    commission = referral_storage.accrue_commission(referral_user_id, bet_amount)
    if commission <= 0 or _bot is None:
        return

    referrer_id = referral_storage.get_referrer_id(referral_user_id)
    if referrer_id is None:
        return

    try:
        await _bot.send_message(
            chat_id=referrer_id,
            text=(
                f"{emoji(EMOJI_GIFT,'🎁')} <b>Реферальная комиссия!</b>\n\n"
                f"<blockquote>"
                f"{emoji(EMOJI_COIN,'💎')} Начислено: <code>+{commission:.4f} USDT</code>\n"
                f"{emoji(EMOJI_WALLET,'💰')} Реф-баланс: <code>{referral_storage.get_ref_balance(referrer_id):.4f} USDT</code>"
                f"</blockquote>"
            ),
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        logging.warning(f"[Referral] Не удалось уведомить реферрера {referrer_id}: {e}")


# ──────────────────────────────────────────────
#  ОБРАБОТКА СТАРТА ПО РЕФЕРАЛЬНОЙ ССЫЛКЕ
#  Подключается к хэндлеру /start в main.py
# ──────────────────────────────────────────────
async def process_start_referral(message: Message, start_param: str) -> bool:
    """
    Проверяет параметр /start и регистрирует реферала.
    Возвращает True, если реферал был успешно привязан.
    Вызывать в начале cmd_start ДО основной логики.
    """
    if not start_param.startswith("ref_"):
        return False

    try:
        referrer_id = int(start_param[4:])
    except ValueError:
        return False

    new_user_id = message.from_user.id
    registered  = referral_storage.register_referral(new_user_id, referrer_id)

    if registered and _bot is not None:
        # Уведомить реферрера о новом реферале
        try:
            await _bot.send_message(
                chat_id=referrer_id,
                text=(
                    f"{emoji(EMOJI_USERS,'👥')} <b>Новый реферал!</b>\n\n"
                    f"<blockquote>"
                    f"Пользователь <code>{new_user_id}</code> зарегистрировался по вашей ссылке.\n"
                    f"Вы будете получать <b>{REFERRAL_PERCENT}%</b> с каждой его ставки."
                    f"</blockquote>"
                ),
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            logging.warning(f"[Referral] Не удалось уведомить реферрера {referrer_id}: {e}")

    return registered
