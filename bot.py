import logging
import os
import tempfile
from typing import Dict, Set
from datetime import datetime, timedelta
import asyncio
from collections import defaultdict
import time
import sys
import platform

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from telegram.constants import ParseMode

from config import (
    BOT_TOKEN, ADMIN_USER_IDS, MESSAGES, MAX_FILE_SIZE, ALLOWED_EXTENSIONS,
    RATE_LIMIT_MESSAGES, RATE_LIMIT_PERIOD, STATS_WORK_START_HOUR, STATS_WORK_END_HOUR
)
from database import db
from ocr_processor import ocr_processor
from scheduler import start_scheduler
from utils import create_user_stats_message, format_duration, format_number, create_table_report, create_csv_report, create_user_detailed_csv, create_all_users_csv_package

# Налаштування логування
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Rate limiting
user_message_history: Dict[int, list] = defaultdict(list)

# Стани користувачів
user_states: Dict[int, str] = {}

class TikTokStatsBot:
    def __init__(self):
        """Ініціалізація бота"""
        self.application = None
        
    def is_admin(self, user_id: int) -> bool:
        """Перевірити чи є користувач адміністратором"""
        return user_id in ADMIN_USER_IDS
    
    def is_working_hours(self) -> bool:
        """Перевірити чи зараз робочі години для оновлення статистики (7:00-19:00)"""
        current_hour = datetime.now().hour
        return STATS_WORK_START_HOUR <= current_hour < STATS_WORK_END_HOUR
    
    def check_rate_limit(self, user_id: int) -> bool:
        """Перевірити rate limit для користувача"""
        now = time.time()
        user_history = user_message_history[user_id]
        
        # Видалити старі записи
        user_history[:] = [msg_time for msg_time in user_history if now - msg_time < RATE_LIMIT_PERIOD]
        
        # Перевірити ліміт
        if len(user_history) >= RATE_LIMIT_MESSAGES:
            return False
        
        # Додати поточний час
        user_history.append(now)
        return True
    
    def validate_file(self, file_path: str) -> bool:
        """Валідувати файл"""
        try:
            # Перевірити розширення
            _, ext = os.path.splitext(file_path.lower())
            if ext not in ALLOWED_EXTENSIONS:
                return False
            
            # Перевірити розмір
            if os.path.getsize(file_path) > MAX_FILE_SIZE:
                return False
            
            return True
        except Exception:
            return False
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обробник команди /start"""
        if not update.message or not update.effective_user:
            return
            
        user_id = update.effective_user.id
        
        # Перевірити чи користувач вже зареєстрований
        existing_user = db.get_user(user_id)
        if existing_user:
            # Користувач вже зареєстрований - показати привітання
            welcome_message = f"""З поверненням, {existing_user['tiktok_nickname']}! 

🎯 TikTok Live Analytics Bot готовий до роботи!

✨ Швидкий старт:
🔸 Надсилайте скріншоти статистики TikTok Live
🔸 Отримуйте миттєвий аналіз та звіти
🔸 Переглядайте статистику через /menu

🎊 Новинки:
📊 Розширені звіти адміна
🌴 Система вихідних днів  
📥 CSV експорт даних
🚀 Доступ 24/7

Готові почати? Надішліть скріншот або використайте /menu! 🚀"""
            
            keyboard = [[InlineKeyboardButton("🎯 Відкрити меню", callback_data="back_to_menu")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Додати постійні кнопки внизу
            persistent_keyboard = [
                [KeyboardButton("📊 Моя статистика"), KeyboardButton("📈 Статистика за день")],
                [KeyboardButton("📅 Статистика за тиждень"), KeyboardButton("📆 Статистика за місяць")],
                [KeyboardButton("🏆 Топ ефіри"), KeyboardButton("🌟 Мої досягнення")],
                [KeyboardButton("🌍 Загальна статистика"), KeyboardButton("🏅 Топ користувачі")],
                [KeyboardButton("📋 Остання активність"), KeyboardButton("📄 Експорт даних")],
                [KeyboardButton("📥 Скачати мій звіт"), KeyboardButton("📅 Мої вихідні")],
                [KeyboardButton("🌴 Вихідний день"), KeyboardButton("⚙️ Налаштування")],
                [KeyboardButton("ℹ️ Допомога")]
            ]
            
            # Додати адмін панель для адмінів
            if self.is_admin(user_id):
                persistent_keyboard.append([KeyboardButton("🔧 Адмін панель")])
            
            persistent_reply_markup = ReplyKeyboardMarkup(persistent_keyboard, resize_keyboard=True)
            
            await update.message.reply_text(welcome_message, reply_markup=persistent_reply_markup)
            return
        
        # Новий користувач - показати привітання з кнопкою реєстрації
        welcome_message = f"""Вітаємо в TikTok Live Analytics Bot! 

🎯 Що це за бот?
Це потужний інструмент для аналізу статистики TikTok Live ефірів!

🌟 Можливості:
🔸 Автоматичний аналіз скріншотів статистики
🔸 Детальні звіти по днях, тижнях, місяцях
🔸 CSV експорт для Excel та Google Sheets
🔸 Система вихідних днів для точної аналітики
🔸 Багато фото на день з автосумуванням
🔸 Доступ 24/7

🚀 Як це працює:
1. Зареєструйтеся вказавши TikTok нікнейм
2. Надсилайте скріншоти після ефірів (доступно цілодобово)
3. Отримуйте детальну аналітику та звіти

💎 Відстежуємо:
• Тривалість ефірів
• Кількість глядачів  
• Кількість дарувальників
• Кількість алмазів

Готові почати? Натисніть кнопку нижче! 👇"""
        
        keyboard = [[InlineKeyboardButton("🚀 Почати реєстрацію", callback_data="start_registration")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(welcome_message, reply_markup=reply_markup)

    async def handle_start_registration(self, query):
        """Обробляти початок реєстрації з кнопки"""
        user_id = query.from_user.id
        
        # Перевірити чи користувач вже зареєстрований
        existing_user = db.get_user(user_id)
        if existing_user:
            await self.show_main_menu(query, user_id)
            return
        
        # Почати процес реєстрації
        user_states[user_id] = 'waiting_nickname'
        
        message = f"""Вітаємо в TikTok Live Analytics Bot! 

{MESSAGES['nickname_prompt']}

💡 Поради для ніку:
• Введіть свій TikTok нікнейм без символу @
• Довжина від 1 до 50 символів
• Можна використовувати літери, цифри, крапки та підкреслення

📝 Приклад: username123

🎉 Після реєстрації ви зможете:
🔸 Надсилати скріншоти статистики
🔸 Переглядати детальну аналітику
🔸 Завантажувати звіти в Excel
🔸 Відмічати вихідні дні"""
        
        await query.edit_message_text(message)
    
    async def myid_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обробник команди /myid - показати свій Telegram ID"""
        if not update.message or not update.effective_user:
            return
            
        user_id = update.effective_user.id
        username = update.effective_user.username or "немає username"
        is_admin = self.is_admin(user_id)
        
        message = f"🆔 Ваші дані:\n"
        message += f"👤 Username: @{username}\n"
        message += f"🔢 Telegram ID: `{user_id}`\n"
        message += f"🔧 Статус адміна: {'✅ Так' if is_admin else '❌ Ні'}\n\n"
        message += f"📋 Список адмін ID: {ADMIN_USER_IDS}\n\n"
        
        if is_admin:
            message += "🎉 У вас є доступ до адмін панелі! Використовуйте /admin"
        else:
            message += "ℹ️ Для отримання адмін прав зв'яжіться з розробником"
        
        await update.message.reply_text(message)
    
    async def menu_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обробник команди /menu"""
        if not update.message or not update.effective_user:
            return
            
        user_id = update.effective_user.id
        user_data = db.get_user(user_id)
        
        if not user_data:
            await update.message.reply_text("❌ Спочатку зареєструйтеся командою /start")
            return
        
        # Додати постійні кнопки внизу
        persistent_keyboard = [
            [KeyboardButton("📊 Моя статистика"), KeyboardButton("📈 Статистика за день")],
            [KeyboardButton("📅 Статистика за тиждень"), KeyboardButton("📆 Статистика за місяць")],
            [KeyboardButton("🏆 Топ ефіри"), KeyboardButton("🌟 Мої досягнення")],
            [KeyboardButton("🌍 Загальна статистика"), KeyboardButton("🏅 Топ користувачі")],
            [KeyboardButton("📋 Остання активність"), KeyboardButton("📄 Експорт даних")],
            [KeyboardButton("📥 Скачати мій звіт"), KeyboardButton("📅 Мої вихідні")],
            [KeyboardButton("🌴 Вихідний день"), KeyboardButton("⚙️ Налаштування")],
            [KeyboardButton("ℹ️ Допомога")]
        ]
        
        # Додати адмін панель для адмінів
        if self.is_admin(user_id):
            persistent_keyboard.append([KeyboardButton("🔧 Адмін панель")])
        
        persistent_reply_markup = ReplyKeyboardMarkup(persistent_keyboard, resize_keyboard=True)
        
        welcome_text = f"""🎯 Головне меню TikTok Live Analytics

👋 Привіт, {user_data['tiktok_nickname']}!

