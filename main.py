import asyncio
import logging
import os
from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, Update
from aiogram.filters.command import CommandStart
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiohttp import web

# Настройки
BOT_TOKEN = "8586332532:AAHX758cf6iOUpPNpY2sqseGBYsKJo9js4U"  # замени на свой токен
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

# Клавиатура для разделов (только кнопка "На главную")
def get_back_menu():
    buttons = [
        [
            InlineKeyboardButton(
                text="◀️ На главную",
                callback_data="back_to_main"
            )
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# Текст главного меню
def get_main_menu_text():
    return """
<tg-emoji emoji-id="5197288647275071607">🎰</tg-emoji> <b>Честные игры — прозрачные правила и реальные шансы на победу.</b>
<b>Без скрытых условий, всё открыто и по-настоящему честно.</b>

<tg-emoji emoji-id="5195033767969839232">⚡</tg-emoji> <b>Быстрые выплаты — моментальный вывод средств без задержек.</b>
<tg-emoji emoji-id="5445355530111437729">💎</tg-emoji> <b>Выводы через-<a href="https://t.me/send"><tg-emoji emoji-id="5427054176246991778">🔵</tg-emoji> Cryptobot</a></b>

<tg-emoji emoji-id="5907025791006283345">💬</tg-emoji> <b><a href="https://t.me/your_support">Тех. поддержка</a> | <a href="https://t.me/your_chat">Наш чат</a> | <a href="https://t.me/your_news">Новости</a></b>
"""

# Старт
@router.message(CommandStart())
async def cmd_start(message: Message):
    photo_url = "https://iimg.su/i/gArwKT":
    
    await message.answer(
        get_main_menu_text(),
        parse_mode=ParseMode.HTML,
        reply_markup=get_main_menu()
        disable_web_page_preview=True
    )

# Обработчики кнопок разделов
@router.callback_query(F.data == "profile")
async def profile_callback(callback):
    await callback.message.edit_text(
        f'<tg-emoji emoji-id="{EMOJI_PROFILE}">👤</tg-emoji> <b>Раздел профиля</b>\n\n'
        f'Здесь будет отображаться информация о вашем профиле, статистика и настройки.',
        parse_mode=ParseMode.HTML,
        reply_markup=get_back_menu()
    )
    await callback.answer()

@router.callback_query(F.data == "partners")
async def partners_callback(callback):
    await callback.message.edit_text(
        f'<tg-emoji emoji-id="{EMOJI_PARTNERS}">🤝</tg-emoji> <b>Наши партнёры</b>\n\n'
        f'Список партнёров и информация о партнёрской программе появится здесь.',
        parse_mode=ParseMode.HTML,
        reply_markup=get_back_menu()
    )
    await callback.answer()

@router.callback_query(F.data == "games")
async def games_callback(callback):
    await callback.message.edit_text(
        f'<tg-emoji emoji-id="{EMOJI_GAMES}">🎮</tg-emoji> <b>Список игр</b>\n\n'
        f'Здесь будут отображаться все доступные игры с высокими коэффициентами.',
        parse_mode=ParseMode.HTML,
        reply_markup=get_back_menu()
    )
    await callback.answer()

@router.callback_query(F.data == "leaders")
async def leaders_callback(callback):
    await callback.message.edit_text(
        f'<tg-emoji emoji-id="{EMOJI_LEADERS}">🏆</tg-emoji> <b>Таблица лидеров</b>\n\n'
        f'Лучшие игроки недели и их достижения будут отображаться здесь.',
        parse_mode=ParseMode.HTML,
        reply_markup=get_back_menu()
    )
    await callback.answer()

@router.callback_query(F.data == "about")
async def about_callback(callback):
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

# Обработчик кнопки "На главную"
@router.callback_query(F.data == "back_to_main")
async def back_to_main_callback(callback):
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
