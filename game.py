import asyncio
from aiogram import Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import json
import os
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Конфигурация
MIN_BET = 0.1

# ID кастомных эмодзи
EMOJI_DICE = "5424972470023104089"
EMOJI_BASKETBALL = "5424972470023104089"
EMOJI_FOOTBALL = "5424972470023104089"
EMOJI_DARTS = "5424972470023104089"
EMOJI_BOWLING = "5424972470023104089"
EMOJI_BACK = "5906771962734057347"
EMOJI_WIN = "5199885118214255386"
EMOJI_LOSE = "5906986955911993888"
EMOJI_BALANCE = "5443127283898405358"
EMOJI_PROFILE = "5906581476639513176"
EMOJI_CHECK = "5197269100878907942"
EMOJI_CROSS = "5906949717859230132"
EMOJI_ARROW_UP = "5906856435426279601"
EMOJI_ARROW_DOWN = "5906856429256319396"
EMOJI_TARGET = "5907049601640308729"

# Конфигурации для ставок
DICE_BET_TYPES = {
    'куб_нечет': {'name': '🎲 Нечетное', 'values': [1, 3, 5], 'multiplier': 1.8},
    'куб_чет': {'name': '🎲 Четное', 'values': [2, 4, 6], 'multiplier': 1.8},
    'куб_мал': {'name': '📉 Меньше (1-3)', 'values': [1, 2, 3], 'multiplier': 1.8},
    'куб_бол': {'name': '📈 Больше (4-6)', 'values': [4, 5, 6], 'multiplier': 1.8},
    'куб_2меньше': {'name': '🎲🎲 Оба меньше 4', 'multiplier': 3.6, 'special': 'double_dice'},
    'куб_2больше': {'name': '🎲🎲 Оба больше 3', 'multiplier': 3.6, 'special': 'double_dice'},
    'куб_1': {'name': '1️⃣', 'values': [1], 'multiplier': 4.0},
    'куб_2': {'name': '2️⃣', 'values': [2], 'multiplier': 4.0},
    'куб_3': {'name': '3️⃣', 'values': [3], 'multiplier': 4.0},
    'куб_4': {'name': '4️⃣', 'values': [4], 'multiplier': 4.0},
    'куб_5': {'name': '5️⃣', 'values': [5], 'multiplier': 4.0},
    'куб_6': {'name': '6️⃣', 'values': [6], 'multiplier': 4.0},
}

BASKETBALL_BET_TYPES = {
    'баскет_гол': {'name': '🏀 Гол (2 очка)', 'values': [4, 5], 'multiplier': 1.85},
    'баскет_мимо': {'name': '🏀 Мимо', 'values': [1, 2, 3], 'multiplier': 1.7},
    'баскет_3очка': {'name': '🏀 3-очковый', 'values': [5], 'multiplier': 2.75},
}

FOOTBALL_BET_TYPES = {
    'футбол_гол': {'name': '⚽ Гол', 'values': [4, 5], 'multiplier': 1.3},
    'футбол_мимо': {'name': '⚽ Мимо', 'values': [1, 2, 3], 'multiplier': 1.7},
}

DART_BET_TYPES = {
    'дартс_белое': {'name': '⚪ Белое', 'values': [3, 5], 'multiplier': 1.85},
    'дартс_красное': {'name': '🔴 Красное', 'values': [2, 4], 'multiplier': 1.85},
    'дартс_мимо': {'name': '❌ Мимо', 'values': [1], 'multiplier': 2.2},
    'дартс_центр': {'name': '🎯 Центр', 'values': [6], 'multiplier': 3.35},
}

BOWLING_BET_TYPES = {
    'боулинг_поражение': {'name': '🎳 Поражение', 'values': [], 'multiplier': 1.8, 'special': 'bowling_vs'},
    'боулинг_победа': {'name': '🎳 Победа', 'values': [], 'multiplier': 1.8, 'special': 'bowling_vs'},
    'боулинг_страйк': {'name': '🎳 Страйк', 'values': [6], 'multiplier': 3.75},
}

# Состояния FSM
class BetStates(StatesGroup):
    waiting_for_amount = State()

