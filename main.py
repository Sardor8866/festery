import asyncio
import logging
import os
from datetime import datetime
from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, Update, CallbackQuery
from aiogram.filters.command import CommandStart
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiohttp import web

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
EMOJI_WITHDrAWAL = "5445355530111437729"

# File ID для приветственного стикера
WELCOME_STICKER_ID = "CAACAgIAAxkBAAIGUWmRflo7gmuMF5MNUcs4LGpyA93yAAKaDAAC753ZS6lNRCGaKqt5OgQ"

# Роутер
router = Router()

# Клавиатура главного меню (расположение: 2+2+1)
def get_main_menu():
    buttons = [
        # Первый ряд: 2 кнопки
        [
            InlineKeyboardButton(
                text="Профиль",
                callback_data="profile",
                icon_custom_emoji_id=EMOJI_PROFILE
            ),
            InlineKeyboardButton(
                text="Партнёры", 
                callback_data="partners",
                icon_custom_emoji_id=EMOJI_PARTNERS
            )
        ],
        # Второй ряд: 2 кнопки
        [
            InlineKeyboardButton(
                text="Игры",
                callback_data="games",
                icon_custom_emoji_id=EMOJI_GAMES
            ),
            InlineKeyboardButton(
                text="Лидеры",
                callback_data="leaders",
                icon_custom_emoji_id=EMOJI_LEADERS
            )
        ],
        # Третий ряд: 1 кнопка
        [
            InlineKeyboardButton(
                text="О проекте",
                callback_data="about",
                icon_custom_emoji_id=EMOJI_ABOUT
            )
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# Клавиатура для профиля (кнопки с кастомными эмодзи)
def get_profile_menu():
    buttons = [
        [
            InlineKeyboardButton(
                text="Пополнить",
                callback_data="deposit",
                icon_custom_emoji_id=EMOJI_WALLET
            ),
            InlineKeyboardButton(
                text="Вывести",
                callback_data="withdraw",
                icon_custom_emoji_id=EMOJI_WITHDrAWAL
            )
        ],
        [
            InlineKeyboardButton(
                text="На главную",
                callback_data="back_to_main",
                icon_custom_emoji_id=EMOJI_BACK
            )
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# Клавиатура для остальных разделов
def get_back_menu():
    buttons = [
        [
            InlineKeyboardButton(
                text="На главную",
                callback_data="back_to_main",
                icon_custom_emoji_id=EMOJI_BACK
            )
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# Текст главного меню
def get_main_menu_text():
    return f"""
<blockquote><tg-emoji emoji-id="5197288647275071607">🎰</tg-emoji> <b>Честные игры — прозрачные правила и реальные шансы на победу.</b>
<b>Без скрытых условий, всё открыто и по-настоящему честно.</b></blockquote>

<blockquote><tg-emoji emoji-id="5195033767969839232">⚡</tg-emoji> <b>Быстрые выплаты — моментальный вывод средств без задержек.</b>
<tg-emoji emoji-id="5445355530111437729">💎</tg-emoji> <b>Выводы через <tg-emoji emoji-id="{EMOJI_CRYPTOBOT}">🔵</tg-emoji> <a href="https://t.me/send">Cryptobot</a></b></blockquote>

<tg-emoji emoji-id="5907025791006283345">💬</tg-emoji> <b><a href="https://t.me/your_support">Тех. поддержка</a> | <a href="https://t.me/your_chat">Наш чат</a> | <a href="https://t.me/your_news">Новости</a></b>
"""

# Красивый профиль
def get_profile_text(user_first_name, days_in_project):
    # Пример данных (в реальном боте нужно брать из БД)
    balance = 1250.50
    total_deposits = 3500.00
    total_withdrawals = 2250.00
    
    # Склонение слова "день"
    if 11 <= days_in_project <= 19:
        days_text = "дней"
    elif days_in_project % 10 == 1:
        days_text = "день"
    elif days_in_project % 10 in [2, 3, 4]:
        days_text = "дня"
    else:
        days_text = "дней"
    
    return f"""
<blockquote><b><tg-emoji emoji-id="{EMOJI_PROFILE}">👤</tg-emoji> Профиль</b></blockquote>

<blockquote>
<b><tg-emoji emoji-id="5197434882321567830">💰</tg-emoji><code>{balance:,.2f}</code></b>
<tg-emoji emoji-id="5443127283898405358">📥</tg-emoji> Депозитов: <b><code>{total_deposits:,.2f}</code></b>
<tg-emoji emoji-id="5445355530111437729">📤</tg-emoji> Выводов: <b><code>{total_withdrawals:,.2f}</code></b>
<tg-emoji emoji-id="5274055917766202507">📅</tg-emoji> В проекте: <b><code>{days_in_project} {days_text}</code></b>
</blockquote>

<tg-emoji emoji-id="5907025791006283345">💬</tg-emoji> <b><a href="https://t.me/your_support">Тех. поддержка</a> | <a href="https://t.me/your_chat">Наш чат</a> | <a href="https://t.me/your_news">Новости</a></b>
"""

# Старт - отправляем стикер и меню
@router.message(CommandStart())
async def cmd_start(message: Message):
    try:
        # Отправляем приветственный стикер
        await message.answer_sticker(
            sticker=WELCOME_STICKER_ID
        )
        # Отправляем текстовое меню
        await message.answer(
            get_main_menu_text(),
            parse_mode=ParseMode.HTML,
            reply_markup=get_main_menu()
        )
    except Exception as e:
        logging.error(f"Ошибка при отправке: {e}")
        # Если стикер не отправился, отправляем только текст
        await message.answer(
            get_main_menu_text(),
            parse_mode=ParseMode.HTML,
            reply_markup=get_main_menu()
        )

# Профиль
@router.callback_query(F.data == "profile")
async def profile_callback(callback: CallbackQuery):
    # Для примера берем 30 дней
    # В реальном боте нужно хранить дату регистрации в БД
    days_in_project = 30
    
    await callback.message.edit_text(
        get_profile_text(callback.from_user.first_name, days_in_project),
        parse_mode=ParseMode.HTML,
        reply_markup=get_profile_menu(),
        disable_web_page_preview=True
    )
    await callback.answer()

# Пополнение (в разработке)
@router.callback_query(F.data == "deposit")
async def deposit_callback(callback: CallbackQuery):
    await callback.message.edit_text(
        f"<b><tg-emoji emoji-id=\"{EMOJI_WALLET}\">💰</tg-emoji> Пополнение баланса</b>\n\n"
        f"<tg-emoji emoji-id=\"{EMOJI_DEVELOPMENT}\">🔧</tg-emoji> <b>Раздел в разработке</b>\n\n"
        f"Скоро здесь появится возможность пополнения баланса через Cryptobot.",
        parse_mode=ParseMode.HTML,
        reply_markup=get_back_menu()
    )
    await callback.answer()

# Вывод (в разработке)
@router.callback_query(F.data == "withdraw")
async def withdraw_callback(callback: CallbackQuery):
    await callback.message.edit_text(
        f"<b><tg-emoji emoji-id=\"{EMOJI_CRYPTOBOT}\">💸</tg-emoji> Вывод средств</b>\n\n"
        f"<tg-emoji emoji-id=\"{EMOJI_DEVELOPMENT}\">🔧</tg-emoji> <b>Раздел в разработке</b>\n\n"
        f"Скоро здесь появится возможность вывода средств через Cryptobot.",
        parse_mode=ParseMode.HTML,
        reply_markup=get_back_menu()
    )
    await callback.answer()

# Партнёры
@router.callback_query(F.data == "partners")
async def partners_callback(callback: CallbackQuery):
    await callback.message.edit_text(
        f'<tg-emoji emoji-id="{EMOJI_PARTNERS}">🤝</tg-emoji> <b>Наши партнёры</b>\n\n'
        f'<tg-emoji emoji-id="{EMOJI_DEVELOPMENT}">🔧</tg-emoji> <b>Раздел в разработке</b>\n\n'
        f'Скоро здесь появится информация о партнёрах и партнёрской программе.',
        parse_mode=ParseMode.HTML,
        reply_markup=get_back_menu()
    )
    await callback.answer()

# Игры
@router.callback_query(F.data == "games")
async def games_callback(callback: CallbackQuery):
    await callback.message.edit_text(
        f'<tg-emoji emoji-id="{EMOJI_GAMES}">🎮</tg-emoji> <b>Список игр</b>\n\n'
        f'<tg-emoji emoji-id="{EMOJI_DEVELOPMENT}">🔧</tg-emoji> <b>Раздел в разработке</b>\n\n'
        f'Скоро здесь появятся все доступные игры с высокими коэффициентами.',
        parse_mode=ParseMode.HTML,
        reply_markup=get_back_menu()
    )
    await callback.answer()

# Лидеры
@router.callback_query(F.data == "leaders")
async def leaders_callback(callback: CallbackQuery):
    await callback.message.edit_text(
        f'<tg-emoji emoji-id="{EMOJI_LEADERS}">🏆</tg-emoji> <b>Таблица лидеров</b>\n\n'
        f'<tg-emoji emoji-id="{EMOJI_DEVELOPMENT}">🔧</tg-emoji> <b>Раздел в разработке</b>\n\n'
        f'Скоро здесь появятся лучшие игроки недели и их достижения.',
        parse_mode=ParseMode.HTML,
        reply_markup=get_back_menu()
    )
    await callback.answer()

# О проекте
@router.callback_query(F.data == "about")
async def about_callback(callback: CallbackQuery):
    await callback.message.edit_text(
        f'<tg-emoji emoji-id="{EMOJI_ABOUT}">ℹ️</tg-emoji> <b>О проекте</b>\n\n'
        f'Мы — команда профессионалов, создающая честный гемблинг с 2020 года.\n\n'
        f'• Мгновенные выплаты\n'
        f'• Прозрачные алгоритмы\n'
        f'• Поддержка 24/7\n'
        f'• Лицензия Curacao',
        parse_mode=ParseMode.HTML,
        reply_markup=get_back_menu()
    )
    await callback.answer()

# Кнопка "На главную"
@router.callback_query(F.data == "back_to_main")
async def back_to_main_callback(callback: CallbackQuery):
    await callback.message.edit_text(
        get_main_menu_text(),
        parse_mode=ParseMode.HTML,
        reply_markup=get_main_menu()
    )
    await callback.answer()

# Основная функция
async def main():
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_router(router)

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
