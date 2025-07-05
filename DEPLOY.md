# 🚀 Деплой TikTok Live Analytics Bot на Heroku

## Підготовка

### 1. Реєстрація облікових записів
- Створіть акаунт на [Heroku](https://heroku.com)
- Створіть Telegram бота у [@BotFather](https://t.me/BotFather)

### 2. Встановлення інструментів
```bash
# Встановіть Heroku CLI
# Windows: https://devcenter.heroku.com/articles/heroku-cli
# macOS: brew tap heroku/brew && brew install heroku
# Linux: snap install --classic heroku

# Увійдіть в акаунт
heroku login
```

## Деплой через GitHub (рекомендовано)

### 1. Завантажте код на GitHub
```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/your-username/tiktok-live-analytics-bot.git
git push -u origin main
```

### 2. Створіть додаток на Heroku
```bash
heroku create your-bot-name
```

### 3. Налаштуйте змінні середовища
```bash
heroku config:set BOT_TOKEN="your_bot_token_here"
heroku config:set ADMIN_CHAT_ID="your_admin_chat_id"
heroku config:set ADMIN_USER_IDS="123456789,987654321"
heroku config:set TESSERACT_PATH="/app/.apt/usr/bin/tesseract"
```

### 4. Підключіть GitHub до Heroku
1. Перейдіть в Dashboard Heroku
2. Виберіть ваш додаток
3. Перейдіть в "Deploy" tab
4. Підключіть GitHub репозиторій
5. Увімкніть автоматичний деплой

## Деплой через Heroku CLI

### 1. Клонуйте репозиторій
```bash
git clone https://github.com/your-username/tiktok-live-analytics-bot.git
cd tiktok-live-analytics-bot
```

### 2. Створіть Heroku додаток
```bash
heroku create your-bot-name
```

### 3. Додайте buildpacks
```bash
heroku buildpacks:add --index 1 https://github.com/heroku/heroku-buildpack-apt
heroku buildpacks:add --index 2 heroku/python
```

### 4. Налаштуйте змінні середовища
```bash
heroku config:set BOT_TOKEN="your_bot_token_here"
heroku config:set ADMIN_CHAT_ID="your_admin_chat_id"
heroku config:set ADMIN_USER_IDS="123456789,987654321"
heroku config:set TESSERACT_PATH="/app/.apt/usr/bin/tesseract"
```

### 5. Додайте PostgreSQL
```bash
heroku addons:create heroku-postgresql:mini
```

### 6. Деплой
```bash
git push heroku main
```

## Швидкий деплой з app.json

Натисніть кнопку для автоматичного деплою:

[![Deploy](https://www.herokucdn.com/deploy/button.svg)](https://heroku.com/deploy?template=https://github.com/your-username/tiktok-live-analytics-bot)

## Отримання токенів

### Telegram Bot Token
1. Напишіть [@BotFather](https://t.me/BotFather)
2. Виконайте `/newbot`
3. Дайте назву боту
4. Скопіюйте токен

### Admin Chat ID
1. Напишіть [@userinfobot](https://t.me/userinfobot)
2. Скопіюйте ваш ID

### Admin User IDs
- Використайте ваш Telegram User ID
- Для кількох адмінів: `123456,789012,345678`

## Налаштування після деплою

### 1. Запустіть worker процес
```bash
heroku ps:scale worker=1
```

### 2. Перевірте логи
```bash
heroku logs --tail
```

### 3. Ініціалізуйте базу даних
База даних ініціалізується автоматично при першому запуску

## Моніторинг

### Перегляд логів
```bash
heroku logs --tail -a your-bot-name
```

### Статус додатку
```bash
heroku ps -a your-bot-name
```

### Конфігурація
```bash
heroku config -a your-bot-name
```

## Оновлення

### Через GitHub
1. Зробіть зміни в коді
2. Запуште на GitHub
3. Heroku автоматично оновить додаток

### Через CLI
```bash
git add .
git commit -m "Update"
git push heroku main
```

## Усунення проблем

### Бот не відповідає
```bash
heroku restart -a your-bot-name
heroku logs --tail -a your-bot-name
```

### Помилки OCR
- Перевірте чи встановлений Tesseract
- Перевірте змінну TESSERACT_PATH

### Помилки бази даних
```bash
heroku pg:reset DATABASE_URL -a your-bot-name --confirm your-bot-name
```

## Ціни

- **Basic dyno**: ~$7/місяць
- **PostgreSQL Mini**: Безкоштовно
- **Загалом**: ~$7/місяць для повнофункціонального бота

## Безпека

- Ніколи не додавайте токени в код
- Використовуйте тільки змінні середовища
- Регулярно оновлюйте залежності

## Підтримка

Якщо виникли проблеми:
1. Перевірте логи: `heroku logs --tail`
2. Перезапустіть: `heroku restart`
3. Зверніться до документації Heroku 