import random
import logging
from aiogram import Router, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.enums import ParseMode

# ========== ПРОВЕРЕННЫЕ ID ИЗ game.py (для кнопок управления) ==========
EMOJI_BACK   = "5906771962734057347"
EMOJI_GOAL   = "5206607081334906820"
EMOJI_3POINT = "5397782960512444700"
EMOJI_NUMBER = "5456140674028019486"

GRID_SIZE = 5  # 5x5 = 25 клеток

# ========== СКРЫТЫЕ МИНЫ ==========
# Реальное кол-во мин на поле = mines_count + HIDDEN_MINES[mines_count]
# При проигрыше показываем только mines_count мин (без скрытых)
HIDDEN_MINES = {
    2: 1, 3: 1, 4: 2, 5: 2, 6: 2, 7: 2, 8: 2, 9: 2, 10: 2,
    11: 3, 12: 3, 13: 3, 14: 3, 15: 3, 16: 3,
    17: 2, 18: 2, 19: 2, 20: 2, 21: 2,
    22: 1, 23: 0, 24: 0,
}


# Эмодзи ячеек — обычные, без кастомных (в тексте кнопки)
CELL_CLOSED  = "🌑"   # закрытая, не открытая
CELL_GEM     = "💎"   # открытый гем
CELL_MINE    = "💣"   # мина (показывается после проигрыша)
CELL_EXPLODE = "💥"   # мина на которую нажали

# ========== МНОЖИТЕЛИ ==========
MINES_MULTIPLIERS = {
    2:  [1.05, 1.15, 1.26, 1.39, 1.53, 1.7, 1.9, 2.14, 2.42, 2.77, 3.2, 3.73, 4.41, 5.29, 6.47, 8.08, 10.39, 13.86, 19.4, 29.1, 48.5, 97.0, 291.0],
    3:  [1.1, 1.26, 1.45, 1.68, 1.96, 2.3, 2.73, 3.28, 3.98, 4.9, 6.13, 7.8, 10.14, 13.52, 18.59, 26.56, 39.84, 63.74, 111.55, 223.1, 557.75, 2231.0],
    4:  [1.15, 1.39, 1.68, 2.05, 2.53, 3.17, 4.01, 5.16, 6.74, 8.99, 12.26, 17.16, 24.79, 37.18, 58.43, 97.38, 175.29, 350.59, 818.03, 2454.1, 12270.5],
    5:  [1.21, 1.53, 1.96, 2.53, 3.32, 4.43, 6.01, 8.33, 11.8, 17.16, 25.74, 40.04, 65.07, 111.55, 204.51, 409.02, 920.29, 2454.1, 8589.35, 51536.1],
    6:  [1.28, 1.7, 2.3, 3.17, 4.43, 6.33, 9.25, 13.88, 21.45, 34.32, 57.21, 100.11, 185.92, 371.83, 818.03, 2045.08, 6135.25, 24541.0, 171787.0],
    7:  [1.35, 1.9, 2.73, 4.01, 6.01, 9.25, 14.65, 23.98, 40.76, 72.46, 135.86, 271.72, 588.74, 1412.97, 3885.66, 12952.19, 58284.88, 466279.0],
    8:  [1.43, 2.14, 3.28, 5.16, 8.33, 13.88, 23.98, 43.16, 81.52, 163.03, 349.36, 815.17, 2119.45, 6358.35, 23313.95, 116569.75, 1049127.75],
    9:  [1.52, 2.42, 3.98, 6.74, 11.8, 21.45, 40.76, 81.52, 173.22, 395.94, 989.85, 2771.59, 9007.66, 36030.65, 198168.57, 1981685.75],
    10: [1.62, 2.77, 4.9, 8.99, 17.16, 34.32, 72.46, 163.03, 395.94, 1055.84, 3167.53, 11086.35, 48040.87, 288245.2, 3170697.2],
    11: [1.73, 3.2, 6.13, 12.26, 25.74, 57.21, 135.86, 349.36, 989.85, 3167.53, 11878.24, 55431.77, 360306.5, 4323678.0],
    12: [1.87, 3.73, 7.8, 17.16, 40.04, 100.11, 271.72, 815.17, 2771.59, 11086.35, 55431.77, 388022.38, 5044291.0],
    13: [2.02, 4.41, 10.14, 24.79, 65.07, 185.92, 588.74, 2119.45, 9007.66, 48040.87, 360306.5, 5044291.0],
    14: [2.2, 5.29, 13.52, 37.18, 111.55, 371.83, 1412.97, 6358.35, 36030.65, 288245.2, 4323678.0],
    15: [2.42, 6.47, 18.59, 58.43, 204.51, 818.03, 3885.66, 23313.95, 198168.57, 3170697.2],
    16: [2.69, 8.08, 26.56, 97.38, 409.02, 2045.08, 12952.19, 116569.75, 1981685.75],
    17: [3.03, 10.39, 39.84, 175.29, 920.29, 6135.25, 58284.88, 1049127.75],
    18: [3.46, 13.86, 63.74, 350.59, 2454.1, 24541.0, 466279.0],
    19: [4.04, 19.4, 111.55, 818.03, 8589.35, 171787.0],
    20: [4.85, 29.1, 223.1, 2454.1, 51536.1],
    21: [6.06, 48.5, 557.75, 12270.5],
    22: [8.08, 97.0, 2231.0],
    23: [12.12, 291.0],
    24: [24.25],
}


