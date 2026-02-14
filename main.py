import asyncio
import logging
from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters.command import CommandStart
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiohttp import web

# Настройки
BOT_TOKEN = "8586332532:AAHX758cf6iOUpPNpY2sqseGBYsKJo9js4U"  # замени на свой токен
WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = "https://festery.onrender.com" + WEBHOOK_PATH  # замени на свой домен Render

# ID кастомных эмодзи (позже можно поменять)
EMOJI_WELCOME = "5199885118214255386"  # для приветствия
EMOJI_PROFILE = "5199885118214255386"  # для кнопки профиля
EMOJI_PARTNERS = "5199885118214255386"  # для кнопки партнеры
EMOJI_GAMES = "5199885118214255386"     # для кнопки игры
EMOJI_LEADERS = "5199885118214255386"   # для кнопки лидеры
EMOJI_ABOUT = "5199885118214255386"     # для кнопки о проекте

# Роутер
router = Router()

# Клавиатура с inline-кнопками (с кастомными эмодзи)
def get_main_menu():
    buttons = [
        [InlineKeyboardButton(
            text=f'<tg-emoji emoji-id="{EMOJI_PROFILE}">👤</tg-emoji> Профиль', 
            callback_data="profile"
        )],
        [InlineKeyboardButton(
            text=f'<tg-emoji emoji-id="{EMOJI_PARTNERS}">🤝</tg-emoji> Партнёры', 
            callback_data="partners"
        )],
        [InlineKeyboardButton(
            text=f'<tg-emoji emoji-id="{EMOJI_GAMES}">🎮</tg-emoji> Игры', 
            callback_data="games"
        )],
        [InlineKeyboardButton(
            text=f'<tg-emoji emoji-id="{EMOJI_LEADERS}">🏆</tg-emoji> Лидеры', 
            callback_data="leaders"
        )],
        [InlineKeyboardButton(
            text=f'<tg-emoji emoji-id="{EMOJI_ABOUT}">ℹ️</tg-emoji> О проекте', 
            callback_data="about"
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

@router.callback_query(F.data == "partners")
async def partners_callback(callback):
    await callback.message.edit_text(
        f'<tg-emoji emoji-id="{EMOJI_PARTNERS}">🤝</tg-emoji> Наши партнёры (в разработке)',
        parse_mode=ParseMode.HTML,
        reply_markup=get_main_menu()
    )

@router.callback_query(F.data == "games")
async def games_callback(callback):
    await callback.message.edit_text(
        f'<tg-emoji emoji-id="{EMOJI_GAMES}">🎮</tg-emoji> Список игр (в разработке)',
        parse_mode=ParseMode.HTML,
        reply_markup=get_main_menu()
    )

@router.callback_query(F.data == "leaders")
async def leaders_callback(callback):
    await callback.message.edit_text(
        f'<tg-emoji emoji-id="{EMOJI_LEADERS}">🏆</tg-emoji> Таблица лидеров (в разработке)',
        parse_mode=ParseMode.HTML,
        reply_markup=get_main_menu()
    )

@router.callback_query(F.data == "about")
async def about_callback(callback):
    await callback.message.edit_text(
        f'<tg-emoji emoji-id="{EMOJI_ABOUT}">ℹ️</tg-emoji> О проекте (в разработке)',
        parse_mode=ParseMode.HTML,
        reply_markup=get_main_menu()
    )

# Основная функция
async def main():
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_router(router)

    # Удаляем вебхук перед установкой нового
    await bot.delete_webhook(drop_pending_updates=True)
    await bot.set_webhook(WEBHOOK_URL)

    # Запускаем aiohttp сервер для вебхуков
    app = web.Application()
    
    async def webhook_handler(request):
        update = await request.json()
        await dp.feed_update(bot, update)
        return web.Response()
    
    app.router.add_post(WEBHOOK_PATH, webhook_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=8080)
    await site.start()

    logging.info(f"Бот запущен на вебхуках: {WEBHOOK_URL}")
    await asyncio.Event().wait()  # держим запущенным

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
