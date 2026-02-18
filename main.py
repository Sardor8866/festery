import asyncio
import logging
import os
from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, Update, CallbackQuery
from aiogram.filters.command import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiohttp import web

# Импортируем модуль платежей
from payments import payment_router, setup_payments, storage, MIN_DEPOSIT, MIN_WITHDRAWAL

# Импортируем игровой модуль
from game import (
    BettingGame, show_dice_menu, show_basketball_menu, show_football_menu,
    show_darts_menu, show_bowling_menu, show_exact_number_menu, request_amount,
    cancel_bet, is_bet_command, handle_text_bet_command
)

# Импортируем модуль мин
from mines import mines_router, setup_mines

# Настройки
BOT_TOKEN = "8586332532:AAHX758cf6iOUpPNpY2sqseGBYsKJo9js4U"
WEBHOOK_PATH = "/webhook"
PORT = int(os.getenv('PORT', 8080))
RENDER_URL = os.getenv('RENDER_EXTERNAL_URL')

if RENDER_URL:
    WEBHOOK_URL = f"{RENDER_URL}{WEBHOOK_PATH}"
else:
    WEBHOOK_URL = f"https://festery.onrender.com{WEBHOOK_PATH}"

# ID кастомных эмодзи
EMOJI_WELCOME = "5199885118214255386"
EMOJI_PROFILE = "5906581476639513176"
EMOJI_PARTNERS = "5906986955911993888"
EMOJI_GAMES = "5424972470023104089"
EMOJI_LEADERS = "5440539497383087970"
EMOJI_ABOUT = "5251203410396458957"
EMOJI_CRYPTOBOT = "5427054176246991778"
EMOJI_BACK = "5906771962734057347"
EMOJI_DEVELOPMENT = "5445355530111437729"
EMOJI_WALLET = "5443127283898405358"
EMOJI_STATS = "5197288647275071607"
EMOJI_WITHDRAWAL = "5445355530111437729"
EMOJI_MINES = "5199988776655443322"  # 💣 для игры в мины

# Кастомные callback_data для игр
GAME_CALLBACKS = {
    'dice': 'custom_dice_001',
    'basketball': 'custom_basketball_002',
    'football': 'custom_football_003',
    'darts': 'custom_darts_004',
    'bowling': 'custom_bowling_005',
    'exact_number': 'custom_exact_006',
    'back_to_games': 'custom_back_games_007',
    'mines': 'custom_mines_008'  # Добавляем мины
}

# File ID для приветственного стикера
WELCOME_STICKER_ID = "CAACAgIAAxkBAAIGUWmRflo7gmuMF5MNUcs4LGpyA93yAAKaDAAC753ZS6lNRCGaKqt5OgQ"

# Роутер
router = Router()

# Экземпляр игры
betting_game = None


# ========== СИНХРОНИЗАЦИЯ БАЛАНСОВ ==========
def sync_balances(user_id: int):
    """Синхронизирует баланс между storage и betting_game"""
    global betting_game
    if betting_game and storage:
        payment_balance = storage.get_balance(user_id)
        game_balance = betting_game.get_balance(user_id)

        if abs(payment_balance - game_balance) > 0.01:
            logging.info(f"Синхронизация баланса для user {user_id}: payment={payment_balance}, game={game_balance}")
            betting_game.user_balances[user_id] = payment_balance
            betting_game.save_balances()

        return payment_balance
    return 0


# ========== КЛАВИАТУРЫ ==========
def get_main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Профиль", callback_data="profile", icon_custom_emoji_id=EMOJI_PROFILE),
            InlineKeyboardButton(text="Партнёры", callback_data="partners", icon_custom_emoji_id=EMOJI_PARTNERS)
        ],
        [
            InlineKeyboardButton(text="Игры", callback_data="games", icon_custom_emoji_id=EMOJI_GAMES),
            InlineKeyboardButton(text="Лидеры", callback_data="leaders", icon_custom_emoji_id=EMOJI_LEADERS)
        ],
        [
            InlineKeyboardButton(text="О проекте", callback_data="about", icon_custom_emoji_id=EMOJI_ABOUT)
        ]
    ])


def get_games_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🎲 Кубик", callback_data=GAME_CALLBACKS['dice']),
            InlineKeyboardButton(text="🏀 Баскетбол", callback_data=GAME_CALLBACKS['basketball'])
        ],
        [
            InlineKeyboardButton(text="⚽️ Футбол", callback_data=GAME_CALLBACKS['football']),
            InlineKeyboardButton(text="🎯 Дартс", callback_data=GAME_CALLBACKS['darts'])
        ],
        [
            InlineKeyboardButton(text="🎳 Боулинг", callback_data=GAME_CALLBACKS['bowling'])
        ],
        [  # Новая строка с игрой Мины
            InlineKeyboardButton(text="💣 Мины", callback_data="play_mines")
        ],
        [
            InlineKeyboardButton(text="Назад", callback_data="back_to_main", icon_custom_emoji_id=EMOJI_BACK)
        ]
    ])


