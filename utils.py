import re
import logging
import csv
import io
import os
from typing import Optional, Tuple, List, Dict
from datetime import datetime

logger = logging.getLogger(__name__)

def parse_number(text: str) -> int:
    """
    Конвертує текст типу '4.9K', '18.9K', '1.2M' в числа
    
    Args:
        text: Текст для парсингу
        
    Returns:
        int: Числове значення
    """
    if not text:
        return 0
    
    # Очищуємо текст від зайвих символів
    text = re.sub(r'[^\d.,KkMmМКk]', '', text.strip())
    
    # Шаблони для розпізнавання
    patterns = [
        (r'(\d+(?:[.,]\d+)?)[KkКк]', 1000),
        (r'(\d+(?:[.,]\d+)?)[MmМм]', 1000000),
        (r'(\d+(?:[.,]\d+)?)', 1),
    ]
    
    for pattern, multiplier in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                number = float(match.group(1).replace(',', '.'))
                return int(number * multiplier)
            except (ValueError, AttributeError):
                continue
    
    # Якщо нічого не знайдено, спробуємо просто числа
    numbers = re.findall(r'\d+', text)
    if numbers:
        return int(numbers[0])
    
    return 0

def parse_duration(text: str) -> int:
    """
    Конвертує тривалість '3 год 25 хв', '3 hours 40 min' в хвилини
    
    Args:
        text: Текст з тривалістю
        
    Returns:
        int: Тривалість в хвилинах
    """
    if not text:
        return 0
    
    total_minutes = 0
    
    # Український формат
    hours_match = re.search(r'(\d+)\s*(?:год|hours?)', text, re.IGNORECASE)
    minutes_match = re.search(r'(\d+)\s*(?:хв|min(?:ute)?s?)', text, re.IGNORECASE)
    
    if hours_match:
        total_minutes += int(hours_match.group(1)) * 60
    
    if minutes_match:
        total_minutes += int(minutes_match.group(1))
    
    # Якщо не знайшли формат годин:хвилин, спробуємо інші варіанти
    if total_minutes == 0:
        # Формат HH:MM
        time_match = re.search(r'(\d{1,2}):(\d{2})', text)
        if time_match:
            total_minutes = int(time_match.group(1)) * 60 + int(time_match.group(2))
        else:
            # Просто число (вважаємо що це хвилини)
            number_match = re.search(r'(\d+)', text)
            if number_match:
                total_minutes = int(number_match.group(1))
    
    return total_minutes

def format_duration(minutes: int) -> str:
    """
    Форматує хвилини у вигляд 'X год Y хв'
    
    Args:
        minutes: Кількість хвилин
        
    Returns:
        str: Відформатована тривалість
    """
    if minutes < 60:
        return f"{minutes} хв"
    
    hours = minutes // 60
    remaining_minutes = minutes % 60
    
    if remaining_minutes == 0:
        return f"{hours} год"
    
    return f"{hours} год {remaining_minutes} хв"

def format_number(number: int) -> str:
    """
    Форматує число з розділювачами тисяч
    
    Args:
        number: Число для форматування
        
    Returns:
        str: Відформатоване число
    """
    if number >= 1000000:
        return f"{number/1000000:.1f}M"
    elif number >= 1000:
        return f"{number/1000:.1f}K"
    else:
        return str(number)

