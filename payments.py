import logging
import uuid
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from dataclasses import dataclass
import aiohttp
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ParseMode
from aiogram.filters import Command

# Настройки Cryptobot (обязательно замените!)
CRYPTOBOT_API_KEY = "477733:AAzooy5vcnCpJuGgTZc1Rdfbu71bqmrRMgr"  # Получить в @CryptoBot
CRYPTOBOT_API_URL = "https://pay.crypt.bot/api"
ADMIN_ID = 8118184388  # Замените на ваш Telegram ID

# Минимальные суммы
MIN_DEPOSIT = 0.1
MIN_WITHDRAWAL = 1.5

# Задержка между выводами (3 минуты)
WITHDRAWAL_COOLDOWN = 180  # секунд

# Время жизни счета (5 минут)
INVOICE_LIFETIME = 300  # секунд

# Эмодзи из вашего main.py
EMOJI_CRYPTOBOT = "5427054176246991778"
EMOJI_WALLET = "5443127283898405358"
EMOJI_WITHDRAWAL = "5445355530111437729"
EMOJI_BACK = "5906771962734057347"
EMOJI_SUCCESS = "5199436362280976367"
EMOJI_ERROR = "5197923386472879129"
EMOJI_LINK = "5271604874419647061"
payment_router = Router()
bot: Bot = None  # Установится через setup_payments

# Простое хранилище (в реальном проекте замените на БД)
class Storage:
    def __init__(self):
        self.users: Dict[int, dict] = {}  # user_id -> {balance, last_withdrawal, total_deposits, total_withdrawals}
        self.invoices: Dict[str, dict] = {}  # invoice_id -> данные счета
        self.check_tasks: Dict[str, asyncio.Task] = {}  # задачи проверки
        self.withdrawal_checks: List[dict] = []  # список всех созданных чеков на вывод
        
    def get_user(self, user_id: int) -> dict:
        if user_id not in self.users:
            self.users[user_id] = {
                'balance': 1000.0,  # Тестовый баланс
                'last_withdrawal': None,
                'total_deposits': 3500.0,  # Тестовые данные
                'total_withdrawals': 2250.0  # Тестовые данные
            }
        return self.users[user_id]
    
    def get_balance(self, user_id: int) -> float:
        return self.get_user(user_id)['balance']
    
    def add_balance(self, user_id: int, amount: float):
        user = self.get_user(user_id)
        user['balance'] += amount
        user['total_deposits'] = user.get('total_deposits', 0) + amount
    
    def deduct_balance(self, user_id: int, amount: float) -> bool:
        user = self.get_user(user_id)
        if user['balance'] >= amount:
            user['balance'] -= amount
            user['total_withdrawals'] = user.get('total_withdrawals', 0) + amount
            return True
        return False
    
    def can_withdraw(self, user_id: int) -> tuple[bool, Optional[int]]:
        """Проверка задержки 3 минуты"""
        user = self.get_user(user_id)
        last = user['last_withdrawal']
        
        if not last:
            return True, None
        
        seconds = (datetime.now() - last).total_seconds()
        if seconds < WITHDRAWAL_COOLDOWN:
            return False, int(WITHDRAWAL_COOLDOWN - seconds)
        return True, None
    
    def set_last_withdrawal(self, user_id: int):
        self.get_user(user_id)['last_withdrawal'] = datetime.now()
    
    def create_invoice(self, user_id: int, amount: float, crypto_id: int, pay_url: str) -> str:
        """Создает счет и запускает проверку"""
        invoice_id = str(uuid.uuid4())
        expires_at = datetime.now() + timedelta(seconds=INVOICE_LIFETIME)
        
        self.invoices[invoice_id] = {
            'user_id': user_id,
            'amount': amount,
            'crypto_id': crypto_id,
            'pay_url': pay_url,
            'expires_at': expires_at,
            'status': 'pending',
            'message_id': None,
            'chat_id': None,
            'created_at': datetime.now()
        }
        
        return invoice_id
    
    def get_invoice(self, invoice_id: str) -> Optional[dict]:
        return self.invoices.get(invoice_id)
    
    def update_invoice_status(self, invoice_id: str, status: str):
        if invoice_id in self.invoices:
            self.invoices[invoice_id]['status'] = status
    
    def set_message_info(self, invoice_id: str, chat_id: int, message_id: int):
        if invoice_id in self.invoices:
            self.invoices[invoice_id]['chat_id'] = chat_id
            self.invoices[invoice_id]['message_id'] = message_id
    
    def add_withdrawal_check(self, user_id: int, amount: float, check_data: dict):
        """Сохраняет информацию о созданном чеке на вывод"""
        self.withdrawal_checks.append({
            'user_id': user_id,
            'amount': amount,
            'check_id': check_data.get('check_id'),
            'check_url': check_data.get('check_url'),
            'created_at': datetime.now(),
            'status': 'created'
        })
    
    def get_all_withdrawal_checks(self) -> List[dict]:
        """Возвращает все созданные чеки на вывод"""
        return self.withdrawal_checks