class BettingGame:
    def __init__(self, bot: Bot):
        self.bot = bot
        self.user_balances = {}
        self.pending_bets = {}
        self.referral_system = None
        self.load_balances()

    def load_balances(self):
        if os.path.exists('balances.json'):
            try:
                with open('balances.json', 'r') as f:
                    data = json.load(f)
                    self.user_balances = {int(k): float(v) for k, v in data.items()}
            except Exception as e:
                logging.error(f"Error loading balances: {e}")
                self.user_balances = {}
        else:
            self.user_balances = {}

    def save_balances(self):
        try:
            data_to_save = {str(k): v for k, v in self.user_balances.items()}
            with open('balances.json', 'w') as f:
                json.dump(data_to_save, f, indent=4)
        except Exception as e:
            logging.error(f"Error saving balances: {e}")

    def get_balance(self, user_id: int) -> float:
        return float(self.user_balances.get(user_id, 0.0))

    def add_balance(self, user_id: int, amount: float) -> float:
        if user_id not in self.user_balances:
            self.user_balances[user_id] = 0.0
        self.user_balances[user_id] += float(amount)
        self.save_balances()
        return self.user_balances[user_id]

    def subtract_balance(self, user_id: int, amount: float) -> bool:
        amount_float = float(amount)
        if self.get_balance(user_id) >= amount_float:
            self.user_balances[user_id] = max(0, self.user_balances.get(user_id, 0) - amount_float)
            self.save_balances()
            return True
        return False

    def get_bet_config(self, bet_type: str):
        """Получить конфигурацию ставки по типу"""
        if bet_type.startswith('куб_'):
            return DICE_BET_TYPES.get(bet_type)
        elif bet_type.startswith('баскет_'):
            return BASKETBALL_BET_TYPES.get(bet_type)
        elif bet_type.startswith('футбол_'):
            return FOOTBALL_BET_TYPES.get(bet_type)
        elif bet_type.startswith('дартс_'):
            return DART_BET_TYPES.get(bet_type)
        elif bet_type.startswith('боулинг_'):
            return BOWLING_BET_TYPES.get(bet_type)
        return None

    def set_referral_system(self, referral_system):
        self.referral_system = referral_system

async def safe_edit_message(callback: CallbackQuery, text: str, reply_markup=None, parse_mode=None):
    """Безопасное редактирование сообщения с обработкой ошибок"""
    try:
        await callback.message.edit_text(text, parse_mode=parse_mode, reply_markup=reply_markup)
    except Exception as e:
        logging.error(f"Error editing message: {e}")
        try:
            await callback.message.answer(text, parse_mode=parse_mode, reply_markup=reply_markup)
        except:
            pass

async def show_dice_menu(callback: CallbackQuery):
    """Показать меню кубика с кастомными эмодзи"""
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🎲 Нечет (x1.8)", callback_data="bet_dice_куб_нечет", icon_custom_emoji_id=EMOJI_DICE),
            InlineKeyboardButton(text="🎲 Чет (x1.8)", callback_data="bet_dice_куб_чет", icon_custom_emoji_id=EMOJI_DICE)
        ],
        [
            InlineKeyboardButton(text="📉 Меньше (x1.8)", callback_data="bet_dice_куб_мал", icon_custom_emoji_id=EMOJI_ARROW_DOWN),
            InlineKeyboardButton(text="📈 Больше (x1.8)", callback_data="bet_dice_куб_бол", icon_custom_emoji_id=EMOJI_ARROW_UP)
        ],
        [
            InlineKeyboardButton(text="🎲🎲 Оба меньше 4 (x3.6)", callback_data="bet_dice_куб_2меньше", icon_custom_emoji_id=EMOJI_DICE),
            InlineKeyboardButton(text="🎲🎲 Оба больше 3 (x3.6)", callback_data="bet_dice_куб_2больше", icon_custom_emoji_id=EMOJI_DICE)
        ],
        [
            InlineKeyboardButton(text="🎯 Точное число (x4)", callback_data="bet_dice_exact", icon_custom_emoji_id=EMOJI_TARGET)
        ],
        [
            InlineKeyboardButton(text="◀️ Назад", callback_data="games", icon_custom_emoji_id=EMOJI_BACK)
        ]
    ])
    
    await safe_edit_message(callback, 
        f"<b>🎲 Кубик</b>\n\n"
        f"<i>Выберите тип ставки:</i>",
        reply_markup=markup,
        parse_mode='HTML'
    )
    await callback.answer()

