import logging
import uuid
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict
from dataclasses import dataclass
import aiohttp
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

# Настройки Cryptobot (обязательно замените!)
CRYPTOBOT_API_KEY = "477733:AAzooy5vcnCpJuGgTZc1Rdfbu71bqmrRMgr"  # Получить в @CryptoBot
CRYPTOBOT_API_URL = "https://pay.crypt.bot/api"

# Минимальные суммы
MIN_DEPOSIT = 0.1
MIN_WITHDRAWAL = 0.2  # ← изменено с 1.5

# Задержка между выводами (3 минуты)
WITHDRAWAL_COOLDOWN = 180  # секунд

# Время жизни счета (5 минут)
INVOICE_LIFETIME = 300  # секунд

# Эмодзи
EMOJI_CRYPTOBOT = "5427054176246991778"
EMOJI_WALLET = "5443127283898405358"
EMOJI_WITHDRAWAL = "5445355530111437729"
EMOJI_BACK = "5906771962734057347"
EMOJI_SUCCESS = "5199436362280976367"
EMOJI_ERROR = "5197923386472879129"
EMOJI_LINK = "5271604874419647061"

payment_router = Router()
bot: Bot = None  # Установится через setup_payments


# ========== FSM СОСТОЯНИЯ ==========
# ВАЖНО: в вашем main.py нужно добавить эти состояния
# и переводить пользователя в нужное состояние при нажатии кнопок
class PaymentStates(StatesGroup):
    waiting_deposit_amount = State()
    waiting_withdraw_amount = State()


# ========== ХРАНИЛИЩЕ ==========
class Storage:
    def __init__(self):
        self.users: Dict[int, dict] = {}
        self.invoices: Dict[str, dict] = {}
        self.check_tasks: Dict[str, asyncio.Task] = {}

    def get_user(self, user_id: int) -> dict:
        if user_id not in self.users:
            self.users[user_id] = {
                'balance': 1000.0,
                'last_withdrawal': None,
                'total_deposits': 3500.0,
                'total_withdrawals': 2250.0
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
            'chat_id': None
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


storage = Storage()


# ========== API CRYPTOBOT ==========
class CryptoBotAPI:
    def __init__(self, token: str):
        self.token = token
        self.headers = {"Crypto-Pay-API-Token": token}

    async def create_invoice(self, amount: float) -> Optional[dict]:
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


crypto_api = CryptoBotAPI(CRYPTOBOT_API_KEY)


# ========== ЗАДАЧА ПРОВЕРКИ ОПЛАТЫ ==========
async def check_payment_task(invoice_id: str):
    """Проверяет оплату каждые 2 секунды, обновляет сообщение"""
    try:
        invoice = storage.get_invoice(invoice_id)
        if not invoice:
            return

        for attempt in range(150):
            await asyncio.sleep(2)  # ← sleep в начале, чтобы Cryptobot успел зарегистрировать счет

            # Перечитываем актуальные данные счета (chat_id/message_id могут появиться чуть позже)
            invoice = storage.get_invoice(invoice_id)
            if not invoice:
                return

            # Проверяем истечение срока
            if datetime.now() > invoice['expires_at']:
                if invoice.get('chat_id') and invoice.get('message_id'):
                    try:
                        await bot.edit_message_text(
                            text=(
                                f"<tg-emoji emoji-id=\"{EMOJI_ERROR}\">❌</tg-emoji> <b>Счет истек</b>\n\n"
                                f"Время оплаты вышло. Попробуйте снова."
                            ),
                            parse_mode=ParseMode.HTML,
                            chat_id=invoice['chat_id'],
                            message_id=invoice['message_id'],
                            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                                InlineKeyboardButton(text="◀️ В профиль", callback_data="profile")
                            ]])
                        )
                    except Exception as e:
                        logging.error(f"Ошибка редактирования сообщения (expired): {e}")
                storage.update_invoice_status(invoice_id, 'expired')
                return

            # Проверяем статус в Cryptobot
            status = await crypto_api.get_invoice_status(invoice['crypto_id'])

            if status == 'paid':
                # Зачисляем баланс
                storage.add_balance(invoice['user_id'], invoice['amount'])
                storage.update_invoice_status(invoice_id, 'paid')

                # ← ИСПРАВЛЕНИЕ: обновляем сообщение с подтверждением оплаты
                if invoice.get('chat_id') and invoice.get('message_id'):
                    try:
                        await bot.edit_message_text(
                            text=(
                                f"<tg-emoji emoji-id=\"{EMOJI_SUCCESS}\">✅</tg-emoji> <b>Оплата получена!</b>\n\n"
                                f"Сумма <b>{invoice['amount']} USDT</b> зачислена на ваш баланс.\n"
                                f"Текущий баланс: <b>{storage.get_balance(invoice['user_id']):.2f} USDT</b>"
                            ),
                            parse_mode=ParseMode.HTML,
                            chat_id=invoice['chat_id'],
                            message_id=invoice['message_id'],
                            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                                InlineKeyboardButton(text="◀️ В профиль", callback_data="profile")
                            ]])
                        )
                    except Exception as e:
                        logging.error(f"Ошибка редактирования сообщения (paid): {e}")
                return

    except Exception as e:
        logging.error(f"Ошибка в задаче проверки: {e}")
    finally:
        if invoice_id in storage.check_tasks:
            del storage.check_tasks[invoice_id]