# ========== FSM ==========
class MinesGame(StatesGroup):
    choosing_bet = State()
    playing      = State()


mines_router = Router()
_sessions: dict = {}


# ========== ХЕЛПЕРЫ ==========

def get_multiplier(mines_count: int, gems_opened: int) -> float:
    if gems_opened == 0:
        return 1.0
    mults = MINES_MULTIPLIERS.get(mines_count, [])
    if not mults:
        return 1.0
    return mults[min(gems_opened - 1, len(mults) - 1)]


def get_next_mult(mines_count: int, gems_opened: int) -> float:
    mults = MINES_MULTIPLIERS.get(mines_count, [])
    if not mults or gems_opened >= len(mults):
        return get_multiplier(mines_count, gems_opened)
    return mults[gems_opened]


def generate_board(mines_count: int) -> tuple:
    """Возвращает (board, real_mine_positions)
    board — 25 клеток, True = мина (включая скрытые)
    real_mine_positions — set позиций ТОЛЬКО реальных мин (без скрытых)
    """
    hidden = HIDDEN_MINES.get(mines_count, 0)
    total_mines = mines_count + hidden
    total_mines = min(total_mines, GRID_SIZE * GRID_SIZE - 1)  # защита

    all_positions = random.sample(range(GRID_SIZE * GRID_SIZE), total_mines)
    # Первые mines_count — реальные, остальные — скрытые
    real_positions = set(all_positions[:mines_count])
    hidden_positions = set(all_positions[mines_count:])

    board = [False] * (GRID_SIZE * GRID_SIZE)
    for pos in all_positions:
        board[pos] = True

    return board, real_positions


def build_game_keyboard(session: dict, game_over: bool = False) -> InlineKeyboardMarkup:
    board    = session['board']
    revealed = session['revealed']
    rows = []

    for row in range(GRID_SIZE):
        btn_row = []
        for col in range(GRID_SIZE):
            idx     = row * GRID_SIZE + col
            is_mine = board[idx]
            is_open = revealed[idx]

            real_positions = session.get('real_positions', set())
            is_real_mine = idx in real_positions

            if is_open:
                if is_mine and is_real_mine:
                    # Игрок нажал на реальную мину — взрыв
                    text = CELL_EXPLODE
                else:
                    # Открытый гем ИЛИ скрытая мина (показываем как алмаз)
                    text = CELL_GEM
                cb = "mines_noop"
            elif game_over and is_real_mine:
                # После проигрыша — только реальные мины показываем как мины
                text = CELL_MINE
                cb   = "mines_noop"
            elif game_over:
                # Скрытые мины и безопасные клетки — алмазы
                text = CELL_GEM
                cb   = "mines_noop"
            else:
                text = CELL_CLOSED
                cb   = f"mines_cell_{idx}"

            btn_row.append(InlineKeyboardButton(text=text, callback_data=cb))
        rows.append(btn_row)

    # Управляющие кнопки
    if not game_over:
        gems    = session.get('gems_opened', 0)
        mult    = get_multiplier(session['mines_count'], gems)
        cashout = round(session['bet'] * mult, 2)
        ctrl = []
        if gems > 0:
            ctrl.append(InlineKeyboardButton(
                text=f"Забрать {cashout}",
                callback_data="mines_cashout",
                icon_custom_emoji_id=EMOJI_GOAL
            ))
        ctrl.append(InlineKeyboardButton(
            text="Выйти",
            callback_data="mines_exit",
            icon_custom_emoji_id=EMOJI_BACK
        ))
        rows.append(ctrl)
    else:
        rows.append([
            InlineKeyboardButton(
                text="Снова",
                callback_data="mines_play_again",
                icon_custom_emoji_id=EMOJI_3POINT
            ),
            InlineKeyboardButton(
                text="Выйти",
                callback_data="mines_exit",
                icon_custom_emoji_id=EMOJI_BACK
            ),
        ])

    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_mines_select_keyboard() -> InlineKeyboardMarkup:
    presets = [2, 5, 10, 15, 18]
    row = []
    for m in presets:
        first = MINES_MULTIPLIERS[m][0]
        row.append(InlineKeyboardButton(
            text=f"{m}  x{first}",
            callback_data=f"mines_select_{m}",
            icon_custom_emoji_id=EMOJI_NUMBER
        ))
    return InlineKeyboardMarkup(inline_keyboard=[
        row,
        [InlineKeyboardButton(
            text="Ввести вручную",
            callback_data="mines_manual",
            icon_custom_emoji_id=EMOJI_NUMBER
        )],
        [InlineKeyboardButton(
            text="Назад",
            callback_data="games",
            icon_custom_emoji_id=EMOJI_BACK
        )]
    ])