async def show_exact_number_menu(callback: CallbackQuery):
    """Показать меню точного числа"""
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="1️⃣ (x4)", callback_data="bet_dice_куб_1", icon_custom_emoji_id=EMOJI_DICE),
            InlineKeyboardButton(text="2️⃣ (x4)", callback_data="bet_dice_куб_2", icon_custom_emoji_id=EMOJI_DICE),
            InlineKeyboardButton(text="3️⃣ (x4)", callback_data="bet_dice_куб_3", icon_custom_emoji_id=EMOJI_DICE)
        ],
        [
            InlineKeyboardButton(text="4️⃣ (x4)", callback_data="bet_dice_куб_4", icon_custom_emoji_id=EMOJI_DICE),
            InlineKeyboardButton(text="5️⃣ (x4)", callback_data="bet_dice_куб_5", icon_custom_emoji_id=EMOJI_DICE),
            InlineKeyboardButton(text="6️⃣ (x4)", callback_data="bet_dice_куб_6", icon_custom_emoji_id=EMOJI_DICE)
        ],
        [
            InlineKeyboardButton(text="◀️ Назад", callback_data="custom_dice_001", icon_custom_emoji_id=EMOJI_BACK)
        ]
    ])
    
    await safe_edit_message(callback,
        f"<b>🎯 Точное число</b>\n\n"
        f"<i>Выберите число от 1 до 6:</i>",
        reply_markup=markup,
        parse_mode='HTML'
    )
    await callback.answer()

async def show_basketball_menu(callback: CallbackQuery):
    """Показать меню баскетбола"""
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🏀 Гол 2 очка (x1.85)", callback_data="bet_basketball_баскет_гол", icon_custom_emoji_id=EMOJI_BASKETBALL)
        ],
        [
            InlineKeyboardButton(text="🏀 3-очковый (x2.75)", callback_data="bet_basketball_баскет_3очка", icon_custom_emoji_id=EMOJI_BASKETBALL)
        ],
        [
            InlineKeyboardButton(text="🏀 Мимо (x1.7)", callback_data="bet_basketball_баскет_мимо", icon_custom_emoji_id=EMOJI_BASKETBALL)
        ],
        [
            InlineKeyboardButton(text="◀️ Назад", callback_data="games", icon_custom_emoji_id=EMOJI_BACK)
        ]
    ])
    
    await safe_edit_message(callback,
        f"<b>🏀 Баскетбол</b>\n\n"
        f"<i>Выберите тип ставки:</i>",
        reply_markup=markup,
        parse_mode='HTML'
    )
    await callback.answer()

async def show_football_menu(callback: CallbackQuery):
    """Показать меню футбола"""
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⚽ Гол (x1.3)", callback_data="bet_football_футбол_гол", icon_custom_emoji_id=EMOJI_FOOTBALL)
        ],
        [
            InlineKeyboardButton(text="⚽ Мимо (x1.7)", callback_data="bet_football_футбол_мимо", icon_custom_emoji_id=EMOJI_FOOTBALL)
        ],
        [
            InlineKeyboardButton(text="◀️ Назад", callback_data="games", icon_custom_emoji_id=EMOJI_BACK)
        ]
    ])
    
    await safe_edit_message(callback,
        f"<b>⚽ Футбол</b>\n\n"
        f"<i>Выберите тип ставки:</i>",
        reply_markup=markup,
        parse_mode='HTML'
    )
    await callback.answer()