def get_profile_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Пополнить", callback_data="deposit", icon_custom_emoji_id=EMOJI_WALLET),
            InlineKeyboardButton(text="Вывести", callback_data="withdraw", icon_custom_emoji_id=EMOJI_WITHDRAWAL)
        ],
        [
            InlineKeyboardButton(text="На главную", callback_data="back_to_main", icon_custom_emoji_id=EMOJI_BACK)
        ]
    ])


def get_cancel_menu():
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Отмена", callback_data="profile", icon_custom_emoji_id=EMOJI_BACK)
    ]])


# ========== ТЕКСТЫ ==========
def get_main_menu_text():
    return (
        f"<blockquote><tg-emoji emoji-id=\"5197288647275071607\">🎰</tg-emoji> <b>Честные игры — прозрачные правила и реальные шансы на победу.</b>\n"
        f"<b>Без скрытых условий, всё открыто и по-настоящему честно.</b></blockquote>\n\n"
        f"<blockquote><tg-emoji emoji-id=\"5195033767969839232\">⚡</tg-emoji> <b>Быстрые выплаты — моментальный вывод средств без задержек.</b>\n"
        f"<tg-emoji emoji-id=\"5445355530111437729\">💎</tg-emoji> <b>Выводы через <tg-emoji emoji-id=\"{EMOJI_CRYPTOBOT}\">🔵</tg-emoji> <a href=\"https://t.me/send\">Cryptobot</a></b></blockquote>\n\n"
        f"<tg-emoji emoji-id=\"5907025791006283345\">💬</tg-emoji> <b><a href=\"https://t.me/your_support\">Тех. поддержка</a> | <a href=\"https://t.me/your_chat\">Наш чат</a> | <a href=\"https://t.me/your_news\">Новости</a></b>\n"
    )


def get_games_menu_text(user_id: int):
    balance = sync_balances(user_id)
    return (
        f"<blockquote><tg-emoji emoji-id=\"{EMOJI_GAMES}\">🎮</tg-emoji> <b>Игры</b></blockquote>\n\n"
        f"<blockquote><tg-emoji emoji-id=\"5278467510604160626\">🎮</tg-emoji>:<code>{balance:.2f}</code><tg-emoji emoji-id=\"5197434882321567830\">🎮</tg-emoji></blockquote>\n\n"
        f"<blockquote><b>Выберите игру:</b></blockquote>\n\n"
        f"<tg-emoji emoji-id=\"5907025791006283345\">💬</tg-emoji> <b><a href=\"https://t.me/your_support\">Тех. поддержка</a> | <a href=\"https://t.me/your_chat\">Наш чат</a> | <a href=\"https://t.me/your_news\">Новости</a></b>\n"
    )


def get_profile_text(user_first_name: str, days_in_project: int, user_id: int):
    balance = sync_balances(user_id)
    user_data = storage.get_user(user_id)
    total_deposits = user_data.get('total_deposits', 0)
    total_withdrawals = user_data.get('total_withdrawals', 0)

    if 11 <= days_in_project <= 19:
        days_text = "дней"
    elif days_in_project % 10 == 1:
        days_text = "день"
    elif days_in_project % 10 in [2, 3, 4]:
        days_text = "дня"
    else:
        days_text = "дней"

    return (
        f"<blockquote><b><tg-emoji emoji-id=\"{EMOJI_PROFILE}\">👤</tg-emoji> Профиль</b></blockquote>\n\n"
        f"<blockquote>\n"
        f"<b><tg-emoji emoji-id=\"5278467510604160626\">💰</tg-emoji>:<code>{balance:,.2f}</code><tg-emoji emoji-id=\"5197434882321567830\">💰</tg-emoji></b>\n"
        f"<tg-emoji emoji-id=\"5443127283898405358\">📥</tg-emoji> Депозитов: <b><code>{total_deposits:,.2f}</code><tg-emoji emoji-id=\"5197434882321567830\">💰</tg-emoji></b>\n"
        f"<tg-emoji emoji-id=\"5445355530111437729\">📤</tg-emoji> Выводов: <b><code>{total_withdrawals:,.2f}</code><tg-emoji emoji-id=\"5197434882321567830\">💰</tg-emoji></b>\n"
        f"<tg-emoji emoji-id=\"5274055917766202507\">📅</tg-emoji> В проекте: <b><code>{days_in_project} {days_text}</code></b>\n"
        f"</blockquote>\n\n"
        f"<tg-emoji emoji-id=\"5907025791006283345\">💬</tg-emoji> <b><a href=\"https://t.me/your_support\">Тех. поддержка</a> | <a href=\"https://t.me/your_chat\">Наш чат</a> | <a href=\"https://t.me/your_news\">Новости</a></b>\n"
    )