def game_text(session: dict) -> str:
    mines      = session['mines_count']
    bet        = session['bet']
    gems       = session.get('gems_opened', 0)
    mult       = get_multiplier(mines, gems)
    next_mult  = get_next_mult(mines, gems)
    profit     = round(bet * mult, 2)
    hidden     = HIDDEN_MINES.get(mines, 0)
    total_safe = GRID_SIZE * GRID_SIZE - mines - hidden
    safe_left  = total_safe - gems

    return (
        f"<blockquote><b>💣 Мины</b> | Поле 5×5</blockquote>\n\n"
        f"<blockquote>"
        f"💰 Ставка: <code>{bet}</code>\n"
        f"💣 Мин: <b>{mines}</b>\n"
        f"💎 Открыто: <b>{gems}/{total_safe}</b>\n"
        f"⚡ Текущий: <b>x{mult}</b>\n"
        f"⚡ Следующий: <b>x{next_mult}</b>\n"
        f"💰 К выплате: <code>{profit}</code>"
        f"</blockquote>\n\n"
        f"<i>Безопасных клеток осталось: {safe_left}</i>"
    )


# ========== ПУБЛИЧНАЯ ФУНКЦИЯ ВХОДА ==========

async def show_mines_menu(callback: CallbackQuery, storage, betting_game):
    user_id = callback.from_user.id
    balance = storage.get_balance(user_id)
    text = (
        f"<blockquote><b>💣 Мины</b> — поле 5×5</blockquote>\n\n"
        f"<blockquote>"
        f"💰 Баланс: <code>{balance:.2f}</code>\n\n"
        f"Выберите количество мин.\n"
        f"Рядом — множитель за первый безопасный гем."
        f"</blockquote>"
    )
    await callback.message.edit_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=build_mines_select_keyboard()
    )
    await callback.answer()


# ========== ХЕНДЛЕРЫ ==========

@mines_router.callback_query(F.data.startswith("mines_select_"))
async def mines_select_handler(callback: CallbackQuery, state: FSMContext):
    mines_count = int(callback.data.split("_")[-1])
    await state.update_data(mines_count=mines_count)
    await state.set_state(MinesGame.choosing_bet)

    mults      = MINES_MULTIPLIERS[mines_count]
    total_safe = GRID_SIZE * GRID_SIZE - mines_count

    mult_lines = ""
    for i, m in enumerate(mults):
        mult_lines += f"  Гем {i+1}: <b>x{m}</b>\n"

    text = (
        f"<blockquote>💣 Мин: <b>{mines_count}</b> | Гемов: <b>{total_safe}</b></blockquote>\n\n"
        f"<blockquote><b>Множители по каждому гему:</b>\n{mult_lines}</blockquote>\n\n"
        f"Введите сумму ставки:"
    )
    await callback.message.edit_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(
                text="Назад",
                callback_data="mines_back_select",
                icon_custom_emoji_id=EMOJI_BACK
            )
        ]])
    )
    await callback.answer()


@mines_router.callback_query(F.data == "mines_back_select")
async def mines_back_select(callback: CallbackQuery, state: FSMContext):
    from payments import storage as pay_storage
    await state.clear()
    await show_mines_menu(callback, pay_storage, None)


