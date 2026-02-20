# leaders.py

import logging
from datetime import datetime, timedelta
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.enums import ParseMode

# Импортируем эмодзи из main (они будут переданы при инициализации)
EMOJI_LEADERS = "5440539497383087970"
EMOJI_BACK = "5906771962734057347"
EMOJI_PROFILE = "5906581476639513176"
EMOJI_WALLET = "5443127283898405358"
EMOJI_WITHDRAWAL = "5445355530111437729"
EMOJI_STATS = "5197288647275071607"
EMOJI_GAMES = "5424972470023104089"

leaders_router = Router()

# Хранилище для статистики (будет связано с основным storage)
class LeadersStorage:
    def __init__(self, main_storage):
        self.main_storage = main_storage
        self.leaders_cache = {
            'turnover': {},    # оборот (сумма ставок)
            'wins': {},        # выигрыши
            'deposits': {},    # депозиты
            'withdrawals': {}  # выводы
        }
        self.daily_stats = {}  # статистика по дням

    def update_user_stats(self, user_id: int, bet_amount: float = 0, win_amount: float = 0):
        """Обновление статистики пользователя при игре"""
        user_data = self.main_storage.get_user(user_id)
        today = datetime.now().strftime('%Y-%m-%d')
        
        # Инициализация если нужно
        if user_id not in self.leaders_cache['turnover']:
            self.leaders_cache['turnover'][user_id] = 0
            self.leaders_cache['wins'][user_id] = 0
        
        # Обновляем оборот (сумма ставок)
        if bet_amount > 0:
            self.leaders_cache['turnover'][user_id] += bet_amount
            
        # Обновляем выигрыши (чистый выигрыш)
        if win_amount > 0:
            self.leaders_cache['wins'][user_id] += win_amount
            
        # Обновляем дневную статистику
        if today not in self.daily_stats:
            self.daily_stats[today] = {}
        if user_id not in self.daily_stats[today]:
            self.daily_stats[today][user_id] = {
                'turnover': 0,
                'wins': 0,
                'deposits': 0,
                'withdrawals': 0
            }
        
        if bet_amount > 0:
            self.daily_stats[today][user_id]['turnover'] += bet_amount
        if win_amount > 0:
            self.daily_stats[today][user_id]['wins'] += win_amount

    def update_from_payment(self, user_id: int, amount: float, is_deposit: bool):
        """Обновление статистики из платежей"""
        user_data = self.main_storage.get_user(user_id)
        
        if is_deposit:
            if user_id not in self.leaders_cache['deposits']:
                self.leaders_cache['deposits'][user_id] = 0
            self.leaders_cache['deposits'][user_id] += amount
        else:
            if user_id not in self.leaders_cache['withdrawals']:
                self.leaders_cache['withdrawals'][user_id] = 0
            self.leaders_cache['withdrawals'][user_id] += amount

    def get_top_users(self, stat_type: str, period: str = 'all') -> list:
        """
        Получение топ-10 пользователей
        stat_type: turnover, wins, deposits, withdrawals
        period: all, today, yesterday, week, month
        """
        if period == 'all':
            stats_dict = self.leaders_cache.get(stat_type, {})
            sorted_users = sorted(stats_dict.items(), key=lambda x: x[1], reverse=True)[:10]
            return [(user_id, amount) for user_id, amount in sorted_users]
        
        # Статистика за период
        today = datetime.now()
        
        if period == 'today':
            target_date = today.strftime('%Y-%m-%d')
            return self._get_period_stats(target_date, stat_type)
            
        elif period == 'yesterday':
            target_date = (today - timedelta(days=1)).strftime('%Y-%m-%d')
            return self._get_period_stats(target_date, stat_type)
            
        elif period == 'week':
            # Собираем статистику за последние 7 дней
            combined_stats = {}
            for i in range(7):
                date = (today - timedelta(days=i)).strftime('%Y-%m-%d')
                if date in self.daily_stats:
                    for user_id, stats in self.daily_stats[date].items():
                        if user_id not in combined_stats:
                            combined_stats[user_id] = 0
                        combined_stats[user_id] += stats.get(stat_type, 0)
            
            sorted_users = sorted(combined_stats.items(), key=lambda x: x[1], reverse=True)[:10]
            return [(user_id, amount) for user_id, amount in sorted_users]
            
        elif period == 'month':
            # Собираем статистику за последние 30 дней
            combined_stats = {}
            for i in range(30):
                date = (today - timedelta(days=i)).strftime('%Y-%m-%d')
                if date in self.daily_stats:
                    for user_id, stats in self.daily_stats[date].items():
                        if user_id not in combined_stats:
                            combined_stats[user_id] = 0
                        combined_stats[user_id] += stats.get(stat_type, 0)
            
            sorted_users = sorted(combined_stats.items(), key=lambda x: x[1], reverse=True)[:10]
            return [(user_id, amount) for user_id, amount in sorted_users]
        
        return []

    def _get_period_stats(self, date: str, stat_type: str) -> list:
        """Получение статистики за конкретную дату"""
        if date not in self.daily_stats:
            return []
        
        stats_for_date = []
        for user_id, stats in self.daily_stats[date].items():
            amount = stats.get(stat_type, 0)
            if amount > 0:
                stats_for_date.append((user_id, amount))
        
        return sorted(stats_for_date, key=lambda x: x[1], reverse=True)[:10]

