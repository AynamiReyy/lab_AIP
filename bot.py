import pymysql
import requests
import telebot
import threading
import time
from datetime import datetime
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from telebot.apihelper import ApiTelegramException
import logging
from queue import Queue
from urllib.parse import urlparse, parse_qs

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Конфигурация
with open("key.config") as key:
    bot = telebot.TeleBot(key.readline(), threaded=False)

# Константы
MAX_RETRIES = 3
RETRY_DELAY = 5
PRICE_CHECK_INTERVAL = 1800  # 30 минут
REQUEST_TIMEOUT = 15
DB_WRITE_QUEUE = Queue()

# Кэш для хранения данных о товарах
product_cache = {}
user_settings_cache = {}

# Доступные валюты
CURRENCIES = {
    'rub': {'symbol': '₽', 'name': 'Российский рубль'},
    'byn': {'symbol': 'Br', 'name': 'Белорусский рубль'},
    'kzt': {'symbol': '₸', 'name': 'Казахстанский тенге'},
    'amd': {'symbol': '֏', 'name': 'Армянский драм'},
    'kgs': {'symbol': 'с', 'name': 'Киргизский сом'},
    'uzs': {'symbol': 'soʻm', 'name': 'Узбекский сум'},
    'tjs': {'symbol': 'SM', 'name': 'Таджикский сомони'}
}


