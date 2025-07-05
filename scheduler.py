import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any
from database import db
from config import ADMIN_USER_IDS, ADMIN_DAILY_REPORT_HOUR, ADMIN_DAILY_REPORT_MINUTE
from utils import format_duration, format_number, create_table_report

logger = logging.getLogger(__name__)

class AdminReportScheduler:
    def __init__(self, bot_application):
        self.bot_application = bot_application
        self.is_running = False
        
    async def start(self):
        """Запустити планувальник"""
        if self.is_running:
            return
            
        self.is_running = True
        logger.info("Планувальник автоматичних звітів адміністратору запущено")
        
        # Запустити основний цикл
        await self.run_scheduler()
    
    async def run_scheduler(self):
        """Основний цикл планувальника"""
        while self.is_running:
            try:
                now = datetime.now()
                
                # Перевірити чи настав час для звіту
                if (now.hour == ADMIN_DAILY_REPORT_HOUR and 
                    now.minute == ADMIN_DAILY_REPORT_MINUTE):
                    
                    await self.send_daily_report_to_admins()
                    
                    # Чекати хвилину щоб не відправляти повторно
                    await asyncio.sleep(60)
                else:
                    # Чекати 30 секунд перед наступною перевіркою
                    await asyncio.sleep(30)
                    
            except Exception as e:
                logger.error(f"Помилка в планувальнику: {e}")
                await asyncio.sleep(60)
    
    async def send_daily_report_to_admins(self):
        """Відправити щоденний звіт всім адміністраторам"""
        try:
            # Отримати статистику за сьогодні
            today = datetime.now().date()
            report = await self.generate_daily_report(today)
            
            if not report:
                logger.info("Немає даних для щоденного звіту")
                return
            
            # Відправити звіт кожному адміністратору
            for admin_id in ADMIN_USER_IDS:
                try:
                    await self.bot_application.bot.send_message(
                        chat_id=admin_id,
                        text=report,
                        parse_mode='HTML'
                    )
                    logger.info(f"Щоденний звіт відправлено адміністратору {admin_id}")
                except Exception as e:
                    logger.error(f"Не вдалося відправити звіт адміністратору {admin_id}: {e}")
                    
        except Exception as e:
            logger.error(f"Помилка при відправці щоденного звіту: {e}")
    
    async def generate_daily_report(self, date) -> str:
        """Генерувати щоденний звіт"""
        try:
            # Отримати загальну статистику за день
            daily_stats = db.get_daily_stats(date)
            
            if not daily_stats:
                return ""
            
            # Отримати активних користувачів за день
            active_users = db.get_active_users_for_date(date)
            
            report = f"""🤖 <b>Щоденний звіт TikTok Bot</b> 📊
📅 <b>Дата:</b> {date.strftime('%d.%m.%Y')}
🕘 <b>Час звіту:</b> {datetime.now().strftime('%H:%M')}

📈 <b>Загальна статистика:</b>
👥 Активних користувачів: <b>{len(active_users)}</b>
📸 Скріншотів оброблено: <b>{daily_stats.get('total_sessions', 0)}</b>
⏱️ Загальна тривалість: <b>{format_duration(daily_stats.get('total_duration', 0))}</b>
👁️ Загальні глядачі: <b>{format_number(daily_stats.get('total_viewers', 0))}</b>
🎁 Загальні дарувальники: <b>{format_number(daily_stats.get('total_gifters', 0))}</b>
💎 Загальні алмази: <b>{format_number(daily_stats.get('total_diamonds', 0))}</b>

"""
            
            # Додати топ користувачів
            if active_users:
                report += "<b>🏆 Топ користувачі за день:</b>\n"
                for i, user in enumerate(active_users[:5], 1):
                    user_data = db.get_user(user['user_id'])
                    nickname = user_data['tiktok_nickname'] if user_data else f"ID:{user['user_id']}"
                    report += f"{i}. {nickname} - {user['sessions']} сесій, {format_duration(user['total_duration'])}\n"
                
                report += "\n"
            
            # Додати статистику системи
            total_users = db.get_total_users_count()
            report += f"👤 <b>Всього користувачів:</b> {total_users}\n"
            report += f"🚀 <b>Бот працює в режимі 24/7</b>\n\n"
            
            report += "ℹ️ <i>Автоматичний звіт від TikTok Analytics Bot</i>"
            
            return report
            
        except Exception as e:
            logger.error(f"Помилка генерації щоденного звіту: {e}")
            return ""
    
    def stop(self):
        """Зупинити планувальник"""
        self.is_running = False
        logger.info("Планувальник автоматичних звітів зупинено")

# Глобальний планувальник
scheduler = None

async def start_scheduler(bot_application):
    """Запустити планувальник"""
    global scheduler
    scheduler = AdminReportScheduler(bot_application)
    await scheduler.start()

def stop_scheduler():
    """Зупинити планувальник"""
    global scheduler
    if scheduler:
        scheduler.stop() 