def extract_tiktok_stats(text: str) -> Optional[Tuple[int, int, int, int]]:
    """
    Витягує статистику TikTok з розпізнаного тексту
    
    Args:
        text: Текст, отриманий з OCR
        
    Returns:
        Tuple: (duration_minutes, viewers_count, gifters_count, diamonds_count) або None
    """
    try:
        logger.info(f"Аналізую OCR текст: {repr(text)}")
        
        lines = text.split('\n')
        stats = {
            'duration': 0,
            'viewers': 0, 
            'gifters': 0,
            'diamonds': 0
        }
        
        # Об'єднаємо весь текст для пошуку паттернів
        full_text = ' '.join(lines).lower()
        logger.info(f"Повний текст для аналізу: {repr(full_text)}")
        
        # Покращені паттерни для розпізнавання
        patterns = {
            'duration': [
                r'(\d+)\s*(?:hours?|год)\s*(\d+)\s*(?:min(?:ute)?s?|хв)',
                r'(\d+)\s*(?:hours?|год)',
                r'(\d+)\s*(?:min(?:ute)?s?|хв)',
                r'(\d{1,2}):(\d{2})'
            ],
            'viewers': [
                r'(\d+\.?\d*[KkКк]?)\s*(?:views?|глядач|viewer)',
                r'views?\s*(\d+\.?\d*[KkКк]?)',
                r'(\d+\.?\d*[KkКк]?)\s*views?'
            ],
            'gifters': [
                r'(\d+\.?\d*[KkКк]?)\s*(?:gifters?|дарувальник)',
                r'gifters?\s*(\d+\.?\d*[KkКк]?)',
                r'(\d+\.?\d*[KkКк]?)\s*gifters?'
            ],
            'diamonds': [
                r'(\d+\.?\d*[KkКк]?)\s*(?:diamonds?|діамант|алмаз)',
                r'diamonds?\s*(\d+\.?\d*[KkКк]?)',
                r'(\d+\.?\d*[KkКк]?)\s*diamonds?'
            ]
        }
        
        # Спеціальні паттерни для числових значень поряд
        number_patterns = [
            r'(\d+\.?\d*[KkКк]?)\s+(\d+\.?\d*[KkКк]?)\s+(\d+\.?\d*[KkКк]?)',  # три числа підряд
            r'(\d+\.?\d*[KkКк]?)\s+(\d+\.?\d*[KkКк]?)'  # два числа підряд
        ]
        
        # Шукаємо числові паттерни
        for line in lines:
            line_clean = line.strip()
            if not line_clean:
                continue
                
            logger.info(f"Аналізую рядок: {repr(line_clean)}")
            
            # Шукаємо три числа підряд (може бути Views, Gifters, Diamonds)
            three_numbers = re.search(r'(\d+\.?\d*[KkКк]?)\s+(\d+\.?\d*[KkКк]?)\s+(\d+\.?\d*[KkКк]?)', line_clean)
            if three_numbers:
                logger.info(f"Знайдено три числа: {three_numbers.groups()}")
                if not stats['viewers']:
                    stats['viewers'] = parse_number(three_numbers.group(1))
                    logger.info(f"Встановлено viewers: {stats['viewers']}")
                if not stats['gifters']:
                    stats['gifters'] = parse_number(three_numbers.group(2))
                    logger.info(f"Встановлено gifters: {stats['gifters']}")
                if not stats['diamonds']:
                    stats['diamonds'] = parse_number(three_numbers.group(3))
                    logger.info(f"Встановлено diamonds: {stats['diamonds']}")
        
        # Тепер шукаємо за специфічними паттернами
        for category, category_patterns in patterns.items():
            if stats[category] > 0:  # Якщо вже знайшли, пропускаємо
                continue
                
            for pattern in category_patterns:
                match = re.search(pattern, full_text, re.IGNORECASE)
                if match:
                    logger.info(f"Знайдено паттерн {category}: {pattern} -> {match.groups()}")
                    
                    if category == 'duration':
                        if len(match.groups()) == 2:
                            # Години та хвилини
                            hours = int(match.group(1))
                            minutes = int(match.group(2))
                            stats['duration'] = hours * 60 + minutes
                        else:
                            # Тільки години або хвилини
                            value = int(match.group(1))
                            if 'hour' in pattern or 'год' in pattern:
                                stats['duration'] = value * 60
                            else:
                                stats['duration'] = value
                    else:
                        stats[category] = parse_number(match.group(1))
                    
                    logger.info(f"Встановлено {category}: {stats[category]}")
                    break
        
        # Додатковий пошук чисел, якщо щось не знайшли
        if not any(stats.values()):
            logger.info("Не знайдено паттернів, шукаємо будь-які числа...")
            numbers = re.findall(r'\d+\.?\d*[KkКк]?', full_text)
            logger.info(f"Знайдені числа: {numbers}")
            
            for i, number in enumerate(numbers[:4]):  # Беремо перші 4 числа
                value = parse_number(number)
                if i == 0 and not stats['duration']:
                    stats['duration'] = value
                elif i == 1 and not stats['viewers']:
                    stats['viewers'] = value
                elif i == 2 and not stats['gifters']:
                    stats['gifters'] = value
                elif i == 3 and not stats['diamonds']:
                    stats['diamonds'] = value
        
        logger.info(f"Фінальна статистика: {stats}")
        
        # Перевіряємо, чи знайшли хоча б щось
        if any(value > 0 for value in stats.values()):
            return (stats['duration'], stats['viewers'], stats['gifters'], stats['diamonds'])
        
        logger.warning("Не вдалося витягти жодних даних")
        return None
        
    except Exception as e:
        logger.error(f"Помилка вилучення статистики з тексту: {e}")
        return None