# Создаем экземпляр хранилища
storage = Storage()

# API Cryptobot
class CryptoBotAPI:
    def __init__(self, token: str):
        self.token = token
        self.headers = {"Crypto-Pay-API-Token": token}
    
    async def create_invoice(self, amount: float) -> Optional[dict]:
        """Создает счет на оплату"""
        async with aiohttp.ClientSession() as session:
            try:
                resp = await session.post(
                    f"{CRYPTOBOT_API_URL}/createInvoice",
                    headers=self.headers,
                    json={
                        "asset": "USDT",
                        "amount": str(amount),
                        "expires_in": INVOICE_LIFETIME
                    }
                )
                if resp.status == 200:
                    data = await resp.json()
                    return data.get('result') if data.get('ok') else None
            except Exception as e:
                logging.error(f"Ошибка создания счета: {e}")
            return None
    
    async def get_invoice_status(self, invoice_id: int) -> Optional[str]:
        """Проверяет статус счета"""
        async with aiohttp.ClientSession() as session:
            try:
                resp = await session.post(
                    f"{CRYPTOBOT_API_URL}/getInvoices",
                    headers=self.headers,
                    json={"invoice_ids": [invoice_id]}
                )
                if resp.status == 200:
                    data = await resp.json()
                    if data.get('ok') and data.get('result', {}).get('items'):
                        return data['result']['items'][0].get('status')
            except Exception as e:
                logging.error(f"Ошибка проверки статуса: {e}")
            return None
    
    async def create_check(self, amount: float, user_id: int) -> Optional[dict]:
        """Создает чек на выплату"""
        async with aiohttp.ClientSession() as session:
            try:
                resp = await session.post(
                    f"{CRYPTOBOT_API_URL}/createCheck",
                    headers=self.headers,
                    json={
                        "asset": "USDT",
                        "amount": str(amount),
                        "pin_to_user_id": str(user_id)
                    }
                )
                if resp.status == 200:
                    data = await resp.json()
                    return data.get('result') if data.get('ok') else None
            except Exception as e:
                logging.error(f"Ошибка создания чека: {e}")
            return None
    
    async def get_checks(self) -> Optional[List[dict]]:
        """Получает список всех чеков из Cryptobot"""
        async with aiohttp.ClientSession() as session:
            try:
                resp = await session.post(
                    f"{CRYPTOBOT_API_URL}/getChecks",
                    headers=self.headers,
                    json={"status": "active"}  # Можно изменить на нужный статус
                )
                if resp.status == 200:
                    data = await resp.json()
                    if data.get('ok'):
                        return data.get('result', {}).get('items', [])
            except Exception as e:
                logging.error(f"Ошибка получения чеков: {e}")
            return None

# Инициализация API
crypto_api = CryptoBotAPI(CRYPTOBOT_API_KEY)