# ========== ПОПОЛНЕНИЕ ==========
# Фильтр: состояние waiting_deposit_amount — только тогда обрабатываем как депозит
@payment_router.message(PaymentStates.waiting_deposit_amount, F.text.regexp(r'^\d+\.?\d*$'))
async def deposit_amount(message: Message, state: FSMContext):
    """Обработка введенной суммы для пополнения"""
    await state.clear()  # Сбрасываем состояние

    try:
        amount = float(message.text)

        if amount < MIN_DEPOSIT:
            await message.answer(
                f"❌ Минимальная сумма пополнения: {MIN_DEPOSIT} USDT",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="◀️ В профиль", callback_data="profile")
                ]])
            )
            return

        # Создаем счет в Cryptobot
        invoice_data = await crypto_api.create_invoice(amount)

        if not invoice_data or 'pay_url' not in invoice_data:
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
            invoice_data['invoice_id'],
            invoice_data['pay_url']
        )

        sent_msg = await message.answer(
            text=(
                f"<b><tg-emoji emoji-id=\"5906482735341377395\">💰</tg-emoji> Счет создан!</b>\n\n"
                f"<blockquote>"
                f"<tg-emoji emoji-id=\"5197434882321567830\">💰</tg-emoji> Сумма: <b><code>{amount}</code> USDT</b>\n"
                f"<tg-emoji emoji-id=\"5906598824012420908\">⌛️</tg-emoji> Действует: <b>5 минут</b>"
                f"</blockquote>\n\n"
                f"<tg-emoji emoji-id=\"5386367538735104399\">🔵</tg-emoji> Ожидаем оплату..."
            ),
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💳 Оплатить", url=invoice_data['pay_url'], icon_custom_emoji_id=EMOJI_LINK)],
                [InlineKeyboardButton(text="◀️ Отмена", callback_data="profile", icon_custom_emoji_id=EMOJI_BACK)]
            ])
        )

        # Сохраняем chat_id и message_id для последующего редактирования
        storage.set_message_info(invoice_id, message.chat.id, sent_msg.message_id)

        # Запускаем фоновую проверку
        if invoice_id not in storage.check_tasks:
            task = asyncio.create_task(check_payment_task(invoice_id))
            storage.check_tasks[invoice_id] = task

    except ValueError:
        await message.answer("❌ Введите корректное число")


# ========== ВЫВОД ==========
# Фильтр: состояние waiting_withdraw_amount — только тогда обрабатываем как вывод
@payment_router.message(PaymentStates.waiting_withdraw_amount, F.text.regexp(r'^\d+\.?\d*$'))
async def withdraw_amount(message: Message, state: FSMContext):
    """Обработка суммы вывода"""
    await state.clear()  # Сбрасываем состояние

    try:
        amount = float(message.text)
        user_id = message.from_user.id
        balance = storage.get_balance(user_id)

        if amount < MIN_WITHDRAWAL:
            await message.answer(
                f"❌ Минимальная сумма вывода: {MIN_WITHDRAWAL} USDT",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="◀️ В профиль", callback_data="profile")
                ]])
            )
            return

        if amount > balance:
            await message.answer(
                f"❌ Недостаточно средств.\nВаш баланс: <b>{balance:.2f} USDT</b>",
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="◀️ В профиль", callback_data="profile")
                ]])
            )
            return

        # Проверяем cooldown
        can_withdraw, wait_time = storage.can_withdraw(user_id)
        if not can_withdraw:
            minutes = wait_time // 60
            seconds = wait_time % 60
            await message.answer(
                f"⏳ Следующий вывод доступен через <b>{minutes} мин {seconds} сек</b>",
                parse_mode=ParseMode.HTML,
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

        # Списываем баланс только после успешного создания чека
        storage.deduct_balance(user_id, amount)
        storage.set_last_withdrawal(user_id)

        # ← ИСПРАВЛЕНИЕ: отправляем сообщение с кнопкой-ссылкой на чек
        await message.answer(
            text=(
                f"<tg-emoji emoji-id=\"{EMOJI_SUCCESS}\">✅</tg-emoji> <b>Чек создан!</b>\n\n"
                f"Сумма: <b>{amount} USDT</b>\n"
                f"Новый баланс: <b>{storage.get_balance(user_id):.2f} USDT</b>\n\n"
                f"Нажмите кнопку ниже, чтобы получить чек в @CryptoBot"
            ),
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💸 Получить чек", url=check['check_url'])],
                [InlineKeyboardButton(text="◀️ В профиль", callback_data="profile")]
            ])
        )

    except ValueError:
        await message.answer("❌ Введите корректное число")


# ========== ИНИЦИАЛИЗАЦИЯ ==========
def setup_payments(bot_instance: Bot):
    global bot
    bot = bot_instance