@mines_router.callback_query(F.data == "mines_manual")
async def mines_manual_handler(callback: CallbackQuery, state: FSMContext):
    """Ввод количества мин вручную"""
    await state.update_data(mines_count=None, waiting_manual=True)
    await state.set_state(MinesGame.choosing_bet)
    await callback.message.edit_text(
        f"<blockquote>💣 <b>Мины</b> — ввод вручную</blockquote>\n\n"
        f"<blockquote>Введите количество мин от <b>2</b> до <b>24</b>:</blockquote>",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(
                text="Назад",
                callback_data="mines_back_select",
                icon_custom_emoji_id=EMOJI_BACK
            )
        ]])
    )
    await callback.answer()


@mines_router.callback_query(F.data == "mines_play_again")
async def mines_play_again(callback: CallbackQuery, state: FSMContext):
    from payments import storage as pay_storage
    _sessions.pop(callback.from_user.id, None)
    await state.clear()
    await show_mines_menu(callback, pay_storage, None)


@mines_router.callback_query(F.data == "mines_exit")
async def mines_exit(callback: CallbackQuery, state: FSMContext):
    from payments import storage as pay_storage
    user_id = callback.from_user.id
    _sessions.pop(user_id, None)
    await state.clear()
    sync_balances = getattr(callback.message, '_sync_balances', None)
    balance = pay_storage.get_balance(user_id)
    from main import get_games_menu, get_games_menu_text
    await callback.message.edit_text(
        get_games_menu_text(user_id),
        parse_mode="HTML",
        reply_markup=get_games_menu()
    )
    await callback.answer()


@mines_router.callback_query(F.data == "mines_noop")
async def mines_noop(callback: CallbackQuery):
    await callback.answer()


@mines_router.callback_query(F.data.startswith("mines_cell_"))
async def mines_cell_handler(callback: CallbackQuery, state: FSMContext):
    from payments import storage as pay_storage
    user_id = callback.from_user.id
    idx     = int(callback.data.split("_")[-1])

    session = _sessions.get(user_id)
    if not session:
        await callback.answer("Игра не найдена. Начните заново.", show_alert=True)
        return

    if session['revealed'][idx]:
        await callback.answer("Уже открыта!")
        return

    session['revealed'][idx] = True

    if session['board'][idx]:
        # МИНА
        mines_count    = session['mines_count']
        bet            = session['bet']
        real_positions = session.get('real_positions', set())

        # Если нажал на СКРЫТУЮ мину — убираем одну реальную из показа
        # чтобы на экране всегда было ровно mines_count мин
        if idx not in real_positions:
            # Скрытая мина — добавляем idx в real_positions вместо одной реальной
            # Убираем случайную реальную мину (она станет алмазом)
            if real_positions:
                remove_one = random.choice(list(real_positions))
                real_positions = (real_positions - {remove_one}) | {idx}
                session['real_positions'] = real_positions

        _sessions.pop(user_id, None)
        await state.clear()

        balance = pay_storage.get_balance(user_id)
        await callback.message.edit_text(
            f"<b>💥 БУМ! Вы попали на мину!</b>\n\n"
            f"<blockquote>"
            f"💣 Мин было: <b>{mines_count}</b>\n"
            f"💰 Проиграно: <code>{bet}</code>\n"
            f"💰 Баланс: <code>{balance:.2f}</code>"
            f"</blockquote>",
            parse_mode=ParseMode.HTML,
            reply_markup=build_game_keyboard(session, game_over=True)
        )
        await callback.answer("💥 Мина!")

    else:
        # ГЕМ
        session['gems_opened'] += 1
        gems        = session['gems_opened']
        mines_count = session['mines_count']
        hidden      = HIDDEN_MINES.get(mines_count, 0)
        total_safe  = GRID_SIZE * GRID_SIZE - mines_count - hidden
        mult        = get_multiplier(mines_count, gems)

        if gems == total_safe:
            # ПОБЕДА
            bet      = session['bet']
            winnings = round(bet * mult, 2)
            pay_storage.add_balance(user_id, winnings)
            _sessions.pop(user_id, None)
            await state.clear()

            balance = pay_storage.get_balance(user_id)
            await callback.message.edit_text(
                f"<b>🏆 ПОБЕДА! Все гемы открыты!</b>\n\n"
                f"<blockquote>"
                f"⚡ Множитель: <b>x{mult}</b>\n"
                f"💰 Выигрыш: <code>{winnings}</code>\n"
                f"💰 Баланс: <code>{balance:.2f}</code>"
                f"</blockquote>",
                parse_mode=ParseMode.HTML,
                reply_markup=build_game_keyboard(session, game_over=True)
            )
            await callback.answer(f"🏆 Победа! +{winnings}")
        else:
            await callback.message.edit_text(
                game_text(session),
                parse_mode=ParseMode.HTML,
                reply_markup=build_game_keyboard(session)
            )
            await callback.answer(f"💎 x{mult}")