def validate_stats(duration: int, viewers: int, gifters: int, diamonds: int) -> bool:
    """
    Валідує чи є статистика реалістичною
    
    Args:
        duration: Тривалість в хвилинах
        viewers: Кількість глядачів
        gifters: Кількість дарувальників
        diamonds: Кількість алмазів
        
    Returns:
        bool: True якщо статистика валідна
    """
    # Базові перевірки
    if duration < 0 or duration > 24*60:  # Не більше 24 годин
        return False
    
    if viewers < 0 or viewers > 10000000:  # Не більше 10М глядачів
        return False
    
    if gifters < 0 or gifters > viewers:  # Дарувальників не може бути більше глядачів
        return False
    
    if diamonds < 0 or diamonds > 1000000:  # Не більше 1М алмазів
        return False
    
    # Хоча б один параметр повинен бути > 0
    if all(value == 0 for value in [duration, viewers, gifters, diamonds]):
        return False
    
    return True

def create_user_stats_message(user_data: dict, summary: dict) -> str:
    """
    Створює повідомлення з статистикою користувача
    
    Args:
        user_data: Дані користувача
        summary: Зведена статистика
        
    Returns:
        str: Відформатоване повідомлення
    """
    nickname = user_data.get('tiktok_nickname', 'Невідомо')
    total_sessions = summary.get('total_sessions', 0)
    total_duration = summary.get('total_duration', 0)
    total_viewers = summary.get('total_viewers', 0)
    total_diamonds = summary.get('total_diamonds', 0)
    avg_duration = summary.get('avg_duration', 0)
    max_diamonds = summary.get('max_diamonds', 0)
    
    message = f"""📊 Ваша статистика ({nickname})

📈 Загальні показники (30 днів):
🎥 Всього ефірів: {total_sessions}
⏱️ Загальна тривалість: {format_duration(total_duration)}
👥 Всього глядачів: {format_number(total_viewers)}
💎 Всього алмазів: {format_number(total_diamonds)}

📋 Середні показники:
⏱️ Середня тривалість ефіру: {format_duration(int(avg_duration))}
🏆 Максимум алмазів за ефір: {format_number(max_diamonds)}
"""
    
    return message

def create_daily_report(stats: dict, date: datetime) -> str:
    """
    Створює щоденний звіт
    
    Args:
        stats: Статистика за день
        date: Дата звіту
        
    Returns:
        str: Відформатований звіт
    """
    date_str = date.strftime('%d.%m.%Y')
    active_users = stats.get('active_users', 0)
    total_duration = stats.get('total_duration', 0)
    total_viewers = stats.get('total_viewers', 0)
    total_diamonds = stats.get('total_diamonds', 0)
    total_sessions = stats.get('total_sessions', 0)
    top_diamonds = stats.get('top_diamonds', [])
    
    hours = total_duration // 60
    minutes = total_duration % 60
    
    report = f"""📊 ЩОДЕННИЙ ЗВІТ TikTok LIVE
📅 Дата: {date_str}

👥 Активних користувачів: {active_users}
⏱️ Загальна тривалість ефірів: {hours}:{minutes:02d}
👀 Загальна кількість глядачів: {format_number(total_viewers)}
💎 Загальна кількість алмазів: {format_number(total_diamonds)}

🏆 ТОП 3 ЗА АЛМАЗАМИ:"""
    
    for i, user in enumerate(top_diamonds, 1):
        nickname = user.get('tiktok_nickname', 'Невідомо')
        diamonds = user.get('total_diamonds', 0)
        report += f"\n{i}. {nickname} - {format_number(diamonds)} 💎"
    
    if not top_diamonds:
        report += "\nСьогодні не було активності"
    
    report += f"\n\n📸 Скріншотів оброблено: {total_sessions}"
    
    return report