# Создаем экземпляр хранилища (будет инициализирован позже)
leaders_storage = None

def setup_leaders(main_storage):
    """Инициализация модуля лидеров"""
    global leaders_storage
    leaders_storage = LeadersStorage(main_storage)
    return leaders_storage

# Клавиатуры
def get_leaders_main_menu():
    """Главное меню лидеров с 9 кнопками"""
    return InlineKeyboardMarkup(inline_keyboard=[
        # Первый ряд: типы статистики
        [
            InlineKeyboardButton(text="📊 Оборот", callback_data="leaders_turnover_all"),
            InlineKeyboardButton(text="🏆 Выигрыш", callback_data="leaders_wins_all"),
            InlineKeyboardButton(text="📥 Депозиты", callback_data="leaders_deposits_all"),
            InlineKeyboardButton(text="📤 Выводы", callback_data="leaders_withdrawals_all")
        ],
        # Второй ряд: периоды
        [
            InlineKeyboardButton(text="📅 Сегодня", callback_data="leaders_turnover_today"),
            InlineKeyboardButton(text="📅 Вчера", callback_data="leaders_turnover_yesterday"),
            InlineKeyboardButton(text="📅 Неделя", callback_data="leaders_turnover_week"),
            InlineKeyboardButton(text="📅 Месяц", callback_data="leaders_turnover_month")
        ],
        # Третий ряд: навигация
        [
            InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_main", icon_custom_emoji_id=EMOJI_BACK)
        ]
    ])

def get_leaders_back_button():
    """Кнопка назад для подменю"""
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="◀️ Назад к лидерам", callback_data="leaders_back", icon_custom_emoji_id=EMOJI_BACK)
    ]])

# Обработчики
@leaders_router.callback_query(F.data == "leaders")
async def show_leaders_menu(callback: CallbackQuery, state: FSMContext):
    """Показать главное меню лидеров"""
    await state.clear()
    
    text = (
        f"<tg-emoji emoji-id=\"{EMOJI_LEADERS}\">🏆</tg-emoji> <b>ТОП-10 ИГРОКОВ</b>\n\n"
        f"<blockquote>Выберите категорию и период:</blockquote>\n\n"
        f"<tg-emoji emoji-id=\"5907025791006283345\">💬</tg-emoji> <b><a href=\"https://t.me/your_support\">Тех. поддержка</a> | <a href=\"https://t.me/your_chat\">Наш чат</a> | <a href=\"https://t.me/your_news\">Новости</a></b>"
    )
    
    await callback.message.edit_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=get_leaders_main_menu()
    )
    await callback.answer()

