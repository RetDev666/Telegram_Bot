# 🌊 Розгортання на DigitalOcean

## 🚀 App Platform (Рекомендовано)

### 1. Створення додатку
1. Увійдіть на [DigitalOcean](https://cloud.digitalocean.com/)
2. Apps → Create App → GitHub
3. Оберіть репозиторій `RetDev666/Telegram_Bot`
4. Гілка: `main`, Autodeploy: увімкнути

### 2. Налаштування
- **Type:** Web Service
- **Run Command:** `python run.py`
- **Port:** 8000
- **Plan:** Basic ($5/місяць)

### 3. Змінні середовища
```
BOT_TOKEN=your_bot_token
ADMIN_USER_IDS=your_telegram_id
TESSERACT_PATH=/usr/bin/tesseract
PORT=8000
```

### 4. Деплой
Натисніть "Create App" - DigitalOcean автоматично:
- Встановить Tesseract OCR
- Встановить Python залежності  
- Запустить бота

## 🐳 Droplet з Docker

```bash
# Створіть Droplet Ubuntu 22.04
# Встановіть Docker
sudo apt update && sudo apt install docker.io -y

# Клонуйте проект
git clone https://github.com/RetDev666/Telegram_Bot.git
cd Telegram_Bot

# Налаштуйте .env
cp env.example .env
nano .env  # Додайте токени

# Збудуйте та запустіть
docker build -t tiktok-bot .
docker run -d -p 8000:8000 --env-file .env tiktok-bot
```

## ✅ Переваги DigitalOcean для OCR

- Відмінна підтримка Tesseract OCR
- Простий деплой з GitHub
- Конкурентні ціни ($5-12/місяць)
- Автоскейлінг при потребі

**DigitalOcean ідеально підходить для OCR проектів! 🚀** 