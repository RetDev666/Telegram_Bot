#!/usr/bin/env python3
"""
Тестовий скрипт для перевірки Railway налаштувань
"""

import os
import sys
from config import BOT_TOKEN, IS_RAILWAY, TESSERACT_PATH, DATABASE_URL, PORT

def test_railway_config():
    """Тестує конфігурацію для Railway"""
    print("🧪 Тестування Railway конфігурації...")
    print("=" * 50)
    
    # Перевірка основних змінних
    tests = [
        ("BOT_TOKEN", BOT_TOKEN, "Токен Telegram бота"),
        ("RAILWAY_ENVIRONMENT", os.getenv('RAILWAY_ENVIRONMENT'), "Середовище Railway"),
        ("TESSERACT_PATH", TESSERACT_PATH, "Шлях до Tesseract"),
        ("DATABASE_URL", DATABASE_URL, "URL бази даних"),
        ("PORT", PORT, "Порт веб-сервера"),
    ]
    
    passed = 0
    failed = 0
    
    for var_name, var_value, description in tests:
        if var_value:
            print(f"✅ {var_name}: {description}")
            if var_name == "BOT_TOKEN":
                print(f"   Токен: {var_value[:10]}...")
            elif var_name == "DATABASE_URL":
                print(f"   URL: {var_value[:20]}...")
            else:
                print(f"   Значення: {var_value}")
            passed += 1
        else:
            print(f"❌ {var_name}: {description} - НЕ ВСТАНОВЛЕНО")
            failed += 1
    
    print("\n" + "=" * 50)
    print(f"📊 Результат: {passed} пройдено, {failed} не пройдено")
    
    # Перевірка платформи
    print(f"\n🔧 Платформа: {'Railway' if IS_RAILWAY else 'Локальна'}")
    
    # Перевірка Python версії
    print(f"🐍 Python версія: {sys.version}")
    
    # Перевірка залежностей
    print(f"\n📦 Перевірка залежностей:")
    try:
        import telegram
        print(f"✅ python-telegram-bot: {telegram.__version__}")
    except ImportError:
        print("❌ python-telegram-bot: не встановлено")
    
    try:
        import cv2
        print(f"✅ opencv-python: {cv2.__version__}")
    except ImportError:
        print("❌ opencv-python: не встановлено")
    
    try:
        import pytesseract
        print("✅ pytesseract: встановлено")
    except ImportError:
        print("❌ pytesseract: не встановлено")
    
    try:
        import flask
        print("✅ flask: встановлено")
    except ImportError:
        print("❌ flask: не встановлено")
    
    if failed == 0:
        print("\n🎉 Всі тести пройдено! Готово до деплою на Railway.")
        return True
    else:
        print(f"\n⚠️  Є {failed} проблем(и). Виправте їх перед деплоєм.")
        return False

if __name__ == "__main__":
    success = test_railway_config()
    sys.exit(0 if success else 1) 