async def show_darts_menu(callback: CallbackQuery):
    """Показать меню дартса"""
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⚪ Белое (x1.85)", callback_data="bet_darts_дартс_белое", icon_custom_emoji_id=EMOJI_DARTS),
            InlineKeyboardButton(text="🔴 Красное (x1.85)", callback_data="bet_darts_дартс_красное", icon_custom_emoji_id=EMOJI_DARTS)
        ],
        [
            InlineKeyboardButton(text="🎯 Центр (x3.35)", callback_data="bet_darts_дартс_центр", icon_custom_emoji_id=EMOJI_DARTS)
        ],
        [
            InlineKeyboardButton(text="❌ Мимо (x2.2)", callback_data="bet_darts_дартс_мимо", icon_custom_emoji_id=EMOJI_DARTS)
        ],
        [
            InlineKeyboardButton(text="◀️ Назад", callback_data="games", icon_custom_emoji_id=EMOJI_BACK)
        ]
    ])
    
    await safe_edit_message(callback,
        f"<b>🎯 Дартс</b>\n\n"
        f"<i>Выберите тип ставки:</i>",
        reply_markup=markup,
        parse_mode='HTML'
    )
    await callback.answer()

async def show_bowling_menu(callback: CallbackQuery):
    """Показать меню боулинга"""
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🎳 Победа (x1.8)", callback_data="bet_bowling_боулинг_победа", icon_custom_emoji_id=EMOJI_BOWLING),
            InlineKeyboardButton(text="🎳 Поражение (x1.8)", callback_data="bet_bowling_боулинг_поражение", icon_custom_emoji_id=EMOJI_BOWLING)
        ],
        [
            InlineKeyboardButton(text="🎳 Страйк (x3.75)", callback_data="bet_bowling_боулинг_страйк", icon_custom_emoji_id=EMOJI_BOWLING)
        ],
        [
            InlineKeyboardButton(text="◀️ Назад", callback_data="games", icon_custom_emoji_id=EMOJI_BACK)
        ]
    ])
    
    await safe_edit_message(callback,
        f"<b>🎳 Боулинг</b>\n\n"
        f"<i>Выберите тип ставки:</i>",
        reply_markup=markup,
        parse_mode='HTML'
    )
    await callback.answer()

async def request_amount(callback: CallbackQuery, state: FSMContext, betting_game: BettingGame):
    """Запросить сумму ставки"""
    bet_type = callback.data.split('_', 2)[2]
    user_id = callback.from_user.id
    
    balance = betting_game.get_balance(user_id)
    
    if balance < MIN_BET:
        await callback.answer(f"❌ Недостаточно средств! Мин. {MIN_BET} USDT", show_alert=True)
        return
    
    betting_game.pending_bets[user_id] = bet_type
    bet_config = betting_game.get_bet_config(bet_type)
    
    if not bet_config:
        await callback.answer("❌ Ошибка", show_alert=True)
        return
    
    await state.set_state(BetStates.waiting_for_amount)
    
    markup = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="◀️ Отмена", callback_data="cancel_bet", icon_custom_emoji_id=EMOJI_BACK)
    ]])
    
    await callback.message.edit_text(
        f"<b>{bet_config['name']}</b>\n\n"
        f"<i>Введите сумму ставки:</i>\n"
        f"<blockquote>Мин: <code>{MIN_BET} USDT</code>\n"
        f"Макс: <code>{balance:.2f} USDT</code>\n"
        f"Выигрыш: <code>x{bet_config['multiplier']}</code></blockquote>",
        parse_mode='HTML',
        reply_markup=markup
    )
    await callback.answer()

