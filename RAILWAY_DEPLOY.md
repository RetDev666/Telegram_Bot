# Деплой TikTok Live Analytics Bot на Railway

## Огляд

Цей посібник допоможе вам розгорнути TikTok Live Analytics Bot на платформі Railway. Railway - це сучасна платформа для хостингу застосунків, яка пропонує простий деплой та автоматичне масштабування.

## Передумови

1. **Telegram бот**: Створіть бота через [@BotFather](https://t.me/BotFather) та отримайте токен
2. **Railway акаунт**: Зареєструйтеся на [Railway](https://railway.app)
3. **GitHub репозиторій**: Завантажте код проекту до GitHub

## Крок 1: Підготовка проекту

### 1.1 Клонування репозиторію

```bash
git clone https://github.com/your-username/tiktok-live-analytics-bot.git
cd tiktok-live-analytics-bot
```

### 1.2 Налаштування змінних середовища

Створіть файл `.env` на основі `env.example`:

```bash
cp env.example .env
```

Відредагуйте `.env` файл з вашими даними:

```env
# Основні налаштування бота
BOT_TOKEN=your_bot_token_here
ADMIN_CHAT_ID=your_admin_chat_id
GROUP_CHAT_ID=your_group_chat_id
ADMIN_USER_IDS=admin_id1,admin_id2

# Railway налаштування
RAILWAY_ENVIRONMENT=production
TESSERACT_PATH=/usr/bin/tesseract

# Порт для веб-сервера
PORT=8000
```

## Крок 2: Деплой на Railway

### 2.1 Через GitHub (Рекомендовано)

1. **Підключіться до Railway:**
   - Перейдіть на [Railway](https://railway.app)
   - Увійдіть через GitHub акаунт

2. **Створіть новий проект:**
   - Натисніть "New Project"
   - Виберіть "Deploy from GitHub repo"
   - Оберіть ваш репозиторій

3. **Налаштуйте змінні середовища:**
   - Перейдіть у розділ "Variables"
   - Додайте всі необхідні змінні:

   ```
   BOT_TOKEN=your_bot_token_here
   ADMIN_CHAT_ID=your_admin_chat_id
   GROUP_CHAT_ID=your_group_chat_id
   ADMIN_USER_IDS=admin_id1,admin_id2
   RAILWAY_ENVIRONMENT=production
   TESSERACT_PATH=/usr/bin/tesseract
   PORT=8000
   ```

4. **Додайте PostgreSQL базу даних:**
   - У панелі проекту натисніть "Add service"
   - Виберіть "PostgreSQL"
   - Railway автоматично створить змінну `DATABASE_URL`

### 2.2 Через Railway CLI

1. **Встановіть Railway CLI:**
   ```bash
   npm install -g @railway/cli
   ```

2. **Увійдіть в акаунт:**
   ```bash
   railway login
   ```

3. **Ініціалізуйте проект:**
   ```bash
   railway init
   ```

4. **Додайте змінні середовища:**
   ```bash
   railway variables set BOT_TOKEN=your_bot_token_here
   railway variables set ADMIN_CHAT_ID=your_admin_chat_id
   railway variables set ADMIN_USER_IDS=admin_id1,admin_id2
   railway variables set RAILWAY_ENVIRONMENT=production
   railway variables set TESSERACT_PATH=/usr/bin/tesseract
   railway variables set PORT=8000
   ```

5. **Додайте PostgreSQL:**
   ```bash
   railway add postgresql
   ```

6. **Розгорніть проект:**
   ```bash
   railway up
   ```

## Крок 3: Налаштування домену (Опційно)

1. **Отримайте URL проекту:**
   - У панелі Railway перейдіть в "Settings"
   - Скопіюйте згенерований URL

2. **Налаштуйте webhook для Telegram:**
   - Використовуйте отриманий URL для налаштування webhook
   - Бот автоматично налаштує webhook при запуску

## Крок 4: Моніторинг та логи

### 4.1 Перегляд логів

```bash
railway logs
```

### 4.2 Перегляд статусу

- Відкрийте `https://your-app.railway.app/health`
- Перевірте статус: `https://your-app.railway.app/status`

## Крок 5: Автоматичне оновлення

Railway автоматично оновлює ваш додаток при кожному push до головної гілки GitHub.

### Налаштування автоматичного деплою:

1. Перейдіть у "Settings" > "Service"
2. Увімкніть "Auto Deploy" для main гілки
3. Налаштуйте "Deploy Triggers" за потребою

## Конфігураційні файли

### railway.toml
Основний конфігураційний файл для Railway:

```toml
[build]
builder = "nixpacks"
buildCommand = "pip install -r requirements.txt"

[deploy]
restartPolicyType = "ON_FAILURE"
restartPolicyMaxRetries = 10
startCommand = "python railway-start.py"
healthcheckPath = "/health"
healthcheckTimeout = 300
```

### nixpacks.toml
Конфігурація системних залежностей:

```toml
[phases.setup]
nixPkgs = [
  "python311",
  "pip",
  "tesseract",
  "opencv4",
  "libGL",
  "libglib"
]

[start]
cmd = "python railway-start.py"
```

## Оцінка ресурсів

### Безкоштовний план:
- 512MB RAM
- 1GB діскового простору
- 100GB трафіку
- $5 кредитів на місяць

### Платний план:
- Необмежені ресурси
- Оплата за використання
- Підтримка custom доменів

## Відлагодження

### Часті проблеми:

1. **Бот не запускається:**
   - Перевірте `BOT_TOKEN` в змінних середовища
   - Перегляньте логи: `railway logs`

2. **OCR не працює:**
   - Перевірте наявність Tesseract в nixpacks.toml
   - Перевірте `TESSERACT_PATH` змінну

3. **База даних не підключається:**
   - Перевірте наявність PostgreSQL сервісу
   - Перегляньте змінну `DATABASE_URL`

### Перегляд логів:
```bash
railway logs --follow
```

### Перевірка статусу:
```bash
railway status
```

## Додаткові налаштування

### Масштабування:
- Railway автоматично масштабує ваш додаток
- Можна налаштувати ліміти в панелі управління

### Резервне копіювання:
- PostgreSQL автоматично створює резервні копії
- Можна налаштувати додаткові резервні копії

### Моніторинг:
- Встановіть алерти в панелі Railway
- Інтегруйте з зовнішніми системами моніторингу

## Підтримка

Якщо виникли проблеми:
1. Перевірте [документацію Railway](https://docs.railway.app)
2. Перегляньте логи додатку
3. Зверніться до спільноти Railway або GitHub Issues

## Висновок

Тепер ваш TikTok Live Analytics Bot успішно розгорнуто на Railway! Бот автоматично буде оновлюватися при кожному push до GitHub та масштабуватися відповідно до навантаження.

Основні переваги Railway:
- ✅ Простий деплой
- ✅ Автоматичне масштабування  
- ✅ Вбудована PostgreSQL
- ✅ Безкоштовний план для початку
- ✅ Відмінна документація 