# Функция автоматической проверки оплаты
async def check_payment_task(invoice_id: str):
    """Проверяет оплату каждые 2 секунды"""
    try:
        invoice = storage.get_invoice(invoice_id)
        if not invoice:
            return
        
        # Проверяем 5 минут (300 секунд / 2 = 150 попыток)
        for attempt in range(150):
            # Проверяем, не истек ли срок
            if datetime.now() > invoice['expires_at']:
                await bot.edit_message_text(
                    f"<tg-emoji emoji-id=\"{EMOJI_ERROR}\">❌</tg-emoji> <b>Счет истек</b>\n\n"
                    f"Время оплаты вышло. Попробуйте снова.",
                    parse_mode=ParseMode.HTML,
                    chat_id=invoice['chat_id'],
                    message_id=invoice['message_id'],
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                        InlineKeyboardButton(text="◀️ В профиль", callback_data="profile")
                    ]])
                )
                storage.update_invoice_status(invoice_id, 'expired')
                return
            
            # Проверяем статус в Cryptobot
            status = await crypto_api.get_invoice_status(invoice['crypto_id'])
            
            if status == 'paid':
                # Зачисляем баланс
                storage.add_balance(invoice['user_id'], invoice['amount'])
                
                await bot.edit_message_text(
                    f"<tg-emoji emoji-id=\"{EMOJI_SUCCESS}\">✅</tg-emoji> <b>Оплата получена!</b>\n\n"
                    f"Сумма <b>{invoice['amount']} USDT</b> зачислена на ваш баланс.",
                    parse_mode=ParseMode.HTML,
                    chat_id=invoice['chat_id'],
                    message_id=invoice['message_id'],
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                        InlineKeyboardButton(text="◀️ В профиль", callback_data="profile")
                    ]])
                )
                storage.update_invoice_status(invoice_id, 'paid')
                return
            
            # Ждем 2 секунды перед следующей проверкой
            await asyncio.sleep(2)
            
    except Exception as e:
        logging.error(f"Ошибка в задаче проверки: {e}")
    finally:
        # Удаляем задачу из словаря
        if invoice_id in storage.check_tasks:
            del storage.check_tasks[invoice_id]

# ========== КОМАНДА АДМИНА ДЛЯ ПРОСМОТРА ЧЕКОВ ==========
@payment_router.message(Command("checks"))
async def admin_checks(message: Message):
    """Команда для админа - показывает все созданные чеки"""
    # Проверяем, что пользователь - администратор
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ У вас нет прав для выполнения этой команды")
        return
    
    # Получаем чеки из локального хранилища
    local_checks = storage.get_all_withdrawal_checks()
    
    # Получаем чеки из API Cryptobot
    api_checks = await crypto_api.get_checks()
    
    # Формируем сообщение
    text = "<b>📋 Все созданные чеки</b>\n\n"
    
    # Локальные чеки
    text += f"<b>Локальные чеки ({len(local_checks)}):</b>\n"
    if local_checks:
        for i, check in enumerate(local_checks[-10:], 1):  # Показываем последние 10
            text += (
                f"{i}. <a href='{check['check_url']}'>Чек #{check['check_id']}</a>\n"
                f"   👤 User: {check['user_id']}\n"
                f"   💰 Сумма: {check['amount']} USDT\n"
                f"   ⏰ {check['created_at'].strftime('%d.%m %H:%M')}\n\n"
            )
    else:
        text += "Нет локальных чеков\n\n"
    
    # Чеки из API
    text += f"<b>Чеки из API Cryptobot ({len(api_checks) if api_checks else 0}):</b>\n"
    if api_checks:
        for i, check in enumerate(api_checks[:10], 1):  # Показываем первые 10
            text += (
                f"{i}. <a href='{check.get('check_url')}'>Чек #{check.get('check_id')}</a>\n"
                f"   💰 Сумма: {check.get('amount')} {check.get('asset')}\n"
                f"   👤 Для: {check.get('user_id')}\n"
                f"   📊 Статус: {check.get('status')}\n\n"
            )
    else:
        text += "Нет чеков в API"
    
    # Кнопка для обновления
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🔄 Обновить", callback_data="admin_refresh_checks")
    ]])
    
    await message.answer(text, parse_mode=ParseMode.HTML, reply_markup=keyboard, disable_web_page_preview=True)

@payment_router.callback_query(F.data == "admin_refresh_checks")
async def admin_refresh_checks(callback: CallbackQuery):
    """Обновляет список чеков"""
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    await callback.message.delete()
    # Создаем новое сообщение с командой /checks
    await admin_checks(callback.message)

