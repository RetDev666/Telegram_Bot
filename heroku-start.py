#!/usr/bin/env python3
"""
Heroku Starter - запуск бота и веб-сервера одновременно
"""

import os
import threading
import time
from flask import Flask, jsonify
from bot import main as bot_main
from config import PORT, IS_HEROKU, BOT_TOKEN
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Flask приложение для healthcheck
app = Flask(__name__)

@app.route('/')
def index():
    """Главная страница для healthcheck"""
    return jsonify({
        'status': 'ok',
        'message': 'TikTok Live Analytics Bot is running',
        'platform': 'Heroku' if IS_HEROKU else 'Local'
    })

@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'telegram-bot',
        'timestamp': time.time()
    })

@app.route('/ping')
def ping():
    """Ping endpoint"""
    return 'pong'

def run_bot():
    """Запустить Telegram бота в отдельном потоке"""
    try:
        logger.info("🤖 Запуск Telegram бота...")
        bot_main()
    except Exception as e:
        logger.error(f"❌ Ошибка запуска бота: {e}")

def run_web():
    """Запустить веб-сервер"""
    try:
        logger.info(f"🌐 Запуск веб-сервера на порту {PORT}...")
        app.run(host='0.0.0.0', port=PORT, debug=False)
    except Exception as e:
        logger.error(f"❌ Ошибка запуска веб-сервера: {e}")

def main():
    """Главная функция"""
    if not BOT_TOKEN:
        logger.error("❌ BOT_TOKEN не установлен!")
        return
    
    logger.info("🚀 Запуск TikTok Live Analytics Bot на Heroku...")
    
    # Запустить бота в отдельном потоке
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    
    # Небольшая задержка
    time.sleep(2)
    
    # Запустить веб-сервер в основном потоке
    run_web()

if __name__ == "__main__":
    main() 