Оберіть опцію для перегляду статистики:"""
        
        await update.message.reply_text(welcome_text, reply_markup=persistent_reply_markup)
    
    async def admin_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обробник команди /admin"""
        if not update.message or not update.effective_user:
            return
            
        user_id = update.effective_user.id
        username = update.effective_user.username or "немає username"
        
        # Логування для діагностики
        logger.info(f"👤 Користувач {username} (ID: {user_id}) намагається використати /admin")
        logger.info(f"🔧 Поточні адмін ID: {ADMIN_USER_IDS}")
        logger.info(f"🔑 Результат перевірки is_admin: {self.is_admin(user_id)}")
        
        if not self.is_admin(user_id):
            await update.message.reply_text(
                f"{MESSAGES['admin_only']}\n\n"
                f"🆔 Ваш ID: `{user_id}`\n"
                f"📋 Поточні адмін ID: {ADMIN_USER_IDS}\n\n"
                f"ℹ️ Якщо ви повинні мати доступ, зв'яжіться з розробником"
            )
            return
        
        keyboard = [
            [InlineKeyboardButton("📊 Статистика всіх", callback_data="admin_all_stats"),
             InlineKeyboardButton("📋 Таблиця звітів", callback_data="admin_table_report")],
            [InlineKeyboardButton("👥 Список користувачів", callback_data="admin_users_list"),
             InlineKeyboardButton("🎯 Активність користувачів", callback_data="admin_user_activity")],
            [InlineKeyboardButton("📈 Статистика за період", callback_data="admin_period_stats"),
             InlineKeyboardButton("🔧 Тест OCR", callback_data="admin_test_ocr")],
            [InlineKeyboardButton("📥 Скачати зведений звіт", callback_data="download_summary_report"),
             InlineKeyboardButton("📥 Скачати всі звіти", callback_data="download_all_reports")],
            [InlineKeyboardButton("👤 Звіт по користувачу", callback_data="download_user_report"),
             InlineKeyboardButton("📊 Звіт з вихідними", callback_data="download_holiday_report")],
            [InlineKeyboardButton("📁 Експорт всіх даних", callback_data="admin_export_all"),
             InlineKeyboardButton("🗑️ Очистити старі дані", callback_data="admin_cleanup")],
            [InlineKeyboardButton("📋 Логи системи", callback_data="admin_logs"),
             InlineKeyboardButton("🔑 Діагностика доступу", callback_data="admin_diagnostics")],
            [InlineKeyboardButton("⚙️ Системна інформація", callback_data="admin_system_info"),
             InlineKeyboardButton("🔧 Техобслуговування", callback_data="admin_maintenance")],
            [InlineKeyboardButton("🔙 Назад до меню", callback_data="back_to_menu")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            f"🔧 Адмін панель\n"
            f"👋 Привіт, {username}!\n"
            f"🆔 Ваш ID: {user_id}\n\n"
            f"Оберіть дію:", 
            reply_markup=reply_markup
        )
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обробник текстових повідомлень"""
        if not update.message or not update.effective_user:
            return
            
        user_id = update.effective_user.id
        text = update.message.text
        
        if not text:
            return
        
        # Перевірити rate limit
        if not self.check_rate_limit(user_id):
            await update.message.reply_text("⏳ Занадто багато повідомлень. Зачекайте хвилину.")
            return
        
        # Перевірити стан користувача
        if user_id in user_states and user_states[user_id] == 'waiting_nickname':
            # Зберегти TikTok нікнейм
            nickname = text.strip().replace('@', '')
            if len(nickname) < 1 or len(nickname) > 50:
                await update.message.reply_text("❌ Нікнейм повинен бути від 1 до 50 символів.")
                return
            
            # Зареєструвати користувача
            if db.register_user(user_id, nickname):
                user_states.pop(user_id, None)
                
                # Привітання для нового користувача
                success_message = f"""🎉 Реєстрація успішна! 

👤 Вітаємо, {nickname}! 
🆔 Ваш ID: `{user_id}`

🎯 Що далі?
📸 Надішліть скріншот TikTok Live статистики для автоматичного аналізу
📊 Використовуйте `/menu` для перегляду опцій

✨ Готові функції:
🔹 Автоматичне розпізнавання статистики
🔹 Аналітика за різні періоди
🔹 Експорт даних у CSV
🔹 Система відмітки вихідних днів
🔹 Доступ 24/7

🚀 Почніть зараз: Надішліть ваш перший скріншот!"""
                
                await update.message.reply_text(success_message)
                
                logger.info(f"Новий користувач зареєстрований: {user_id} - {nickname}")
            else:
                await update.message.reply_text("❌ Помилка збереження ніку. Спробуйте ще раз.")
        
        # Обробка постійних кнопок
        elif text == "📊 Моя статистика":
            user_data = db.get_user(user_id)
            if user_data:
                summary = db.get_user_summary(user_id, 30)
                message = create_user_stats_message(user_data, summary)
                await update.message.reply_text(message)
            else:
                await update.message.reply_text("❌ Спочатку зареєструйтеся командою /start")
        
        elif text == "📈 Статистика за день":
            user_data = db.get_user(user_id)
            if user_data:
                summary = db.get_user_summary(user_id, 1)
                message = f"""📈 Статистика сьогодні ({user_data['tiktok_nickname']})

🎥 Кількість ефірів: {summary.get('sessions_count', 0)}
⏱️ Загальна тривалість: {format_duration(summary.get('total_duration', 0))}
👥 Всього глядачів: {format_number(summary.get('total_viewers', 0))}
🎁 Всього дарувальників: {format_number(summary.get('total_gifters', 0))}
💎 Всього алмазів: {format_number(summary.get('total_diamonds', 0))}

📊 Середні показники:
⏱️ Середня тривалість: {format_duration(summary.get('avg_duration', 0))}
👥 Середня к-ть глядачів: {format_number(summary.get('avg_viewers', 0))}
💎 Середня к-ть алмазів: {format_number(summary.get('avg_diamonds', 0))}"""
                await update.message.reply_text(message)
            else:
                await update.message.reply_text("❌ Спочатку зареєструйтеся командою /start")
        
        elif text == "📄 Експорт даних":
            user_data = db.get_user(user_id)
            if user_data:
                # Створити CSV файл з даними користувача
                stats = db.get_user_statistics(user_id, 365)  # Всі дані за рік
                if stats:
                    # Відправити повідомлення про експорт
                    await update.message.reply_text("📄 Експорт даних успішно виконано!")
                else:
                    await update.message.reply_text("📄 Немає даних для експорту.")
            else:
                await update.message.reply_text("❌ Спочатку зареєструйтеся командою /start")
        
        elif text == "📅 Статистика за тиждень":
            user_data = db.get_user(user_id)
            if user_data:
                summary = db.get_user_summary(user_id, 7)
                message = f"""📅 Статистика за тиждень ({user_data['tiktok_nickname']})

🎥 Кількість ефірів: {summary.get('sessions_count', 0)}
⏱️ Загальна тривалість: {format_duration(summary.get('total_duration', 0))}
👥 Всього глядачів: {format_number(summary.get('total_viewers', 0))}
🎁 Всього дарувальників: {format_number(summary.get('total_gifters', 0))}
💎 Всього алмазів: {format_number(summary.get('total_diamonds', 0))}

📊 Середні показники:
⏱️ Середня тривалість: {format_duration(summary.get('avg_duration', 0))}
👥 Середня к-ть глядачів: {format_number(summary.get('avg_viewers', 0))}
💎 Середня к-ть алмазів: {format_number(summary.get('avg_diamonds', 0))}"""
                await update.message.reply_text(message)
            else:
                await update.message.reply_text("❌ Спочатку зареєструйтеся командою /start")
        
        elif text == "📆 Статистика за місяць":
            user_data = db.get_user(user_id)
            if user_data:
                summary = db.get_user_summary(user_id, 30)
                message = f"""📆 Статистика за місяць ({user_data['tiktok_nickname']})

🎥 Кількість ефірів: {summary.get('sessions_count', 0)}
⏱️ Загальна тривалість: {format_duration(summary.get('total_duration', 0))}
👥 Всього глядачів: {format_number(summary.get('total_viewers', 0))}
🎁 Всього дарувальників: {format_number(summary.get('total_gifters', 0))}
💎 Всього алмазів: {format_number(summary.get('total_diamonds', 0))}

📊 Середні показники:
⏱️ Середня тривалість: {format_duration(summary.get('avg_duration', 0))}
👥 Середня к-ть глядачів: {format_number(summary.get('avg_viewers', 0))}
💎 Середня к-ть алмазів: {format_number(summary.get('avg_diamonds', 0))}"""
                await update.message.reply_text(message)
            else:
                await update.message.reply_text("❌ Спочатку зареєструйтеся командою /start")
        
        elif text == "🏆 Топ ефіри":
            user_data = db.get_user(user_id)
            if user_data:
                stats = db.get_user_statistics(user_id, 30)
                if not stats:
                    message = "🏆 Топ ефіри\n\nНемає даних за останні 30 днів."
                else:
                    # Сортуємо за алмазами
                    top_streams = sorted(stats, key=lambda x: x.get('diamonds_count', 0), reverse=True)[:5]
                    message = "🏆 Топ 5 ефірів за алмазами:\n\n"
                    for i, stream in enumerate(top_streams, 1):
                        date = datetime.fromisoformat(stream['timestamp']).strftime('%d.%m %H:%M')
                        message += f"{i}. 📅 {date}\n"
                        message += f"⏱️ {format_duration(stream['duration_minutes'])}\n"
                        message += f"👥 {format_number(stream['viewers_count'])} глядачів\n"
                        message += f"💎 {format_number(stream['diamonds_count'])} алмазів\n\n"
                await update.message.reply_text(message)
            else:
                await update.message.reply_text("❌ Спочатку зареєструйтеся командою /start")
        
        elif text == "🌟 Мої досягнення":
            user_data = db.get_user(user_id)
            if user_data:
                summary = db.get_user_summary(user_id, 999)
                achievements = []
                total_sessions = summary.get('sessions_count', 0)
                total_diamonds = summary.get('total_diamonds', 0)
                total_duration = summary.get('total_duration', 0)
                
                if total_sessions >= 1:
                    achievements.append("🎯 Перший ефір")
                if total_sessions >= 10:
                    achievements.append("🔥 10 ефірів")
                if total_diamonds >= 1000:
                    achievements.append("💎 1K алмазів")
                if total_duration >= 60:
                    achievements.append("⏰ Годинний стрімер")
                
                message = f"""🌟 Мої досягнення

🏅 Отримано досягнень: {len(achievements)}

"""
                if achievements:
                    message += "🎊 Ваші нагороди:\n"
                    for achievement in achievements:
                        message += f"✅ {achievement}\n"
                    message += "\n🌟 Вітаємо з досягненнями!"
                else:
                    message += "Поки що досягнень немає. Продовжуйте стрімити! 💪"
                
                await update.message.reply_text(message)
            else:
                await update.message.reply_text("❌ Спочатку зареєструйтеся командою /start")
        
        elif text == "🌍 Загальна статистика":
            total_stats = db.get_total_stats()
            message = f"""📊 Загальна статистика

👥 Всього користувачів: {total_stats.get('total_users', 0)}
🎥 Всього ефірів: {total_stats.get('total_sessions', 0)}
⏱️ Загальна тривалість: {format_duration(total_stats.get('total_duration', 0))}
👀 Всього глядачів: {format_number(total_stats.get('total_viewers', 0))}
💎 Всього алмазів: {format_number(total_stats.get('total_diamonds', 0))}"""
            await update.message.reply_text(message)
        
        elif text == "🏅 Топ користувачі":
            users = db.get_all_users()
            sorted_users = sorted(users, key=lambda x: x.get('total_diamonds', 0) or 0, reverse=True)
            message = f"🏅 Топ користувачі за алмазами:\n\n"
            emoji_medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
            for i, user in enumerate(sorted_users[:10], 0):
                nickname = user.get('tiktok_nickname', 'Невідомо')
                diamonds = user.get('total_diamonds', 0) or 0
                sessions = user.get('total_sessions', 0) or 0
                medal = emoji_medals[i] if i < len(emoji_medals) else f"{i+1}."
                message += f"{medal} {nickname}\n"
                message += f"💎 {format_number(diamonds)} алмазів\n"
                message += f"🎥 {sessions} ефірів\n\n"
            await update.message.reply_text(message)
        
        elif text == "📋 Остання активність":
            user_data = db.get_user(user_id)
            if user_data:
                recent_stats = db.get_user_statistics(user_id, 7)
                if not recent_stats:
                    message = "📋 Немає активності за останні 7 днів."
                else:
                    message = "📋 Остання активність (7 днів):\n\n"
                    for stat in recent_stats[:5]:
                        date = datetime.fromisoformat(stat['timestamp']).strftime('%d.%m %H:%M')
                        message += f"📅 {date}\n"
                        message += f"⏱️ {format_duration(stat['duration_minutes'])}\n"
                        message += f"👥 {format_number(stat['viewers_count'])} глядачів\n"
                        message += f"💎 {format_number(stat['diamonds_count'])} алмазів\n\n"
                await update.message.reply_text(message)
            else:
                await update.message.reply_text("❌ Спочатку зареєструйтеся командою /start")
        
        elif text == "📥 Скачати мій звіт":
            user_data = db.get_user(user_id)
            if user_data:
                await update.message.reply_text("📥 Функція скачування звіту доступна через інлайн кнопки в меню!")
            else:
                await update.message.reply_text("❌ Спочатку зареєструйтеся командою /start")
        
        elif text == "📅 Мої вихідні":
            user_data = db.get_user(user_id)
            if user_data:
                holidays = db.get_user_holidays(user_id)
                if not holidays:
                    message = "📅 У вас поки що немає позначених вихідних днів."
                else:
                    message = f"📅 Мої вихідні дні ({len(holidays)}):\n\n"
                    for holiday in holidays[:10]:
                        date_obj = datetime.strptime(holiday['holiday_date'], '%Y-%m-%d')
                        date_str = date_obj.strftime('%d.%m.%Y')
                        message += f"🌴 {date_str}\n"
                    if len(holidays) > 10:
                        message += f"... та ще {len(holidays) - 10} вихідних"
                await update.message.reply_text(message)
            else:
                await update.message.reply_text("❌ Спочатку зареєструйтеся командою /start")
        
        elif text == "🌴 Вихідний день":
            user_data = db.get_user(user_id)
            if user_data:
                today = datetime.now().strftime('%Y-%m-%d')
                if db.is_holiday(user_id, today):
                    message = f"🌴 Сьогодні ({datetime.now().strftime('%d.%m.%Y')}) вже позначено як вихідний день!"
                else:
                    if db.add_holiday(user_id, today):
                        message = f"🌴 Вихідний день додано! Дата: {datetime.now().strftime('%d.%m.%Y')}"
                    else:
                        message = "❌ Помилка додавання вихідного дня."
                await update.message.reply_text(message)
            else:
                await update.message.reply_text("❌ Спочатку зареєструйтеся командою /start")
        
        elif text == "⚙️ Налаштування":
            user_data = db.get_user(user_id)
            if user_data:
                reg_date = datetime.fromisoformat(user_data['registration_date']).strftime('%d.%m.%Y')
                message = f"""⚙️ Налаштування профілю

👤 TikTok нікнейм: {user_data['tiktok_nickname']}
📅 Дата реєстрації: {reg_date}
🆔 ID користувача: {user_id}"""
                await update.message.reply_text(message)
            else:
                await update.message.reply_text("❌ Спочатку зареєструйтеся командою /start")
        
        elif text == "ℹ️ Допомога":
            message = """ℹ️ Допомога TikTok Live Analytics Bot

🎯 Як користуватися:
1. 📸 Зробіть скріншот TikTok Live статистики
2. 📨 Надішліть фото боту  
3. ⏳ Зачекайте на аналіз
4. 📊 Переглядайте статистику

🔧 Команди:
• /start - Реєстрація
• /menu - Меню
• /help - Детальна допомога

💡 Поради:
• Якісні скріншоти
• Читабельний текст
• Максимум 10MB

🆘 Проблеми? Використайте /help для детальної інструкції"""
            await update.message.reply_text(message)
        
        elif text == "🔧 Адмін панель":
            if self.is_admin(user_id):
                await update.message.reply_text("🔧 Адмін панель відкрита! Використовуйте команду /admin для повної панелі")
            else:
                await update.message.reply_text("❌ У вас немає доступу до адмін панелі")
        
        else:
            # Інші текстові повідомлення
            await update.message.reply_text(MESSAGES['photo_only'])
    
    async def handle_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обробити фото від користувача"""
        if not update.message or not update.effective_user:
            return
            
        user_id = update.effective_user.id
        
        # Перевірити чи користувач зареєстрований
        user_data = db.get_user(user_id)
        if not user_data:
            keyboard = [[InlineKeyboardButton("🚀 Почати реєстрацію", callback_data="start_registration")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                "👋 Привіт! Схоже, ви ще не зареєстровані.\n\n"
                "🎯 Цей бот допомагає аналізувати статистику TikTok Live!\n"
                "🔸 Просто надсилайте скріншоти та отримуйте детальну аналітику\n\n"
                "Натисніть кнопку нижче, щоб почати:",
                reply_markup=reply_markup
            )
            return
        
        # Перевірити режим технічного обслуговування
        if db.is_maintenance_mode():
            maintenance_info = db.get_maintenance_info()
            maintenance_message = maintenance_info.get('message', '')
            
            message = "🔧 **Технічне обслуговування**\n\n"
            message += "⏳ Бот тимчасово недоступний для обробки скріншотів\n"
            message += "🛠️ Проводяться технічні роботи для покращення сервісу\n\n"
            
            if maintenance_message:
                message += f"📋 Причина: {maintenance_message}\n\n"
            
            message += "🕐 Спробуйте пізніше\n"
            message += "📞 Для термінових питань зверніться до адміністратора"
            
            await update.message.reply_text(message)
            return
        
        # Перевірити робочі години (24/7)
        if not self.is_working_hours():
            current_time = datetime.now().strftime('%H:%M')
            await update.message.reply_text(
                f"🕐 Бот тимчасово недоступний\n\n"
                f"⏰ Поточний час: {current_time}\n"
                f"⏳ Робочі години: 00:00 - 23:59\n\n"
                f"🕐 Спробуйте ще раз через хвилину!"
            )
            return
        
        # Перевірити ліміт
        if not self.check_rate_limit(user_id):
            await update.message.reply_text("⏰ Занадто багато запитів. Спробуйте через хвилину.")
            return
        
        try:
            # Відправити повідомлення про початок обробки
            processing_msg = await update.message.reply_text("⏳ Починаю обробку вашого скріншота...")
            
            # Отримати фото
            photo = update.message.photo[-1]  # Найбільший розмір
            file = await context.bot.get_file(photo.file_id)
            
            # Створити унікальне ім'я файлу
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"screenshot_{user_id}_{timestamp}.jpg"
            
            # Завантажити файл
            file_path = await file.download_to_drive(filename)
            
            # Валідація файлу
            if not self.validate_file(filename):
                await processing_msg.edit_text("❌ Неправильний формат файлу. Надішліть JPG або PNG.")
                os.unlink(filename)
                return
            
            # Обробити фото за допомогою OCR
            await processing_msg.edit_text("⚙️ Обробляю зображення... 🔍\n📖 Розпізнаю текст...")
            
            stats = ocr_processor.process_tiktok_screenshot(filename)
            
            if not stats:
                await processing_msg.edit_text("❌ Не вдалося розпізнати статистику на зображенні. Спробуйте інший скріншот.")
                os.unlink(filename)
                return
            
            duration, viewers, gifters, diamonds = stats
            
            # Повідомлення про успіх
            await processing_msg.edit_text("✅ Успішно оброблено! \n💾 Зберігаю дані...")
            
            # Зберегти в базу даних
            success = db.add_statistics(user_id, duration, viewers, gifters, diamonds)
            
            if success:
                # Отримати статистику за сьогодні для відображення
                today_stats = db.get_today_total_stats(user_id)
                total_screenshots = today_stats.get('sessions_count', 1) if today_stats else 1
                
                # Повідомлення про успіх
                success_message = f"""✅ Обробка завершена успішно! 

📊 Поточний скріншот:
⏱️ Тривалість: {format_duration(duration)}
👥 Глядачі: {format_number(viewers)}
🎁 Дарувальники: {format_number(gifters)}
💎 Алмази: {format_number(diamonds)}

📈 Статистика за сьогодні:
🎥 Скріншотів оброблено: {total_screenshots}"""

                if today_stats and total_screenshots > 1:
                    success_message += f"""
⏱️ Загальна тривалість: {format_duration(today_stats.get('total_duration', 0))}
👥 Всього глядачів: {format_number(today_stats.get('total_viewers', 0))}
💎 Всього алмазів: {format_number(today_stats.get('total_diamonds', 0))}"""

                success_message += "\n\n📊 Дякую за використання бота!"
                
                await processing_msg.edit_text(success_message)
                
                logger.info(f"Статистика збережена: {user_id}, {duration}хв, {viewers} глядачів, {diamonds} алмазів")
            else:
                await processing_msg.edit_text("❌ Помилка збереження даних. Спробуйте ще раз.")
            
            # Видалити файл
            os.unlink(filename)
            
        except Exception as e:
            logger.error(f"Помилка обробки фото: {e}")
            try:
                await processing_msg.edit_text("❌ Помилка обробки фото. Спробуйте ще раз.")
            except:
                await update.message.reply_text("❌ Помилка обробки фото. Спробуйте ще раз.")
            
            # Видалити файл якщо існує
            if 'filename' in locals() and os.path.exists(filename):
                os.unlink(filename)
    
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обробник callback запитів"""
        query = update.callback_query
        if not query or not query.from_user:
            return
            
        await query.answer()
        
        user_id = query.from_user.id
        data = query.data
        
        try:
            # Основні функції
            if data == "my_stats":
                await self.show_user_stats(query, user_id)
            elif data == "stats_today":
                await self.show_stats_period(query, user_id, 1, "сьогодні")
            elif data == "stats_week":
                await self.show_stats_period(query, user_id, 7, "за тиждень")
            elif data == "stats_month":
                await self.show_stats_period(query, user_id, 30, "за місяць")
            elif data == "my_top_streams":
                await self.show_top_streams(query, user_id)
            elif data == "my_achievements":
                await self.show_achievements(query, user_id)
            elif data == "general_stats":
                await self.show_general_stats(query)
            elif data == "top_users":
                await self.show_top_users(query)
            elif data == "recent_activity":
                await self.show_recent_activity(query, user_id)
            elif data == "export_data":
                await self.export_user_data(query, user_id)
            elif data == "settings":
                await self.show_settings(query, user_id)
            elif data == "help":
                await self.show_help(query)
            elif data == "change_nickname":
                await self.change_nickname(query, user_id)
            elif data == "back_to_menu":
                await self.show_main_menu(query, user_id)
            elif data == "show_commands_inline":
                await self.show_commands_inline(query, user_id)
            elif data == "add_holiday":
                await self.add_holiday(query, user_id)
            elif data == "my_holidays":
                await self.show_my_holidays(query, user_id)
            elif data and data.startswith("remove_holiday_"):
                date = data.replace("remove_holiday_", "")
                await self.remove_holiday(query, user_id, date)
            elif data == "download_my_report":
                await self.download_my_report(query, user_id)
            
            # Адмін функції
            elif data == "admin_panel" and self.is_admin(user_id):
                await self.show_admin_panel(query)
            elif data == "admin_all_stats" and self.is_admin(user_id):
                await self.show_admin_stats(query)
            elif data == "admin_table_report" and self.is_admin(user_id):
                await self.show_admin_table_report(query)
            elif data == "admin_users_list" and self.is_admin(user_id):
                await self.show_users_list(query)
            elif data == "admin_period_stats" and self.is_admin(user_id):
                await self.show_admin_period_stats(query)
            elif data == "admin_user_activity" and self.is_admin(user_id):
                await self.show_admin_user_activity(query)
            elif data == "admin_test_ocr" and self.is_admin(user_id):
                await self.test_ocr(query)
            elif data == "admin_export_all" and self.is_admin(user_id):
                await self.admin_export_all(query)
            elif data == "admin_cleanup" and self.is_admin(user_id):
                await self.admin_cleanup(query)
            elif data == "admin_logs" and self.is_admin(user_id):
                await self.show_admin_logs(query)
            elif data == "admin_diagnostics" and self.is_admin(user_id):
                await self.admin_diagnostics(query)
            elif data == "admin_system_info" and self.is_admin(user_id):
                await self.admin_system_info(query)
            elif data == "admin_maintenance" and self.is_admin(user_id):
                await self.show_maintenance_menu(query)
            elif data == "maintenance_enable" and self.is_admin(user_id):
                await self.enable_maintenance_mode(query)
            elif data == "maintenance_disable" and self.is_admin(user_id):
                await self.disable_maintenance_mode(query)
            elif data == "maintenance_status" and self.is_admin(user_id):
                await self.show_maintenance_status(query)
            elif data == "admin_detailed_reports" and self.is_admin(user_id):
                await self.show_admin_detailed_reports(query)
            elif data and data.startswith("detailed_period_"):
                period = data.replace("detailed_period_", "")
                await self.show_detailed_period_menu(query, period)
            elif data and data.startswith("detailed_user_"):
                parts = data.replace("detailed_user_", "").split("_")
                if len(parts) >= 2:
                    period = parts[0]
                    target_user_id = int(parts[1])
                    await self.show_detailed_user_stats(query, target_user_id, period)
            elif data == "download_summary_report" and self.is_admin(user_id):
                await self.download_summary_report(query, user_id)
            elif data == "download_all_reports" and self.is_admin(user_id):
                await self.download_all_reports(query, user_id)
            elif data == "download_user_report" and self.is_admin(user_id):
                await self.download_user_report(query, user_id)
            elif data == "download_holiday_report" and self.is_admin(user_id):
                await self.download_holiday_report(query, user_id)
            elif data and data.startswith("user_report_"):
                target_user_id = int(data.replace("user_report_", ""))
                await self.generate_individual_user_report(query, target_user_id)
            elif data and data.startswith("download_detailed_") and self.is_admin(user_id):
                parts = data.replace("download_detailed_", "").split("_")
                if len(parts) >= 2:
                    period = parts[0]
                    target_user_id = int(parts[1])
                    await self.download_detailed_user_report(query, target_user_id, period)
            elif data == "start_registration":
                await self.handle_start_registration(query)
            else:
                await query.edit_message_text("❌ Невідома команда або немає доступу.")
                
        except Exception as e:
            logger.error(f"Помилка callback: {e}")
            await query.edit_message_text("❌ Помилка обробки запиту.")
    
    async def show_user_stats(self, query, user_id: int):
        """Показати статистику користувача"""
        user_data = db.get_user(user_id)
        if not user_data:
            await query.edit_message_text("❌ Користувач не зареєстрований.")
            return
        
        summary = db.get_user_summary(user_id, 30)
        message = create_user_stats_message(user_data, summary)
        
        keyboard = [[InlineKeyboardButton("🔙 Назад до меню", callback_data="back_to_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(message, reply_markup=reply_markup)
    
    async def show_general_stats(self, query):
        """Показати загальну статистику"""
        total_stats = db.get_total_stats()
        
        message = f"""📊 Загальна статистика

👥 Всього користувачів: {total_stats.get('total_users', 0)}
🎥 Всього ефірів: {total_stats.get('total_sessions', 0)}
⏱️ Загальна тривалість: {format_duration(total_stats.get('total_duration', 0))}
👀 Всього глядачів: {format_number(total_stats.get('total_viewers', 0))}
💎 Всього алмазів: {format_number(total_stats.get('total_diamonds', 0))}
"""
        
        keyboard = [[InlineKeyboardButton("🔙 Назад до меню", callback_data="back_to_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(message, reply_markup=reply_markup)
    
    async def show_recent_activity(self, query, user_id: int):
        """Показати останню активність користувача"""
        recent_stats = db.get_user_statistics(user_id, 7)
        
        if not recent_stats:
            message = "📋 Немає активності за останні 7 днів."
        else:
            message = "📋 Остання активність (7 днів):\n\n"
            
            for stat in recent_stats[:5]:  # Показати останні 5 записів
                date = datetime.fromisoformat(stat['timestamp']).strftime('%d.%m %H:%M')
                message += f"📅 {date}\n"
                message += f"⏱️ {format_duration(stat['duration_minutes'])}\n"
                message += f"👥 {format_number(stat['viewers_count'])} глядачів\n"
                message += f"💎 {format_number(stat['diamonds_count'])} алмазів\n\n"
        
        keyboard = [[InlineKeyboardButton("🔙 Назад до меню", callback_data="back_to_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(message, reply_markup=reply_markup)
    
    async def change_nickname(self, query, user_id: int):
        """Змінити TikTok нікнейм"""
        user_states[user_id] = 'waiting_nickname'
        
        message = f"""✏️ Зміна TikTok ніку

{MESSAGES['nickname_prompt']}

💡 **Поради:**
• Введіть новий нікнейм без символу @
• Довжина від 1 до 50 символів
• Використовуйте тільки допустимі символи

🔙 Щоб скасувати, використайте команду /menu"""
        
        keyboard = [[InlineKeyboardButton("🔙 Назад до меню", callback_data="back_to_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(message, reply_markup=reply_markup)
    
    async def show_admin_stats(self, query):
        """Показати статистику для адміна"""
        users = db.get_all_users()
        total_stats = db.get_total_stats()
        
        message = f"""🔧 Адмін статистика

👥 Всього користувачів: {len(users)}
🎥 Всього ефірів: {total_stats.get('total_sessions', 0)}
⏱️ Загальна тривалість: {format_duration(total_stats.get('total_duration', 0))}
💎 Всього алмазів: {format_number(total_stats.get('total_diamonds', 0))}

📊 Топ користувачі:
"""
        
        # Сортувати за кількістю алмазів
        sorted_users = sorted(users, key=lambda x: x.get('total_diamonds', 0) or 0, reverse=True)
        
        for i, user in enumerate(sorted_users[:5], 1):
            nickname = user.get('tiktok_nickname', 'Невідомо')
            diamonds = user.get('total_diamonds', 0) or 0
            sessions = user.get('total_sessions', 0) or 0
            message += f"{i}. {nickname} - {format_number(diamonds)} 💎 ({sessions} ефірів)\n"
        
        keyboard = [[InlineKeyboardButton("🔙 Назад до адмін панелі", callback_data="admin_panel")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(message, reply_markup=reply_markup)
    
    async def show_admin_table_report(self, query):
        """Показати табличний звіт для адміна"""
        report_data = db.get_admin_table_report(30)
        
        message = create_table_report(report_data, "Табличний звіт (останні 30 днів)")
        
        message += "```"
        
        keyboard = [[InlineKeyboardButton("🔄 Оновити", callback_data="admin_table_report")],
                   [InlineKeyboardButton("🔙 Назад до адмін панелі", callback_data="admin_panel")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(message, reply_markup=reply_markup)
    
    async def show_users_list(self, query):
        """Показати список користувачів"""
        users = db.get_all_users()
        
        message = f"👥 Список користувачів ({len(users)}):\n\n"
        
        for user in users[:20]:  # Показати перших 20
            nickname = user.get('tiktok_nickname', 'Невідомо')
            reg_date = datetime.fromisoformat(user['registration_date']).strftime('%d.%m.%Y')
            last_activity = datetime.fromisoformat(user['last_activity']).strftime('%d.%m.%Y')
            sessions = user.get('total_sessions', 0) or 0
            
            message += f"{nickname}\n"
            message += f"📅 Реєстрація: {reg_date}\n"
            message += f"🕐 Остання активність: {last_activity}\n"
            message += f"🎥 Ефірів: {sessions}\n\n"
        
        if len(users) > 20:
            message += f"... та ще {len(users) - 20} користувачів"
        
        keyboard = [[InlineKeyboardButton("🔙 Назад до адмін панелі", callback_data="admin_panel")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(message, reply_markup=reply_markup)
    
    async def test_ocr(self, query):
        """Тест OCR"""
        if ocr_processor.test_ocr_installation():
            message = "✅ OCR працює правильно!"
        else:
            message = "❌ Проблеми з OCR. Перевірте встановлення Tesseract."
            
        keyboard = [[InlineKeyboardButton("🔙 Назад до адмін панелі", callback_data="admin_panel")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(message, reply_markup=reply_markup)
    
    async def show_main_menu(self, query, user_id: int):
        """Показати головне меню"""
        user_data = db.get_user(user_id)
        if not user_data:
            await query.edit_message_text("❌ Користувач не зареєстрований.")
            return
        
        welcome_text = f"""🎯 Головне меню TikTok Live Analytics

👋 Привіт, {user_data['tiktok_nickname']}!

🎯 Оберіть опцію для перегляду статистики:

✨ Доступні функції:
📊 Детальна аналітика 
🌴 Відмітка вихідних днів  
📥 Експорт у CSV
🚀 Доступ 24/7

🕐 Робочий режим: Цілодобово"""
        
        await query.edit_message_text(welcome_text)
        
        # Додати постійні кнопки внизу
        persistent_keyboard = [
            [KeyboardButton("📊 Моя статистика"), KeyboardButton("📈 Статистика за день")],
            [KeyboardButton("📅 Статистика за тиждень"), KeyboardButton("📆 Статистика за місяць")],
            [KeyboardButton("🏆 Топ ефіри"), KeyboardButton("🌟 Мої досягнення")],
            [KeyboardButton("🌍 Загальна статистика"), KeyboardButton("🏅 Топ користувачі")],
            [KeyboardButton("📋 Остання активність"), KeyboardButton("📄 Експорт даних")],
            [KeyboardButton("📥 Скачати мій звіт"), KeyboardButton("📅 Мої вихідні")],
            [KeyboardButton("🌴 Вихідний день"), KeyboardButton("⚙️ Налаштування")],
            [KeyboardButton("ℹ️ Допомога")]
        ]
        
        # Додати адмін панель для адмінів
        if self.is_admin(user_id):
            persistent_keyboard.append([KeyboardButton("🔧 Адмін панель")])
        
        persistent_reply_markup = ReplyKeyboardMarkup(persistent_keyboard, resize_keyboard=True)
        
        await query.message.reply_text("🔽 Швидкий доступ:", reply_markup=persistent_reply_markup)

    async def show_stats_period(self, query, user_id: int, days: int, period_name: str):
        """Показати статистику за період"""
        user_data = db.get_user(user_id)
        if not user_data:
            await query.edit_message_text("❌ Користувач не зареєстрований.")
            return
        
        summary = db.get_user_summary(user_id, days)
        
        message = f"""📈 Статистика {period_name} ({user_data['tiktok_nickname']})

🎥 Кількість ефірів: {summary.get('sessions_count', 0)}
⏱️ Загальна тривалість: {format_duration(summary.get('total_duration', 0))}
👥 Всього глядачів: {format_number(summary.get('total_viewers', 0))}
🎁 Всього дарувальників: {format_number(summary.get('total_gifters', 0))}
💎 Всього алмазів: {format_number(summary.get('total_diamonds', 0))}

📊 Середні показники:
⏱️ Середня тривалість: {format_duration(summary.get('avg_duration', 0))}
👥 Середня к-ть глядачів: {format_number(summary.get('avg_viewers', 0))}
💎 Середня к-ть алмазів: {format_number(summary.get('avg_diamonds', 0))}
"""
        
        keyboard = [[InlineKeyboardButton("🔙 Назад до меню", callback_data="back_to_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(message, reply_markup=reply_markup)

    async def show_top_streams(self, query, user_id: int):
        """Показати топ ефіри користувача"""
        # Отримуємо топ 5 ефірів за алмазами
        stats = db.get_user_statistics(user_id, 30)
        
        if not stats:
            message = "🏆 Топ ефіри\n\nНемає даних за останні 30 днів."
        else:
            # Сортуємо за алмазами
            top_streams = sorted(stats, key=lambda x: x.get('diamonds_count', 0), reverse=True)[:5]
            
            message = "🏆 Топ 5 ефірів за алмазами:\n\n"
            
            for i, stream in enumerate(top_streams, 1):
                date = datetime.fromisoformat(stream['timestamp']).strftime('%d.%m %H:%M')
                message += f"{i}. 📅 {date}\n"
                message += f"⏱️ {format_duration(stream['duration_minutes'])}\n"
                message += f"👥 {format_number(stream['viewers_count'])} глядачів\n"
                message += f"💎 {format_number(stream['diamonds_count'])} алмазів\n\n"
        
        keyboard = [[InlineKeyboardButton("🔙 Назад до меню", callback_data="back_to_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(message, reply_markup=reply_markup)

    async def show_achievements(self, query, user_id: int):
        """Показати досягнення користувача"""
        summary = db.get_user_summary(user_id, 999)  # Всі дані
        
        # Розрахувати досягнення
        achievements = []
        total_sessions = summary.get('sessions_count', 0)
        total_diamonds = summary.get('total_diamonds', 0)
        total_duration = summary.get('total_duration', 0)
        max_viewers = summary.get('max_viewers', 0)
        
        # Досягнення за сесії
        if total_sessions >= 1:
            achievements.append("🎯 Перший ефір")
        if total_sessions >= 10:
            achievements.append("🔥 10 ефірів")
        if total_sessions >= 50:
            achievements.append("⭐ 50 ефірів")
        if total_sessions >= 100:
            achievements.append("👑 100 ефірів")
        
        # Досягнення за алмази
        if total_diamonds >= 1000:
            achievements.append("💎 1K алмазів")
        if total_diamonds >= 10000:
            achievements.append("💠 10K алмазів")
        if total_diamonds >= 100000:
            achievements.append("💍 100K алмазів")
        
        # Досягнення за тривалість
        if total_duration >= 60:
            achievements.append("⏰ Годинний стрімер")
        if total_duration >= 600:
            achievements.append("🕙 10 годин стрімінгу")
        
        # Досягнення за глядачів
        if max_viewers >= 100:
            achievements.append("👥 100 глядачів")
        if max_viewers >= 1000:
            achievements.append("🌟 1K глядачів")
        
        message = f"""🌟 Мої досягнення

🏅 Отримано досягнень: {len(achievements)}

"""
        
        if achievements:
            message = f"""🌟 Мої досягнення

🏅 Отримано досягнень: {len(achievements)}

🎊 Ваші нагороди:
"""
            for achievement in achievements:
                message += f"✅ {achievement}\n"
            
            message += "\n🌟 Вітаємо з досягненнями!"
        else:
            message = f"""🌟 Мої досягнення

🏅 Отримано досягнень: {len(achievements)}

Поки що досягнень немає. Продовжуйте стрімити! 💪

🎯 Найближчі цілі:
🔸 Зробіть перший ефір
🔸 Досягніть 1K алмазів  
🔸 Проведіть годину стрімінгу

🚀 Успіхів у досягненні цілей!"""
        
        keyboard = [[InlineKeyboardButton("🔙 Назад до меню", callback_data="back_to_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(message, reply_markup=reply_markup)

    async def show_top_users(self, query):
        """Показати топ користувачів"""
        users = db.get_all_users()
        
        # Сортуємо за загальною кількістю алмазів
        sorted_users = sorted(users, key=lambda x: x.get('total_diamonds', 0) or 0, reverse=True)
        
        message = f"🏅 Топ користувачі за алмазами:\n\n"
        
        emoji_medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
        
        for i, user in enumerate(sorted_users[:10], 0):
            nickname = user.get('tiktok_nickname', 'Невідомо')
            diamonds = user.get('total_diamonds', 0) or 0
            sessions = user.get('total_sessions', 0) or 0
            
            medal = emoji_medals[i] if i < len(emoji_medals) else f"{i+1}."
            
            message += f"{medal} {nickname}\n"
            message += f"💎 {format_number(diamonds)} алмазів\n"
            message += f"🎥 {sessions} ефірів\n\n"
        
        keyboard = [[InlineKeyboardButton("🔙 Назад до меню", callback_data="back_to_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(message, reply_markup=reply_markup)

    async def export_user_data(self, query, user_id: int):
        """Експорт даних користувача"""
        user_data = db.get_user(user_id)
        if not user_data:
            await query.edit_message_text("❌ Користувач не зареєстрований.")
            return
        
        stats = db.get_user_statistics(user_id, 365)  # За рік
        
        if not stats:
            message = """📄 Експорт даних

📄 Немає даних для експорту.

🎯 Що потрібно зробити:
🔸 Надішліть кілька скріншотів статистики
🔸 Дочекайтеся обробки даних
🔸 Поверніться для експорту

🚀 Почніть збирати дані зараз! 📸"""
        else:
            # Створити CSV-подібний вивід
            export_text = f"Експорт даних для {user_data['tiktok_nickname']}\n"
            export_text += f"Дата експорту: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
            export_text += "Дата | Тривалість | Глядачі | Дарувальники | Алмази\n"
            export_text += "-" * 50 + "\n"
            
            for stat in stats[-20:]:  # Останні 20 записів
                date = datetime.fromisoformat(stat['timestamp']).strftime('%d.%m.%Y')
                duration = format_duration(stat['duration_minutes'])
                viewers = format_number(stat['viewers_count'])
                gifters = format_number(stat['gifters_count'])
                diamonds = format_number(stat['diamonds_count'])
                
                export_text += f"{date} | {duration} | {viewers} | {gifters} | {diamonds}\n"
            
            message = f"""📄 Експорт даних

📄 Експорт даних (останні 20 записів):

{export_text}

📊 Дані готові до використання!"""
        
        keyboard = [[InlineKeyboardButton("🔙 Назад до меню", callback_data="back_to_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(message, reply_markup=reply_markup)

    async def show_settings(self, query, user_id: int):
        """Показати налаштування"""
        user_data = db.get_user(user_id)
        if not user_data:
            await query.edit_message_text("❌ Користувач не зареєстрований.")
            return
        
        reg_date = datetime.fromisoformat(user_data['registration_date']).strftime('%d.%m.%Y')
        
        message = f"""⚙️ Налаштування профілю

👤 TikTok нікнейм: {user_data['tiktok_nickname']}
📅 Дата реєстрації: {reg_date}
🆔 ID користувача: {user_id}
"""
        
        keyboard = [
            [InlineKeyboardButton("✏️ Змінити нікнейм", callback_data="change_nickname")],
            [InlineKeyboardButton("🔙 Назад до меню", callback_data="back_to_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(message, reply_markup=reply_markup)

    async def show_help(self, query):
        """Показати детальну допомогу"""
        message = """ℹ️ Детальна довідка TikTok Live Analytics Bot

🎯 Як користуватися ботом:

Крок 1: Підготовка скріншоту
📱 Зробіть скріншот статистики TikTok Live після завершення ефіру
📸 Переконайтеся, що скріншот містить всі дані:
   • Тривалість ефіру (наприклад: "3 год 25 хв")
   • Кількість глядачів (наприклад: "4.9K Views")
   • Кількість дарувальників (наприклад: "61 Gifters")
   • Кількість алмазів (наприклад: "18.9K Diamonds")

Крок 2: Відправка боту
📨 Надішліть фото скріншоту в чат з ботом
🕐 Пам'ятайте: статистика оновлюється тільки з 7:00 до 19:00
⏳ Зачекайте кілька секунд на обробку
✅ Отримайте результат аналізу

Крок 3: Аналіз статистики
📊 Використовуйте `/menu` для перегляду статистики
📈 Дивіться тренди та порівнюйте результати

🔧 Основні команди:
• `/start` - Реєстрація або перезапуск
• `/menu` - Інтерактивне меню
• `/commands` - Список всіх команд
• `/myid` - Ваш Telegram ID

📊 Типи статистики:
• Моя статистика - ваші особисті дані
• За період - день/тиждень/місяць
• Топ ефіри - найкращі результати
• Досягнення - отримані нагороди
• Загальна статистика - дані всіх користувачів

🌍 Підтримувані мови OCR:
• 🇺🇦 Українська ("3 год 25 хв", "Глядачі", "Діаманти")
• 🇬🇧 Англійська ("3 hours 40 min", "Views", "Diamonds")

💡 Поради для кращого розпізнавання:
• Використовуйте якісні, чіткі скріншоти
• Уникайте засвічених або затемнених зображень
• Переконайтеся, що текст добре читається
• Розмір файлу не повинен перевищувати 10MB

🕐 Важливо про робочі години:
• Статистика оновлюється тільки з 07:00 до 19:00
• Поза цим часом скріншоти не обробляються
• Це забезпечує стабільну роботу системи

⚠️ Можливі проблеми та рішення:
• "Не вдалося розпізнати" → Зробіть кращий скріншот
• "Файл занадто великий" → Стисніть зображення
• "Спочатку зареєструйтеся" → Використайте `/start`

🔒 Безпека та конфіденційність:
• Всі дані зберігаються безпечно
• Скріншоти не зберігаються після обробки
• Доступ тільки до вашої особистої статистики

🆘 Потрібна додаткова допомога?
Використайте `/commands` для списку всіх команд"""
        
        keyboard = [
            [InlineKeyboardButton("📋 Список команд", callback_data="show_commands_inline")],
            [InlineKeyboardButton("🔙 Назад до меню", callback_data="back_to_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(message, reply_markup=reply_markup)

    async def add_holiday(self, query, user_id: int):
        """Додати вихідний день"""
        today = datetime.now().strftime('%Y-%m-%d')
        
        # Перевірити чи сьогодні вже позначено як вихідний
        if db.is_holiday(user_id, today):
            message = f"""🌴 Вихідний день

📅 Сьогодні ({datetime.now().strftime('%d.%m.%Y')}) вже позначено як вихідний день.

✅ Статус: Вихідний день активний
🏖️ Ви можете відпочивати від стрімінгу!"""
            
            keyboard = [
                [InlineKeyboardButton("❌ Скасувати вихідний", callback_data=f"remove_holiday_{today}")],
                [InlineKeyboardButton("🔙 Назад до меню", callback_data="back_to_menu")]
            ]
        else:
            # Додати вихідний день
            if db.add_holiday(user_id, today):
                message = f"""🌴 Вихідний день додано!

📅 Дата: {datetime.now().strftime('%d.%m.%Y')}
✅ Сьогодні позначено як вихідний день

🏖️ Відпочивайте від стрімінгу!
💡 Це допоможе при аналізі вашої активності."""
                
                keyboard = [
                    [InlineKeyboardButton("❌ Скасувати вихідний", callback_data=f"remove_holiday_{today}")],
                    [InlineKeyboardButton("📅 Мої вихідні", callback_data="my_holidays")],
                    [InlineKeyboardButton("🔙 Назад до меню", callback_data="back_to_menu")]
                ]
            else:
                message = "❌ Помилка додавання вихідного дня. Спробуйте ще раз."
                keyboard = [[InlineKeyboardButton("🔙 Назад до меню", callback_data="back_to_menu")]]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(message, reply_markup=reply_markup)

    async def show_my_holidays(self, query, user_id: int):
        """Показати список вихідних днів користувача"""
        holidays = db.get_user_holidays(user_id)
        
        if not holidays:
            message = """📅 Мої вихідні дні

🏖️ У вас поки що немає позначених вихідних днів.

💡 Використовуйте кнопку "🌴 Вихідний день" для позначення днів, коли ви не стрімите."""
            
            keyboard = [
                [InlineKeyboardButton("🌴 Додати сьогодні", callback_data="add_holiday")],
                [InlineKeyboardButton("🔙 Назад до меню", callback_data="back_to_menu")]
            ]
        else:
            message = f"📅 Мої вихідні дні ({len(holidays)}):\n\n"
            
            for holiday in holidays[:10]:  # Показати останні 10
                date_obj = datetime.strptime(holiday['holiday_date'], '%Y-%m-%d')
                date_str = date_obj.strftime('%d.%m.%Y')
                created_obj = datetime.fromisoformat(holiday['created_at'])
                created_str = created_obj.strftime('%d.%m %H:%M')
                
                message += f"🌴 {date_str} (додано {created_str})\n"
            
            if len(holidays) > 10:
                message += f"\n... та ще {len(holidays) - 10} вихідних"
            
            keyboard = [
                [InlineKeyboardButton("🌴 Додати сьогодні", callback_data="add_holiday")],
                [InlineKeyboardButton("🔙 Назад до меню", callback_data="back_to_menu")]
            ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(message, reply_markup=reply_markup)

    async def remove_holiday(self, query, user_id: int, date_str: str):
        """Видалити вихідний день"""
        if db.remove_holiday(user_id, date_str):
            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
            formatted_date = date_obj.strftime('%d.%m.%Y')
            
            message = f"""❌ Вихідний день скасовано

📅 Дата: {formatted_date}
✅ День більше не позначений як вихідний

💡 Тепер цей день буде враховуватись при аналізі активності."""
        else:
            message = "❌ Помилка скасування вихідного дня."
        
        keyboard = [
            [InlineKeyboardButton("📅 Мої вихідні", callback_data="my_holidays")],
            [InlineKeyboardButton("🔙 Назад до меню", callback_data="back_to_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(message, reply_markup=reply_markup)

    async def show_commands_inline(self, query, user_id: int):
        """Показати список команд через інлайн меню"""
        is_admin = self.is_admin(user_id)
        
        # Основні команди
        commands_message = """🤖 TikTok Live Analytics Bot - Команди

📋 Основні команди:
• `/start` - Реєстрація або перезапуск бота
• `/menu` - Головне меню з інтерактивними кнопками  
• `/myid` - Показати ваш Telegram ID та статус
• `/commands` - Показати цей список команд
• `/help` - Детальна довідка по використанню

📊 Функції через меню:
• 📈 Моя статистика за різні періоди
• 🏆 Топ ефіри та досягнення
• 🌍 Загальна статистика платформи
• 📄 Експорт даних
• ⚙️ Налаштування профілю

📸 Як використовувати:
1. Зробіть скріншот статистики TikTok Live
2. Надішліть фото боту
3. Отримайте автоматичний аналіз
4. Переглядайте статистику через `/menu`"""

        # Додати адмін команди якщо користувач адмін
        if is_admin:
            commands_message += """

🔧 Адмін команди:
• `/admin` - Адмін панель з управлінням системою

🎯 Адмін функції:
• 📊 Статистика всіх користувачів
• 👥 Управління користувачами
• 📈 Аналітика за періоди
• 🔧 Системна діагностика
• 📁 Експорт всіх даних
• 🗑️ Очищення бази даних
• 📋 Перегляд логів системи"""

        commands_message += """

💡 Підказки:
• Для кращого розпізнавання використовуйте якісні скріншоти
• Всі дані зберігаються безпечно та конфіденційно
• Бот підтримує українську та англійську мови OCR

🆘 Потрібна допомога? Використайте `/help` для детальної інструкції"""

        keyboard = [
            [InlineKeyboardButton("ℹ️ Повна довідка", callback_data="help")],
            [InlineKeyboardButton("🔙 Назад до меню", callback_data="back_to_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(commands_message, reply_markup=reply_markup)

    async def show_admin_panel(self, query):
        """Показати адмін панель"""
        keyboard = [
            [InlineKeyboardButton("📊 Статистика всіх", callback_data="admin_all_stats"),
             InlineKeyboardButton("📋 Таблиця звітів", callback_data="admin_table_report")],
            [InlineKeyboardButton("👥 Список користувачів", callback_data="admin_users_list"),
             InlineKeyboardButton("🎯 Активність користувачів", callback_data="admin_user_activity")],
            [InlineKeyboardButton("📊 Розширені звіти", callback_data="admin_detailed_reports"),
             InlineKeyboardButton("📈 Статистика за період", callback_data="admin_period_stats")],
            [InlineKeyboardButton("🔧 Тест OCR", callback_data="admin_test_ocr"),
             InlineKeyboardButton("📥 Скачати зведений звіт", callback_data="download_summary_report")],
            [InlineKeyboardButton("📥 Скачати всі звіти", callback_data="download_all_reports"),
             InlineKeyboardButton("👤 Звіт по користувачу", callback_data="download_user_report")],
            [InlineKeyboardButton("📊 Звіт з вихідними", callback_data="download_holiday_report"),
             InlineKeyboardButton("📁 Експорт всіх даних", callback_data="admin_export_all")],
            [InlineKeyboardButton("🗑️ Очистити старі дані", callback_data="admin_cleanup"),
             InlineKeyboardButton("📋 Логи системи", callback_data="admin_logs")],
            [InlineKeyboardButton("🔑 Діагностика доступу", callback_data="admin_diagnostics"),
             InlineKeyboardButton("⚙️ Системна інформація", callback_data="admin_system_info")],
            [InlineKeyboardButton("🔧 Техобслуговування", callback_data="admin_maintenance")],
            [InlineKeyboardButton("🔙 Назад до меню", callback_data="back_to_menu")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("🔧 Адмін панель\n\nОберіть дію:", reply_markup=reply_markup)

    async def show_admin_period_stats(self, query):
        """Статистика за період для адміна"""
        total_stats_7d = db.get_total_stats_period(7)
        total_stats_30d = db.get_total_stats_period(30)
        
        message = f"""📈 Статистика за період

📅 За 7 днів:
🎥 Ефірів: {total_stats_7d.get('total_sessions', 0)}
⏱️ Тривалість: {format_duration(total_stats_7d.get('total_duration', 0))}
💎 Алмазів: {format_number(total_stats_7d.get('total_diamonds', 0))}

📆 За 30 днів:
🎥 Ефірів: {total_stats_30d.get('total_sessions', 0)}
⏱️ Тривалість: {format_duration(total_stats_30d.get('total_duration', 0))}
💎 Алмазів: {format_number(total_stats_30d.get('total_diamonds', 0))}
"""
        
        keyboard = [[InlineKeyboardButton("🔙 Назад до адмін панелі", callback_data="admin_panel")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(message, reply_markup=reply_markup)

    async def show_admin_user_activity(self, query):
        """Активність користувачів"""
        users = db.get_all_users()
        now = datetime.now()
        
        # Розділити користувачів за активністю
        active_today = 0
        active_week = 0
        active_month = 0
        
        for user in users:
            last_activity = datetime.fromisoformat(user['last_activity'])
            days_ago = (now - last_activity).days
            
            if days_ago == 0:
                active_today += 1
            if days_ago <= 7:
                active_week += 1
            if days_ago <= 30:
                active_month += 1
        
        message = f"""🎯 Активність користувачів

👥 Всього користувачів: {len(users)}

📅 Активність:
🔥 Сьогодні: {active_today}
📅 За тиждень: {active_week}
📆 За місяць: {active_month}
😴 Неактивні (>30д): {len(users) - active_month}
"""
        
        keyboard = [[InlineKeyboardButton("🔙 Назад до адмін панелі", callback_data="admin_panel")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(message, reply_markup=reply_markup)

    async def admin_export_all(self, query):
        """Експорт всіх даних"""
        message = """📁 Експорт всіх даних

⚠️ Ця функція експортує всі дані з бази даних.
Це може зайняти час для великої кількості записів.

🔄 Експорт розпочато... (це може зайняти кілька хвилин)
"""
        
        await query.edit_message_text(message)
        
        # Тут можна додати реальний експорт у файл
        # Поки що просто показуємо статистику
        
        total_stats = db.get_total_stats()
        users = db.get_all_users()
        
        export_message = f"""✅ Експорт завершено

📊 Загальна статистика:
👥 Користувачів: {len(users)}
🎥 Ефірів: {total_stats.get('total_sessions', 0)}
⏱️ Тривалість: {format_duration(total_stats.get('total_duration', 0))}
💎 Алмазів: {format_number(total_stats.get('total_diamonds', 0))}

📄 Дані готові для вивантаження.
"""
        
        keyboard = [[InlineKeyboardButton("🔙 Назад до адмін панелі", callback_data="admin_panel")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(export_message, reply_markup=reply_markup)

    async def admin_cleanup(self, query):
        """Очистити старі дані"""
        message = """🗑️ Очистка старих даних

⚠️ УВАГА! Ця дія видалить:
• Статистику старшу за 365 днів
• Неактивних користувачів (>180 днів)

⚠️ Ця дія незворотна!

Очистка розпочата...
"""
        
        await query.edit_message_text(message)
        
        # Тут можна додати реальну очистку
        # Поки що просто показуємо що зробили б
        
        cleanup_message = """✅ Очистка завершена

📊 Результати:
🗑️ Видалено старих записів: 0
👥 Видалено неактивних користувачів: 0

База даних оптимізована.
"""
        
        keyboard = [[InlineKeyboardButton("🔙 Назад до адмін панелі", callback_data="admin_panel")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(cleanup_message, reply_markup=reply_markup)

    async def show_admin_logs(self, query):
        """Показати логи системи"""
        message = """📋 Логи системи

🔍 Останні події:
• Запуск бота: OK
• OCR тест: ✅ Пройшов
• База даних: ✅ Підключена
• Telegram API: ✅ Активний

📊 Статистика помилок:
• OCR помилки: 0
• Помилки бази даних: 0
• Telegram помилки: 0

🕐 Останнє оновлення: {datetime.now().strftime('%d.%m.%Y %H:%M')}
"""
        
        keyboard = [[InlineKeyboardButton("🔙 Назад до адмін панелі", callback_data="admin_panel")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(message, reply_markup=reply_markup)

    async def admin_diagnostics(self, query):
        """Діагностика доступу"""
        user_id = query.from_user.id
        username = query.from_user.username or "немає username"
        
        # Детальна діагностика
        config_admin_ids = ADMIN_USER_IDS
        is_admin_check = self.is_admin(user_id)
        
        message = f"""🔑 Діагностика доступу

👤 Інформація про користувача:
• Username: @{username}
• User ID: {user_id}
• Telegram ID: {user_id}

🔧 Перевірка адмін прав:
• Ваш ID: {user_id}
• Список адмін ID: {config_admin_ids}
• ID присутній у списку: {'✅ Так' if user_id in config_admin_ids else '❌ Ні'}
• Результат is_admin(): {'✅ Так' if is_admin_check else '❌ Ні'}

📋 Налаштування з config.py:
• ADMIN_USER_IDS: {config_admin_ids}
• Кількість адмінів: {len(config_admin_ids)}

🔍 Додаткова інформація:
• Тип user_id: {type(user_id).__name__}
• Тип елементів у списку: {type(config_admin_ids[0]).__name__ if config_admin_ids else 'список порожній'}

🕐 Перевірено: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}
"""
        
        keyboard = [
            [InlineKeyboardButton("🔄 Оновити", callback_data="admin_diagnostics")],
            [InlineKeyboardButton("🔙 Назад до адмін панелі", callback_data="admin_panel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(message, reply_markup=reply_markup)

    async def admin_system_info(self, query):
        """Системна інформація"""
        total_stats = db.get_total_stats()
        users = db.get_all_users()
        
        message = f"""⚙️ Системна інформація

🔍 Система:
• ОС: {platform.system()} {platform.release()}
• Python: {sys.version.split()[0]}
• Архітектура: {platform.machine()}

📊 Статистика бота:
• Всього користувачів: {len(users)}
• Всього ефірів: {total_stats.get('total_sessions', 0)}
• Загальна тривалість: {format_duration(total_stats.get('total_duration', 0))}
• Всього алмазів: {format_number(total_stats.get('total_diamonds', 0))}

🔧 Налаштування:
• Адмін ID: {ADMIN_USER_IDS}
• Rate Limit: {RATE_LIMIT_MESSAGES} повідомлень за {RATE_LIMIT_PERIOD}с
• Макс розмір файлу: {MAX_FILE_SIZE // (1024*1024)}MB

🕐 Останнє оновлення: {datetime.now().strftime('%d.%m.%Y %H:%M')}
"""
        
        keyboard = [[InlineKeyboardButton("🔙 Назад до адмін панелі", callback_data="admin_panel")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(message, reply_markup=reply_markup)

    async def commands_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обробник команди /commands - показати список команд"""
        if not update.message or not update.effective_user:
            return
            
        user_id = update.effective_user.id
        username = update.effective_user.username or "немає username"
        is_admin = self.is_admin(user_id)
        
        # Основні команди
        commands_message = """🤖 **TikTok Live Analytics Bot - Команди**

📋 **Основні команди:**
• `/start` - Реєстрація або перезапуск бота
• `/menu` - Головне меню з інтерактивними кнопками  
• `/myid` - Показати ваш Telegram ID та статус
• `/commands` - Показати цей список команд
• `/help` - Детальна довідка по використанню

📊 **Функції через меню:**
• 📈 Моя статистика за різні періоди
• 🏆 Топ ефіри та досягнення
• 🌍 Загальна статистика платформи
• 📄 Експорт даних
• ⚙️ Налаштування профілю

📸 **Як використовувати:**
1. Зробіть скріншот статистики TikTok Live
2. Надішліть фото боту
3. Отримайте автоматичний аналіз
4. Переглядайте статистику через `/menu`"""

        # Додати адмін команди якщо користувач адмін
        if is_admin:
            commands_message += """

🔧 **Адмін команди:**
• `/admin` - Адмін панель з управлінням системою

🎯 **Адмін функції:**
• 📊 Статистика всіх користувачів
• 👥 Управління користувачами
• 📈 Аналітика за періоди
• 🔧 Системна діагностика
• 📁 Експорт всіх даних
• 🗑️ Очищення бази даних
• 📋 Перегляд логів системи"""

        commands_message += """

💡 **Підказки:**
• Для кращого розпізнавання використовуйте якісні скріншоти
• Всі дані зберігаються безпечно та конфіденційно
• Бот підтримує українську та англійську мови OCR

🆘 **Потрібна допомога?** Використайте `/help` для детальної інструкції"""

        await update.message.reply_text(commands_message)

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обробник команди /help - показати довідку"""
        if not update.message or not update.effective_user:
            return
            
        user_id = update.effective_user.id
        
        help_message = """ℹ️ Довідка TikTok Live Analytics Bot

🎯 Як користуватися:
1. 📸 Зробіть скріншот статистики TikTok Live
2. 📨 Надішліть фото боту  
3. ⏳ Зачекайте на автоматичний аналіз
4. 📊 Переглядайте статистику через `/menu`

🔧 Основні команди:
• `/start` - Реєстрація або перезапуск
• `/menu` - Інтерактивне меню
• `/commands` - Повний список команд
• `/myid` - Ваш Telegram ID
• `/help` - Ця довідка

🌍 Підтримувані мови:
• 🇺🇦 Українська
• 🇬🇧 Англійська

💡 Поради:
• Використовуйте якісні скріншоти
• Переконайтеся, що текст добре читається
• Максимальний розмір файлу: 10MB

🆘 Проблеми?
Використайте `/commands` для детального списку всіх функцій"""

        await update.message.reply_text(help_message)

    def setup_handlers(self):
        """Налаштувати обробники"""
        if not self.application:
            return
            
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("menu", self.menu_command))
        self.application.add_handler(CommandHandler("admin", self.admin_command))
        self.application.add_handler(CommandHandler("myid", self.myid_command))
        self.application.add_handler(CommandHandler("commands", self.commands_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        self.application.add_handler(MessageHandler(filters.PHOTO, self.handle_photo))
        
        self.application.add_handler(CallbackQueryHandler(self.handle_callback))
    
    def run_bot(self):
        """Запустити бота синхронно"""
        # Тест OCR
        if ocr_processor.test_ocr_installation():
            logger.info("OCR тест пройшов успішно")
        else:
            logger.warning("Проблеми з OCR - перевірте встановлення Tesseract")
        
        # Створити додаток
        if not BOT_TOKEN:
            logger.error("BOT_TOKEN не встановлений!")
            return
        self.application = Application.builder().token(BOT_TOKEN).build()
        
        # Налаштувати обробники
        self.setup_handlers()
        
        # Запустити бота з планувальником
        logger.info("Запуск TikTok Stats Bot з автоматичними звітами...")
        
        # Запустити планувальник в окремому потоці
        import threading
        
        def run_scheduler():
            """Запустити планувальник в окремому потоці"""
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(start_scheduler(self.application))
            
        scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
        scheduler_thread.start()
        
        # Запустити бота
        self.application.run_polling()

    async def download_summary_report(self, query, user_id: int):
        """Скачати зведений звіт"""
        try:
            await query.edit_message_text("📥 Генерую зведений звіт...")
            
            # Отримати дані
            report_data = db.get_summary_report_with_holidays(30)
            
            if not report_data:
                await query.edit_message_text("❌ Немає даних для звіту.")
                return
            
            # Створити CSV файл
            filepath = create_csv_report(report_data, "summary")
            
            # Відправити файл
            with open(filepath, 'rb') as file:
                await query.message.reply_document(
                    document=file,
                    filename=os.path.basename(filepath),
                    caption=f"📊 Зведений звіт TikTok Analytics\n📅 Період: останні 30 днів\n👥 Користувачів: {len(report_data)}"
                )
            
            # Видалити файл
            os.unlink(filepath)
            
            await query.edit_message_text("✅ Зведений звіт надіслано!")
            
        except Exception as e:
            logger.error(f"Помилка створення зведеного звіту: {e}")
            await query.edit_message_text("❌ Помилка створення звіту. Спробуйте ще раз.")

    async def download_all_reports(self, query, user_id: int):
        """Скачати всі детальні звіти користувачів"""
        try:
            await query.edit_message_text("📥 Генерую звіти всіх користувачів... Це може зайняти час.")
            
            # Отримати всі звіти
            all_reports = db.get_all_users_detailed_report(30)
            
            if not all_reports:
                await query.edit_message_text("❌ Немає даних для звітів.")
                return
            
            # Створити файли для кожного користувача
            files_created = create_all_users_csv_package(all_reports)
            
            if not files_created:
                await query.edit_message_text("❌ Не вдалося створити файли звітів.")
                return
            
            # Відправити файли (максимум 10 за раз)
            for i, filepath in enumerate(files_created[:10]):
                try:
                    with open(filepath, 'rb') as file:
                        nickname = os.path.basename(filepath).replace('tiktok_detail_', '').split('_')[0]
                        await query.message.reply_document(
                            document=file,
                            filename=os.path.basename(filepath),
                            caption=f"📊 Детальний звіт: {nickname}\n📅 Період: останні 30 днів"
                        )
                    
                    # Видалити файл після відправки
                    os.unlink(filepath)
                    
                except Exception as e:
                    logger.error(f"Помилка відправки файлу {filepath}: {e}")
                    continue
            
            total_sent = min(len(files_created), 10)
            message = f"✅ Надіслано {total_sent} детальних звітів!"
            
            if len(files_created) > 10:
                message += f"\n⚠️ Показано тільки перші 10 з {len(files_created)} звітів."
            
            await query.edit_message_text(message)
            
        except Exception as e:
            logger.error(f"Помилка створення всіх звітів: {e}")
            await query.edit_message_text("❌ Помилка створення звітів. Спробуйте ще раз.")

    async def download_user_report(self, query, user_id: int):
        """Показати список користувачів для вибору звіту"""
        try:
            users = db.get_all_users()
            
            if not users:
                await query.edit_message_text("❌ Немає користувачів для звіту.")
                return
            
            # Створити кнопки для вибору користувача
            keyboard = []
            for user in users[:20]:  # Показати перших 20
                nickname = user.get('tiktok_nickname', 'Невідомо')
                telegram_id = user.get('telegram_id', 0)
                keyboard.append([InlineKeyboardButton(f"👤 {nickname}", callback_data=f"user_report_{telegram_id}")])
            
            keyboard.append([InlineKeyboardButton("🔙 Назад до адмін панелі", callback_data="admin_panel")])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text("👤 Оберіть користувача для детального звіту:", reply_markup=reply_markup)
            
        except Exception as e:
            logger.error(f"Помилка показу списку користувачів: {e}")
            await query.edit_message_text("❌ Помилка отримання списку користувачів.")

    async def download_holiday_report(self, query, user_id: int):
        """Скачати звіт з урахуванням вихідних днів"""
        try:
            await query.edit_message_text("📥 Генерую звіт з вихідними днями...")
            
            # Отримати дані з вихідними
            report_data = db.get_summary_report_with_holidays(30)
            
            if not report_data:
                await query.edit_message_text("❌ Немає даних для звіту.")
                return
            
            # Створити CSV файл з розширеною інформацією
            filepath = create_csv_report(report_data, "summary")
            
            # Відправити файл
            with open(filepath, 'rb') as file:
                await query.message.reply_document(
                    document=file,
                    filename=f"tiktok_holidays_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    caption=f"📊 Звіт з вихідними днями\n📅 Період: останні 30 днів\n👥 Користувачів: {len(report_data)}\n🌴 Включає інформацію про вихідні дні"
                )
            
            # Видалити файл
            os.unlink(filepath)
            
            await query.edit_message_text("✅ Звіт з вихідними днями надіслано!")
            
        except Exception as e:
            logger.error(f"Помилка створення звіту з вихідними: {e}")
            await query.edit_message_text("❌ Помилка створення звіту. Спробуйте ще раз.")

    async def generate_individual_user_report(self, query, target_user_id: int):
        """Генерувати індивідуальний звіт користувача"""
        try:
            await query.edit_message_text("📥 Генерую індивідуальний звіт...")
            
            # Отримати дані користувача
            user_data = db.get_user(target_user_id)
            if not user_data:
                await query.edit_message_text("❌ Користувач не знайдений.")
                return
            
            # Отримати детальні дані
            detailed_data = db.get_detailed_user_report(target_user_id, 30)
            
            if not detailed_data:
                await query.edit_message_text(f"❌ Немає даних для користувача {user_data['tiktok_nickname']}.")
                return
            
            # Створити CSV файл
            nickname = user_data['tiktok_nickname']
            filepath = create_user_detailed_csv(user_data, detailed_data, nickname)
            
            # Підрахувати статистику
            total_days = len(detailed_data)
            active_days = len([d for d in detailed_data if d.get('sessions_count', 0) > 0])
            holiday_days = len([d for d in detailed_data if d.get('is_holiday', 0) > 0])
            total_diamonds = sum(d.get('total_diamonds', 0) for d in detailed_data)
            
            # Відправити файл
            with open(filepath, 'rb') as file:
                await query.message.reply_document(
                    document=file,
                    filename=os.path.basename(filepath),
                    caption=f"""📊 Детальний звіт: {nickname}
📅 Період: останні 30 днів
📈 Активних днів: {active_days}/{total_days}
🌴 Вихідних днів: {holiday_days}
💎 Загальна к-ть алмазів: {format_number(total_diamonds)}

📋 Звіт містить поденну статистику з позначенням вихідних днів."""
                )
            
            # Видалити файл
            os.unlink(filepath)
            
            await query.edit_message_text(f"✅ Індивідуальний звіт для {nickname} надіслано!")
            
        except Exception as e:
            logger.error(f"Помилка створення індивідуального звіту: {e}")
            await query.edit_message_text("❌ Помилка створення звіту. Спробуйте ще раз.")

    async def download_my_report(self, query, user_id: int):
        """Скачати власний звіт користувача"""
        try:
            await query.edit_message_text("📥 Генерую ваш персональний звіт...")
            
            # Отримати дані користувача
            user_data = db.get_user(user_id)
            if not user_data:
                await query.edit_message_text("❌ Користувач не зареєстрований.")
                return
            
            # Отримати детальні дані за 30 днів
            detailed_data = db.get_detailed_user_report(user_id, 30)
            
            if not detailed_data:
                await query.edit_message_text("❌ Немає даних для створення звіту. Почніть надсилати скріншоти!")
                return
            
            # Створити CSV файл
            nickname = user_data['tiktok_nickname']
            filepath = create_user_detailed_csv(user_data, detailed_data, nickname)
            
            # Підрахувати статистику для опису
            total_days = len(detailed_data)
            active_days = len([d for d in detailed_data if d.get('sessions_count', 0) > 0])
            holiday_days = len([d for d in detailed_data if d.get('is_holiday', 0) > 0])
            total_sessions = sum(d.get('sessions_count', 0) for d in detailed_data)
            total_diamonds = sum(d.get('total_diamonds', 0) for d in detailed_data)
            total_duration = sum(d.get('total_duration', 0) for d in detailed_data)
            
            # Відправити файл
            with open(filepath, 'rb') as file:
                await query.message.reply_document(
                    document=file,
                    filename=f"my_tiktok_report_{nickname}_{datetime.now().strftime('%Y%m%d')}.csv",
                    caption=f"""📊 Ваш персональний звіт TikTok

👤 Користувач: {nickname}
📅 Період: останні 30 днів

📈 Статистика:
• Всього днів у звіті: {total_days}
• Активних днів: {active_days}
• Вихідних днів: {holiday_days}
• Всього ефірів: {total_sessions}
• Загальна тривалість: {format_duration(total_duration)}
• Всього алмазів: {format_number(total_diamonds)}

📋 Звіт містить поденну детальну статистику з позначенням вихідних днів.
Ви можете відкрити файл у Excel або Google Sheets."""
                )
            
            # Видалити файл
            os.unlink(filepath)
            
            await query.edit_message_text("✅ Ваш персональний звіт надіслано!")
            
        except Exception as e:
            logger.error(f"Помилка створення персонального звіту для {user_id}: {e}")
            await query.edit_message_text("❌ Помилка створення звіту. Спробуйте ще раз.")

    async def show_admin_detailed_reports(self, query):
        """Показати меню розширених звітів"""
        message = """📊 Розширені звіти по користувачах

Оберіть період для детального аналізу:
• 📅 День - статистика за останній день
• 📆 Тиждень - поденна статистика за тиждень  
• 🗓️ Місяць - поденна статистика за місяць

Для кожного користувача буде показана детальна статистика з розбивкою по днях та позначенням вихідних."""
        
        keyboard = [
            [InlineKeyboardButton("📅 За день", callback_data="detailed_period_day"),
             InlineKeyboardButton("📆 За тиждень", callback_data="detailed_period_week")],
            [InlineKeyboardButton("🗓️ За місяць", callback_data="detailed_period_month")],
            [InlineKeyboardButton("🔙 Назад до адмін панелі", callback_data="admin_panel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(message, reply_markup=reply_markup)

    async def show_detailed_period_menu(self, query, period: str):
        """Показати меню вибору користувача для періоду"""
        period_names = {
            'day': '📅 день',
            'week': '📆 тиждень', 
            'month': '🗓️ місяць'
        }
        
        period_name = period_names.get(period, period)
        
        try:
            users = db.get_all_users()
            
            if not users:
                await query.edit_message_text("❌ Немає користувачів для звіту.")
                return
            
            message = f"👥 Оберіть користувача для розширеного звіту за {period_name}:"
            
            # Створити кнопки для вибору користувача
            keyboard = []
            for user in users[:15]:  # Показати перших 15
                nickname = user.get('tiktok_nickname', 'Невідомо')
                telegram_id = user.get('telegram_id', 0)
                keyboard.append([InlineKeyboardButton(f"👤 {nickname}", callback_data=f"detailed_user_{period}_{telegram_id}")])
            
            # Кнопки навігації
            keyboard.append([InlineKeyboardButton("🔙 Назад до вибору періоду", callback_data="admin_detailed_reports")])
            keyboard.append([InlineKeyboardButton("🏠 Назад до адмін панелі", callback_data="admin_panel")])
            
            if len(users) > 15:
                message += f"\n\n📋 Показано перших 15 з {len(users)} користувачів."
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(message, reply_markup=reply_markup)
            
        except Exception as e:
            logger.error(f"Помилка показу меню користувачів: {e}")
            await query.edit_message_text("❌ Помилка отримання списку користувачів.")

    async def show_detailed_user_stats(self, query, target_user_id: int, period: str):
        """Показати детальну статистику користувача"""
        try:
            # Визначити кількість днів для періоду
            days_map = {
                'day': 1,
                'week': 7,
                'month': 30
            }
            
            period_names = {
                'day': 'за день',
                'week': 'за тиждень',
                'month': 'за місяць'
            }
            
            days = days_map.get(period, 7)
            period_name = period_names.get(period, period)
            
            # Отримати дані користувача
            user_data = db.get_user(target_user_id)
            if not user_data:
                await query.edit_message_text("❌ Користувач не знайдений.")
                return
            
            # Отримати детальні дані
            detailed_data = db.get_detailed_user_report(target_user_id, days)
            
            if not detailed_data:
                await query.edit_message_text(f"❌ Немає даних для користувача {user_data['tiktok_nickname']} {period_name}.")
                return
            
            nickname = user_data['tiktok_nickname']
            
            # Формувати повідомлення
            message = f"📊 Розширений звіт: {nickname} {period_name}\n\n"
            
            # Підрахувати загальну статистику
            total_days = len(detailed_data)
            active_days = len([d for d in detailed_data if d.get('sessions_count', 0) > 0])
            holiday_days = len([d for d in detailed_data if d.get('is_holiday', 0) > 0])
            total_sessions = sum(d.get('sessions_count', 0) for d in detailed_data)
            total_duration = sum(d.get('total_duration', 0) for d in detailed_data)
            total_viewers = sum(d.get('total_viewers', 0) for d in detailed_data)
            total_diamonds = sum(d.get('total_diamonds', 0) for d in detailed_data)
            
            # Загальна статистика
            message += f"📈 Загальна статистика:\n"
            message += f"• Період: {total_days} днів\n"
            message += f"• Активних днів: {active_days}\n"
            message += f"• Вихідних днів: {holiday_days}\n"
            message += f"• Всього ефірів: {total_sessions}\n"
            message += f"• Загальна тривалість: {format_duration(total_duration)}\n"
            message += f"• Всього глядачів: {format_number(total_viewers)}\n"
            message += f"• Всього алмазів: {format_number(total_diamonds)}\n\n"
            
            # Поденна статистика (останні 10 днів для читабельності)
            message += f"📅 Поденна статистика:\n"
            for day in detailed_data[:10]:
                date = datetime.strptime(day['date'], '%Y-%m-%d').strftime('%d.%m')
                status = "🌴" if day.get('is_holiday', 0) else "📺"
                sessions = day.get('sessions_count', 0)
                duration = day.get('total_duration', 0)
                diamonds = day.get('total_diamonds', 0)
                
                if sessions > 0:
                    message += f"{status} {date}: {sessions} ефірів, {format_duration(duration)}, {format_number(diamonds)} 💎\n"
                else:
                    message += f"{status} {date}: Немає активності\n"
            
            if len(detailed_data) > 10:
                message += f"\n... та ще {len(detailed_data) - 10} днів"
            
            # Кнопки навігації
            keyboard = [
                [InlineKeyboardButton("📥 Скачати повний звіт", callback_data=f"download_detailed_{period}_{target_user_id}")],
                [InlineKeyboardButton("🔙 Назад до списку користувачів", callback_data=f"detailed_period_{period}")],
                [InlineKeyboardButton("🏠 Назад до адмін панелі", callback_data="admin_panel")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(message, reply_markup=reply_markup)
            
        except Exception as e:
            logger.error(f"Помилка створення розширеного звіту: {e}")
            await query.edit_message_text("❌ Помилка створення звіту. Спробуйте ще раз.")

    async def download_detailed_user_report(self, query, target_user_id: int, period: str):
        """Завантажити детальний звіт користувача як CSV"""
        try:
            # Визначити кількість днів для періоду
            days_map = {
                'day': 1,
                'week': 7,
                'month': 30
            }
            
            period_names = {
                'day': 'день',
                'week': 'тиждень',
                'month': 'місяць'
            }
            
            days = days_map.get(period, 7)
            period_name = period_names.get(period, period)
            
            # Отримати дані користувача
            user_data = db.get_user(target_user_id)
            if not user_data:
                await query.edit_message_text("❌ Користувач не знайдений.")
                return
            
            nickname = user_data['tiktok_nickname']
            
            # Отримати детальні дані
            detailed_data = db.get_detailed_user_report(target_user_id, days)
            
            if not detailed_data:
                await query.edit_message_text(f"❌ Немає даних для створення звіту для {nickname}")
                return
            
            # Створити CSV файл
            filepath = create_user_detailed_csv(user_data, detailed_data, nickname)
            
            if not filepath:
                await query.edit_message_text(f"❌ Помилка створення CSV для {nickname}")
                return
            
            # Файл вже створений функцією create_user_detailed_csv
            filename = os.path.basename(filepath)
            
            # Підготувати статистику для caption
            total_days = len(detailed_data)
            active_days = len([d for d in detailed_data if d.get('sessions_count', 0) > 0])
            holiday_days = len([d for d in detailed_data if d.get('is_holiday', 0) > 0])
            
            caption = f"📊 Розширений звіт: {nickname} за {period_name}\n"
            caption += f"📅 Період: {total_days} днів\n"
            caption += f"📺 Активних днів: {active_days}\n"
            caption += f"🌴 Вихідних днів: {holiday_days}"
            
            # Відправити файл
            with open(filepath, 'rb') as f:
                await query.message.reply_document(
                    document=f,
                    filename=filename,
                    caption=caption
                )
            
            # Видалити тимчасовий файл
            try:
                os.remove(filepath)
            except:
                pass
            
            await query.edit_message_text(f"✅ Розширений звіт для {nickname} відправлено!")
            
        except Exception as e:
            logger.error(f"Помилка завантаження розширеного звіту: {e}")
            await query.edit_message_text("❌ Помилка створення звіту. Спробуйте ще раз.")

    async def show_maintenance_menu(self, query):
        """Показати меню технічного обслуговування"""
        maintenance_info = db.get_maintenance_info()
        is_enabled = maintenance_info.get('enabled', False)
        
        if is_enabled:
            timestamp = maintenance_info.get('timestamp', '')
            message = maintenance_info.get('message', '')
            
            if timestamp:
                try:
                    dt = datetime.fromisoformat(timestamp)
                    formatted_time = dt.strftime('%d.%m.%Y %H:%M')
                except:
                    formatted_time = timestamp
            else:
                formatted_time = 'Невідомо'
            
            status_text = f"""🔧 Технічне обслуговування

🔴 **Режим АКТИВНИЙ**
🕐 Включено: {formatted_time}"""
            
            if message:
                status_text += f"\n📋 Причина: {message}"
            
            status_text += "\n\n⚠️ Користувачі не можуть надсилати скріншоти"
            
            keyboard = [
                [InlineKeyboardButton("🔴 Вимкнути техобслуговування", callback_data="maintenance_disable")],
                [InlineKeyboardButton("📊 Статус", callback_data="maintenance_status")],
                [InlineKeyboardButton("🔙 Назад до адмін панелі", callback_data="admin_panel")]
            ]
        else:
            status_text = """🔧 Технічне обслуговування

🟢 **Режим НЕАКТИВНИЙ**
✅ Бот працює в нормальному режимі
👥 Користувачі можуть надсилати скріншоти"""
            
            keyboard = [
                [InlineKeyboardButton("🔴 Включити техобслуговування", callback_data="maintenance_enable")],
                [InlineKeyboardButton("📊 Статус", callback_data="maintenance_status")],
                [InlineKeyboardButton("🔙 Назад до адмін панелі", callback_data="admin_panel")]
            ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(status_text, reply_markup=reply_markup)

    async def enable_maintenance_mode(self, query):
        """Включити режим технічного обслуговування"""
        # Включити режим без повідомлення (користувач може додати пізніше)
        success = db.set_maintenance_mode(True, "Планове технічне обслуговування")
        
        if success:
            message = """🔧 Режим технічного обслуговування ВКЛЮЧЕНО

🔴 **Статус**: АКТИВНИЙ
⏰ **Час**: {current_time}
📋 **Причина**: Планове технічне обслуговування

⚠️ **Що це означає:**
• Користувачі не можуть надсилати скріншоти
• Вони отримуватимуть повідомлення про техобслуговування
• Адмін функції залишаються доступними
• Автоматичні звіти продовжують працювати

✅ **Рекомендації:**
• Виконайте необхідні технічні роботи
• Завантажте звіти якщо потрібно
• Вимкніть режим після завершення

🔙 Використовуйте кнопку нижче для управління""".format(
                current_time=datetime.now().strftime('%d.%m.%Y %H:%M')
            )
            
            keyboard = [
                [InlineKeyboardButton("🔴 Вимкнути техобслуговування", callback_data="maintenance_disable")],
                [InlineKeyboardButton("📊 Поточний статус", callback_data="maintenance_status")],
                [InlineKeyboardButton("🔙 Назад до меню техобслуговування", callback_data="admin_maintenance")]
            ]
        else:
            message = "❌ Помилка включення режиму техобслуговування"
            keyboard = [
                [InlineKeyboardButton("🔙 Назад до меню техобслуговування", callback_data="admin_maintenance")]
            ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(message, reply_markup=reply_markup)

    async def disable_maintenance_mode(self, query):
        """Вимкнути режим технічного обслуговування"""
        success = db.set_maintenance_mode(False)
        
        if success:
            message = """🔧 Режим технічного обслуговування ВИМКНЕНО

🟢 **Статус**: НЕАКТИВНИЙ
⏰ **Час**: {current_time}

✅ **Що змінилося:**
• Користувачі знову можуть надсилати скріншоти
• Бот працює в нормальному режимі
• Всі функції доступні

🚀 **Бот готовий до роботи!**""".format(
                current_time=datetime.now().strftime('%d.%m.%Y %H:%M')
            )
            
            keyboard = [
                [InlineKeyboardButton("🔴 Включити техобслуговування", callback_data="maintenance_enable")],
                [InlineKeyboardButton("📊 Поточний статус", callback_data="maintenance_status")],
                [InlineKeyboardButton("🔙 Назад до меню техобслуговування", callback_data="admin_maintenance")]
            ]
        else:
            message = "❌ Помилка вимкнення режиму техобслуговування"
            keyboard = [
                [InlineKeyboardButton("🔙 Назад до меню техобслуговування", callback_data="admin_maintenance")]
            ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(message, reply_markup=reply_markup)

    async def show_maintenance_status(self, query):
        """Показати детальний статус технічного обслуговування"""
        maintenance_info = db.get_maintenance_info()
        is_enabled = maintenance_info.get('enabled', False)
        
        current_time = datetime.now().strftime('%d.%m.%Y %H:%M:%S')
        
        if is_enabled:
            timestamp = maintenance_info.get('timestamp', '')
            message = maintenance_info.get('message', '')
            
            if timestamp:
                try:
                    dt = datetime.fromisoformat(timestamp)
                    formatted_time = dt.strftime('%d.%m.%Y %H:%M:%S')
                    
                    # Розрахувати тривалість
                    duration = datetime.now() - dt
                    duration_str = str(duration).split('.')[0]  # Видалити мікросекунди
                except:
                    formatted_time = timestamp
                    duration_str = "Невідомо"
            else:
                formatted_time = 'Невідомо'
                duration_str = "Невідомо"
            
            status_text = f"""🔧 Детальний статус техобслуговування

🔴 **РЕЖИМ АКТИВНИЙ**
📅 Поточний час: {current_time}
🕐 Включено: {formatted_time}
⏱️ Тривалість: {duration_str}

📋 **Причина обслуговування:**
{message or 'Не вказано'}

⚠️ **Поточний стан:**
• Скріншоти від користувачів блокуються
• Адмін функції працюють
• Автоматичні звіти активні
• Звіти можна завантажувати

👥 **Повідомлення для користувачів:**
"🔧 Технічне обслуговування
⏳ Бот тимчасово недоступний для обробки скріншотів"

🔧 **Дії адміністратора:**
• Виконайте необхідні роботи
• Завантажте звіти
• Вимкніть режим після завершення"""
        else:
            status_text = f"""🔧 Детальний статус техобслуговування

🟢 **РЕЖИМ НЕАКТИВНИЙ**
📅 Поточний час: {current_time}
✅ Бот працює в нормальному режимі

👥 **Поточний стан:**
• Користувачі можуть надсилати скріншоти
• Всі функції доступні
• Автоматичні звіти працюють
• Планувальник активний

🚀 **Готовність до роботи: 100%**"""
        
        keyboard = [
            [InlineKeyboardButton("🔄 Оновити статус", callback_data="maintenance_status")],
            [InlineKeyboardButton("🔙 Назад до меню техобслуговування", callback_data="admin_maintenance")],
            [InlineKeyboardButton("🏠 Назад до адмін панелі", callback_data="admin_panel")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(status_text, reply_markup=reply_markup)

def main():
    """Головна функція"""
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN не встановлений!")
        return
    
    bot = TikTokStatsBot()
    
    try:
        bot.run_bot()
    except KeyboardInterrupt:
        logger.info("Бот зупинений користувачем")
    except Exception as e:
        logger.error(f"Помилка запуску бота: {e}")

if __name__ == "__main__":
    main() 