def create_table_report(data: List[Dict], title: str = "Звіт") -> str:
    """
    Створити табличний звіт з даних
    
    Args:
        data: Список словників з даними користувачів
        title: Заголовок звіту
        
    Returns:
        str: Відформатований табличний звіт
    """
    if not data:
        return f"📋 {title}\n\nНемає даних для відображення."
    
    message = f"📋 {title}\n\n"
    
    # Заголовок таблиці
    message += "```\n"
    message += f"{'Користувач':<15} {'Ефіри':>6} {'Тривал':>8} {'Алмази':>8}\n"
    message += "-" * 45 + "\n"
    
    total_sessions = 0
    total_duration = 0
    total_diamonds = 0
    
    for user in data[:15]:  # Показати топ 15
        nickname = user.get('tiktok_nickname', 'Невідомо')[:14]  # Обрізати довгі ніки
        sessions = user.get('total_sessions', 0) or 0
        duration = user.get('total_duration', 0) or 0
        diamonds = user.get('total_diamonds', 0) or 0
        
        total_sessions += sessions
        total_duration += duration  
        total_diamonds += diamonds
        
        duration_str = format_duration(duration)[:7]  # Скоротити формат
        diamonds_str = format_number(diamonds)[:7]
        
        message += f"{nickname:<15} {sessions:>6} {duration_str:>8} {diamonds_str:>8}\n"
    
    message += "-" * 45 + "\n"
    message += f"{'ВСЬОГО':<15} {total_sessions:>6} {format_duration(total_duration)[:7]:>8} {format_number(total_diamonds)[:7]:>8}\n"
    message += "```\n"
    
    message += f"\n📊 Всього користувачів у звіті: {len(data)}"
    
    if len(data) > 15:
        message += f"\n📋 Показано топ 15 з {len(data)}"
    
    return message 

def create_csv_report(data: List[Dict], report_type: str = "report") -> str:
    """
    Створити CSV звіт з даних
    
    Args:
        data: Список словників з даними
        report_type: Тип звіту для визначення структури
        
    Returns:
        str: Шлях до створеного CSV файлу
    """
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"tiktok_{report_type}_{timestamp}.csv"
    filepath = os.path.join(os.getcwd(), filename)
    
    if not data:
        # Створити порожній файл з заголовками
        with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['Повідомлення', 'Немає даних для експорту'])
        return filepath
    
    with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        
        if report_type == "summary":
            # Зведений звіт
            writer.writerow([
                'Користувач', 'Telegram ID', 'Активні дні', 'Вихідні дні', 
                'Всього ефірів', 'Загальна тривалість (хв)', 'Всього глядачів',
                'Всього дарувальників', 'Всього алмазів', 'Середня тривалість (хв)',
                'Середня к-ть глядачів', 'Середня к-ть алмазів', 'Макс алмазів', 'Останній ефір'
            ])
            
            for row in data:
                writer.writerow([
                    row.get('tiktok_nickname', ''),
                    row.get('telegram_id', ''),
                    row.get('active_days', 0),
                    row.get('holiday_days', 0),
                    row.get('total_sessions', 0),
                    row.get('total_duration', 0),
                    row.get('total_viewers', 0),
                    row.get('total_gifters', 0),
                    row.get('total_diamonds', 0),
                    round(row.get('avg_duration', 0), 2),
                    round(row.get('avg_viewers', 0), 2),
                    round(row.get('avg_diamonds', 0), 2),
                    row.get('max_diamonds', 0),
                    row.get('last_stream', '')
                ])
                
        elif report_type == "detailed":
            # Детальний звіт по днях
            writer.writerow([
                'Дата', 'Тривалість (хв)', 'Глядачі', 'Дарувальники', 
                'Алмази', 'К-ть ефірів', 'Вихідний день'
            ])
            
            for row in data:
                is_holiday = "Так" if row.get('is_holiday', 0) else "Ні"
                writer.writerow([
                    row.get('date', ''),
                    row.get('total_duration', 0),
                    row.get('total_viewers', 0),
                    row.get('total_gifters', 0),
                    row.get('total_diamonds', 0),
                    row.get('sessions_count', 0),
                    is_holiday
                ])
        
        else:
            # Загальний формат
            if data:
                headers = list(data[0].keys())
                writer.writerow(headers)
                for row in data:
                    writer.writerow([row.get(key, '') for key in headers])
    
    return filepath

