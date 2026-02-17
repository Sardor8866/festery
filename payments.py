import logging
import uuid
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict
import aiohttp
from aiogram import Router, F, Bot
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ParseMode

# Настройки Cryptobot
CRYPTOBOT_API_KEY = "477733:AAzooy5vcnCpJuGgTZc1Rdfbu71bqmrRMgr"
CRYPTOBOT_API_URL = "https://pay.crypt.bot/api"

# Минимальные суммы
MIN_DEPOSIT = 0.1
MIN_WITHDRAWAL = 0.2

# Задержка между выводами (3 минуты)
WITHDRAWAL_COOLDOWN = 180

# Время жизни счета (5 минут)
INVOICE_LIFETIME = 300

# Эмодзи
EMOJI_BACK = "5906771962734057347"
EMOJI_SUCCESS = "5199436362280976367"
EMOJI_ERROR = "5197923386472879129"
EMOJI_LINK = "5271604874419647061"

payment_router = Router()
bot: Bot = None


# ========== ХРАНИЛИЩЕ ==========
class Storage:
    def __init__(self):
        self.users: Dict[int, dict] = {}
        self.invoices: Dict[str, dict] = {}
        self.check_tasks: Dict[str, asyncio.Task] = {}
        self.pending_action: Dict[int, str] = {}

    def set_pending(self, user_id: int, action: str):
        self.pending_action[user_id] = action

    def get_pending(self, user_id: int) -> Optional[str]:
        return self.pending_action.get(user_id)

    def clear_pending(self, user_id: int):
        self.pending_action.pop(user_id, None)

    def get_user(self, user_id: int) -> dict:
        if user_id not in self.users:
            self.users[user_id] = {
                'balance': 0.0,
                'last_withdrawal': None,
                'total_deposits': 0.0,
                'total_withdrawals': 0.0
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
            logging.info(f"[{invoice_id}] set_message_info: chat_id={chat_id}, message_id={message_id}")


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
                data = await resp.json()
                logging.info(f"createCheck response (status={resp.status}): {data}")
                if resp.status == 200 and data.get("ok"):
                    return data.get("result")
                else:
                    logging.error(f"createCheck error: {data}")
                    return None
            except Exception as e:
                logging.error(f"Ошибка создания чека: {e}")
            return None


crypto_api = CryptoBotAPI(CRYPTOBOT_API_KEY)


# ========== ФОНОВАЯ ПРОВЕРКА ОПЛАТЫ ==========
async def check_payment_task(invoice_id: str):
    """Проверяет оплату каждые 2 секунды, обновляет сообщение при оплате/истечении"""
    try:
        # Ждём появления chat_id и message_id (до 10 секунд, по 1 сек)
        for wait in range(10):
            await asyncio.sleep(1)
            invoice = storage.get_invoice(invoice_id)
            if invoice and invoice.get('chat_id') and invoice.get('message_id'):
                logging.info(f"[{invoice_id}] message_id получен за {wait+1} сек")
                break
        else:
            logging.error(f"[{invoice_id}] chat_id/message_id не появились за 10 сек — продолжаем без обновления сообщения")

        for attempt in range(150):
            invoice = storage.get_invoice(invoice_id)
            if not invoice:
                return

            # Счет истек
            if datetime.now() > invoice['expires_at']:
                logging.info(f"[{invoice_id}] Счет истек на попытке {attempt}")
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
                        logging.error(f"[{invoice_id}] Ошибка edit (expired): {e}")
                storage.update_invoice_status(invoice_id, 'expired')
                return

            # Проверяем статус в Cryptobot
            status = await crypto_api.get_invoice_status(invoice['crypto_id'])
            logging.info(f"[{invoice_id}] Попытка {attempt+1}: статус={status}, chat_id={invoice.get('chat_id')}, msg_id={invoice.get('message_id')}")

            if status == 'paid':
                storage.add_balance(invoice['user_id'], invoice['amount'])
                storage.update_invoice_status(invoice_id, 'paid')
                logging.info(f"[{invoice_id}] ОПЛАЧЕН — начислено {invoice['amount']} USDT пользователю {invoice['user_id']}")

                if invoice.get('chat_id') and invoice.get('message_id'):
                    try:
                        await bot.edit_message_text(
                            text=(
                                f"✅ <b>Оплата получена!</b>\n\n"
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
                        logging.info(f"[{invoice_id}] Сообщение обновлено успешно")
                    except Exception as e:
                        logging.error(f"[{invoice_id}] Ошибка edit (paid): {e}")
                else:
                    logging.error(f"[{invoice_id}] НЕТ chat_id/message_id — сообщение не обновлено!")
                return

            await asyncio.sleep(2)

    except Exception as e:
        logging.error(f"Ошибка в задаче проверки [{invoice_id}]: {e}")
    finally:
        if invoice_id in storage.check_tasks:
            del storage.check_tasks[invoice_id]


# ========== ХЕНДЛЕР ВВОДА СУММЫ ==========
@payment_router.message(F.text.regexp(r'^\d+\.?\d*$'))
async def handle_amount_input(message: Message):
    """Единый обработчик числового ввода — смотрит pending_action"""
    user_id = message.from_user.id
    action = storage.get_pending(user_id)

    if action == 'deposit':
        storage.clear_pending(user_id)
        await _process_deposit(message, user_id)
    elif action == 'withdraw':
        storage.clear_pending(user_id)
        await _process_withdraw(message, user_id)


# ========== ПОПОЛНЕНИЕ ==========
async def _process_deposit(message: Message, user_id: int):
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

        invoice_data = await crypto_api.create_invoice(amount)

        if not invoice_data or 'pay_url' not in invoice_data:
            await message.answer(
                "❌ Ошибка создания счета. Попробуйте позже.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="◀️ В профиль", callback_data="profile")
                ]])
            )
            return

        invoice_id = storage.create_invoice(
            user_id,
            amount,
            invoice_data['invoice_id'],
            invoice_data['pay_url']
        )

        sent_msg = await message.answer(
            text=(
                f"<b><tg-emoji emoji-id=\"5906482735341377395\">💰</tg-emoji>Счет Создан!</b>\n\n"
                f"<blockquote><tg-emoji emoji-id=\"5197434882321567830\">💰</tg-emoji>Сумма: <b><code>{amount}</code></b>\n"
                f"<tg-emoji emoji-id=\"5906598824012420908\">⌛️</tg-emoji>Действует-<b>5 минут</b></blockquote>\n\n"
                f"<tg-emoji emoji-id=\"5386367538735104399\">🔵</tg-emoji>Ждем оплату!"
            ),
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Оплатить", url=invoice_data['pay_url'], icon_custom_emoji_id=EMOJI_LINK)],
                [InlineKeyboardButton(text="Отмена", callback_data="profile", icon_custom_emoji_id=EMOJI_BACK)]
            ])
        )

        # Сохраняем СРАЗУ после отправки — до запуска задачи
        storage.set_message_info(invoice_id, message.chat.id, sent_msg.message_id)

        # Запускаем фоновую проверку уже ПОСЛЕ set_message_info
        if invoice_id not in storage.check_tasks:
            task = asyncio.create_task(check_payment_task(invoice_id))
            storage.check_tasks[invoice_id] = task

    except ValueError:
        await message.answer("❌ Введите число")


