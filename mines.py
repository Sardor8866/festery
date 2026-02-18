import random
import logging
from aiogram import Router, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.enums import ParseMode

# ========== КОНСТАНТЫ ЭМОДЗИ ==========
EMOJI_MINE        = "5307996024738395492"   # 💣 мина
EMOJI_GEM         = "5368324170671202286"   # 💎 гем (открытая безопасная клетка)
EMOJI_CELL        = "5424972470023104089"   # 🟦 закрытая клетка
EMOJI_BOMB_EXP    = "5199885118214255386"   # 💥 взрыв
EMOJI_WIN         = "5440539497383087970"   # 🏆 победа
EMOJI_BACK        = "5906771962734057347"   # ◀️ назад
EMOJI_CASHOUT     = "5443127283898405358"   # 💰 кэшаут
EMOJI_BALANCE     = "5278467510604160626"   # 💵 баланс
EMOJI_CURRENCY    = "5197434882321567830"   # монетка-валюта
EMOJI_MINES_ICON  = "5307996024738395492"   # иконка мин для заголовка
EMOJI_MULTIPLIER  = "5197288647275071607"   # множитель

# ========== МНОЖИТЕЛИ ДЛЯ МИН ==========
# mines_count -> multiplier_per_gem (применяется каждый раз при открытии gem)
MINES_MULTIPLIERS = {
    2:  1.09,
    3:  1.15,
    4:  1.22,
    5:  1.30,
    6:  1.40,
    7:  1.52,
    8:  1.67,
    9:  1.85,
    10: 2.08,
    11: 2.38,
    12: 2.78,
    13: 3.33,
    14: 4.17,
    15: 5.56,
    16: 8.33,
    17: 12.5,
    18: 16.7,
    19: 25.0,
    20: 33.3,
    21: 50.0,
    22: 75.0,
    23: 100.0,
    24: 200.0,
}

GRID_SIZE = 5  # 5x5 = 25 клеток

# ========== FSM ==========
class MinesGame(StatesGroup):
    choosing_mines = State()
    choosing_bet   = State()
    playing        = State()

# ========== РОУТЕР ==========
mines_router = Router()

# ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========

def _te(emoji_id: str, fallback: str) -> str:
    """Кастомный эмодзи тег"""
    return f'<tg-emoji emoji-id="{emoji_id}">{fallback}</tg-emoji>'


def generate_board(mines_count: int) -> list[bool]:
    """Возвращает список 25 bool: True = мина"""
    board = [False] * GRID_SIZE * GRID_SIZE
    mine_positions = random.sample(range(GRID_SIZE * GRID_SIZE), mines_count)
    for pos in mine_positions:
        board[pos] = True
    return board


def get_current_multiplier(mines_count: int, gems_opened: int) -> float:
    """Текущий накопленный множитель"""
    base = MINES_MULTIPLIERS.get(mines_count, 1.09)
    return round(base ** gems_opened, 2) if gems_opened > 0 else 1.0


