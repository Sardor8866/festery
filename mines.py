import random
import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder

# ID кастомных эмодзи
EMOJI_MINE = "5199988776655443322"  # 💣
EMOJI_GEM = "5199888776655443311"    # 💎
EMOJI_COINS = "5197434882321567830"  # 🪙
EMOJI_BACK = "5906771962734057347"   # ◀️

# Константы
MIN_BET = 0.1
MAX_BET = 10000
MIN_MINES = 2
MAX_MINES = 24
FIELD_SIZE = 5
TOTAL_CELLS = FIELD_SIZE * FIELD_SIZE

# Роутер для мин
mines_router = Router()

# Класс состояний для FSM
class MinesStates(StatesGroup):
    waiting_for_bet = State()
    waiting_for_mines_count = State()
    playing = State()


class MinesGame:
    """Класс для управления игрой в мины"""
    
    def __init__(self, bot, betting_game):
        self.bot = bot
        self.betting_game = betting_game  # Для доступа к балансам
        self.active_games = {}  # user_id -> game_data
        self.multipliers = self._generate_multipliers()
    
    def _generate_multipliers(self):
        """Генерирует таблицу множителей для разного количества мин"""
        multipliers = {}
        for mines in range(MIN_MINES, MAX_MINES + 1):
            # Чем больше мин, тем выше множитель
            # Формула: (общее_клеток / (общее_клеток - мины)) ^ (количество_открытий)
            safe_cells = TOTAL_CELLS - mines
            # Множитель за каждую открытую клетку увеличивается
            multipliers[mines] = []
            current_mult = 1.0
            for cells_opened in range(1, safe_cells + 1):
                # Множитель для открытия клетки
                mult_step = TOTAL_CELLS / (TOTAL_CELLS - mines - cells_opened + 1)
                current_mult *= mult_step
                multipliers[mines].append(round(current_mult, 2))
        return multipliers
    
    def new_game(self, user_id: int, bet: float, mines_count: int):
        """Создает новую игру"""
        if mines_count < MIN_MINES or mines_count > MAX_MINES:
            return False
        
        # Проверяем баланс
        balance = self.betting_game.get_balance(user_id)
        if balance < bet:
            return False
        
        # Списываем ставку
        self.betting_game.update_balance(user_id, -bet)
        
        # Генерируем поле с минами
        all_cells = list(range(TOTAL_CELLS))
        mine_positions = set(random.sample(all_cells, mines_count))
        
        game_data = {
            'bet': bet,
            'mines_count': mines_count,
            'mine_positions': mine_positions,
            'opened_cells': set(),
            'field': [[None for _ in range(FIELD_SIZE)] for _ in range(FIELD_SIZE)],
            'game_over': False,
            'win': False,
            'current_multiplier': 1.0
        }
        
        self.active_games[user_id] = game_data
        return True
    
    def open_cell(self, user_id: int, row: int, col: int):
        """Открывает клетку"""
        game = self.active_games.get(user_id)
        if not game or game['game_over']:
            return None, None
        
        cell_index = row * FIELD_SIZE + col
        
        # Проверяем, не открыта ли уже клетка
        if cell_index in game['opened_cells']:
            return None, None
        
        # Проверяем, не мина ли это
        if cell_index in game['mine_positions']:
            # Проигрыш
            game['game_over'] = True
            game['win'] = False
            return False, game
        
        # Открываем клетку
        game['opened_cells'].add(cell_index)
        opened_count = len(game['opened_cells'])
        
        # Обновляем множитель
        if opened_count <= len(self.multipliers[game['mines_count']]):
            game['current_multiplier'] = self.multipliers[game['mines_count']][opened_count - 1]
        
        # Проверяем победу (открыты все безопасные клетки)
        if opened_count == TOTAL_CELLS - game['mines_count']:
            game['game_over'] = True
            game['win'] = True
            # Начисляем выигрыш
            win_amount = game['bet'] * game['current_multiplier']
            self.betting_game.update_balance(user_id, win_amount)
            return True, game
        
        return True, game
    
    def cashout(self, user_id: int):
        """Забрать выигрыш"""
        game = self.active_games.get(user_id)
        if not game or game['game_over']:
            return False
        
        if len(game['opened_cells']) == 0:
            return False
        
        # Начисляем выигрыш
        win_amount = game['bet'] * game['current_multiplier']
        self.betting_game.update_balance(user_id, win_amount)
        
        game['game_over'] = True
        game['win'] = True
        return win_amount
    
    def get_field_display(self, user_id: int, show_mines: bool = False):
        """Возвращает отображение поля"""
        game = self.active_games.get(user_id)
        if not game:
            return None
        
        keyboard = InlineKeyboardBuilder()
        
        for row in range(FIELD_SIZE):
            row_buttons = []
            for col in range(FIELD_SIZE):
                cell_index = row * FIELD_SIZE + col
                
                if cell_index in game['opened_cells']:
                    # Открытая клетка - безопасна
                    text = f"{EMOJI_GEM}✅"
                elif show_mines and cell_index in game['mine_positions']:
                    # Показываем мину (при проигрыше)
                    text = f"{EMOJI_MINE}💣"
                else:
                    # Закрытая клетка
                    text = "⬜️"
                
                callback_data = f"mines_open_{row}_{col}"
                row_buttons.append(InlineKeyboardButton(text=text, callback_data=callback_data))
            
            keyboard.row(*row_buttons)
        
        # Добавляем кнопки управления
        game_control = []
        if not game['game_over'] and len(game['opened_cells']) > 0:
            game_control.append(InlineKeyboardButton(
                text=f"💰 Забрать {game['current_multiplier']}x",
                callback_data="mines_cashout"
            ))
        
        game_control.append(InlineKeyboardButton(
            text="◀️ Выйти",
            callback_data="mines_exit"
        ))
        
        keyboard.row(*game_control)
        
        return keyboard.as_markup()
    
    def get_game_info(self, user_id: int):
        """Возвращает информацию об игре"""
        game = self.active_games.get(user_id)
        if not game:
            return None
        
        opened = len(game['opened_cells'])
        total_safe = TOTAL_CELLS - game['mines_count']
        remaining = total_safe - opened
        
        return {
            'bet': game['bet'],
            'mines': game['mines_count'],
            'opened': opened,
            'remaining': remaining,
            'multiplier': game['current_multiplier'],
            'potential_win': game['bet'] * game['current_multiplier']
        }