# ========== ПОПОЛНЕНИЕ ==========
@payment_router.message(F.text.regexp(r'^\d+\.?\d*$'))
async def deposit_amount(message: Message):
    """Обработка введенной суммы для пополнения"""
    # Проверяем, что это пополнение (в реальном проекте используйте FSM)
    # Для простоты будем считать, что если пользователь ввел число и не в процессе вывода - это пополнение
    
    try:
        amount = float(message.text)
        
        if amount < MIN_DEPOSIT:
            await message.answer(
                f"❌ Минимальная сумма {MIN_DEPOSIT} USDT",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="◀️ В профиль", callback_data="profile")
                ]])
            )
            return
        
        # Создаем счет в Cryptobot
        invoice = await crypto_api.create_invoice(amount)
        
        if not invoice or 'pay_url' not in invoice:
            await message.answer(
                "❌ Ошибка создания счета. Попробуйте позже.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="◀️ В профиль", callback_data="profile")
                ]])
            )
            return
        
        # Сохраняем счет
        invoice_id = storage.create_invoice(
            message.from_user.id,
            amount,
            invoice['invoice_id'],
            invoice['pay_url']
        )
        
        # Отправляем сообщение с кнопкой оплаты
        sent_msg = await message.answer(
            f"<b><tg-emoji emoji-id=\"5906482735341377395\">💰</tg-emoji>Счет Создан!</b>\n\n"
            f"<blockquote><tg-emoji emoji-id=\"5197434882321567830\">💰</tg-emoji>Сумма: <b><code>{amount}</code></b>\n"
            f"<tg-emoji emoji-id=\"5906598824012420908\">⌛️</tg-emoji>Действует-<b>5 минут</b></blockquote>\n\n"
            f"<tg-emoji emoji-id=\"5386367538735104399\">🔵</tg-emoji>Ждем оплату!",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text="Оплатить", 
                    url=invoice['pay_url'],
                    icon_custom_emoji_id=EMOJI_LINK  
                )],
                [InlineKeyboardButton(
                    text="Отмена", 
                    callback_data="profile",
                    icon_custom_emoji_id=EMOJI_BACK
                )]
            ])
        )
        
        # Сохраняем информацию о сообщении
        storage.set_message_info(invoice_id, message.chat.id, sent_msg.message_id)
        
        # Запускаем автоматическую проверку
        if invoice_id not in storage.check_tasks:
            task = asyncio.create_task(check_payment_task(invoice_id))
            storage.check_tasks[invoice_id] = task
        
    except ValueError:
        await message.answer("❌ Введите число")

# ========== ВЫВОД ==========
@payment_router.message(F.text.regexp(r'^\d+\.?\d*$'))
async def withdraw_amount(message: Message):
    """Обработка суммы вывода"""
    try:
        amount = float(message.text)
        user_id = message.from_user.id
        balance = storage.get_balance(user_id)
        
        # Проверки
        if amount < MIN_WITHDRAWAL:
            await message.answer(
                f"❌ Минимальная сумма {MIN_WITHDRAWAL} USDT",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="◀️ В профиль", callback_data="profile")
                ]])
            )
            return
        
        if amount > balance:
            await message.answer(
                f"❌ Недостаточно средств. Баланс: {balance:.2f} USDT",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="◀️ В профиль", callback_data="profile")
                ]])
            )
            return
        
        # Проверяем задержку
        can_withdraw, wait_time = storage.can_withdraw(user_id)
        if not can_withdraw:
            minutes = wait_time // 60
            seconds = wait_time % 60
            await message.answer(
                f"⏳ Подождите {minutes} мин {seconds} сек",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="◀️ В профиль", callback_data="profile")
                ]])
            )
            return
        
        # Создаем чек в Cryptobot
        check = await crypto_api.create_check(amount, user_id)
        
        if not check or 'check_url' not in check:
            await message.answer(
                "❌ Ошибка создания чека. Попробуйте позже.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="◀️ В профиль", callback_data="profile")
                ]])
            )
            return
        
        # Сохраняем чек в локальное хранилище
        storage.add_withdrawal_check(user_id, amount, check)
        
        # Списываем баланс
        storage.deduct_balance(user_id, amount)
        storage.set_last_withdrawal(user_id)
        
        # Отправляем чек
        buttons = [
            [InlineKeyboardButton(text="💸 Получить чек", url=check['check_url'])],
            [InlineKeyboardButton(text="◀️ В профиль", callback_data="profile")]
        ]
        
        await message.answer(
            f"<tg-emoji emoji-id=\"{EMOJI_SUCCESS}\">✅</tg-emoji> <b>Чек создан!</b>\n\n"
            f"Сумма: <b>{amount} USDT</b>\n"
            f"Новый баланс: <b>{storage.get_balance(user_id):.2f} USDT</b>\n\n"
            f"Нажмите кнопку ниже, чтобы активировать чек в @CryptoBot",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
        )
        
    except ValueError:
        await message.answer("❌ Введите число")

# Функция для установки bot из main.py
def setup_payments(bot_instance: Bot):
    global bot
    bot = bot_instance