# ========== СТАРТ ==========
@router.message(CommandStart())
async def cmd_start(message: Message):
    try:
        storage.get_user(message.from_user.id)
        sync_balances(message.from_user.id)

        await message.answer_sticker(sticker=WELCOME_STICKER_ID)
        await message.answer(
            get_main_menu_text(),
            parse_mode=ParseMode.HTML,
            reply_markup=get_main_menu()
        )
    except Exception as e:
        logging.error(f"Error in start: {e}")
        await message.answer("Произошла ошибка. Попробуйте позже.")


# ========== ПРОФИЛЬ ==========
@router.callback_query(F.data == "profile")
async def profile_callback(callback: CallbackQuery, state: FSMContext):
    # Сбрасываем все состояния
    await state.clear()
    storage.clear_pending(callback.from_user.id)
    sync_balances(callback.from_user.id)

    await callback.message.edit_text(
        get_profile_text(callback.from_user.first_name, 30, callback.from_user.id),
        parse_mode=ParseMode.HTML,
        reply_markup=get_profile_menu(),
        disable_web_page_preview=True
    )
    await callback.answer()


# ========== ИГРЫ ==========
@router.callback_query(F.data == "games")
async def games_callback(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    storage.clear_pending(callback.from_user.id)

    await callback.message.edit_text(
        get_games_menu_text(callback.from_user.id),
        parse_mode=ParseMode.HTML,
        reply_markup=get_games_menu(),
        disable_web_page_preview=True
    )
    await callback.answer()


# ========== ОБРАБОТЧИКИ ИГР ==========
@router.callback_query(F.data == GAME_CALLBACKS['dice'])
async def dice_game(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await show_dice_menu(callback)

@router.callback_query(F.data == GAME_CALLBACKS['basketball'])
async def basketball_game(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await show_basketball_menu(callback)

@router.callback_query(F.data == GAME_CALLBACKS['football'])
async def football_game(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await show_football_menu(callback)

@router.callback_query(F.data == GAME_CALLBACKS['darts'])
async def darts_game(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await show_darts_menu(callback)

@router.callback_query(F.data == GAME_CALLBACKS['bowling'])
async def bowling_game(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await show_bowling_menu(callback)

@router.callback_query(F.data == "bet_dice_exact")
async def exact_number_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await show_exact_number_menu(callback)

@router.callback_query(F.data.startswith("bet_"))
async def handle_bet_selection(callback: CallbackQuery, state: FSMContext):
    await request_amount(callback, state, betting_game)

@router.callback_query(F.data == "cancel_bet")
async def handle_cancel_bet(callback: CallbackQuery, state: FSMContext):
    await cancel_bet(callback, state, betting_game)


# ========== ПОПОЛНЕНИЕ ==========
@router.callback_query(F.data == "deposit")
async def deposit_callback(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    # Устанавливаем pending — payments.py увидит его при вводе числа
    storage.set_pending(callback.from_user.id, 'deposit')

    await callback.message.edit_text(
        f"<b><tg-emoji emoji-id=\"{EMOJI_WALLET}\">💰</tg-emoji> Пополнение баланса</b>\n\n"
        f"<blockquote><i><tg-emoji emoji-id=\"5197269100878907942\">💸</tg-emoji>Введите сумму пополнения:</i></blockquote>",
        parse_mode=ParseMode.HTML,
        reply_markup=get_cancel_menu()
    )
    await callback.answer()


# ========== ВЫВОД ==========
@router.callback_query(F.data == "withdraw")
async def withdraw_callback(callback: CallbackQuery, state: FSMContext):
    await state.clear()

    balance = sync_balances(callback.from_user.id)

    if balance < MIN_WITHDRAWAL:
        await callback.answer(f"❌ Минимум для вывода: {MIN_WITHDRAWAL} USDT", show_alert=True)
        return

    can_withdraw, wait_time = storage.can_withdraw(callback.from_user.id)
    if not can_withdraw:
        minutes = wait_time // 60
        seconds = wait_time % 60
        await callback.answer(f"⏳ Подождите {minutes} мин {seconds} сек", show_alert=True)
        return

    # Устанавливаем pending — payments.py увидит его при вводе числа
    storage.set_pending(callback.from_user.id, 'withdraw')

    await callback.message.edit_text(
        f"<b><tg-emoji emoji-id=\"{EMOJI_WITHDRAWAL}\">💸</tg-emoji> Вывод средств</b>\n\n"
        f"<blockquote><i><tg-emoji emoji-id=\"5197269100878907942\">💸</tg-emoji>Введите сумму вывода:</i></blockquote>",
        parse_mode=ParseMode.HTML,
        reply_markup=get_cancel_menu()
    )
    await callback.answer()


# ========== ТЕКСТОВЫЕ СООБЩЕНИЯ (ставки) ==========
@router.message(F.text)
async def handle_text_message(message: Message, state: FSMContext):
    """Обработка текста — команды ставок или ввод суммы"""
    from payments import handle_amount_input

    # Команды ставок (не числа)
    if is_bet_command(message.text):
        await handle_text_bet_command(message, betting_game)
        return

    # Числовой ввод
    try:
        float(message.text)
        current_state = await state.get_state()
        if current_state:
            # В процессе ставки — передаём в игру
            from game import process_bet_amount
            await process_bet_amount(message, state, betting_game)
        else:
            # Нет FSM — передаём в payments (депозит/вывод)
            await handle_amount_input(message)
    except ValueError:
        pass  # Неизвестный текст — игнорируем


# ========== ПАРТНЁРЫ ==========
@router.callback_query(F.data == "partners")
async def partners_callback(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        f'<tg-emoji emoji-id="{EMOJI_PARTNERS}">🤝</tg-emoji> <b>Наши партнёры</b>\n\n'
        f'<tg-emoji emoji-id="{EMOJI_DEVELOPMENT}">🔧</tg-emoji> <b>Раздел в разработке</b>\n\n'
        f'Скоро здесь появится информация о партнёрах.',
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="◀️ Назад", callback_data="profile")
        ]])
    )
    await callback.answer()


# ========== ЛИДЕРЫ ==========
@router.callback_query(F.data == "leaders")
async def leaders_callback(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        f'<tg-emoji emoji-id="{EMOJI_LEADERS}">🏆</tg-emoji> <b>Таблица лидеров</b>\n\n'
        f'<tg-emoji emoji-id="{EMOJI_DEVELOPMENT}">🔧</tg-emoji> <b>Раздел в разработке</b>\n\n'
        f'Скоро здесь появятся лучшие игроки.',
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="◀️ Назад", callback_data="profile")
        ]])
    )
    await callback.answer()