def build_game_keyboard(session: dict, game_over: bool = False, won: bool = False) -> InlineKeyboardMarkup:
    """Строит клавиатуру игрового поля 5x5"""
    board    = session['board']
    revealed = session['revealed']
    rows = []

    for row in range(GRID_SIZE):
        btn_row = []
        for col in range(GRID_SIZE):
            idx = row * GRID_SIZE + col
            is_mine   = board[idx]
            is_open   = revealed[idx]

            if is_open:
                if is_mine:
                    # Взрыв
                    text = _te(EMOJI_BOMB_EXP, "💥")
                else:
                    text = _te(EMOJI_GEM, "💎")
            elif game_over and is_mine:
                # Показываем все мины после проигрыша
                text = _te(EMOJI_MINE, "💣")
            else:
                text = _te(EMOJI_CELL, "🟦")

            if game_over or not is_open:
                cb = f"mines_cell_{idx}" if not game_over else "mines_noop"
            else:
                cb = "mines_noop"

            btn_row.append(InlineKeyboardButton(text=text, callback_data=cb))
        rows.append(btn_row)

    # Кнопки управления
    if not game_over:
        gems_opened = session.get('gems_opened', 0)
        mult = get_current_multiplier(session['mines_count'], gems_opened)
        bet  = session['bet']
        cashout_amount = round(bet * mult, 2)

        control_row = []
        if gems_opened > 0:
            control_row.append(
                InlineKeyboardButton(
                    text=f"{_te(EMOJI_CASHOUT, '💰')} Забрать {cashout_amount}",
                    callback_data="mines_cashout"
                )
            )
        control_row.append(
            InlineKeyboardButton(
                text=f"{_te(EMOJI_BACK, '◀️')} Выйти",
                callback_data="mines_exit"
            )
        )
        rows.append(control_row)
    else:
        rows.append([
            InlineKeyboardButton(
                text=f"{_te(EMOJI_MINES_ICON, '💣')} Играть снова",
                callback_data="mines_play_again"
            ),
            InlineKeyboardButton(
                text=f"{_te(EMOJI_BACK, '◀️')} Выйти",
                callback_data="mines_exit"
            )
        ])

    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_mines_select_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора количества мин"""
    rows = []
    options = list(range(2, 25))  # 2..24
    row = []
    for i, m in enumerate(options):
        mult = MINES_MULTIPLIERS[m]
        row.append(InlineKeyboardButton(
            text=f"{_te(EMOJI_MINE, '💣')} {m}  ×{mult}",
            callback_data=f"mines_select_{m}"
        ))
        if len(row) == 4 or i == len(options) - 1:
            rows.append(row)
            row = []
    rows.append([InlineKeyboardButton(
        text=f"{_te(EMOJI_BACK, '◀️')} Назад",
        callback_data="games"
    )])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def game_status_text(session: dict) -> str:
    mines  = session['mines_count']
    bet    = session['bet']
    gems   = session.get('gems_opened', 0)
    mult   = get_current_multiplier(mines, gems)
    profit = round(bet * mult, 2)

    return (
        f"<blockquote>{_te(EMOJI_MINES_ICON, '💣')} <b>Мины</b></blockquote>\n\n"
        f"<blockquote>"
        f"{_te(EMOJI_BALANCE, '💵')} Ставка: <code>{bet}</code>{_te(EMOJI_CURRENCY, '🪙')}\n"
        f"{_te(EMOJI_MINE, '💣')} Мин: <b>{mines}</b>\n"
        f"{_te(EMOJI_GEM, '💎')} Открыто: <b>{gems}</b>\n"
        f"{_te(EMOJI_MULTIPLIER, '⚡')} Множитель: <b>×{mult}</b>\n"
        f"{_te(EMOJI_CASHOUT, '💰')} К выплате: <code>{profit}</code>{_te(EMOJI_CURRENCY, '🪙')}"
        f"</blockquote>"
    )


# ========== ХРАНИЛИЩЕ СЕССИЙ ==========
# { user_id: { board, revealed, mines_count, bet, gems_opened } }
_sessions: dict = {}

# ========== ХЕНДЛЕРЫ ==========

async def show_mines_menu(callback: CallbackQuery, storage, betting_game):
    """Показать меню Mines — вызывается из main.py"""
    user_id = callback.from_user.id

    balance = storage.get_balance(user_id)
    text = (
        f"<blockquote>{_te(EMOJI_MINES_ICON, '💣')} <b>Игра Мины</b></blockquote>\n\n"
        f"<blockquote>"
        f"{_te(EMOJI_BALANCE, '💵')} Баланс: <code>{balance:.2f}</code>{_te(EMOJI_CURRENCY, '🪙')}\n\n"
        f"Выберите количество мин на поле 5×5.\n"
        f"Каждая открытая безопасная клетка умножает ставку."
        f"</blockquote>"
    )
    await callback.message.edit_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=build_mines_select_keyboard()
    )
    await callback.answer()


@mines_router.callback_query(F.data.startswith("mines_select_"))
async def mines_select_handler(callback: CallbackQuery, state: FSMContext):
    mines_count = int(callback.data.split("_")[-1])
    await state.update_data(mines_count=mines_count)
    await state.set_state(MinesGame.choosing_bet)

    mult = MINES_MULTIPLIERS[mines_count]
    text = (
        f"<blockquote>{_te(EMOJI_MINES_ICON, '💣')} <b>Мины: {mines_count}</b></blockquote>\n\n"
        f"<blockquote>"
        f"{_te(EMOJI_MULTIPLIER, '⚡')} Базовый множитель за гем: <b>×{mult}</b>\n\n"
        f"Введите сумму ставки:"
        f"</blockquote>"
    )
    await callback.message.edit_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(
                text=f"{_te(EMOJI_BACK, '◀️')} Назад",
                callback_data="mines_back_select"
            )
        ]])
    )
    await callback.answer()


@mines_router.callback_query(F.data == "mines_back_select")
async def mines_back_select(callback: CallbackQuery, state: FSMContext):
    from payments import storage as pay_storage
    await state.clear()
    await show_mines_menu(callback, pay_storage, None)


@mines_router.callback_query(F.data == "mines_play_again")
async def mines_play_again(callback: CallbackQuery, state: FSMContext):
    from payments import storage as pay_storage
    await state.clear()
    await show_mines_menu(callback, pay_storage, None)


@mines_router.callback_query(F.data == "mines_exit")
async def mines_exit(callback: CallbackQuery, state: FSMContext):
    from payments import storage as pay_storage
    user_id = callback.from_user.id
    _sessions.pop(user_id, None)
    await state.clear()

    balance = pay_storage.get_balance(user_id)
    await callback.message.edit_text(
        f"<blockquote>{_te(EMOJI_BACK, '◀️')} Вы вышли из игры Мины</blockquote>\n\n"
        f"<blockquote>{_te(EMOJI_BALANCE, '💵')} Баланс: <code>{balance:.2f}</code>{_te(EMOJI_CURRENCY, '🪙')}</blockquote>",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text=f"{_te(EMOJI_MINES_ICON, '💣')} Играть снова",
                callback_data="mines_menu"
            )],
            [InlineKeyboardButton(
                text=f"{_te(EMOJI_BACK, '◀️')} Игры",
                callback_data="games"
            )]
        ])
    )
    await callback.answer()


@mines_router.callback_query(F.data == "mines_noop")
async def mines_noop(callback: CallbackQuery):
    await callback.answer()


@mines_router.callback_query(F.data.startswith("mines_cell_"))
async def mines_cell_handler(callback: CallbackQuery, state: FSMContext):
    from payments import storage as pay_storage
    user_id = callback.from_user.id
    idx = int(callback.data.split("_")[-1])

    session = _sessions.get(user_id)
    if not session:
        await callback.answer("Игра не найдена. Начните заново.", show_alert=True)
        return

    if session['revealed'][idx]:
        await callback.answer("Клетка уже открыта!")
        return

    session['revealed'][idx] = True

    if session['board'][idx]:
        # МИНА!
        bet = session['bet']
        mines_count = session['mines_count']
        # Списываем ставку (уже списана при старте)
        _sessions.pop(user_id, None)
        await state.clear()

        text = (
            f"<blockquote>{_te(EMOJI_BOMB_EXP, '💥')} <b>БУМ! Вы попали на мину!</b></blockquote>\n\n"
            f"<blockquote>"
            f"{_te(EMOJI_MINE, '💣')} Мин было: <b>{mines_count}</b>\n"
            f"{_te(EMOJI_BALANCE, '💵')} Проиграно: <code>{bet}</code>{_te(EMOJI_CURRENCY, '🪙')}\n"
            f"{_te(EMOJI_BALANCE, '💵')} Баланс: <code>{pay_storage.get_balance(user_id):.2f}</code>{_te(EMOJI_CURRENCY, '🪙')}"
            f"</blockquote>"
        )
        await callback.message.edit_text(
            text,
            parse_mode=ParseMode.HTML,
            reply_markup=build_game_keyboard(
                {**session, 'revealed': session['revealed']},
                game_over=True, won=False
            )
        )
        await callback.answer("💥 Мина!")
    else:
        session['gems_opened'] += 1
        gems = session['gems_opened']
        mines_count = session['mines_count']

        # Проверка победы (все гемы открыты)
        total_gems = GRID_SIZE * GRID_SIZE - mines_count
        if gems == total_gems:
            mult = get_current_multiplier(mines_count, gems)
            bet  = session['bet']
            winnings = round(bet * mult, 2)
            pay_storage.update_balance(user_id, winnings)
            _sessions.pop(user_id, None)
            await state.clear()

            text = (
                f"<blockquote>{_te(EMOJI_WIN, '🏆')} <b>ПОБЕДА! Вы открыли все гемы!</b></blockquote>\n\n"
                f"<blockquote>"
                f"{_te(EMOJI_MULTIPLIER, '⚡')} Множитель: <b>×{mult}</b>\n"
                f"{_te(EMOJI_CASHOUT, '💰')} Выигрыш: <code>{winnings}</code>{_te(EMOJI_CURRENCY, '🪙')}\n"
                f"{_te(EMOJI_BALANCE, '💵')} Баланс: <code>{pay_storage.get_balance(user_id):.2f}</code>{_te(EMOJI_CURRENCY, '🪙')}"
                f"</blockquote>"
            )
            await callback.message.edit_text(
                text,
                parse_mode=ParseMode.HTML,
                reply_markup=build_game_keyboard(
                    {**session, 'revealed': session['revealed']},
                    game_over=True, won=True
                )
            )
            await callback.answer(f"🏆 Победа! +{winnings}")
        else:
            mult = get_current_multiplier(mines_count, gems)
            await callback.message.edit_text(
                game_status_text(session),
                parse_mode=ParseMode.HTML,
                reply_markup=build_game_keyboard(session)
            )
            await callback.answer(f"💎 Гем! ×{mult}")


@mines_router.callback_query(F.data == "mines_cashout")
async def mines_cashout(callback: CallbackQuery, state: FSMContext):
    from payments import storage as pay_storage
    user_id = callback.from_user.id
    session = _sessions.get(user_id)

    if not session:
        await callback.answer("Игра не найдена.", show_alert=True)
        return

    gems  = session.get('gems_opened', 0)
    if gems == 0:
        await callback.answer("Сначала откройте хотя бы одну клетку!", show_alert=True)
        return

    mines_count = session['mines_count']
    bet   = session['bet']
    mult  = get_current_multiplier(mines_count, gems)
    winnings = round(bet * mult, 2)

    pay_storage.update_balance(user_id, winnings)
    _sessions.pop(user_id, None)
    await state.clear()

    balance = pay_storage.get_balance(user_id)
    text = (
        f"<blockquote>{_te(EMOJI_CASHOUT, '💰')} <b>Кэшаут!</b></blockquote>\n\n"
        f"<blockquote>"
        f"{_te(EMOJI_GEM, '💎')} Открыто гемов: <b>{gems}</b>\n"
        f"{_te(EMOJI_MULTIPLIER, '⚡')} Множитель: <b>×{mult}</b>\n"
        f"{_te(EMOJI_CASHOUT, '💰')} Выигрыш: <code>{winnings}</code>{_te(EMOJI_CURRENCY, '🪙')}\n"
        f"{_te(EMOJI_BALANCE, '💵')} Баланс: <code>{balance:.2f}</code>{_te(EMOJI_CURRENCY, '🪙')}"
        f"</blockquote>"
    )
    await callback.message.edit_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text=f"{_te(EMOJI_MINES_ICON, '💣')} Играть снова",
                callback_data="mines_menu"
            )],
            [InlineKeyboardButton(
                text=f"{_te(EMOJI_BACK, '◀️')} Игры",
                callback_data="games"
            )]
        ])
    )
    await callback.answer(f"💰 Выигрыш: {winnings}!")


# ========== ОБРАБОТКА ВВОДА СТАВКИ (текстовое сообщение) ==========
async def process_mines_bet(message: Message, state: FSMContext, storage):
    """Вызывается из main.py при вводе суммы ставки в состоянии MinesGame.choosing_bet"""
    user_id = message.from_user.id
    data = await state.get_data()
    mines_count = data.get('mines_count')

    if mines_count is None:
        await state.clear()
        return

    try:
        bet = float(message.text.replace(',', '.'))
    except ValueError:
        await message.answer("Введите корректную сумму ставки.")
        return

    balance = storage.get_balance(user_id)

    if bet <= 0:
        await message.answer("Ставка должна быть больше 0.")
        return
    if bet > balance:
        await message.answer(
            f"Недостаточно средств.\n"
            f"{_te(EMOJI_BALANCE, '💵')} Баланс: <code>{balance:.2f}</code>{_te(EMOJI_CURRENCY, '🪙')}",
            parse_mode=ParseMode.HTML
        )
        return

    # Списываем ставку
    storage.update_balance(user_id, -bet)

    # Создаём сессию
    board = generate_board(mines_count)
    session = {
        'board':       board,
        'revealed':    [False] * GRID_SIZE * GRID_SIZE,
        'mines_count': mines_count,
        'bet':         bet,
        'gems_opened': 0,
    }
    _sessions[user_id] = session
    await state.set_state(MinesGame.playing)

    await message.answer(
        game_status_text(session),
        parse_mode=ParseMode.HTML,
        reply_markup=build_game_keyboard(session)
    )