# ========== ВЫВОД ==========
async def _process_withdraw(message: Message, user_id: int):
    try:
        amount = float(message.text)
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
                f"❌ Недостаточно средств. Баланс: {balance:.2f} USDT",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="◀️ В профиль", callback_data="profile")
                ]])
            )
            return

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

        check = await crypto_api.create_check(amount, user_id)

        if not check or 'check_url' not in check:
            await message.answer(
                "❌ Ошибка создания чека. Попробуйте позже.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="◀️ В профиль", callback_data="profile")
                ]])
            )
            return

        storage.deduct_balance(user_id, amount)
        storage.set_last_withdrawal(user_id)

        await message.answer(
            text=(
                f"<tg-emoji emoji-id=\"{EMOJI_SUCCESS}\">✅</tg-emoji> <b>Чек создан!</b>\n\n"
                f"Сумма: <b>{amount} USDT</b>\n"
                f"Новый баланс: <b>{storage.get_balance(user_id):.2f} USDT</b>\n\n"
                f"Нажмите кнопку ниже, чтобы активировать чек в @CryptoBot"
            ),
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💸 Получить чек", url=check['check_url'])],
                [InlineKeyboardButton(text="◀️ В профиль", callback_data="profile")]
            ])
        )

    except ValueError:
        await message.answer("❌ Введите число")


# ========== ИНИЦИАЛИЗАЦИЯ ==========
def setup_payments(bot_instance: Bot):
    global bot
    bot = bot_instance