@leaders_router.callback_query(F.data.startswith("leaders_"))
async def leaders_category_handler(callback: CallbackQuery):
    """Обработка выбора категории и периода"""
    if not leaders_storage:
        await callback.answer("❌ Ошибка загрузки статистики")
        return
    
    # Формат: leaders_{stat_type}_{period}
    # stat_type: turnover, wins, deposits, withdrawals
    # period: all, today, yesterday, week, month
    
    data = callback.data.replace("leaders_", "")
    
    # Проверяем специальные случаи
    if data == "back":
        await show_leaders_menu(callback, None)
        return
    
    # Разбираем stat_type и period
    parts = data.split("_")
    
    # Маппинг названий
    stat_names = {
        'turnover': '📊 ОБОРОТ',
        'wins': '🏆 ВЫИГРЫШ',
        'deposits': '📥 ДЕПОЗИТЫ',
        'withdrawals': '📤 ВЫВОДЫ'
    }
    
    period_names = {
        'all': 'ЗА ВСЁ ВРЕМЯ',
        'today': 'СЕГОДНЯ',
        'yesterday': 'ВЧЕРА',
        'week': 'ЗА НЕДЕЛЮ',
        'month': 'ЗА МЕСЯЦ'
    }
    
    if len(parts) >= 2:
        stat_type = parts[0]
        period = parts[1]
        
        if stat_type in stat_names and period in period_names:
            await show_top_list(callback, stat_type, period, stat_names[stat_type], period_names[period])
        else:
            # Если нажата кнопка периода в главном меню, показываем оборот за этот период
            if parts[0] in ['today', 'yesterday', 'week', 'month']:
                await show_top_list(callback, 'turnover', parts[0], stat_names['turnover'], period_names[parts[0]])
            else:
                await callback.answer("❌ Неверный выбор")
    else:
        await callback.answer("❌ Неверный формат")

async def show_top_list(callback: CallbackQuery, stat_type: str, period: str, stat_name: str, period_name: str):
    """Показать топ-10 список"""
    if not leaders_storage:
        await callback.answer("❌ Ошибка загрузки статистики")
        return
    
    top_users = leaders_storage.get_top_users(stat_type, period)
    
    # Эмодзи для топ-3
    top_emojis = ["🥇", "🥈", "🥉"]
    
    text = (
        f"<tg-emoji emoji-id=\"{EMOJI_LEADERS}\">🏆</tg-emoji> <b>ТОП-10 {stat_name}</b>\n"
        f"<b>{period_name}</b>\n\n"
    )
    
    if not top_users:
        text += "<blockquote>📭 Пока нет данных за этот период</blockquote>"
    else:
        text += "<blockquote>"
        for i, (user_id, amount) in enumerate(top_users, 1):
            # Получаем имя пользователя (можно добавить кэш имен)
            try:
                user = await callback.bot.get_chat(user_id)
                user_name = user.full_name if user.full_name else f"ID: {user_id}"
            except:
                user_name = f"ID: {user_id}"
            
            # Обрезаем длинные имена
            if len(user_name) > 20:
                user_name = user_name[:17] + "..."
            
            # Эмодзи для позиции
            if i <= 3:
                position = top_emojis[i-1]
            else:
                position = f"{i}."
            
            # Форматируем сумму
            if amount >= 1000:
                amount_str = f"{amount/1000:.2f}K"
            else:
                amount_str = f"{amount:.2f}"
            
            text += f"{position} <b>{user_name}</b> — <code>{amount_str}</code> <tg-emoji emoji-id=\"{EMOJI_WALLET}\">💰</tg-emoji>\n"
        
        text += "</blockquote>"
    
    text += f"\n<tg-emoji emoji-id=\"5907025791006283345\">💬</tg-emoji> <b><a href=\"https://t.me/your_support\">Тех. поддержка</a> | <a href=\"https://t.me/your_chat\">Наш чат</a> | <a href=\"https://t.me/your_news\">Новости</a></b>"
    
    await callback.message.edit_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=get_leaders_back_button()
    )
    await callback.answer()

# Функции для обновления статистики из других модулей
def update_game_stats(user_id: int, bet_amount: float = 0, win_amount: float = 0):
    """Обновление статистики из игр"""
    if leaders_storage:
        leaders_storage.update_user_stats(user_id, bet_amount, win_amount)

def update_payment_stats(user_id: int, amount: float, is_deposit: bool):
    """Обновление статистики из платежей"""
    if leaders_storage:
        leaders_storage.update_from_payment(user_id, amount, is_deposit)