class DatabaseManager:
    """Класс для управления операциями с базой данных MySQL"""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.init_db()
        return cls._instance

    def init_db(self):
        """Инициализация базы данных"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()

                # Создаем таблицу пользователей
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS botUser (
                        chat_id BIGINT NOT NULL,
                        name TEXT NULL,
                        currency VARCHAR(3) NULL DEFAULT 'rub',
                        notification_type VARCHAR(8) NULL DEFAULT 'decrease',
                        treshold_percent TINYINT NULL DEFAULT 5,
                        PRIMARY KEY (chat_id)
                    ) ENGINE=InnoDB;
                """)

                # Создаем таблицу товаров
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS product (
                        articule INT NOT NULL,
                        name TEXT NOT NULL,
                        PRIMARY KEY (articule)
                    ) ENGINE=InnoDB;
                """)

                # Создаем таблицу цен
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS price (
                        articule INT NOT NULL,
                        initial_price INT NULL,
                        curent_price INT NULL,
                        last_price INT NULL,
                        last_check DATETIME NULL,
                        PRIMARY KEY (articule),
                        CONSTRAINT fk_price_product1
                            FOREIGN KEY (articule)
                            REFERENCES product (articule)
                            ON DELETE CASCADE
                            ON UPDATE CASCADE
                    ) ENGINE=InnoDB;
                """)

                # Создаем таблицу связи товаров и пользователей
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS product_has_botUser (
                        product_articule INT NOT NULL,
                        botUser_chat_id BIGINT NOT NULL,
                        PRIMARY KEY (product_articule, botUser_chat_id),
                        CONSTRAINT fk_product_has_botUser_product1
                            FOREIGN KEY (product_articule)
                            REFERENCES product (articule)
                            ON DELETE CASCADE
                            ON UPDATE CASCADE,
                        CONSTRAINT fk_product_has_botUser_botUser1
                            FOREIGN KEY (botUser_chat_id)
                            REFERENCES botUser (chat_id)
                            ON DELETE CASCADE
                            ON UPDATE CASCADE
                    ) ENGINE=InnoDB;
                """)

                conn.commit()
        except Exception as e:
            logger.error(f"Error initializing database: {e}")
            raise

    @staticmethod
    def get_connection():
        """Возвращает соединение с базой данных MySQL"""
        with open("key_to_db.config") as key:
            return pymysql.connect(
                host='127.0.0.1',
                port=3306,
                user='root',
                password=key.readline().strip(),
                database='WBBotProducts',
                charset='utf8mb4',
                cursorclass=pymysql.cursors.DictCursor
            )

    def execute(self, query, params=(), commit=False, fetch=False):
        """Выполняет SQL запрос с обработкой ошибок"""
        for attempt in range(MAX_RETRIES):
            try:
                with self.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(query, params)
                    if commit:
                        conn.commit()
                    if fetch:
                        return cursor.fetchall()
                    return cursor.lastrowid
            except pymysql.Error as e:
                logger.error(f"Database error (attempt {attempt + 1}): {e}")
                if attempt == MAX_RETRIES - 1:
                    raise
                time.sleep(RETRY_DELAY)

    def queue_write(self, query, params=()):
        """Добавляет запись в очередь для асинхронной записи"""
        DB_WRITE_QUEUE.put((query, params, True))  # Все операции в очереди требуют commit


# Инициализация базы данных
db = DatabaseManager()


def db_writer_worker():
    """Фоновый процесс для записи в базу данных"""
    while True:
        try:
            query, params, commit = DB_WRITE_QUEUE.get()
            db.execute(query, params, commit=commit)
            time.sleep(0.1)  # Небольшая задержка для снижения нагрузки
        except Exception as e:
            logger.error(f"Error in db writer worker: {e}")


# Запуск фонового процесса для записи в БД
threading.Thread(target=db_writer_worker, daemon=True).start()


def safe_send_message(chat_id, text, **kwargs):
    """Безопасная отправка сообщения с повторными попытками"""
    for attempt in range(MAX_RETRIES):
        try:
            return bot.send_message(chat_id, text, **kwargs)
        except (ConnectionError, ApiTelegramException) as e:
            logger.warning(f"Attempt {attempt + 1} failed: {str(e)}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY)
            else:
                logger.error(f"Failed to send message after {MAX_RETRIES} attempts")
                raise


def safe_edit_message_text(text, chat_id, message_id, **kwargs):
    """Безопасное редактирование сообщения с повторными попытками"""
    for attempt in range(MAX_RETRIES):
        try:
            return bot.edit_message_text(text, chat_id, message_id, **kwargs)
        except (ConnectionError, ApiTelegramException) as e:
            if "message is not modified" in str(e):
                return  # Игнорируем ошибку, если сообщение не изменилось
            logger.warning(f"Attempt {attempt + 1} failed: {str(e)}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY)
            else:
                logger.error(f"Failed to edit message after {MAX_RETRIES} attempts")
                raise


def extract_article(url):
    try:
        # Удаляем якоря (#) и лишние слеши
        clean_url = url.split('#')[0].rstrip('/')
        parsed = urlparse(clean_url)
        netloc = parsed.netloc.lower()

        # Все возможные домены Wildberries (включая поддомены global., www., wb.)
        wb_domains = (
            'wildberries.ru', 'wildberries.by', 'wildberries.kz', 'wildberries.ua',
            'wildberries.com', 'wildberries.am', 'wildberries.ge',
            'wb.ru', 'wb.by', 'wb.kz', 'wb.ua', 'wb.com', 'wb.am', 'wb.ge',
            'global.wildberries.ru', 'global.wildberries.by',  # и другие global.*
        )

        # Проверяем, относится ли URL к Wildberries
        if not any(netloc.endswith(domain) for domain in wb_domains):
            return None

        # 1. Проверяем query-параметры (?card=123456 или ?nm=123456)
        query_params = parse_qs(parsed.query)
        if 'card' in query_params and query_params['card'][0].isdigit():
            return query_params['card'][0]
        if 'nm' in query_params and query_params['nm'][0].isdigit():
            return query_params['nm'][0]

        # 2. Проверяем /catalog/123456/detail.aspx
        if '/catalog/' in clean_url:
            parts = [p for p in clean_url.split('/') if p]
            for i, part in enumerate(parts):
                if part == 'catalog' and i + 1 < len(parts) and parts[i + 1].isdigit():
                    return parts[i + 1]

        # 3. Проверяем /product/123456/
        if '/product/' in clean_url:
            product_parts = [p for p in clean_url.split('/') if p]
            for i, part in enumerate(product_parts):
                if part == 'product' and i + 1 < len(product_parts) and product_parts[i + 1].isdigit():
                    return product_parts[i + 1]

        # 4. Проверяем /123456/ (короткие ссылки)
        path_parts = [p for p in parsed.path.split('/') if p]
        if len(path_parts) == 1 and path_parts[0].isdigit():
            return path_parts[0]
    except Exception as e:
        logger.error(f"Ошибка при разборе URL: {e}")

    return None


def get_cached_price(article, currency='rub'):
    """Получает цену из кэша или API"""
    now = time.time()
    cache_key = f"{article}_{currency}"
    if cache_key in product_cache:
        cached_data, timestamp = product_cache[cache_key]
        if now - timestamp < 300:  # 5 минут кэширования
            return cached_data

    result = get_current_price(article, currency)
    if result['success']:
        product_cache[cache_key] = (result, now)
    return result


def get_current_price(article, currency='rub'):
    """Получает текущую цену товара с Wildberries"""
    try:
        api_url = f"https://card.wb.ru/cards/v1/detail?appType=1&curr={currency}&dest=-1257786&nm={article}"
        response = requests.get(api_url, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        data = response.json()

        if data.get('data') and data['data'].get('products'):
            product = data['data']['products'][0]
            return {
                'success': True,
                'name': product['name'],
                'price': product.get('salePriceU', 0) // 100,
                'currency': currency,
                'currency_symbol': CURRENCIES.get(currency, {}).get('symbol', '₽')
            }
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка при запросе цены для артикула {article}: {e}")
    except (KeyError, IndexError, ValueError) as e:
        logger.error(f"Ошибка при обработке ответа для артикула {article}: {e}")

    return {'success': False}


def check_price_change(chat_id, article, old_price, new_price):
    """Проверяет, нужно ли отправлять уведомление на основе настроек пользователя"""
    if chat_id in user_settings_cache:
        threshold, notif_type, currency = user_settings_cache[chat_id]
    else:
        result = db.execute('''
            SELECT treshold_percent, notification_type, currency 
            FROM botUser 
            WHERE chat_id = %s
        ''', (chat_id,), fetch=True)

        if not result:
            threshold, notif_type, currency = 10, 'decrease', 'rub'
        else:
            threshold = result[0]['treshold_percent']
            notif_type = result[0]['notification_type'] or 'decrease'
            currency = result[0]['currency'] or 'rub'
            user_settings_cache[chat_id] = (threshold, notif_type, currency)

    if old_price == 0:
        return False

    change_percent = abs((new_price - old_price) / old_price * 100)

    if change_percent < threshold:
        return False

    if notif_type == 'any':
        return True
    elif notif_type == 'increase' and new_price > old_price:
        return True
    elif notif_type == 'decrease' and new_price < old_price:
        return True

    return False


def price_checker():
    """Фоновый процесс для проверки цен"""
    while True:
        try:
            start_time = time.time()

            # Получаем товары для проверки (исправленный запрос)
            products = db.execute('''
                SELECT p.articule, p.name, pr.curent_price, pr.initial_price, bu.currency, bu.chat_id
                FROM product p
                JOIN product_has_botUser ph ON p.articule = ph.product_articule
                JOIN botUser bu ON ph.botUser_chat_id = bu.chat_id
                JOIN price pr ON p.articule = pr.articule
            ''', fetch=True)

            logger.info(f"Начинаем проверку цен для {len(products)} товаров")
            for product in products:
                article = product['articule']
                name = product['name']
                current_price = product['curent_price']
                initial_price = product['initial_price']
                chat_id = product['chat_id']
                currency = product['currency'] or 'rub'

                try:
                    result = get_cached_price(article, currency)
                    logger.info(f"проверка артикула {article}")
                    if not result['success']:
                        continue

                    # Обновляем информацию о товаре
                    update_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    db.queue_write(
                        "UPDATE price SET curent_price = %s, last_check = %s WHERE articule = %s",
                        (result['price'], update_time, article)
                    )

                    # Проверяем изменение цены относительно начальной
                    if check_price_change(chat_id, article, initial_price, result['price']):
                        change_percent = abs((result['price'] - initial_price) / initial_price * 100)
                        change_direction = "↗️ выросла" if result['price'] > initial_price else "↘️ упала"

                        db.queue_write(
                            "UPDATE price SET initial_price = %s WHERE articule = %s",
                            (result['price'], article)
                        )

                        try:
                            safe_send_message(
                                chat_id,
                                f"🔔 Цена {change_direction} на {change_percent:.2f}%!\n"
                                f"📦 {name}\n"
                                f"💰 Было: {initial_price}{result['currency_symbol']}\n"
                                f"💰 Стало: {result['price']}{result['currency_symbol']}\n"
                                f"Артикул {article}\n"
                                f"🔄 Автоматическая проверка"
                            )
                        except Exception as e:
                            logger.error(f"Failed to send price update to {chat_id}: {e}")

                except Exception as e:
                    logger.error(f"Ошибка при обработке товара {article}: {e}")
                    continue

            logger.info(f"Проверено товаров: {len(products)}")
            time.sleep(PRICE_CHECK_INTERVAL)

        except Exception as e:
            logger.error(f"Критическая ошибка в цикле проверки: {e}")
            time.sleep(60)


# Запуск фонового процесса проверки цен
threading.Thread(target=price_checker, daemon=True).start()


# Клавиатуры и меню
def main_menu():
    markup = InlineKeyboardMarkup()
    markup.row_width = 2
    markup.add(
        InlineKeyboardButton("📦 Мои товары", callback_data="my_products"),
        InlineKeyboardButton("➕ Добавить товар", callback_data="add_product"),
        InlineKeyboardButton("⚙️ Настройки", callback_data="settings"),
        InlineKeyboardButton("ℹ️ Помощь", callback_data="help")
    )
    return markup


def back_to_menu_markup():
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🔙 Назад", callback_data="main_menu"))
    return markup


def products_menu(products, currency='rub'):
    markup = InlineKeyboardMarkup()
    for product in products:
        markup.add(
            InlineKeyboardButton(
                f"{product['name'][:30]}...",
                callback_data=f"product_{product['articule']}")
        )
    markup.add(InlineKeyboardButton("🔙 Назад", callback_data="main_menu"))
    return markup


def product_actions(article):
    markup = InlineKeyboardMarkup()
    markup.row_width = 2
    markup.add(
        InlineKeyboardButton("🔄 Проверить цену", callback_data=f"check_{article}"),
        InlineKeyboardButton("❌ Удалить", callback_data=f"delete_{article}"),
        InlineKeyboardButton("🔙 Назад", callback_data="my_products")
    )
    return markup


def settings_menu(chat_id):
    """Generate the settings menu with current user settings"""
    if chat_id in user_settings_cache:
        threshold, notif_type, currency = user_settings_cache[chat_id]
    else:
        result = db.execute('''
            SELECT treshold_percent, notification_type, currency 
            FROM botUser 
            WHERE chat_id = %s
        ''', (chat_id,), fetch=True)

        if not result:
            threshold, notif_type, currency = 10, 'decrease', 'rub'
        else:
            threshold = result[0]['treshold_percent']
            notif_type = result[0]['notification_type'] or 'decrease'
            currency = result[0]['currency'] or 'rub'
            user_settings_cache[chat_id] = (threshold, notif_type, currency)

    notif_type_text = {
        'any': 'любое изменение',
        'increase': 'только рост',
        'decrease': 'только падение'
    }.get(notif_type, 'любое изменение')

    currency_info = CURRENCIES.get(currency, {'name': 'Российский рубль', 'symbol': '₽'})

    text = (
        f"⚙️ Текущие настройки уведомлений:\n\n"
        f"📊 Порог изменения: {threshold}%\n"
        f"🔔 Тип уведомлений: {notif_type_text}\n"
        f"💰 Валюта: {currency_info['name']} ({currency_info['symbol']})\n\n"
        f"Пример: при цене 10,000{currency_info['symbol']}:\n"
    )

    if notif_type == 'any':
        text += f"- Уведомление при цене ≤{int(10000 * (1 - threshold / 100))}{currency_info['symbol']} или ≥{int(10000 * (1 + threshold / 100))}{currency_info['symbol']}\n"
    elif notif_type == 'increase':
        text += f"- Уведомление только при росте до ≥{int(10000 * (1 + threshold / 100))}{currency_info['symbol']}\n"
    else:
        text += f"- Уведомление только при падении до ≤{int(10000 * (1 - threshold / 100))}{currency_info['symbol']}\n"

    markup = InlineKeyboardMarkup()
    markup.row_width = 1
    markup.add(
        InlineKeyboardButton("📊 Изменить порог уведомлений", callback_data="change_threshold"),
        InlineKeyboardButton("🔄 Изменить тип уведомлений", callback_data="change_notif_type"),
        InlineKeyboardButton("💰 Изменить валюту", callback_data="change_currency"),
        InlineKeyboardButton("🔙 Назад", callback_data="main_menu")
    )
    return text, markup


def threshold_menu(chat_id):
    """Generate the threshold selection menu"""
    # Get current threshold
    if chat_id in user_settings_cache:
        current_threshold, current_type, current_currency = user_settings_cache[chat_id]
    else:
        result = db.execute('''
            SELECT treshold_percent, notification_type, currency 
            FROM botUser 
            WHERE chat_id = %s
        ''', (chat_id,), fetch=True)
        if not result:
            current_threshold, current_type, current_currency = 10, 'decrease', 'rub'
        else:
            current_threshold = result[0]['treshold_percent']
            current_type = result[0]['notification_type'] or 'decrease'
            current_currency = result[0]['currency'] or 'rub'

    currency_symbol = CURRENCIES.get(current_currency, {}).get('symbol', '₽')

    text = (
        f"📊 Текущий порог: {current_threshold}%\n"
        f"Пример: при цене 10,000{currency_symbol}\n"
        f"Уведомление при изменении на ±{current_threshold}% (≤{int(10000 * (1 - current_threshold / 100))}{currency_symbol} или ≥{int(10000 * (1 + current_threshold / 100))}{currency_symbol})\n\n"
        f"Выберите новый порог или введите свой:"
    )

    markup = InlineKeyboardMarkup()
    markup.row_width = 4
    markup.add(
        InlineKeyboardButton("1%", callback_data=f"set_threshold_1"),
        InlineKeyboardButton("3%", callback_data=f"set_threshold_3"),
        InlineKeyboardButton("5%", callback_data=f"set_threshold_5"),
        InlineKeyboardButton("10%", callback_data=f"set_threshold_10"),
        InlineKeyboardButton("Другой...", callback_data="custom_threshold"),
        InlineKeyboardButton("🔙 Назад", callback_data="settings")
    )
    return text, markup


def notif_type_menu(chat_id):
    """Generate the notification type selection menu"""
    # Get current notification type
    if chat_id in user_settings_cache:
        current_threshold, current_type, current_currency = user_settings_cache[chat_id]
    else:
        result = db.execute('''
            SELECT treshold_percent, notification_type, currency 
            FROM botUser 
            WHERE chat_id = %s
        ''', (chat_id,), fetch=True)
        if not result:
            current_threshold, current_type, current_currency = 10, 'decrease', 'rub'
        else:
            current_threshold = result[0]['treshold_percent']
            current_type = result[0]['notification_type'] or 'decrease'
            current_currency = result[0]['currency'] or 'rub'

    currency_symbol = CURRENCIES.get(current_currency, {}).get('symbol', '₽')

    type_descriptions = {
        'any': f'🔄 Любое изменение (±{current_threshold}%)',
        'increase': f'🔼 Только рост (≥+{current_threshold}%)',
        'decrease': f'🔽 Только падение (≤-{current_threshold}%)'
    }

    text = (
        f"🔔 Текущий тип: {type_descriptions[current_type]}\n"
        f"Пример для цены 10,000{currency_symbol}:\n"
        f"{type_descriptions[current_type]} (≤{int(10000 * (1 - current_threshold / 100))}{currency_symbol} или ≥{int(10000 * (1 + current_threshold / 100))}{currency_symbol})\n\n"
        f"Выберите новый тип уведомлений:"
    )

    markup = InlineKeyboardMarkup()
    markup.row_width = 1
    markup.add(
        InlineKeyboardButton(type_descriptions['any'],
                             callback_data="set_notif_type_any"),
        InlineKeyboardButton(type_descriptions['increase'],
                             callback_data="set_notif_type_increase"),
        InlineKeyboardButton(type_descriptions['decrease'],
                             callback_data="set_notif_type_decrease"),
        InlineKeyboardButton("🔙 Назад", callback_data="settings")
    )
    return text, markup


def currency_menu(chat_id):
    """Generate the currency selection menu"""
    # Get current currency
    if chat_id in user_settings_cache:
        current_threshold, current_type, current_currency = user_settings_cache[chat_id]
    else:
        result = db.execute('''
            SELECT treshold_percent, notification_type, currency 
            FROM botUser 
            WHERE chat_id = %s
        ''', (chat_id,), fetch=True)
        if not result:
            current_threshold, current_type, current_currency = 10, 'decrease', 'rub'
        else:
            current_threshold = result[0]['treshold_percent']
            current_type = result[0]['notification_type'] or 'decrease'
            current_currency = result[0]['currency'] or 'rub'

    text = (
        f"💰 Текущая валюта: {CURRENCIES.get(current_currency, {}).get('name', 'Российский рубль')} "
        f"({CURRENCIES.get(current_currency, {}).get('symbol', '₽')})\n\n"
        f"Выберите новую валюту:"
    )

    markup = InlineKeyboardMarkup()
    markup.row_width = 2
    for code, data in CURRENCIES.items():
        markup.add(
            InlineKeyboardButton(
                f"{data['name']} ({data['symbol']})",
                callback_data=f"set_currency_{code}"
            )
        )
    markup.add(InlineKeyboardButton("🔙 Назад", callback_data="settings"))
    return text, markup


# Обработчики сообщений
@bot.message_handler(commands=['start'])
def start(message):
    try:
        # Проверяем, есть ли пользователь в базе
        user_exists = db.execute(
            'SELECT 1 FROM botUser WHERE chat_id = %s',
            (message.chat.id,),
            fetch=True
        )

        if not user_exists:
            # Добавляем нового пользователя
            db.queue_write(
                'INSERT INTO botUser (chat_id, name, currency, notification_type, treshold_percent) '
                'VALUES (%s, %s, "rub", "decrease", 10)',
                (message.chat.id, message.from_user.first_name or "Пользователь")
            )

        # Получаем количество товаров пользователя (исправленный запрос)
        count = db.execute(
            'SELECT COUNT(*) as cnt FROM product_has_botUser WHERE botUser_chat_id = %s',
            (message.chat.id,),
            fetch=True
        )[0]['cnt']

        welcome_text = (
            f"Привет, {message.from_user.first_name}!\n"
            f"У вас {'пока нет' if count == 0 else count} отслеживаемых товаров\n\n"
            "Я слежу за ценами и сообщу тебе, когда товар подешевеет.\n"
            "Как это работает:\n"
            "1️⃣ Присылаешь ссылку на товар\n"
            "2️⃣ Я запоминаю цену\n"
            "3️⃣ Ты получаешь уведомление, если цена изменится\n"
            "🔔 Проверка цен происходит автоматически каждые 30 минут"
        )

        safe_send_message(
            message.chat.id,
            welcome_text,
            reply_markup=main_menu()
        )
    except Exception as e:
        logger.error(f"Ошибка в обработчике start: {e}")
        safe_send_message(
            message.chat.id,
            "⚠️ Произошла ошибка при обработке команды. Пожалуйста, попробуйте позже."
        )


@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    chat_id = call.message.chat.id
    message_id = call.message.message_id

    try:
        if call.data == "main_menu":
            count = db.execute('''
                SELECT COUNT(*) as cnt 
                FROM product_has_botUser 
                WHERE botUser_chat_id = %s
            ''', (chat_id,), fetch=True)[0]['cnt']

            welcome_text = (
                "🛍️ Главное меню\n"
                f"📊 Отслеживается товаров: {count}\n"
                "Выберите действие:"
            )

            safe_edit_message_text(
                welcome_text,
                chat_id,
                message_id,
                reply_markup=main_menu()
            )



        elif call.data == "my_products":
            # Получаем валюту пользователя
            result = db.execute(
                'SELECT currency FROM botUser WHERE chat_id = %s',
                (chat_id,),
                fetch=True
            )
            currency = result[0]['currency'] if result else 'rub'

            products = db.execute(
                '''SELECT p.articule, p.name, pr.curent_price, pr.last_price, pr.last_check
                FROM product p
                JOIN product_has_botUser ph ON p.articule = ph.product_articule
                JOIN price pr ON p.articule = pr.articule
                WHERE ph.botUser_chat_id = %s''',
                (chat_id,),
                fetch=True
            )

            if products:
                safe_edit_message_text(
                    "📦 Ваши отслеживаемые товары:",
                    chat_id,
                    message_id,
                    reply_markup=products_menu(products)
                )

            else:
                safe_edit_message_text(
                    "📦 У вас нет отслеживаемых товаров",
                    chat_id,
                    message_id,
                    reply_markup=back_to_menu_markup()
                )


        elif call.data == "add_product":
            msg = safe_edit_message_text(
                "Отправьте ссылку или артикул на товар с Wildberries:",
                chat_id,
                message_id,
                reply_markup=back_to_menu_markup()
            )
            bot.register_next_step_handler(msg, lambda m: process_product(m, 1))

        elif call.data.startswith("product_"):
            article = call.data.split("_")[1]
            safe_edit_message_text(
                "Выберите действие с товаром:",
                chat_id,
                message_id,
                reply_markup=product_actions(article)
            )

        elif call.data.startswith("check_"):
            article = call.data.split("_")[1]

            # Получаем валюту пользователя
            result = db.execute('''
                SELECT currency FROM botUser WHERE chat_id = %s
            ''', (chat_id,), fetch=True)
            currency = result[0]['currency'] if result else 'rub'

            result = get_cached_price(article, currency)

            if result['success']:
                bot.answer_callback_query(
                    call.id,
                    f"Текущая цена: {result['price']}{result['currency_symbol']}",
                    show_alert=True
                )
            else:
                bot.answer_callback_query(
                    call.id,
                    "Не удалось получить текущую цену",
                    show_alert=True
                )


        elif call.data.startswith("delete_"):
            article = call.data.split("_")[1]
            try:
                # 1. Удаляем связь между пользователем и товаром
                db.execute(
                    "DELETE FROM product_has_botUser WHERE product_articule = %s AND botUser_chat_id = %s",
                    (article, chat_id),
                    commit=True
                )
                # 2. Проверяем, есть ли еще пользователи у этого товара
                remaining_users = db.execute(
                    "SELECT COUNT(*) as cnt FROM product_has_botUser WHERE product_articule = %s",
                    (article,),
                    fetch=True
                )[0]['cnt']

                # 3. Если у товара больше нет пользователей, удаляем его и цену
                if remaining_users == 0:
                    # Удаляем цену товара (внешний ключ ON DELETE CASCADE автоматически удалит запись в price)

                    db.execute(
                        "DELETE FROM product WHERE articule = %s",
                        (article,),
                        commit=True
                    )
                # 4. Удаляем из кэша
                for key in list(product_cache.keys()):
                    if key.startswith(f"{article}_"):
                        del product_cache[key]

                # 5. Проверяем оставшиеся товары пользователя
                remaining_products = db.execute(
                    "SELECT COUNT(*) as cnt FROM product_has_botUser WHERE botUser_chat_id = %s",
                    (chat_id,),
                    fetch=True

                )[0]['cnt']
                if remaining_products > 0:
                    callback_handler(call)  # Обновляем список товаров
                else:
                    safe_edit_message_text(
                        "🛍️ Главное меню\n"
                        "Вы удалили все товары из отслеживания\n"
                        "Выберите действие:",
                        chat_id,
                        message_id,
                        reply_markup=main_menu()
                    )
            except Exception as e:
                bot.answer_callback_query(
                    call.id,
                    f"Ошибка при удалении товара: {str(e)}",
                    show_alert=True
                )

        elif call.data == "settings":
            text, markup = settings_menu(chat_id)
            safe_edit_message_text(
                text,
                chat_id,
                message_id,
                reply_markup=markup
            )

        elif call.data == "change_threshold":
            text, markup = threshold_menu(chat_id)
            safe_edit_message_text(
                text,
                chat_id,
                message_id,
                reply_markup=markup
            )

        elif call.data == "change_notif_type":
            text, markup = notif_type_menu(chat_id)
            safe_edit_message_text(
                text,
                chat_id,
                message_id,
                reply_markup=markup
            )

        elif call.data == "change_currency":
            text, markup = currency_menu(chat_id)
            safe_edit_message_text(
                text,
                chat_id,
                message_id,
                reply_markup=markup
            )

        elif call.data.startswith("set_threshold_"):
            new_threshold = int(call.data.split("_")[2])

            # Обновляем настройки пользователя
            db.queue_write('''
                UPDATE botUser 
                SET treshold_percent = %s
                WHERE chat_id = %s
            ''', (new_threshold, chat_id))

            # Обновляем кэш
            if chat_id in user_settings_cache:
                _, current_type, current_currency = user_settings_cache[chat_id]
                user_settings_cache[chat_id] = (new_threshold, current_type, current_currency)
            else:
                result = db.execute('''
                    SELECT notification_type, currency FROM botUser WHERE chat_id = %s
                ''', (chat_id,), fetch=True)
                if result:
                    current_type = result[0]['notification_type'] or 'decrease'
                    current_currency = result[0]['currency'] or 'rub'
                    user_settings_cache[chat_id] = (new_threshold, current_type, current_currency)

            currency_symbol = CURRENCIES.get(current_currency, {}).get('symbol', '₽')

            # Показываем подтверждение
            text = (
                f"✅ Новый порог установлен: {new_threshold}%\n\n"
                f"Теперь вы будете получать уведомления при:\n"
            )

            if current_type == 'any':
                text += f"Любом изменении цены ±{new_threshold}% (≤{int(10000 * (1 - new_threshold / 100))}{currency_symbol} или ≥{int(10000 * (1 + new_threshold / 100))}{currency_symbol})"
            elif current_type == 'increase':
                text += f"Росте цены ≥+{new_threshold}% (≥{int(10000 * (1 + new_threshold / 100))}{currency_symbol})"
            else:
                text += f"Падении цены ≤-{new_threshold}% (≤{int(10000 * (1 - new_threshold / 100))}{currency_symbol})"

            safe_edit_message_text(
                text,
                chat_id,
                message_id,
                reply_markup=InlineKeyboardMarkup().add(
                    InlineKeyboardButton("🔙 Назад", callback_data="settings"))
            )

        elif call.data == "custom_threshold":
            msg = safe_edit_message_text(
                "Введите новый порог уведомлений (1-50%):",
                chat_id,
                message_id,
                reply_markup=InlineKeyboardMarkup().add(
                    InlineKeyboardButton("🔙 Назад", callback_data="change_threshold"))
            )
            bot.register_next_step_handler(msg, process_custom_threshold)

        elif call.data.startswith("set_notif_type_"):
            new_type = call.data.split("_")[3]  # any, increase, or decrease

            # Обновляем настройки пользователя
            db.queue_write('''
                UPDATE botUser 
                SET notification_type = %s
                WHERE chat_id = %s
            ''', (new_type, chat_id))

            # Обновляем кэш
            if chat_id in user_settings_cache:
                current_threshold, _, current_currency = user_settings_cache[chat_id]
                user_settings_cache[chat_id] = (current_threshold, new_type, current_currency)
            else:
                result = db.execute('''
                    SELECT treshold_percent, currency FROM botUser WHERE chat_id = %s
                ''', (chat_id,), fetch=True)
                if result:
                    current_threshold = result[0]['treshold_percent']
                    current_currency = result[0]['currency'] or 'rub'
                    user_settings_cache[chat_id] = (current_threshold, new_type, current_currency)

            currency_symbol = CURRENCIES.get(current_currency, {}).get('symbol', '₽')

            # Показываем подтверждение
            type_description = {
                'any': f"любом изменении цены ±{current_threshold}% (≤{int(10000 * (1 - current_threshold / 100))}{currency_symbol} или ≥{int(10000 * (1 + current_threshold / 100))}{currency_symbol})",
                'increase': f"росте цены ≥+{current_threshold}% (≥{int(10000 * (1 + current_threshold / 100))}{currency_symbol})",
                'decrease': f"падении цены ≤-{current_threshold}% (≤{int(10000 * (1 - current_threshold / 100))}{currency_symbol})"
            }

            safe_edit_message_text(
                f"✅ Тип уведомлений изменен\n\n"
                f"Теперь вы будете получать уведомления при:\n"
                f"{type_description[new_type]}",
                chat_id,
                message_id,
                reply_markup=InlineKeyboardMarkup().add(
                    InlineKeyboardButton("🔙 Назад", callback_data="settings"))
            )

        elif call.data.startswith("set_currency_"):
            new_currency = call.data.split("_")[2]

            # Обновляем настройки пользователя
            db.queue_write('''
                UPDATE botUser 
                SET currency = %s
                WHERE chat_id = %s
            ''', (new_currency, chat_id))

            # Обновляем кэш
            if chat_id in user_settings_cache:
                current_threshold, current_type, _ = user_settings_cache[chat_id]
                user_settings_cache[chat_id] = (current_threshold, current_type, new_currency)
            else:
                result = db.execute('''
                    SELECT treshold_percent, notification_type FROM botUser WHERE chat_id = %s
                ''', (chat_id,), fetch=True)
                if result:
                    current_threshold = result[0]['treshold_percent']
                    current_type = result[0]['notification_type'] or 'decrease'
                    user_settings_cache[chat_id] = (current_threshold, current_type, new_currency)

            currency_info = CURRENCIES.get(new_currency, {'name': 'Российский рубль', 'symbol': '₽'})

            # Обновляем цены для всех товаров пользователя
            products = db.execute('''
                SELECT p.articule 
                FROM product p
                JOIN product_has_botUser ph ON p.articule = ph.product_articule
                WHERE ph.botUser_chat_id = %s
            ''', (chat_id,), fetch=True)

            for product in products:
                article = product['articule']
                price_info = get_current_price(article, new_currency)
                if price_info['success']:
                    db.queue_write('''
                        UPDATE price 
                        SET initial_price = %s, curent_price = %s 
                        WHERE articule = %s
                    ''', (price_info['price'], price_info['price'], article))

            # Показываем подтверждение
            safe_edit_message_text(
                f"✅ Валюта изменена на {currency_info['name']} ({currency_info['symbol']})\n\n"
                f"Теперь цены будут отображаться в {currency_info['symbol']}.\n"
                f"Проверка цен для всех ваших товаров будет выполнена при следующем обновлении.",
                chat_id,
                message_id,
                reply_markup=InlineKeyboardMarkup().add(
                    InlineKeyboardButton("🔙 Назад", callback_data="settings"))
            )

        elif call.data == "help":
            safe_edit_message_text(
                "📖 Как пользоваться ботом?\n"
                "🔸 Добавление товара \n"
                "Отправьте боту ссылку на товар с Wildberries и он начнёт отслеживать его цену.\n"
                "🔸 Просмотр товаров\n"
                "В разделе 'Мои товары' вы увидите список всех добавленных ссылок с текущей ценой.\n"
                "🔸 Удаление товара\n"
                "Если товар больше не нужно отслеживать, просто удалите его из списка.\n"
                "🔸 Уведомления\n"
                "Как только цена изменится, бот сразу сообщит вам!\n"
                "🔸 Настройки\n"
                "Вы можете настроить порог уведомлений, тип изменений и валюту отображения цен.\n"
                "❓ Вопросы? Пишите @notjustrita.",
                chat_id,
                message_id,
                reply_markup=InlineKeyboardMarkup().add(
                    InlineKeyboardButton("🔙 Назад", callback_data="main_menu")
                )
            )

    except Exception as e:
        logger.error(f"Ошибка в обработчике callback: {e}")
        try:
            bot.answer_callback_query(
                call.id,
                "⚠️ Произошла ошибка. Пожалуйста, попробуйте позже.",
                show_alert=True
            )
        except:
            pass


def is_message_article(message):
    cleaned_message = message.text

    # Проверяем, что строка состоит только из цифр и имеет длину от 6 до 9 символов
    return cleaned_message.isdigit() and 6 <= len(cleaned_message) <= 9


def get_article(message):
    if is_message_article(message):
        article = message.text
    else:
        url = message.text.strip()
        article = extract_article(url)

    return article


def process_product(message, attempt=1):
    # Проверяем и создаем пользователя если нужно
    chat_id = message.chat.id
    try:
        db.execute(
            "INSERT IGNORE INTO botUser (chat_id, name) VALUES (%s, %s)",
            (chat_id, message.from_user.first_name or "Пользователь"),
            commit=True
        )
    except Exception as e:
        logger.error(f"Ошибка при создании пользователя: {e}")

    article = get_article(message)
    if not article:
        error_msg = safe_send_message(
            chat_id,
            f"❌ Не удалось определить артикул товара. Попытка {attempt}. Попробуйте еще раз или нажмите 'Назад'",
            reply_markup=back_to_menu_markup()
        )
        bot.register_next_step_handler(error_msg, lambda m: process_product(m, attempt + 1))
        return

    # Получаем информацию о товаре
    result = get_cached_price(article, 'rub')  # Используем рубль по умолчанию
    if not result['success']:
        error_msg = safe_send_message(
            chat_id,
            f"❌ Не удалось получить информацию о товаре. Попытка {attempt}. Попробуйте еще раз или нажмите 'Назад'",
            reply_markup=back_to_menu_markup()
        )
        bot.register_next_step_handler(error_msg, lambda m: process_product(m, attempt + 1))
        return

    try:
        # Проверяем, есть ли уже такой товар у пользователя (исправленный запрос)
        exists = db.execute(
            "SELECT 1 FROM product_has_botUser WHERE botUser_chat_id = %s AND product_articule = %s",
            (chat_id, article),
            fetch=True
        )

        if exists:
            safe_send_message(
                chat_id,
                "⚠️ Этот товар уже в вашем списке",
                reply_markup=back_to_menu_markup()
            )
            return
        else:
            # Сначала добавляем товар в таблицу product (если его еще нет)
            db.execute(
                "INSERT IGNORE INTO product (articule, name) VALUES (%s, %s)",
                (article, result['name']),
                commit=True
            )

            # Затем добавляем связь между пользователем и товаром
            db.execute(
                "INSERT INTO product_has_botUser (product_articule, botUser_chat_id) VALUES (%s, %s)",
                (article, chat_id),
                commit=True
            )

            # Затем добавляем/обновляем цену в таблицу price
            update_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            db.execute(
                "INSERT INTO price (articule, initial_price, curent_price, last_check) VALUES (%s, %s, %s, %s) "
                "ON DUPLICATE KEY UPDATE curent_price = VALUES(curent_price), last_check = VALUES(last_check)",
                (article, result['price'], result['price'], update_time),
                commit=True
            )

            safe_send_message(
                chat_id,
                f"✅ Товар добавлен:\n\n"
                f"📦 {result['name']}\n"
                f"💰 Цена: {result['price']}{result['currency_symbol']}\n\n"
                f"Теперь я буду отслеживать изменения цены",
                reply_markup=main_menu()
            )
    except Exception as e:
        error_msg = safe_send_message(
            chat_id,
            f"⚠️ Ошибка при добавлении товара: {str(e)}\nПопробуйте еще раз или нажмите 'Назад'",
            reply_markup=back_to_menu_markup()
        )
        bot.register_next_step_handler(error_msg, lambda m: process_product(m, attempt + 1))


def process_custom_threshold(message):
    """Process custom threshold input"""
    chat_id = message.chat.id

    try:
        new_threshold = int(message.text)
        if 1 <= new_threshold <= 50:
            # Обновляем настройки пользователя
            db.queue_write('''
                UPDATE botUser 
                SET treshold_percent = %s
                WHERE chat_id = %s
            ''', (new_threshold, chat_id))

            # Обновляем кэш
            if chat_id in user_settings_cache:
                _, current_type, current_currency = user_settings_cache[chat_id]
                user_settings_cache[chat_id] = (new_threshold, current_type, current_currency)
            else:
                result = db.execute('''
                    SELECT notification_type, currency FROM botUser WHERE chat_id = %s
                ''', (chat_id,), fetch=True)
                if result:
                    current_type = result[0]['notification_type'] or 'decrease'
                    current_currency = result[0]['currency'] or 'rub'
                    user_settings_cache[chat_id] = (new_threshold, current_type, current_currency)

            currency_symbol = CURRENCIES.get(current_currency, {}).get('symbol', '₽')

            # Показываем подтверждение
            text = (
                f"✅ Новый порог установлен: {new_threshold}%\n\n"
                f"Теперь вы будете получать уведомления при:\n"
            )

            if current_type == 'any':
                text += f"Любом изменении цены ±{new_threshold}% (≤{int(10000 * (1 - new_threshold / 100))}{currency_symbol} или ≥{int(10000 * (1 + new_threshold / 100))}{currency_symbol})"
            elif current_type == 'increase':
                text += f"Росте цены ≥+{new_threshold}% (≥{int(10000 * (1 + new_threshold / 100))}{currency_symbol})"
            else:
                text += f"Падении цены ≤-{new_threshold}% (≤{int(10000 * (1 - new_threshold / 100))}{currency_symbol})"

            safe_send_message(
                chat_id,
                text,
                reply_markup=InlineKeyboardMarkup().add(
                    InlineKeyboardButton("🔙 Назад", callback_data="settings"))
            )
        else:
            error_msg = safe_send_message(
                chat_id,
                "❌ Порог должен быть от 1 до 50%. Пожалуйста, введите корректное значение:",
                reply_markup=InlineKeyboardMarkup().add(
                    InlineKeyboardButton("🔙 Назад", callback_data="change_threshold"))
            )
            bot.register_next_step_handler(error_msg, process_custom_threshold)
    except ValueError:
        error_msg = safe_send_message(
            chat_id,
            "❌ Пожалуйста, введите число от 1 до 50. Попробуйте еще раз:",
            reply_markup=InlineKeyboardMarkup().add(
                InlineKeyboardButton("🔙 Назад", callback_data="change_threshold"))
        )
        bot.register_next_step_handler(error_msg, process_custom_threshold)

@bot.my_chat_member_handler()
def handle_chat_member_update(update):
    if update.new_chat_member.status == 'kicked':
        user_id = update.chat.id
        try:
            # Удаляем пользователя (внешние ключи настроены на CASCADE, так что все его товары и цены тоже удалятся)
            db.execute(
                "DELETE FROM botUser WHERE chat_id = %s",
                (user_id,),
                commit=True
            )

            user_settings_cache.pop(user_id, None)
            logger.info(f"Удалены данные пользователя {user_id} (заблокировал бота)")
        except Exception as e:
            logger.error(f"Ошибка при удалении данных пользователя {user_id}: {e}")

if __name__ == '__main__':
    logger.info("Бот успешно запущен")
    while True:
        try:
            bot.polling(none_stop=True, interval=1, timeout=20)
        except Exception as e:
            logger.error(f"Ошибка polling: {e}")
            time.sleep(10)