# ========== О ПРОЕКТЕ ==========
@router.callback_query(F.data == "about")
async def about_callback(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        f'<tg-emoji emoji-id="{EMOJI_ABOUT}">ℹ️</tg-emoji> <b>О проекте</b>\n\n'
        f'Мы — команда профессионалов, создающая честный гемблинг с 2020 года.\n\n'
        f'• Мгновенные выплаты\n'
        f'• Прозрачные алгоритмы\n'
        f'• Поддержка 24/7\n'
        f'• Лицензия Curacao',
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="◀️ Назад", callback_data="profile")
        ]])
    )
    await callback.answer()


# ========== НА ГЛАВНУЮ ==========
@router.callback_query(F.data == "back_to_main")
async def back_to_main_callback(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    storage.clear_pending(callback.from_user.id)

    await callback.message.edit_text(
        get_main_menu_text(),
        parse_mode=ParseMode.HTML,
        reply_markup=get_main_menu()
    )
    await callback.answer()


# ========== ЗАПУСК ==========
async def main():
    global betting_game

    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())

    betting_game = BettingGame(bot)
    
    # Инициализируем модуль мин
    setup_mines(bot, betting_game)

    # Подключаем все роутеры
    dp.include_router(router)        # Основной роутер
    dp.include_router(mines_router)  # Роутер для игры в мины
    dp.include_router(payment_router) # Роутер для платежей

    setup_payments(bot)

    await bot.delete_webhook(drop_pending_updates=True)
    await bot.set_webhook(WEBHOOK_URL)

    logging.info(f"Бот запущен на вебхуках: {WEBHOOK_URL}")

    app = web.Application()

    async def webhook_handler(request):
        try:
            json_data = await request.json()
            update = Update.model_validate(json_data, context={"bot": bot})
            await dp.feed_update(bot, update)
            return web.Response(status=200)
        except Exception as e:
            logging.error(f"Ошибка при обработке вебхука: {e}")
            return web.Response(status=500)

    async def handle_index(request):
        return web.Response(text="Бот работает!", content_type="text/html")

    app.router.add_post(WEBHOOK_PATH, webhook_handler)
    app.router.add_get("/", handle_index)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=PORT)

    logging.info(f"Сервер запущен на порту {PORT}")
    await site.start()

    await asyncio.Event().wait()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