async def process_bet_amount(message: Message, state: FSMContext, betting_game: BettingGame):
    """Обработать сумму ставки и начать игру"""
    user_id = message.from_user.id
    
    if user_id not in betting_game.pending_bets:
        await state.clear()
        return
    
    try:
        amount = float(message.text)
        
        if amount < MIN_BET:
            await message.answer(f"❌ Минимум: {MIN_BET} USDT")
            return
            
        balance = betting_game.get_balance(user_id)
        if balance < amount:
            await message.answer(
                f"❌ Недостаточно средств!\n"
                f"Баланс: <code>{balance:.2f} USDT</code>",
                parse_mode='HTML'
            )
            return
            
        bet_type = betting_game.pending_bets[user_id]
        bet_config = betting_game.get_bet_config(bet_type)
        
        if not bet_config:
            await message.answer("❌ Ошибка")
            if user_id in betting_game.pending_bets:
                del betting_game.pending_bets[user_id]
            await state.clear()
            return
        
        # Снимаем средства
        if not betting_game.subtract_balance(user_id, amount):
            await message.answer("❌ Ошибка")
            if user_id in betting_game.pending_bets:
                del betting_game.pending_bets[user_id]
            await state.clear()
            return
        
        # Получаем никнейм игрока
        nickname = message.from_user.first_name or ""
        if message.from_user.last_name:
            nickname += f" {message.from_user.last_name}"
        nickname = nickname.strip() or message.from_user.username or "Игрок"
        
        # Удаляем сообщение с запросом суммы
        try:
            await message.delete()
        except:
            pass
        
        # Запускаем игру
        try:
            if bet_type in ['куб_2меньше', 'куб_2больше']:
                await play_double_dice_game(message.chat.id, user_id, nickname, amount, bet_type, bet_config, betting_game)
            elif bet_type.startswith('боулинг_') and bet_config.get('special') == 'bowling_vs':
                await play_bowling_vs_game(message.chat.id, user_id, nickname, amount, bet_type, bet_config, betting_game)
            else:
                await play_single_dice_game(message.chat.id, user_id, nickname, amount, bet_type, bet_config, betting_game)
        except Exception as e:
            logging.error(f"Ошибка в игре: {e}")
            # Возвращаем средства при ошибке
            betting_game.add_balance(user_id, amount)
            await message.answer("❌ Произошла ошибка. Средства возвращены.")
        finally:
            # Очищаем pending bet
            if user_id in betting_game.pending_bets:
                del betting_game.pending_bets[user_id]
            await state.clear()
        
    except ValueError:
        await message.answer("❌ Введите число")
    except Exception as e:
        logging.error(f"Error: {e}")
        await message.answer("❌ Ошибка")
        if user_id in betting_game.pending_bets:
            del betting_game.pending_bets[user_id]
        await state.clear()

async def play_single_dice_game(chat_id: int, user_id: int, nickname: str, amount: float, bet_type: str, bet_config: dict, betting_game: BettingGame):
    """Игра с одним броском"""
    # Определяем эмодзи
    if bet_type.startswith('куб_'):
        emoji = "🎲"
    elif bet_type.startswith('баскет_'):
        emoji = "🏀"
    elif bet_type.startswith('футбол_'):
        emoji = "⚽"
    elif bet_type.startswith('дартс_'):
        emoji = "🎯"
    elif bet_type.startswith('боулинг_'):
        emoji = "🎳"
    else:
        emoji = "🎲"
    
    dice_message = await betting_game.bot.send_dice(chat_id, emoji=emoji)
    await asyncio.sleep(3)
    
    dice_value = dice_message.dice.value
    
    # Проверяем выигрыш
    is_win = dice_value in bet_config.get('values', [])
    
    if is_win:
        winnings = amount * bet_config['multiplier']
        betting_game.add_balance(user_id, winnings)
        
        if betting_game.referral_system:
            betting_game.referral_system.process_referral_win(user_id, winnings)
        
        await dice_message.reply(
            f"<b><tg-emoji emoji-id=\"{EMOJI_WIN}\">🎉</tg-emoji> ВЫИГРЫШ!</b>\n\n"
            f"👤 {nickname}\n"
            f"💰 +<code>{winnings:.2f} USDT</code> (x{bet_config['multiplier']})",
            parse_mode='HTML'
        )
    else:
        await dice_message.reply(
            f"<b><tg-emoji emoji-id=\"{EMOJI_LOSE}\">❌</tg-emoji> ПРОИГРЫШ</b>\n\n"
            f"👤 {nickname}\n"
            f"💸 -<code>{amount:.2f} USDT</code>",
            parse_mode='HTML'
        )

