#!/usr/bin/env python3
"""
Скрипт для запуску TikTok Stats Bot
"""

import sys
import os
import logging

# Додати поточну папку до Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bot import main

if __name__ == "__main__":
    try:
        print("🚀 Запуск TikTok Stats Bot...")
        print("📋 Переконайтеся що:")
        print("   ✅ Файл .env налаштований")
        print("   ✅ Tesseract встановлений") 
        print("   ✅ Всі залежності встановлені")
        print("   ✅ BOT_TOKEN вказаний в .env")
        print()
        
        main()
        
    except KeyboardInterrupt:
        print("\n👋 Бот зупинений користувачем")
    except Exception as e:
        print(f"\n❌ Помилка запуску: {e}")
        print("💡 Перевірте налаштування в .env файлі")
        sys.exit(1) 