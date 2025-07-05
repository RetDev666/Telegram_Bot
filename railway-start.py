#!/usr/bin/env python3
"""
Railway Starter - запуск бота и веб-сервера одновременно для Railway платформы
"""

import os
import threading
import time
from flask import Flask, jsonify
from bot import main as bot_main
from config import PORT, IS_RAILWAY, BOT_TOKEN
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
        'platform': 'Railway' if IS_RAILWAY else 'Local'
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

@app.route('/status')
def status():
    """Status endpoint для Railway"""
    return jsonify({
        'status': 'running',
        'service': 'TikTok Live Analytics Bot',
        'platform': 'Railway',
        'version': '1.0.0',
        'environment': os.getenv('RAILWAY_ENVIRONMENT', 'development')
    })

def run_bot():
    """Запустить Telegram бота в отдельном потоке"""
    try:
        logger.info("🤖 Запуск Telegram бота на Railway...")
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
    
    logger.info("🚀 Запуск TikTok Live Analytics Bot на Railway...")
    logger.info(f"🌍 Среда: {os.getenv('RAILWAY_ENVIRONMENT', 'development')}")
    logger.info(f"🔧 Платформа: Railway")
    
    # Запустить бота в отдельном потоке
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    
    # Небольшая задержка
    time.sleep(2)
    
    # Запустить веб-сервер в основном потоке
    run_web()

if __name__ == "__main__":
    main() 