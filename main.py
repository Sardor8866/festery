import logging
from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters.command import CommandStart
from aiogram.types import Message
from aiogram.webhook.aiohttp_server import SimpleRequestHandler
from aiohttp import web
import os

# ============================================
# КОНФИГУРАЦИЯ - ЗАМЕНИТЕ НА СВОИ ЗНАЧЕНИЯ
# ============================================
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"  # Вставьте токен от @BotFather
WEBHOOK_URL = "https://your-app-name.onrender.com"  # Ваш URL на Render
# ============================================

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Константы
WEBHOOK_PATH = "/webhook"
WEBAPP_HOST = "0.0.0.0"
WEBAPP_PORT = int(os.getenv("PORT", 10000))  # Render автоматически устанавливает PORT

# Инициализация
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message):
    """Обработчик команды /start с кастомным эмодзи"""
    await message.answer(
        'Добро пожаловать в наш красочный бот! <tg-emoji emoji-id="5199885118214255386">🔥</tg-emoji>',
        parse_mode='HTML'
    )


@router.message(F.text == 'PRIMARY')
async def response_primary(message: Message):
    """Обработчик для текста 'PRIMARY'"""
    await message.answer(
        '<tg-emoji emoji-id="5280950718960781853">🟢</tg-emoji> Наши социальные сети:',
        parse_mode='HTML'
    )


@router.message()
async def echo_message(message: Message):
    """Эхо-обработчик для всех остальных сообщений"""
    await message.answer(
        f'Вы написали: {message.text}\n\n'
        f'Попробуйте:\n'
        f'• /start - приветствие <tg-emoji emoji-id="5199885118214255386">🔥</tg-emoji>\n'
        f'• PRIMARY - социальные сети <tg-emoji emoji-id="5280950718960781853">🟢</tg-emoji>',
        parse_mode='HTML'
    )


# Регистрация роутера
dp.include_router(router)


async def on_startup():
    """Действия при запуске бота"""
    webhook_url = f"{WEBHOOK_URL}{WEBHOOK_PATH}"
    await bot.set_webhook(
        url=webhook_url,
        drop_pending_updates=True
    )
    logger.info(f"✅ Webhook установлен на {webhook_url}")
    logger.info(f"✅ Бот запущен успешно!")


async def on_shutdown():
    """Действия при остановке бота"""
    await bot.delete_webhook()
    await bot.session.close()
    logger.info("❌ Бот остановлен")


def main():
    """Основная функция запуска"""
    # Создание aiohttp приложения
    app = web.Application()
    
    # Настройка webhook
    webhook_requests_handler = SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
    )
    webhook_requests_handler.register(app, path=WEBHOOK_PATH)
    
    # Настройка startup/shutdown
    app.on_startup.append(lambda _: on_startup())
    app.on_shutdown.append(lambda _: on_shutdown())
    
    # Запуск приложения
    logger.info(f"🚀 Запуск бота на порту {WEBAPP_PORT}...")
    web.run_app(
        app,
        host=WEBAPP_HOST,
        port=WEBAPP_PORT
    )


if __name__ == "__main__":
    main()