@mines_router.callback_query(F.data == "mines_cashout")
async def mines_cashout(callback: CallbackQuery, state: FSMContext):
    from payments import storage as pay_storage
    user_id = callback.from_user.id
    session = _sessions.get(user_id)

    if not session:
        await callback.answer("Игра не найдена.", show_alert=True)
        return

    gems = session.get('gems_opened', 0)
    if gems == 0:
        await callback.answer("Сначала откройте хотя бы одну клетку!", show_alert=True)
        return

    mines_count = session['mines_count']
    bet         = session['bet']
    mult        = get_multiplier(mines_count, gems)
    winnings    = round(bet * mult, 2)

    pay_storage.add_balance(user_id, winnings)
    _sessions.pop(user_id, None)
    await state.clear()

    balance = pay_storage.get_balance(user_id)
    await callback.message.edit_text(
        f"<b>💰 Кэшаут!</b>\n\n"
        f"<blockquote>"
        f"💎 Гемов открыто: <b>{gems}</b>\n"
        f"⚡ Множитель: <b>x{mult}</b>\n"
        f"💰 Выигрыш: <code>{winnings}</code>\n"
        f"💰 Баланс: <code>{balance:.2f}</code>"
        f"</blockquote>",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="Играть снова",
                callback_data="mines_menu",
                icon_custom_emoji_id=EMOJI_3POINT
            )],
            [InlineKeyboardButton(
                text="Игры",
                callback_data="games",
                icon_custom_emoji_id=EMOJI_BACK
            )],
        ])
    )
    await callback.answer(f"💰 +{winnings}!")


# ========== ОБРАБОТКА СТАВКИ (вызов из main.py) ==========

async def process_mines_bet(message: Message, state: FSMContext, storage):
    user_id = message.from_user.id
    data    = await state.get_data()
    mines_count  = data.get('mines_count')
    waiting_manual = data.get('waiting_manual', False)

    # Шаг 1: ждём ввод кол-ва мин вручную
    if waiting_manual and mines_count is None:
        try:
            m = int(message.text.strip())
        except ValueError:
            await message.answer("❌ Введите целое число от 2 до 24.")
            return
        if m < 2 or m > 24:
            await message.answer("❌ Число мин должно быть от 2 до 24.")
            return
        await state.update_data(mines_count=m, waiting_manual=False)
        mults = MINES_MULTIPLIERS[m]
        total_safe = GRID_SIZE * GRID_SIZE - m
        mult_lines = ""
        for i, mv in enumerate(mults):
            mult_lines += f"  Гем {i+1}: <b>x{mv}</b>\n"
        await message.answer(
            f"<blockquote>💣 Мин: <b>{m}</b> | Гемов: <b>{total_safe}</b></blockquote>\n\n"
            f"<blockquote><b>Множители:</b>\n{mult_lines}</blockquote>\n\n"
            f"Введите сумму ставки:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="Назад", callback_data="mines_back_select", icon_custom_emoji_id=EMOJI_BACK)
            ]])
        )
        return

    if mines_count is None:
        await state.clear()
        return

    try:
        bet = float(message.text.replace(',', '.'))
    except ValueError:
        await message.answer("Введите корректную сумму ставки.")
        return

    if bet <= 0:
        await message.answer("❌ Ставка должна быть больше 0.")
        return

    balance = storage.get_balance(user_id)
    if bet > balance:
        await message.answer(
            f"<blockquote><b>❌ Недостаточно средств!</b></blockquote>\n\n"
            f"<blockquote>💰 Баланс: <code>{balance:.2f}</code></blockquote>",
            parse_mode=ParseMode.HTML
        )
        return

    storage.deduct_balance(user_id, bet)

    board, real_positions = generate_board(mines_count)
    session = {
        'board':          board,
        'real_positions': real_positions,
        'revealed':       [False] * (GRID_SIZE * GRID_SIZE),
        'mines_count':    mines_count,
        'bet':            bet,
        'gems_opened':    0,
        'exploded_idx':   -1,
    }
    _sessions[user_id] = session
    await state.set_state(MinesGame.playing)

    await message.answer(
        game_text(session),
        parse_mode=ParseMode.HTML,
        reply_markup=build_game_keyboard(session)
    )
