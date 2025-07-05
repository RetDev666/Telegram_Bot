# ✅ Railway Deploy Checklist

## Перевірка готовності проекту до деплою на Railway

### 📋 Основні файли

- [ ] `railway.toml` - конфігурація Railway
- [ ] `nixpacks.toml` - системні залежності
- [ ] `railway-start.py` - стартовий скрипт
- [ ] `requirements.txt` - Python залежності
- [ ] `env.railway` - приклад змінних для Railway

### 🔧 Налаштування

- [ ] `config.py` оновлено для підтримки Railway
- [ ] `IS_RAILWAY` змінна додана
- [ ] `TESSERACT_PATH` налаштовано для Railway
- [ ] Перевірено імпорти в `railway-start.py`

### 📚 Документація

- [ ] `RAILWAY_DEPLOY.md` - детальна інструкція
- [ ] `RAILWAY_VS_HEROKU.md` - порівняння платформ
- [ ] `README.md` оновлено з Railway інформацією
- [ ] `railway-checklist.md` - цей чек-лист

### 🧪 Тестування

- [ ] `test-railway.py` - тест конфігурації
- [ ] Перевірено всі залежності
- [ ] Перевірено змінні середовища
- [ ] Локальне тестування пройдено

### 🚀 Готовність до деплою

- [ ] GitHub репозиторій оновлено
- [ ] Всі файли закоммічено
- [ ] Railway акаунт створено
- [ ] Змінні середовища підготовлено

### 📝 Змінні середовища для Railway

```env
BOT_TOKEN=your_bot_token_here
ADMIN_CHAT_ID=your_admin_chat_id
GROUP_CHAT_ID=your_group_chat_id
ADMIN_USER_IDS=admin_id1,admin_id2
RAILWAY_ENVIRONMENT=production
TESSERACT_PATH=/usr/bin/tesseract
PORT=8000
```

### 🎯 Кроки деплою

1. **Підготовка:**
   - [ ] Всі файли в репозиторії
   - [ ] Тест пройшов успішно
   - [ ] Змінні підготовлено

2. **Railway налаштування:**
   - [ ] Акаунт створено
   - [ ] Проект створено
   - [ ] GitHub підключено

3. **Деплой:**
   - [ ] Змінні встановлено
   - [ ] PostgreSQL додано
   - [ ] Деплой запущено

4. **Перевірка:**
   - [ ] Бот запустився
   - [ ] Health check працює
   - [ ] Telegram бот відповідає

### 🔍 Команди для перевірки

```bash
# Тест конфігурації
python test-railway.py

# Перевірка залежностей
pip install -r requirements.txt

# Локальний тест
python railway-start.py
```

### 📊 Після деплою

- [ ] URL працює: `https://your-app.railway.app`
- [ ] Health check: `https://your-app.railway.app/health`
- [ ] Status: `https://your-app.railway.app/status`
- [ ] Telegram бот відповідає на команди
- [ ] OCR працює коректно
- [ ] База даних підключена

### 🎉 Готово!

Коли всі пункти відмічено ✅, ваш проект готовий до Railway деплою!

---

💡 **Зберігайте цей чек-лист для майбутніх деплоїв** 