def create_user_detailed_csv(user_data: Dict, detailed_data: List[Dict], nickname: str) -> str:
    """
    Створити детальний CSV звіт для користувача
    
    Args:
        user_data: Основні дані користувача
        detailed_data: Поденні дані
        nickname: Нікнейм користувача
        
    Returns:
        str: Шлях до створеного файлу
    """
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    safe_nickname = "".join(c for c in nickname if c.isalnum() or c in (' ', '-', '_')).rstrip()
    filename = f"tiktok_user_{safe_nickname}_{timestamp}.csv"
    filepath = os.path.join(os.getcwd(), filename)
    
    with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        
        # Заголовок з інформацією про користувача
        writer.writerow(['=== ЗВІТ ПО КОРИСТУВАЧУ ==='])
        writer.writerow(['Нікнейм:', nickname])
        writer.writerow(['Telegram ID:', user_data.get('telegram_id', '')])
        writer.writerow(['Дата реєстрації:', user_data.get('registration_date', '')])
        writer.writerow(['Остання активність:', user_data.get('last_activity', '')])
        writer.writerow([])
        
        # Заголовки таблиці
        writer.writerow([
            'Дата', 'Тривалість (хв)', 'Глядачі', 'Дарувальники', 
            'Алмази', 'К-ть ефірів', 'Статус дня'
        ])
        
        # Дані по днях
        for day in detailed_data:
            status = "🌴 Вихідний" if day.get('is_holiday', 0) else "📺 Робочий"
            writer.writerow([
                day.get('date', ''),
                day.get('total_duration', 0),
                day.get('total_viewers', 0),
                day.get('total_gifters', 0),
                day.get('total_diamonds', 0),
                day.get('sessions_count', 0),
                status
            ])
    
    return filepath

def create_all_users_csv_package(all_reports: Dict[str, List[Dict]]) -> List[str]:
    """
    Створити пакет CSV файлів для всіх користувачів
    
    Args:
        all_reports: Словник з звітами всіх користувачів
        
    Returns:
        List[str]: Список шляхів до створених файлів
    """
    files = []
    
    for nickname, detailed_data in all_reports.items():
        if detailed_data:  # Тільки якщо є дані
            try:
                # Створюємо окремий файл для кожного користувача
                filepath = create_csv_report(detailed_data, "detailed")
                
                # Перейменовуємо файл з ніком користувача
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                safe_nickname = "".join(c for c in nickname if c.isalnum() or c in (' ', '-', '_')).rstrip()
                new_filename = f"tiktok_detail_{safe_nickname}_{timestamp}.csv"
                new_filepath = os.path.join(os.getcwd(), new_filename)
                
                if os.path.exists(filepath):
                    os.rename(filepath, new_filepath)
                    files.append(new_filepath)
                    
            except Exception as e:
                logger.error(f"Помилка створення файлу для {nickname}: {e}")
                continue
    
    return files 