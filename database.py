import sqlite3
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import logging
import os

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, db_path: str = 'tiktok_stats.db'):
        self.db_path = db_path
        self.init_database()
    
    def get_connection(self):
        """Отримати з'єднання з базою даних"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def init_database(self):
        """Ініціалізувати базу даних та створити таблиці"""
        conn = self.get_connection()
        try:
            # Таблиця користувачів
            conn.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    telegram_id INTEGER PRIMARY KEY,
                    tiktok_nickname TEXT NOT NULL,
                    registration_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                    last_activity DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Таблиця статистики
            conn.execute('''
                CREATE TABLE IF NOT EXISTS statistics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    duration_minutes INTEGER NOT NULL,
                    viewers_count INTEGER NOT NULL,
                    gifters_count INTEGER NOT NULL,
                    diamonds_count INTEGER NOT NULL,
                    screenshot_path TEXT,
                    FOREIGN KEY (user_id) REFERENCES users (telegram_id)
                )
            ''')
            
            # Індекси для оптимізації
            conn.execute('CREATE INDEX IF NOT EXISTS idx_statistics_user_id ON statistics(user_id)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_statistics_timestamp ON statistics(timestamp)')
            
            # Таблиця вихідних днів
            conn.execute('''
                CREATE TABLE IF NOT EXISTS holidays (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    holiday_date DATE NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (telegram_id),
                    UNIQUE(user_id, holiday_date)
                )
            ''')
            
            # Індекс для вихідних днів
            conn.execute('CREATE INDEX IF NOT EXISTS idx_holidays_user_date ON holidays(user_id, holiday_date)')
            
            conn.commit()
            logger.info("База даних ініціалізована успішно")
        except Exception as e:
            logger.error(f"Помилка ініціалізації бази даних: {e}")
        finally:
            conn.close()
    
    def register_user(self, telegram_id: int, tiktok_nickname: str) -> bool:
        """Зареєструвати нового користувача або оновити існуючого"""
        conn = self.get_connection()
        try:
            conn.execute('''
                INSERT OR REPLACE INTO users (telegram_id, tiktok_nickname, registration_date, last_activity)
                VALUES (?, ?, COALESCE((SELECT registration_date FROM users WHERE telegram_id = ?), CURRENT_TIMESTAMP), CURRENT_TIMESTAMP)
            ''', (telegram_id, tiktok_nickname, telegram_id))
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Помилка реєстрації користувача {telegram_id}: {e}")
            return False
        finally:
            conn.close()
    
    def get_user(self, telegram_id: int) -> Optional[Dict]:
        """Отримати інформацію про користувача"""
        conn = self.get_connection()
        try:
            cursor = conn.execute('SELECT * FROM users WHERE telegram_id = ?', (telegram_id,))
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None
        except Exception as e:
            logger.error(f"Помилка отримання користувача {telegram_id}: {e}")
            return None
        finally:
            conn.close()
    
    def update_user_activity(self, telegram_id: int):
        """Оновити час останньої активності користувача"""
        conn = self.get_connection()
        try:
            conn.execute('UPDATE users SET last_activity = CURRENT_TIMESTAMP WHERE telegram_id = ?', (telegram_id,))
            conn.commit()
        except Exception as e:
            logger.error(f"Помилка оновлення активності користувача {telegram_id}: {e}")
        finally:
            conn.close()
    
    def add_statistics(self, user_id: int, duration_minutes: int, viewers_count: int, 
                      gifters_count: int, diamonds_count: int, screenshot_path: Optional[str] = None) -> bool:
        """Додати запис статистики"""
        conn = self.get_connection()
        try:
            conn.execute('''
                INSERT INTO statistics (user_id, duration_minutes, viewers_count, gifters_count, diamonds_count, screenshot_path)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (user_id, duration_minutes, viewers_count, gifters_count, diamonds_count, screenshot_path))
            conn.commit()
            self.update_user_activity(user_id)
            return True
        except Exception as e:
            logger.error(f"Помилка додавання статистики для користувача {user_id}: {e}")
            return False
        finally:
            conn.close()
    
    def get_user_statistics(self, telegram_id: int, days: int = 30) -> List[Dict]:
        """Отримати статистику користувача за останні N днів"""
        conn = self.get_connection()
        try:
            since_date = datetime.now() - timedelta(days=days)
            cursor = conn.execute('''
                SELECT * FROM statistics 
                WHERE user_id = ? AND timestamp >= ?
                ORDER BY timestamp DESC
            ''', (telegram_id, since_date))
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Помилка отримання статистики користувача {telegram_id}: {e}")
            return []
        finally:
            conn.close()
    
    def get_user_summary(self, telegram_id: int, days: int = 30) -> Dict:
        """Отримати зведену статистику користувача"""
        conn = self.get_connection()
        try:
            since_date = datetime.now() - timedelta(days=days)
            cursor = conn.execute('''
                SELECT 
                    COUNT(*) as sessions_count,
                    SUM(duration_minutes) as total_duration,
                    SUM(viewers_count) as total_viewers,
                    SUM(gifters_count) as total_gifters,
                    SUM(diamonds_count) as total_diamonds,
                    AVG(duration_minutes) as avg_duration,
                    AVG(viewers_count) as avg_viewers,
                    AVG(diamonds_count) as avg_diamonds,
                    MAX(viewers_count) as max_viewers,
                    MAX(diamonds_count) as max_diamonds
                FROM statistics 
                WHERE user_id = ? AND timestamp >= ?
            ''', (telegram_id, since_date))
            row = cursor.fetchone()
            return dict(row) if row else {}
        except Exception as e:
            logger.error(f"Помилка отримання зведеної статистики користувача {telegram_id}: {e}")
            return {}
        finally:
            conn.close()
    
    def get_daily_statistics(self, date: Optional[datetime] = None) -> Dict:
        """Отримати статистику за конкретний день"""
        if date is None:
            date = datetime.now()
        
        start_date = date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = start_date + timedelta(days=1)
        
        conn = self.get_connection()
        try:
            # Загальна статистика за день
            cursor = conn.execute('''
                SELECT 
                    COUNT(DISTINCT user_id) as active_users,
                    COUNT(*) as total_sessions,
                    SUM(duration_minutes) as total_duration,
                    SUM(viewers_count) as total_viewers,
                    SUM(diamonds_count) as total_diamonds
                FROM statistics 
                WHERE timestamp >= ? AND timestamp < ?
            ''', (start_date, end_date))
            daily_stats = dict(cursor.fetchone())
            
            # ТОП 3 за алмазами
            cursor = conn.execute('''
                SELECT u.tiktok_nickname, SUM(s.diamonds_count) as total_diamonds
                FROM statistics s
                JOIN users u ON s.user_id = u.telegram_id
                WHERE s.timestamp >= ? AND s.timestamp < ?
                GROUP BY s.user_id, u.tiktok_nickname
                ORDER BY total_diamonds DESC
                LIMIT 3
            ''', (start_date, end_date))
            top_diamonds = [dict(row) for row in cursor.fetchall()]
            
            daily_stats['top_diamonds'] = top_diamonds
            return daily_stats
        except Exception as e:
            logger.error(f"Помилка отримання щоденної статистики: {e}")
            return {}
        finally:
            conn.close()
    
    def get_all_users(self) -> List[Dict]:
        """Отримати список всіх користувачів"""
        conn = self.get_connection()
        try:
            cursor = conn.execute('''
                SELECT u.*, 
                       COUNT(s.id) as total_sessions,
                       SUM(s.diamonds_count) as total_diamonds
                FROM users u
                LEFT JOIN statistics s ON u.telegram_id = s.user_id
                GROUP BY u.telegram_id
                ORDER BY u.last_activity DESC
            ''')
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Помилка отримання списку користувачів: {e}")
            return []
        finally:
            conn.close()
    
    def get_total_stats(self) -> Dict:
        """Отримати загальну статистику по всіх користувачах"""
        conn = self.get_connection()
        try:
            cursor = conn.execute('''
                SELECT 
                    COUNT(DISTINCT user_id) as total_users,
                    COUNT(*) as total_sessions,
                    SUM(duration_minutes) as total_duration,
                    SUM(viewers_count) as total_viewers,
                    SUM(diamonds_count) as total_diamonds
                FROM statistics
            ''')
            return dict(cursor.fetchone())
        except Exception as e:
            logger.error(f"Помилка отримання загальної статистики: {e}")
            return {}
        finally:
            conn.close()

    def get_total_stats_period(self, days: int) -> Dict:
        """Отримати загальну статистику за останні N днів"""
        conn = self.get_connection()
        try:
            since_date = datetime.now() - timedelta(days=days)
            cursor = conn.execute('''
                SELECT 
                    COUNT(DISTINCT user_id) as total_users,
                    COUNT(*) as total_sessions,
                    SUM(duration_minutes) as total_duration,
                    SUM(viewers_count) as total_viewers,
                    SUM(diamonds_count) as total_diamonds,
                    AVG(duration_minutes) as avg_duration,
                    AVG(viewers_count) as avg_viewers,
                    AVG(diamonds_count) as avg_diamonds
                FROM statistics
                WHERE timestamp >= ?
            ''', (since_date,))
            return dict(cursor.fetchone())
        except Exception as e:
            logger.error(f"Помилка отримання статистики за період: {e}")
            return {}
        finally:
            conn.close()

    def add_holiday(self, user_id: int, holiday_date: str) -> bool:
        """Додати вихідний день для користувача"""
        conn = self.get_connection()
        try:
            conn.execute('''
                INSERT OR REPLACE INTO holidays (user_id, holiday_date)
                VALUES (?, ?)
            ''', (user_id, holiday_date))
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Помилка додавання вихідного дня для користувача {user_id}: {e}")
            return False
        finally:
            conn.close()
    
    def remove_holiday(self, user_id: int, holiday_date: str) -> bool:
        """Видалити вихідний день для користувача"""
        conn = self.get_connection()
        try:
            cursor = conn.execute('DELETE FROM holidays WHERE user_id = ? AND holiday_date = ?', 
                                (user_id, holiday_date))
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Помилка видалення вихідного дня для користувача {user_id}: {e}")
            return False
        finally:
            conn.close()
    
    def get_user_holidays(self, user_id: int) -> List[Dict]:
        """Отримати список вихідних днів користувача"""
        conn = self.get_connection()
        try:
            cursor = conn.execute('''
                SELECT * FROM holidays 
                WHERE user_id = ? 
                ORDER BY holiday_date DESC
            ''', (user_id,))
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Помилка отримання вихідних днів користувача {user_id}: {e}")
            return []
        finally:
            conn.close()
    
    def is_holiday(self, user_id: int, date: str) -> bool:
        """Перевірити чи є день вихідним для користувача"""
        conn = self.get_connection()
        try:
            cursor = conn.execute('SELECT 1 FROM holidays WHERE user_id = ? AND holiday_date = ?', 
                                (user_id, date))
            return cursor.fetchone() is not None
        except Exception as e:
            logger.error(f"Помилка перевірки вихідного дня: {e}")
            return False
        finally:
            conn.close()
    
    def get_admin_table_report(self, days: int = 30) -> List[Dict]:
        """Отримати звіт у табличному форматі для адміна"""
        conn = self.get_connection()
        try:
            since_date = datetime.now() - timedelta(days=days)
            cursor = conn.execute('''
                SELECT 
                    u.tiktok_nickname,
                    u.telegram_id,
                    COUNT(s.id) as total_sessions,
                    SUM(s.duration_minutes) as total_duration,
                    SUM(s.viewers_count) as total_viewers,
                    SUM(s.gifters_count) as total_gifters,
                    SUM(s.diamonds_count) as total_diamonds,
                    AVG(s.duration_minutes) as avg_duration,
                    AVG(s.viewers_count) as avg_viewers,
                    AVG(s.diamonds_count) as avg_diamonds,
                    MAX(s.diamonds_count) as max_diamonds,
                    MAX(s.timestamp) as last_stream
                FROM users u
                LEFT JOIN statistics s ON u.telegram_id = s.user_id 
                    AND s.timestamp >= ?
                GROUP BY u.telegram_id, u.tiktok_nickname
                ORDER BY total_diamonds DESC NULLS LAST
            ''', (since_date,))
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Помилка отримання табличного звіту: {e}")
            return []
        finally:
            conn.close()
    
    def get_today_sessions_count(self, user_id: int) -> int:
        """Отримати кількість сесій користувача за сьогодні"""
        conn = self.get_connection()
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            cursor = conn.execute('''
                SELECT COUNT(*) as count
                FROM statistics 
                WHERE user_id = ? AND DATE(timestamp) = ?
            ''', (user_id, today))
            result = cursor.fetchone()
            return result['count'] if result else 0
        except Exception as e:
            logger.error(f"Помилка отримання кількості сесій: {e}")
            return 0
        finally:
            conn.close()
    
    def get_today_total_stats(self, user_id: int) -> Dict:
        """Отримати загальну статистику користувача за сьогодні"""
        conn = self.get_connection()
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            cursor = conn.execute('''
                SELECT 
                    COUNT(*) as sessions_count,
                    SUM(duration_minutes) as total_duration,
                    SUM(viewers_count) as total_viewers,
                    SUM(gifters_count) as total_gifters,
                    SUM(diamonds_count) as total_diamonds
                FROM statistics 
                WHERE user_id = ? AND DATE(timestamp) = ?
            ''', (user_id, today))
            result = cursor.fetchone()
            return dict(result) if result else {}
        except Exception as e:
            logger.error(f"Помилка отримання щоденної статистики: {e}")
            return {}
        finally:
            conn.close()

    def get_detailed_user_report(self, user_id: int, days: int = 30) -> List[Dict]:
        """Отримати детальний звіт користувача по днях з вихідними"""
        conn = self.get_connection()
        try:
            since_date = datetime.now() - timedelta(days=days)
            
            # Спочатку отримуємо всі дні в діапазоні
            cursor = conn.execute('''
                WITH RECURSIVE date_series(date) AS (
                    SELECT DATE(?) as date
                    UNION ALL
                    SELECT DATE(date, '+1 day')
                    FROM date_series
                    WHERE date < DATE('now')
                )
                SELECT 
                    ds.date,
                    COALESCE(SUM(s.duration_minutes), 0) as total_duration,
                    COALESCE(SUM(s.viewers_count), 0) as total_viewers,
                    COALESCE(SUM(s.gifters_count), 0) as total_gifters,
                    COALESCE(SUM(s.diamonds_count), 0) as total_diamonds,
                    COUNT(s.id) as sessions_count,
                    CASE WHEN h.holiday_date IS NOT NULL THEN 1 ELSE 0 END as is_holiday
                FROM date_series ds
                LEFT JOIN statistics s ON DATE(s.timestamp) = ds.date AND s.user_id = ?
                LEFT JOIN holidays h ON h.holiday_date = ds.date AND h.user_id = ?
                GROUP BY ds.date
                ORDER BY ds.date DESC
            ''', (since_date.strftime('%Y-%m-%d'), user_id, user_id))
            
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Помилка отримання детального звіту користувача {user_id}: {e}")
            return []
        finally:
            conn.close()
    
    def get_all_users_detailed_report(self, days: int = 30) -> Dict[str, List[Dict]]:
        """Отримати детальні звіти всіх користувачів"""
        users = self.get_all_users()
        reports = {}
        
        for user in users:
            user_id = user['telegram_id']
            nickname = user['tiktok_nickname']
            reports[nickname] = self.get_detailed_user_report(user_id, days)
        
        return reports
    
    def get_summary_report_with_holidays(self, days: int = 30) -> List[Dict]:
        """Отримати зведений звіт з урахуванням вихідних днів"""
        conn = self.get_connection()
        try:
            since_date = datetime.now() - timedelta(days=days)
            cursor = conn.execute('''
                SELECT 
                    u.tiktok_nickname,
                    u.telegram_id,
                    COUNT(DISTINCT DATE(s.timestamp)) as active_days,
                    COUNT(DISTINCT h.holiday_date) as holiday_days,
                    COUNT(s.id) as total_sessions,
                    SUM(s.duration_minutes) as total_duration,
                    SUM(s.viewers_count) as total_viewers,
                    SUM(s.gifters_count) as total_gifters,
                    SUM(s.diamonds_count) as total_diamonds,
                    AVG(s.duration_minutes) as avg_duration,
                    AVG(s.viewers_count) as avg_viewers,
                    AVG(s.diamonds_count) as avg_diamonds,
                    MAX(s.diamonds_count) as max_diamonds,
                    MAX(s.timestamp) as last_stream
                FROM users u
                LEFT JOIN statistics s ON u.telegram_id = s.user_id 
                    AND s.timestamp >= ?
                LEFT JOIN holidays h ON u.telegram_id = h.user_id 
                    AND h.holiday_date >= DATE(?)
                GROUP BY u.telegram_id, u.tiktok_nickname
                ORDER BY total_diamonds DESC NULLS LAST
            ''', (since_date, since_date.strftime('%Y-%m-%d')))
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Помилка отримання зведеного звіту: {e}")
            return []
        finally:
            conn.close()
    
    def get_daily_stats(self, date) -> Dict:
        """Отримати загальну статистику за конкретний день"""
        conn = self.get_connection()
        try:
            if isinstance(date, str):
                date_str = date
            else:
                date_str = date.strftime('%Y-%m-%d')
            
            cursor = conn.execute('''
                SELECT 
                    COUNT(*) as total_sessions,
                    SUM(duration_minutes) as total_duration,
                    SUM(viewers_count) as total_viewers,
                    SUM(gifters_count) as total_gifters,
                    SUM(diamonds_count) as total_diamonds
                FROM statistics 
                WHERE DATE(timestamp) = ?
            ''', (date_str,))
            
            result = cursor.fetchone()
            return dict(result) if result else {}
        except Exception as e:
            logger.error(f"Помилка отримання щоденної статистики: {e}")
            return {}
        finally:
            conn.close()
    
    def get_active_users_for_date(self, date) -> List[Dict]:
        """Отримати список активних користувачів за конкретний день"""
        conn = self.get_connection()
        try:
            if isinstance(date, str):
                date_str = date
            else:
                date_str = date.strftime('%Y-%m-%d')
            
            cursor = conn.execute('''
                SELECT 
                    s.user_id,
                    COUNT(*) as sessions,
                    SUM(s.duration_minutes) as total_duration,
                    SUM(s.diamonds_count) as total_diamonds
                FROM statistics s
                WHERE DATE(s.timestamp) = ?
                GROUP BY s.user_id
                ORDER BY total_diamonds DESC
            ''', (date_str,))
            
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Помилка отримання активних користувачів: {e}")
            return []
        finally:
            conn.close()
    
    def get_total_users_count(self) -> int:
        """Отримати загальну кількість користувачів"""
        conn = self.get_connection()
        try:
            cursor = conn.execute('SELECT COUNT(*) as count FROM users')
            result = cursor.fetchone()
            return result['count'] if result else 0
        except Exception as e:
            logger.error(f"Помилка отримання кількості користувачів: {e}")
            return 0
        finally:
            conn.close()
    
    def set_maintenance_mode(self, enabled: bool, message: str = "") -> bool:
        """Встановити режим технічного обслуговування"""
        try:
            from config import MAINTENANCE_MODE_FILE
            
            if enabled:
                # Включити режим техобслуговування
                with open(MAINTENANCE_MODE_FILE, 'w', encoding='utf-8') as f:
                    f.write(f"{datetime.now().isoformat()}\n{message}")
                logger.info("Режим технічного обслуговування ВКЛЮЧЕНО")
            else:
                # Вимкнути режим техобслуговування
                if os.path.exists(MAINTENANCE_MODE_FILE):
                    os.remove(MAINTENANCE_MODE_FILE)
                logger.info("Режим технічного обслуговування ВИМКНЕНО")
            
            return True
        except Exception as e:
            logger.error(f"Помилка встановлення режиму техобслуговування: {e}")
            return False
    
    def is_maintenance_mode(self) -> bool:
        """Перевірити чи активний режим технічного обслуговування"""
        try:
            from config import MAINTENANCE_MODE_FILE
            return os.path.exists(MAINTENANCE_MODE_FILE)
        except Exception as e:
            logger.error(f"Помилка перевірки режиму техобслуговування: {e}")
            return False
    
    def get_maintenance_info(self) -> Dict:
        """Отримати інформацію про режим техобслуговування"""
        try:
            from config import MAINTENANCE_MODE_FILE
            
            if not os.path.exists(MAINTENANCE_MODE_FILE):
                return {"enabled": False}
            
            with open(MAINTENANCE_MODE_FILE, 'r', encoding='utf-8') as f:
                lines = f.read().strip().split('\n')
                timestamp = lines[0] if lines else ""
                message = lines[1] if len(lines) > 1 else ""
                
                return {
                    "enabled": True,
                    "timestamp": timestamp,
                    "message": message
                }
        except Exception as e:
            logger.error(f"Помилка отримання інформації про техобслуговування: {e}")
            return {"enabled": False}

# Створюємо глобальний екземпляр бази даних
db = Database() 