# ========== СОЗДАНИЕ КЛАВИАТУР ==========

def get_mines_count_keyboard():
    """Клавиатура для выбора количества мин"""
    keyboard = InlineKeyboardBuilder()
    
    # Строка 1: 2-7
    row1 = []
    for mines in range(2, 8):
        row1.append(InlineKeyboardButton(
            text=f"{mines} 💣",
            callback_data=f"mines_count_{mines}"
        ))
    keyboard.row(*row1)
    
    # Строка 2: 8-13
    row2 = []
    for mines in range(8, 14):
        row2.append(InlineKeyboardButton(
            text=f"{mines} 💣",
            callback_data=f"mines_count_{mines}"
        ))
    keyboard.row(*row2)
    
    # Строка 3: 14-19
    row3 = []
    for mines in range(14, 20):
        row3.append(InlineKeyboardButton(
            text=f"{mines} 💣",
            callback_data=f"mines_count_{mines}"
        ))
    keyboard.row(*row3)
    
    # Строка 4: 20-24
    row4 = []
    for mines in range(20, 25):
        row4.append(InlineKeyboardButton(
            text=f"{mines} 💣",
            callback_data=f"mines_count_{mines}"
        ))
    keyboard.row(*row4)
    
    # Кнопка назад
    keyboard.row(InlineKeyboardButton(
        text="◀️ Назад в игры",
        callback_data="games"
    ))
    
    return keyboard.as_markup()


# ========== ОБРАБОТЧИКИ ==========

@mines_router.callback_query(F.data == "play_mines")
async def cmd_mines(callback: CallbackQuery, state: FSMContext):
    """Начало игры в мины"""
    await state.clear()
    
    balance = callback.bot.betting_game.get_balance(callback.from_user.id)
    
    await callback.message.edit_text(
        f"<blockquote><b>💣 ИГРА МИНЫ</b></blockquote>\n\n"
        f"<b>Правила игры:</b>\n"
        f"• Поле 5x5 ({TOTAL_CELLS} клеток)\n"
        f"• Выбирайте количество мин от {MIN_MINES} до {MAX_MINES}\n"
        f"• Открывайте клетки и забирайте выигрыш\n"
        f"• Чем больше мин, тем выше множитель\n"
        f"• Наткнулись на мину — проиграли ставку\n\n"
        f"<b>Ваш баланс:</b> <code>{balance:.2f}</code> {EMOJI_COINS}\n\n"
        f"<i>Выберите количество мин:</i>",
        parse_mode="HTML",
        reply_markup=get_mines_count_keyboard()
    )
    await callback.answer()


