import os
from dotenv import load_dotenv

# Завантажуємо змінні середовища
load_dotenv()
load_dotenv('appsettings.env')  # Також спробувати appsettings.env

# Основні налаштування бота
BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_CHAT_ID = os.getenv('ADMIN_CHAT_ID')
GROUP_CHAT_ID = os.getenv('GROUP_CHAT_ID')
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///tiktok_stats.db')

# Автоматичне визначення середовища
IS_HEROKU = os.getenv('DYNO') is not None
PORT = int(os.getenv('PORT', 8000))

# Tesseract шлях (різний для локального та Heroku)
if IS_HEROKU:
    TESSERACT_PATH = os.getenv('TESSERACT_PATH', '/app/.apt/usr/bin/tesseract')
else:
    TESSERACT_PATH = os.getenv('TESSERACT_PATH', '/usr/bin/tesseract')

# Список ID адміністраторів
ADMIN_USER_IDS = list(map(int, os.getenv('ADMIN_USER_IDS', '').split(',') if os.getenv('ADMIN_USER_IDS') else []))

# OCR налаштування
TESSERACT_CONFIG = r'--oem 3 --psm 6 -l ukr+eng'

# Повідомлення бота
MESSAGES = {
    'welcome': '👋 Привіт! Введіть ваш TikTok нікнейм для початку:',
    'photo_only': '📸 Будь ласка, надішліть скріншот TikTok-статистики ефіру.',
    'processing': '⏳ Обробляю скріншот...',
    'success': '✅ Статистика збережена!\n📊 Розпізнано:\n🎥 Тривалість: {duration} хв\n👥 Глядачі: {viewers}\n🎁 Дарувальники: {gifters}\n💎 Алмази: {diamonds}',
    'error': '❌ Помилка обробки. Спробуйте ще раз.',
    'nickname_saved': '✅ TikTok нікнейм збережено: {nickname}',
    'nickname_prompt': '👤 Введіть ваш TikTok нікнейм:',
    'admin_only': '❌ Ця команда доступна тільки адміністраторам.',
    'invalid_format': '❌ Не вдалося розпізнати статистику на скріншоті. Переконайтеся, що скріншот містить дані TikTok Live.'
}

# Налаштування для rate limiting
RATE_LIMIT_MESSAGES = 5  # максимум повідомлень
RATE_LIMIT_PERIOD = 60   # за період в секундах

# Налаштування файлів
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.bmp', '.tiff']

# Час для щоденних звітів
DAILY_REPORT_HOUR = 23
DAILY_REPORT_MINUTE = 59

# Автоматичні звіти адміністратору
ADMIN_DAILY_REPORT_HOUR = 21  # 21:00 вечора
ADMIN_DAILY_REPORT_MINUTE = 0

# Робочі години для оновлення статистики (24/7)
STATS_WORK_START_HOUR = 0  # 00:00 (повна доба)
STATS_WORK_END_HOUR = 24   # 23:59 (повна доба)

# Технічне обслуговування
MAINTENANCE_MODE_FILE = 'maintenance_mode.txt'  # Файл для збереження стану техобслуговування 