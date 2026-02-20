# leaders.py

import json
import logging
from datetime import datetime, timedelta
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.enums import ParseMode

# Эмодзи из main.py
EMOJI_LEADERS = "5440539497383087970"
EMOJI_BACK = "5906771962734057347"
EMOJI_WALLET = "5443127283898405358"
EMOJI_WITHDRAWAL = "5445355530111437729"
EMOJI_STATS = "5197288647275071607"
EMOJI_PROFILE = "5906581476639513176"

leaders_router = Router()

# Хранилище данных пользователей
USER_DATA_FILE = 'users_data.json'

def load_users_data():
    """Загрузка данных пользователей"""
    try:
        with open(USER_DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        return {}

def save_users_data(data):
    """Сохранение данных пользователей"""
    with open(USER_DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def setup_leaders():
    """Инициализация модуля лидеров (создание файла если не существует)"""
    try:
        # Пробуем загрузить данные, если файла нет - создаем пустой
        data = load_users_data()
        if not data:
            save_users_data({})
        logging.info("Модуль лидеров успешно инициализирован")
        return True
    except Exception as e:
        logging.error(f"Ошибка инициализации модуля лидеров: {e}")
        return False

def update_user_stats(user_id: int, username: str = None, deposit: float = 0, turnover: float = 0, wins: float = 0):
    """Обновление статистики пользователя"""
    try:
        data = load_users_data()
        user_id_str = str(user_id)
        
        if user_id_str not in data:
            data[user_id_str] = {
                'username': username,
                'deposit': 0,
                'turnover': 0,
                'wins': 0,
                'first_seen': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
        
        if username:
            data[user_id_str]['username'] = username
        
        if deposit > 0:
            data[user_id_str]['deposit'] = data[user_id_str].get('deposit', 0) + deposit
        
        if turnover > 0:
            data[user_id_str]['turnover'] = data[user_id_str].get('turnover', 0) + turnover
        
        if wins > 0:
            data[user_id_str]['wins'] = data[user_id_str].get('wins', 0) + wins
        
        save_users_data(data)
        return data[user_id_str]
    except Exception as e:
        logging.error(f"Ошибка обновления статистики для user {user_id}: {e}")
        return None

# ========== КЛАВИАТУРЫ ==========
def get_leaders_keyboard(selected: str = 'deposit'):
    """Клавиатура для переключения категорий лидеров"""
    buttons = [
        InlineKeyboardButton(
            text=f"{'✅ ' if selected == 'deposit' else ''}📥 Депозит", 
            callback_data="leaders_deposit"
        ),
        InlineKeyboardButton(
            text=f"{'✅ ' if selected == 'turnover' else ''}💱 Оборот", 
            callback_data="leaders_turnover"
        ),
        InlineKeyboardButton(
            text=f"{'✅ ' if selected == 'wins' else ''}🥳 Выигрыши", 
            callback_data="leaders_wins"
        ),
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=[
        buttons,  # Первый ряд - три кнопки
        [  # Второй ряд - кнопка назад
            InlineKeyboardButton(
                text="◀️ На главную", 
                callback_data="back_to_main",
                icon_custom_emoji_id=EMOJI_BACK
            )
        ]
    ])

# ========== ФОРМАТИРОВАНИЕ ТОПА ==========
def format_leaderboard(users_data, key: str):
    """Форматирование топа 10 пользователей"""
    # Фильтруем пользователей с положительными значениями
    filtered_data = {
        user_id: data for user_id, data in users_data.items() 
        if data.get(key, 0) > 0
    }
    
    # Сортируем по убыванию
    sorted_leaders = sorted(
        filtered_data.items(),
        key=lambda item: item[1].get(key, 0),
        reverse=True
    )[:10]

    if not sorted_leaders:
        return "<blockquote>📭 Пока нет данных для отображения</blockquote>"

    # Заголовки для разных категорий
    titles = {
        'deposit': 'ТОП-10 ПО ДЕПОЗИТАМ 📥',
        'turnover': 'ТОП-10 ПО ОБОРОТУ 💱',
        'wins': 'ТОП-10 ПО ВЫИГРЫШАМ 🥳'
    }
    
    # Эмодзи для топ-3
    top_emojis = ["🥇", "🥈", "🥉"]
    
    text = f"<tg-emoji emoji-id=\"{EMOJI_LEADERS}\">🏆</tg-emoji> <b>{titles.get(key, '')}</b>\n\n"
    text += "<blockquote>"
    
    for i, (user_id, data) in enumerate(sorted_leaders, 1):
        # Определяем эмодзи для позиции
        if i <= 3:
            position = top_emojis[i-1]
        else:
            position = f"{i}."
        
        # Получаем username или ID
        username = data.get('username')
        if username:
            display_name = f"@{username}"
        else:
            # Скрываем часть ID для безопасности
            user_id_str = str(user_id)
            display_name = f"ID: {user_id_str[:4]}...{user_id_str[-4:]}"
        
        # Форматируем значение
        value = data.get(key, 0)
        if value >= 1000000:
            value_str = f"{value/1000000:.2f}M"
        elif value >= 1000:
            value_str = f"{value/1000:.2f}K"
        else:
            value_str = f"{value:.2f}"
        
        text += f"{position} <b>{display_name}</b> — <code>{value_str}</code> <tg-emoji emoji-id=\"{EMOJI_WALLET}\">💰</tg-emoji>\n"
    
    text += "</blockquote>"
    
    # Добавляем футер с поддержкой
    text += (
        f"\n<tg-emoji emoji-id=\"5907025791006283345\">💬</tg-emoji> "
        f"<b><a href=\"https://t.me/your_support\">Тех. поддержка</a> | "
        f"<a href=\"https://t.me/your_chat\">Наш чат</a> | "
        f"<a href=\"https://t.me/your_news\">Новости</a></b>"
    )
    
    return text

# ========== ОБРАБОТЧИКИ ==========
async def show_leaders(callback: CallbackQuery, state: FSMContext):
    """Показать топ по депозитам (по умолчанию)"""
    await state.clear()
    
    users_data = load_users_data()
    text = format_leaderboard(users_data, 'deposit')
    
    await callback.message.edit_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=get_leaders_keyboard('deposit')
    )
    await callback.answer()

@leaders_router.callback_query(F.data.startswith("leaders_"))
async def switch_leaders_category(callback: CallbackQuery):
    """Переключение между категориями лидеров"""
    
    # Определяем выбранную категорию
    key = callback.data.replace("leaders_", "")
    
    # Проверяем валидность категории
    if key not in ['deposit', 'turnover', 'wins']:
        await callback.answer("❌ Неверная категория")
        return
    
    users_data = load_users_data()
    text = format_leaderboard(users_data, key)
    
    await callback.message.edit_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=get_leaders_keyboard(key)
    )
    await callback.answer()

# ========== ФУНКЦИИ ДЛЯ ИНТЕГРАЦИИ ==========
def update_deposit_stats(user_id: int, amount: float, username: str = None):
    """Обновление статистики депозитов (из платежного модуля)"""
    return update_user_stats(user_id, username, deposit=amount)

def update_turnover_stats(user_id: int, amount: float, username: str = None):
    """Обновление статистики оборота (из игрового модуля)"""
    return update_user_stats(user_id, username, turnover=amount)

def update_wins_stats(user_id: int, amount: float, username: str = None):
    """Обновление статистики выигрышей (из игрового модуля)"""
    return update_user_stats(user_id, username, wins=amount)

# ========== АДМИН-КОМАНДА ДЛЯ ПРОСМОТРА СТАТИСТИКИ ==========
@leaders_router.message(F.text == "/stats")
async def show_stats(message: Message):
    """Админ-команда для просмотра статистики"""
    users_data = load_users_data()
    
    total_users = len(users_data)
    total_deposits = sum(data.get('deposit', 0) for data in users_data.values())
    total_turnover = sum(data.get('turnover', 0) for data in users_data.values())
    total_wins = sum(data.get('wins', 0) for data in users_data.values())
    
    stats_text = (
        f"<b>📊 СТАТИСТИКА БОТА</b>\n\n"
        f"👥 Всего пользователей: <code>{total_users}</code>\n"
        f"📥 Общий депозит: <code>{total_deposits:.2f}</code> 💰\n"
        f"💱 Общий оборот: <code>{total_turnover:.2f}</code> 💰\n"
        f"🥳 Общий выигрыш: <code>{total_wins:.2f}</code> 💰\n"
    )
    
    await message.answer(stats_text, parse_mode=ParseMode.HTML)