@mines_router.callback_query(F.data.startswith("mines_count_"))
async def process_mines_count(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора количества мин"""
    mines_count = int(callback.data.split("_")[2])
    
    await state.update_data(mines_count=mines_count)
    await state.set_state(MinesStates.waiting_for_bet)
    
    balance = callback.bot.betting_game.get_balance(callback.from_user.id)
    
    await callback.message.edit_text(
        f"<b>💣 Мины: {mines_count} шт.</b>\n\n"
        f"<b>Ваш баланс:</b> <code>{balance:.2f}</code> {EMOJI_COINS}\n"
        f"<b>Мин. ставка:</b> <code>{MIN_BET}</code> {EMOJI_COINS}\n"
        f"<b>Макс. ставка:</b> <code>{MAX_BET}</code> {EMOJI_COINS}\n\n"
        f"<i>Введите сумму ставки:</i>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="◀️ Назад", callback_data="play_mines")
        ]])
    )
    await callback.answer()


@mines_router.message(MinesStates.waiting_for_bet)
async def process_bet_amount(message, state: FSMContext):
    """Обработка ввода суммы ставки"""
    try:
        bet = float(message.text)
    except ValueError:
        await message.reply("❌ Пожалуйста, введите число")
        return
    
    if bet < MIN_BET or bet > MAX_BET:
        await message.reply(f"❌ Ставка должна быть от {MIN_BET} до {MAX_BET}")
        return
    
    user_data = await state.get_data()
    mines_count = user_data.get('mines_count')
    
    # Создаем игру
    game_created = message.bot.mines_game.new_game(
        message.from_user.id, 
        bet, 
        mines_count
    )
    
    if not game_created:
        await message.reply("❌ Недостаточно средств или неверные параметры")
        await state.clear()
        return
    
    # Показываем поле
    await show_game_field(message, state)


async def show_game_field(message, state: FSMContext):
    """Показывает игровое поле"""
    user_id = message.from_user.id
    game_info = message.bot.mines_game.get_game_info(user_id)
    
    if not game_info:
        await message.reply("❌ Игра не найдена")
        await state.clear()
        return
    
    field_display = message.bot.mines_game.get_field_display(user_id)
    
    await message.answer(
        f"<b>💣 ИГРА МИНЫ</b>\n\n"
        f"<b>Ставка:</b> <code>{game_info['bet']:.2f}</code> {EMOJI_COINS}\n"
        f"<b>Мин:</b> {game_info['mines']} 💣\n"
        f"<b>Открыто:</b> {game_info['opened']}\n"
        f"<b>Осталось безопасных:</b> {game_info['remaining']}\n"
        f"<b>Текущий множитель:</b> {game_info['multiplier']}x\n"
        f"<b>Потенциальный выигрыш:</b> <code>{game_info['potential_win']:.2f}</code> {EMOJI_COINS}\n\n"
        f"<i>Выбирайте клетки:</i>",
        parse_mode="HTML",
        reply_markup=field_display
    )
    
    await state.set_state(MinesStates.playing)


@mines_router.callback_query(F.data.startswith("mines_open_"), MinesStates.playing)
async def open_cell(callback: CallbackQuery, state: FSMContext):
    """Открытие клетки"""
    _, _, row, col = callback.data.split("_")
    row, col = int(row), int(col)
    
    result, game = callback.bot.mines_game.open_cell(callback.from_user.id, row, col)
    
    if result is None:
        await callback.answer("Эта клетка уже открыта!")
        return
    
    game_info = callback.bot.mines_game.get_game_info(callback.from_user.id)
    
    if result is False:
        # Проигрыш
        field_display = callback.bot.mines_game.get_field_display(
            callback.from_user.id, 
            show_mines=True
        )
        
        await callback.message.edit_text(
            f"<b>💣 ВЗОРВАЛОСЬ!</b>\n\n"
            f"<b>Ставка:</b> <code>{game_info['bet']:.2f}</code> {EMOJI_COINS} <b>ПРОИГРАНА</b>\n"
            f"<b>Мин:</b> {game_info['mines']} 💣\n"
            f"<b>Открыто:</b> {game_info['opened']}\n\n"
            f"<i>Попробуйте снова!</i>",
            parse_mode="HTML",
            reply_markup=field_display
        )
        
        # Удаляем игру
        if callback.from_user.id in callback.bot.mines_game.active_games:
            del callback.bot.mines_game.active_games[callback.from_user.id]
        
        await state.clear()
        
    elif result is True and game['game_over'] and game['win']:
        # Победа (открыты все клетки)
        field_display = callback.bot.mines_game.get_field_display(
            callback.from_user.id, 
            show_mines=True
        )
        
        await callback.message.edit_text(
            f"<b>🎉 ПОБЕДА!</b>\n\n"
            f"<b>Выигрыш:</b> <code>{game_info['potential_win']:.2f}</code> {EMOJI_COINS}\n"
            f"<b>Множитель:</b> {game_info['multiplier']}x\n"
            f"<b>Мин:</b> {game_info['mines']} 💣\n"
            f"<b>Открыто клеток:</b> {game_info['opened']}\n\n"
            f"<i>Поздравляем!</i>",
            parse_mode="HTML",
            reply_markup=field_display
        )
        
        # Удаляем игру
        if callback.from_user.id in callback.bot.mines_game.active_games:
            del callback.bot.mines_game.active_games[callback.from_user.id]
        
        await state.clear()
        
    else:
        # Продолжаем игру
        field_display = callback.bot.mines_game.get_field_display(callback.from_user.id)
        
        await callback.message.edit_text(
            f"<b>💣 ИГРА МИНЫ</b>\n\n"
            f"<b>Ставка:</b> <code>{game_info['bet']:.2f}</code> {EMOJI_COINS}\n"
            f"<b>Мин:</b> {game_info['mines']} 💣\n"
            f"<b>Открыто:</b> {game_info['opened']}\n"
            f"<b>Осталось безопасных:</b> {game_info['remaining']}\n"
            f"<b>Текущий множитель:</b> {game_info['multiplier']}x\n"
            f"<b>Потенциальный выигрыш:</b> <code>{game_info['potential_win']:.2f}</code> {EMOJI_COINS}\n\n"
            f"<i>Выбирайте клетки:</i>",
            parse_mode="HTML",
            reply_markup=field_display
        )
    
    await callback.answer()


@mines_router.callback_query(F.data == "mines_cashout", MinesStates.playing)
async def cashout(callback: CallbackQuery, state: FSMContext):
    """Забрать выигрыш"""
    win_amount = callback.bot.mines_game.cashout(callback.from_user.id)
    
    if not win_amount:
        await callback.answer("Нельзя забрать выигрыш сейчас!")
        return
    
    game_info = callback.bot.mines_game.get_game_info(callback.from_user.id)
    field_display = callback.bot.mines_game.get_field_display(
        callback.from_user.id, 
        show_mines=True
    )
    
    await callback.message.edit_text(
        f"<b>💰 ВЫИГРЫШ ЗАБРАН</b>\n\n"
        f"<b>Получено:</b> <code>{win_amount:.2f}</code> {EMOJI_COINS}\n"
        f"<b>Множитель:</b> {game_info['multiplier']}x\n"
        f"<b>Мин:</b> {game_info['mines']} 💣\n"
        f"<b>Открыто клеток:</b> {game_info['opened']}\n\n"
        f"<i>Поздравляем!</i>",
        parse_mode="HTML",
        reply_markup=field_display
    )
    
    # Удаляем игру
    if callback.from_user.id in callback.bot.mines_game.active_games:
        del callback.bot.mines_game.active_games[callback.from_user.id]
    
    await state.clear()
    await callback.answer()


@mines_router.callback_query(F.data == "mines_exit")
async def exit_game(callback: CallbackQuery, state: FSMContext):
    """Выход из игры"""
    # Удаляем игру если есть
    if callback.from_user.id in callback.bot.mines_game.active_games:
        del callback.bot.mines_game.active_games[callback.from_user.id]
    
    await state.clear()
    
    # Возвращаемся в меню игр
    from game import get_games_menu_text
    from main import get_games_menu
    
    await callback.message.edit_text(
        get_games_menu_text(callback.from_user.id),
        parse_mode="HTML",
        reply_markup=get_games_menu(),
        disable_web_page_preview=True
    )
    await callback.answer()


# ========== ИНИЦИАЛИЗАЦИЯ ==========

def setup_mines(bot, betting_game):
    """Инициализация модуля мин"""
    bot.mines_game = MinesGame(bot, betting_game)
    logging.info("Модуль Mines инициализирован")
