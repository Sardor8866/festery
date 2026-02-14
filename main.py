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
EMOJI_PROFILE = "5199885118214255386"
EMOJI_PARTNERS = "5199885118214255386"
EMOJI_GAMES = "5199885118214255386"
EMOJI_LEADERS = "5199885118214255386"
EMOJI_ABOUT = "5199885118214255386"

# Роутер
router = Router()

# Клавиатура с inline-кнопками (с кастомными эмодзи через icon_custom_emoji_id)
def get_main_menu():
    buttons = [
        [InlineKeyboardButton(
            text="Профиль",
            callback_data="profile",
            icon_custom_emoji_id=EMOJI_PROFILE
        )],
        [InlineKeyboardButton(
            text="Партнёры", 
            callback_data="partners",
            icon_custom_emoji_id=EMOJI_PARTNERS
        )],
        [InlineKeyboardButton(
            text="Игры",
            callback_data="games",
            icon_custom_emoji_id=EMOJI_GAMES
        )],
        [InlineKeyboardButton(
            text="Лидеры",
            callback_data="leaders",
            icon_custom_emoji_id=EMOJI_LEADERS
        )],
        [InlineKeyboardButton(
            text="О проекте",
            callback_data="about",
            icon_custom_emoji_id=EMOJI_ABOUT
        )],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# Старт
@router.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer(
        f'Добро пожаловать в наш красочный бот! <tg-emoji emoji-id="{EMOJI_WELCOME}">👋</tg-emoji>',
        parse_mode=ParseMode.HTML,
        reply_markup=get_main_menu()
    )

# Обработчики кнопок
@router.callback_query(F.data == "profile")
async def profile_callback(callback):
    await callback.message.edit_text(
        f'<tg-emoji emoji-id="{EMOJI_PROFILE}">👤</tg-emoji> Раздел профиля (в разработке)',
        parse_mode=ParseMode.HTML,
        reply_markup=get_main_menu()
    )
    await callback.answer()

@router.callback_query(F.data == "partners")
async def partners_callback(callback):
    await callback.message.edit_text(
        f'<tg-emoji emoji-id="{EMOJI_PARTNERS}">🤝</tg-emoji> Наши партнёры (в разработке)',
        parse_mode=ParseMode.HTML,
        reply_markup=get_main_menu()
    )
    await callback.answer()

@router.callback_query(F.data == "games")
async def games_callback(callback):
    await callback.message.edit_text(
        f'<tg-emoji emoji-id="{EMOJI_GAMES}">🎮</tg-emoji> Список игр (в разработке)',
        parse_mode=ParseMode.HTML,
        reply_markup=get_main_menu()
    )
    await callback.answer()

@router.callback_query(F.data == "leaders")
async def leaders_callback(callback):
    await callback.message.edit_text(
        f'<tg-emoji emoji-id="{EMOJI_LEADERS}">🏆</tg-emoji> Таблица лидеров (в разработке)',
        parse_mode=ParseMode.HTML,
        reply_markup=get_main_menu()
    )
    await callback.answer()

@router.callback_query(F.data == "about")
async def about_callback(callback):
    await callback.message.edit_text(
        f'<tg-emoji emoji-id="{EMOJI_ABOUT}">ℹ️</tg-emoji> О проекте (в разработке)',
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