async def play_double_dice_game(chat_id: int, user_id: int, nickname: str, amount: float, bet_type: str, bet_config: dict, betting_game: BettingGame):
    """Игра с двумя кубиками"""
    dice1 = await betting_game.bot.send_dice(chat_id, emoji="🎲")
    await asyncio.sleep(2)
    
    dice2 = await betting_game.bot.send_dice(chat_id, emoji="🎲")
    await asyncio.sleep(3)
    
    dice1_value = dice1.dice.value
    dice2_value = dice2.dice.value
    
    # Проверяем условие
    if bet_type == 'куб_2меньше':
        is_win = dice1_value < 4 and dice2_value < 4
    else:  # куб_2больше
        is_win = dice1_value > 3 and dice2_value > 3
    
    if is_win:
        winnings = amount * bet_config['multiplier']
        betting_game.add_balance(user_id, winnings)
        
        if betting_game.referral_system:
            betting_game.referral_system.process_referral_win(user_id, winnings)
        
        await dice2.reply(
            f"<b><tg-emoji emoji-id=\"{EMOJI_WIN}\">🎉</tg-emoji> ВЫИГРЫШ!</b>\n\n"
            f"👤 {nickname}\n"
            f"🎲 {dice1_value} и {dice2_value}\n"
            f"💰 +<code>{winnings:.2f} USDT</code> (x{bet_config['multiplier']})",
            parse_mode='HTML'
        )
    else:
        await dice2.reply(
            f"<b><tg-emoji emoji-id=\"{EMOJI_LOSE}\">❌</tg-emoji> ПРОИГРЫШ</b>\n\n"
            f"👤 {nickname}\n"
            f"🎲 {dice1_value} и {dice2_value}\n"
            f"💸 -<code>{amount:.2f} USDT</code>",
            parse_mode='HTML'
        )

async def play_bowling_vs_game(chat_id: int, user_id: int, nickname: str, amount: float, bet_type: str, bet_config: dict, betting_game: BettingGame):
    """Игра в боулинг против бота"""
    player_roll = await betting_game.bot.send_dice(chat_id, emoji="🎳")
    await asyncio.sleep(2)
    
    bot_roll = await betting_game.bot.send_dice(chat_id, emoji="🎳")
    await asyncio.sleep(3)
    
    player_value = player_roll.dice.value
    bot_value = bot_roll.dice.value
    
    # При ничьей - переброс
    if player_value == bot_value:
        await player_roll.reply("🔄 Ничья! Переброс...")
        await asyncio.sleep(1)
        
        player_roll = await betting_game.bot.send_dice(chat_id, emoji="🎳")
        await asyncio.sleep(2)
        bot_roll = await betting_game.bot.send_dice(chat_id, emoji="🎳")
        await asyncio.sleep(3)
        
        player_value = player_roll.dice.value
        bot_value = bot_roll.dice.value
    
    # Определяем результат
    if bet_type == 'боулинг_победа':
        is_win = player_value > bot_value
    elif bet_type == 'боулинг_поражение':
        is_win = player_value < bot_value
    else:
        is_win = False
    
    if is_win:
        winnings = amount * bet_config['multiplier']
        betting_game.add_balance(user_id, winnings)
        
        if betting_game.referral_system:
            betting_game.referral_system.process_referral_win(user_id, winnings)
        
        await bot_roll.reply(
            f"<b><tg-emoji emoji-id=\"{EMOJI_WIN}\">🎉</tg-emoji> ВЫИГРЫШ!</b>\n\n"
            f"👤 {nickname}: {player_value}\n"
            f"🤖 Бот: {bot_value}\n"
            f"💰 +<code>{winnings:.2f} USDT</code> (x{bet_config['multiplier']})",
            parse_mode='HTML'
        )
    else:
        await bot_roll.reply(
            f"<b><tg-emoji emoji-id=\"{EMOJI_LOSE}\">❌</tg-emoji> ПРОИГРЫШ</b>\n\n"
            f"👤 {nickname}: {player_value}\n"
            f"🤖 Бот: {bot_value}\n"
            f"💸 -<code>{amount:.2f} USDT</code>",
            parse_mode='HTML'
        )

async def cancel_bet(callback: CallbackQuery, state: FSMContext, betting_game: BettingGame):
    """Отмена ставки - возврат в меню игр"""
    user_id = callback.from_user.id
    if user_id in betting_game.pending_bets:
        del betting_game.pending_bets[user_id]
    await state.clear()
    
    # Возврат в меню игр
    from main import games_callback
    await games_callback(callback, state)
