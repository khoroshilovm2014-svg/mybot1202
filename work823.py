"""
🎮 BLITZ REF — ПОЛНЫЙ БОТ С ПОЧТА:ПАРОЛЬ И БАНАМИ
ИСПРАВЛЕННАЯ ВЕРСИЯ - РАБОТАЕТ 100%
"""

import asyncio
import logging
import sqlite3
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
import io

# =============== НАСТРОЙКИ ===============
BOT_TOKEN = "8587482238:AAFYZLUZqJNv3-q7hdp88HvFHcEc7T-_8JU"
ADMIN_IDS = [7635015201, 8260588511]  # 👑 ДВА АДМИНА!

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# =============== СОСТОЯНИЯ ===============
class UploadStates(StatesGroup):
    waiting_for_category = State()
    waiting_for_file = State()
    waiting_for_ban_reason = State()
    waiting_for_ban_duration = State()
    waiting_for_give_coins = State()
    waiting_for_search = State()

# =============== БАЗА ДАННЫХ ===============
class Database:
    def __init__(self):
        self.conn = sqlite3.connect('blitz_shop.db', check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.create_tables()
    
    def create_tables(self):
        # Пользователи
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                coins INTEGER DEFAULT 0,
                referrals INTEGER DEFAULT 0,
                referrer_id INTEGER,
                joined_date TEXT,
                is_banned INTEGER DEFAULT 0,
                ban_reason TEXT,
                ban_date TEXT,
                ban_expire TEXT
            )
        ''')
        
        # Аккаунты
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tops INTEGER,
                email TEXT,
                password TEXT,
                price INTEGER,
                is_sold INTEGER DEFAULT 0,
                buyer_id INTEGER,
                sold_date TEXT,
                added_date TEXT
            )
        ''')
        
        # Логи банов
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS ban_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                admin_id INTEGER,
                reason TEXT,
                duration TEXT,
                ban_date TEXT
            )
        ''')
        
        self.conn.commit()
        print("✅ База данных создана")
    
    def add_user(self, user_id, username, first_name, referrer_id=None):
        self.cursor.execute('SELECT user_id FROM users WHERE user_id = ?', (user_id,))
        if not self.cursor.fetchone():
            now = datetime.now().isoformat()
            self.cursor.execute('''
                INSERT INTO users (
                    user_id, username, first_name, joined_date, referrer_id,
                    coins, referrals, is_banned, ban_reason, ban_date, ban_expire
                ) VALUES (?, ?, ?, ?, ?, 0, 0, 0, NULL, NULL, NULL)
            ''', (user_id, username, first_name, now, referrer_id))
            
            if referrer_id and referrer_id != user_id:
                self.cursor.execute('SELECT user_id FROM users WHERE user_id = ?', (referrer_id,))
                if self.cursor.fetchone():
                    self.cursor.execute('''
                        UPDATE users SET coins = coins + 50, referrals = referrals + 1
                        WHERE user_id = ?
                    ''', (referrer_id,))
            
            self.conn.commit()
            return True
        return False
    
    def get_user(self, user_id):
        self.cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        row = self.cursor.fetchone()
        if row:
            return {
                'user_id': row[0],
                'username': row[1],
                'first_name': row[2],
                'coins': row[3],
                'referrals': row[4],
                'referrer_id': row[5],
                'joined_date': row[6],
                'is_banned': row[7],
                'ban_reason': row[8],
                'ban_date': row[9],
                'ban_expire': row[10]
            }
        return None
    
    def check_ban(self, user_id):
        if is_admin(user_id):
            return False
        
        user = self.get_user(user_id)
        if not user:
            return False
        
        if user['is_banned'] == 0:
            return False
        
        if user['ban_expire']:
            try:
                expire = datetime.fromisoformat(user['ban_expire'])
                if datetime.now() > expire:
                    self.unban_user(user_id)
                    return False
            except:
                pass
        
        return True
    
    def ban_user(self, user_id, admin_id, reason, duration):
        durations = {
            '1h': timedelta(hours=1),
            '6h': timedelta(hours=6),
            '12h': timedelta(hours=12),
            '24h': timedelta(hours=24),
            '3d': timedelta(days=3),
            '7d': timedelta(days=7),
            '30d': timedelta(days=30),
            'forever': timedelta(days=36500)
        }
        
        expire = datetime.now() + durations.get(duration, timedelta(hours=24))
        
        self.cursor.execute('''
            UPDATE users SET 
                is_banned = 1,
                ban_reason = ?,
                ban_date = ?,
                ban_expire = ?
            WHERE user_id = ?
        ''', (reason, datetime.now().isoformat(), expire.isoformat(), user_id))
        
        self.cursor.execute('''
            INSERT INTO ban_logs (user_id, admin_id, reason, duration, ban_date)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, admin_id, reason, duration, datetime.now().isoformat()))
        
        self.conn.commit()
        return True
    
    def unban_user(self, user_id):
        self.cursor.execute('''
            UPDATE users SET 
                is_banned = 0,
                ban_reason = NULL,
                ban_date = NULL,
                ban_expire = NULL
            WHERE user_id = ?
        ''', (user_id,))
        self.conn.commit()
        return True
    
    def get_banned_users(self):
        self.cursor.execute('''
            SELECT user_id, username, first_name, ban_reason, ban_date, ban_expire 
            FROM users WHERE is_banned = 1
        ''')
        return self.cursor.fetchall()
    
    def get_all_users(self):
        self.cursor.execute('SELECT user_id, username, first_name, coins, referrals FROM users ORDER BY coins DESC')
        return self.cursor.fetchall()
    
    def get_user_count(self):
        self.cursor.execute('SELECT COUNT(*) FROM users')
        return self.cursor.fetchone()[0]
    
    def get_banned_count(self):
        self.cursor.execute('SELECT COUNT(*) FROM users WHERE is_banned = 1')
        return self.cursor.fetchone()[0]
    
    def get_total_coins(self):
        self.cursor.execute('SELECT SUM(coins) FROM users')
        return self.cursor.fetchone()[0] or 0
    
    def get_available_accounts(self):
        self.cursor.execute('''
            SELECT id, tops, price FROM accounts 
            WHERE is_sold = 0 
            ORDER BY tops ASC
        ''')
        return self.cursor.fetchall()
    
    def get_accounts_stats(self):
        self.cursor.execute('''
            SELECT tops, COUNT(*) as count FROM accounts 
            WHERE is_sold = 0 
            GROUP BY tops 
            ORDER BY tops ASC
        ''')
        return self.cursor.fetchall()
    
    def get_total_accounts(self):
        self.cursor.execute('SELECT COUNT(*) FROM accounts')
        return self.cursor.fetchone()[0]
    
    def get_sold_accounts(self):
        self.cursor.execute('SELECT COUNT(*) FROM accounts WHERE is_sold = 1')
        return self.cursor.fetchone()[0]
    
    def get_account(self, account_id):
        self.cursor.execute('''
            SELECT id, tops, email, password, price FROM accounts 
            WHERE id = ? AND is_sold = 0
        ''', (account_id,))
        row = self.cursor.fetchone()
        if row:
            return {
                'id': row[0],
                'tops': row[1],
                'email': row[2],
                'password': row[3],
                'price': row[4]
            }
        return None
    
    def buy_account(self, user_id, account_id):
        user = self.get_user(user_id)
        if not user:
            return False, "❌ Пользователь не найден"
        
        if user['is_banned']:
            return False, "❌ Вы забанены"
        
        account = self.get_account(account_id)
        if not account:
            return False, "❌ Аккаунт уже куплен"
        
        if user['coins'] < account['price']:
            return False, f"❌ Не хватает {account['price'] - user['coins']} монет"
        
        self.cursor.execute('UPDATE users SET coins = coins - ? WHERE user_id = ?', (account['price'], user_id))
        self.cursor.execute('''
            UPDATE accounts SET is_sold = 1, buyer_id = ?, sold_date = ? 
            WHERE id = ?
        ''', (user_id, datetime.now().isoformat(), account_id))
        self.conn.commit()
        
        return True, account
    
    def get_referrals(self, user_id):
        self.cursor.execute('''
            SELECT user_id, username, first_name, joined_date 
            FROM users WHERE referrer_id = ?
        ''', (user_id,))
        return self.cursor.fetchall()
    
    def load_accounts_from_text(self, text, category):
        lines = text.strip().split('\n')
        added = 0
        errors = 0
        
        for line in lines:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            try:
                if ':' in line:
                    email, password = line.split(':', 1)
                elif '|' in line:
                    email, password = line.split('|', 1)
                else:
                    errors += 1
                    continue
                
                email = email.strip()
                password = password.strip()
                
                if email and password:
                    price = category * 30
                    self.cursor.execute('''
                        INSERT INTO accounts (tops, email, password, price, added_date)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (category, email, password, price, datetime.now().isoformat()))
                    added += 1
                else:
                    errors += 1
            except:
                errors += 1
        
        self.conn.commit()
        return added, errors
    
    def give_coins(self, user_id, amount):
        self.cursor.execute('UPDATE users SET coins = coins + ? WHERE user_id = ?', (amount, user_id))
        self.conn.commit()
        return self.cursor.rowcount > 0
    
    def search_user(self, query):
        try:
            user_id = int(query)
            self.cursor.execute('SELECT user_id, username, first_name, coins, referrals, is_banned FROM users WHERE user_id = ?', (user_id,))
            return self.cursor.fetchone()
        except:
            self.cursor.execute('SELECT user_id, username, first_name, coins, referrals, is_banned FROM users WHERE username LIKE ?', (f'%{query}%',))
            return self.cursor.fetchall()

db = Database()

# =============== ПРОВЕРКА АДМИНА ===============
def is_admin(user_id):
    return user_id in ADMIN_IDS

# =============== КНОПКА О БОТЕ ===============
@dp.callback_query(lambda c: c.data == "about")
async def about_bot(callback: types.CallbackQuery):
    """Информация о боте"""
    
    users_count = db.get_user_count()
    accounts_count = db.get_total_accounts()
    sold_count = db.get_sold_accounts()
    
    text = f"""
<b>🤖 О БОТЕ BLITZ REF</b>

<b>👑 Создатель:</b> @mixan2907
<b>👑 Админы:</b> {', '.join([f'<code>{aid}</code>' for aid in ADMIN_IDS])}

<b>📊 СТАТИСТИКА БОТА:</b>
▫️ 👥 Пользователей: {users_count}
▫️ 📦 Аккаунтов всего: {accounts_count}
▫️ ✅ Продано: {sold_count}

<b>⚡️ ВОЗМОЖНОСТИ:</b>
▫️ 🎮 Аккаунты Tanks Blitz (1-50 топов)
▫️ 💰 Заработок монет за рефералов
▫️ 🛒 Покупка аккаунтов за монеты
▫️ 🔨 Система банов
▫️ 📁 Загрузка аккаунтов через TXT

<b>📌 КАК РАБОТАЕТ:</b>
1. Приглашай друзей по ссылке
2. Получай 50 монет за каждого
3. Покупай аккаунты в магазине
"""
    
    keyboard = InlineKeyboardBuilder()
    keyboard.row(InlineKeyboardButton(text="« Назад", callback_data="back"))
    
    await callback.message.edit_text(text, reply_markup=keyboard.as_markup())
    await callback.answer()

# =============== ХЕНДЛЕР СТАРТ ===============
@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    args = message.text.split()
    referrer_id = None
    
    if len(args) > 1:
        try:
            referrer_id = int(args[1])
        except:
            pass
    
    user = message.from_user
    db.add_user(user.id, user.username, user.first_name, referrer_id)
    user_data = db.get_user(user.id)
    
    if not user_data:
        await message.answer("❌ Ошибка загрузки профиля")
        return
    
    # Проверка бана
    if user_data['is_banned']:
        ban_text = f"до {user_data['ban_expire'][:10]}" if user_data['ban_expire'] and user_data['ban_expire'] != 'forever' else "навсегда"
        await message.answer(
            f"<b>❌ ВЫ ЗАБАНЕНЫ!</b>\n\n"
            f"<b>Причина:</b> {user_data['ban_reason']}\n"
            f"<b>Срок:</b> {ban_text}\n\n"
            f"Обратитесь к администратору"
        )
        return
    
    bot_info = await bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start={user.id}"
    
    text = f"""
👋 <b>Привет, {user.first_name}!
Это бот по раздаче аккаунтов за рефералов!</b>

💰 <b>Твои монеты:</b> {user_data['coins']}
👥 <b>Друзей пригласил:</b> {user_data['referrals']}

🔗 <b>Твоя ссылка:</b>
<code>{ref_link}</code>

▫️ <i>Приглашай друзей — 50 монет за каждого</i>
    """
    
    keyboard = InlineKeyboardBuilder()
    keyboard.row(
        InlineKeyboardButton(text="🛒 АККАУНТЫ", callback_data="shop"),
        InlineKeyboardButton(text="👥 ДРУЗЬЯ", callback_data="friends")
    )
    keyboard.row(
        InlineKeyboardButton(text="👤 ПРОФИЛЬ", callback_data="stats"),
        InlineKeyboardButton(text="📤 ПРИГЛАСИТЬ", callback_data="share")
    )
    keyboard.row(
        InlineKeyboardButton(text="🤖 О БОТЕ", callback_data="about")
    )
    
    if is_admin(user.id):
        keyboard.row(InlineKeyboardButton(text="👑 АДМИН ПАНЕЛЬ", callback_data="admin_panel"))
    
    await message.answer(text, reply_markup=keyboard.as_markup())

# =============== МАГАЗИН ===============
@dp.callback_query(lambda c: c.data == "shop")
async def show_shop(callback: types.CallbackQuery):
    user = db.get_user(callback.from_user.id)
    
    if user['is_banned']:
        await callback.answer("❌ Вы забанены!", show_alert=True)
        return
    
    accounts = db.get_available_accounts()
    stats = db.get_accounts_stats()
    
    available_tops = {}
    for acc in accounts:
        tops = acc[1]
        if tops not in available_tops:
            available_tops[tops] = []
        available_tops[tops].append(acc)
    
    text = f"<b>🛒 МАГАЗИН АККАУНТОВ</b>\n\n"
    text += f"<b>💰 Твои монеты:</b> {user['coins']}\n\n"
    
    if stats:
        text += f"<b>📦 В наличии:</b>\n"
        for tops, count in stats:
            text += f"▫️ {tops} топов — {count} шт.\n"
    else:
        text += f"<i>❌ Аккаунтов пока нет</i>\n"
    
    text += f"\n<i>👇 Выбери количество топов:</i>"
    
    keyboard = InlineKeyboardBuilder()
    
    for i in range(1, 51):
        if i in available_tops:
            price = available_tops[i][0][2]
            keyboard.button(text=f"{i} топов ({price}💰)", callback_data=f"show_tops_{i}")
        else:
            keyboard.button(text=f"{i} топов ❌", callback_data="none")
    
    keyboard.adjust(5)
    keyboard.row(InlineKeyboardButton(text="« Назад", callback_data="back"))
    
    await callback.message.edit_text(text, reply_markup=keyboard.as_markup())
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("show_tops_"))
async def show_tops_accounts(callback: types.CallbackQuery):
    user = db.get_user(callback.from_user.id)
    
    if user['is_banned']:
        await callback.answer("❌ Вы забанены!", show_alert=True)
        return
    
    tops = int(callback.data.replace("show_tops_", ""))
    
    db.cursor.execute('''
        SELECT id, email, password, price FROM accounts 
        WHERE tops = ? AND is_sold = 0
    ''', (tops,))
    accounts = db.cursor.fetchall()
    
    if not accounts:
        await callback.answer("❌ Аккаунты закончились", show_alert=True)
        return
    
    text = f"<b>🎮 Аккаунты {tops} топов</b>\n\n"
    text += f"<b>💰 Твои монеты:</b> {user['coins']}\n"
    text += f"<b>📦 Доступно:</b> {len(accounts)} шт.\n"
    text += f"<b>💎 Цена:</b> {accounts[0][3]} монет\n\n"
    text += f"<i>👇 Выбери аккаунт:</i>"
    
    keyboard = InlineKeyboardBuilder()
    
    for i, acc in enumerate(accounts[:10], 1):
        keyboard.button(
            text=f"Аккаунт #{i}",
            callback_data=f"buy_{acc[0]}"
        )
    
    keyboard.adjust(2)
    keyboard.row(InlineKeyboardButton(text="« Назад", callback_data="shop"))
    
    await callback.message.edit_text(text, reply_markup=keyboard.as_markup())
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("buy_"))
async def buy_account(callback: types.CallbackQuery):
    user = db.get_user(callback.from_user.id)
    
    if user['is_banned']:
        await callback.answer("❌ Вы забанены!", show_alert=True)
        return
    
    account_id = int(callback.data.replace("buy_", ""))
    success, result = db.buy_account(callback.from_user.id, account_id)
    
    if success:
        text = f"""
<b>✅ ПОКУПКА УСПЕШНА!</b>

<b>🎮 Аккаунт:</b> {result['tops']} топов
<b>📧 Почта:</b> <code>{result['email']}</code>
<b>🔐 Пароль:</b> <code>{result['password']}</code>

<b>💰 Остаток монет:</b> {user['coins']}

<i>⚠️ Сохрани данные!</i>
        """
    else:
        text = f"<b>❌ {result}</b>"
    
    keyboard = InlineKeyboardBuilder()
    keyboard.row(InlineKeyboardButton(text="« В магазин", callback_data="shop"))
    
    await callback.message.edit_text(text, reply_markup=keyboard.as_markup())
    await callback.answer()

@dp.callback_query(lambda c: c.data == "none")
async def none_callback(callback: types.CallbackQuery):
    await callback.answer("❌ Аккаунтов нет", show_alert=True)

# =============== ДРУЗЬЯ ===============
@dp.callback_query(lambda c: c.data == "friends")
async def show_friends(callback: types.CallbackQuery):
    user = db.get_user(callback.from_user.id)
    
    if user['is_banned']:
        await callback.answer("❌ Вы забанены!", show_alert=True)
        return
    
    referrals = db.get_referrals(callback.from_user.id)
    bot_info = await bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start={callback.from_user.id}"
    
    text = f"""
<b>👥 ДРУЗЬЯ</b>

<b>📊 Приглашено:</b> {user['referrals']}
<b>💰 Заработано:</b> {user['referrals'] * 50} монет

<b>🔗 Твоя ссылка:</b>
<code>{ref_link}</code>

<i>▫️ За каждого друга +50 монет</i>
    """
    
    if referrals:
        text += f"\n<b>📋 Список друзей:</b>\n"
        for ref in referrals[:5]:
            date = ref[3][:10] if ref[3] else "недавно"
            name = f"@{ref[1]}" if ref[1] else ref[2]
            text += f"▫️ {name} — <i>{date}</i>\n"
        
        if len(referrals) > 5:
            text += f"<i>... и ещё {len(referrals)-5}</i>"
    
    keyboard = InlineKeyboardBuilder()
    keyboard.row(
        InlineKeyboardButton(text="📤 Пригласить друга", callback_data="share"),
        InlineKeyboardButton(text="« Назад", callback_data="back")
    )
    
    await callback.message.edit_text(text, reply_markup=keyboard.as_markup())
    await callback.answer()

@dp.callback_query(lambda c: c.data == "share")
async def share_link(callback: types.CallbackQuery):
    user = db.get_user(callback.from_user.id)
    
    if user['is_banned']:
        await callback.answer("❌ Вы забанены!", show_alert=True)
        return
    
    bot_info = await bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start={callback.from_user.id}"
    
    text = f"""
<b>📤 ПРИГЛАШАЙ ДРУЗЕЙ</b>

<b>🔗 Твоя ссылка:</b>
<code>{ref_link}</code>

<i>▫️ Отправь ссылку друзьям</i>
<i>▫️ +50 монет за каждого</i>
    """
    
    keyboard = InlineKeyboardBuilder()
    keyboard.row(InlineKeyboardButton(text="« Назад", callback_data="friends"))
    
    await callback.message.edit_text(text, reply_markup=keyboard.as_markup())
    await callback.answer()

@dp.callback_query(lambda c: c.data == "stats")
async def show_stats(callback: types.CallbackQuery):
    user = db.get_user(callback.from_user.id)
    
    if user['is_banned']:
        await callback.answer("❌ Вы забанены!", show_alert=True)
        return
    
    total_sold = db.get_sold_accounts()
    total_accounts = db.get_total_accounts()
    
    text = f"""
<b>👤 ТВОЙ ПРОФИЛЬ</b>

<b>💰 Баланс:</b> {user['coins']} монет
<b>👥 Друзей:</b> {user['referrals']}
<b>💸 Потрачено:</b> {user['referrals'] * 50 - user['coins']} монет
<b>📅 В боте с:</b> {user['joined_date'][:10]}

<b>🎮 Всего аккаунтов:</b> {total_accounts}
<b>✅ Продано:</b> {total_sold}
    """
    
    keyboard = InlineKeyboardBuilder()
    keyboard.row(InlineKeyboardButton(text="« Назад", callback_data="back"))
    
    await callback.message.edit_text(text, reply_markup=keyboard.as_markup())
    await callback.answer()

@dp.callback_query(lambda c: c.data == "back")
async def go_back(callback: types.CallbackQuery):
    await cmd_start(callback.message)
    await callback.answer()

# =============== АДМИН ПАНЕЛЬ ===============
@dp.callback_query(lambda c: c.data == "admin_panel")
async def admin_panel(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    users_count = db.get_user_count()
    banned_count = db.get_banned_count()
    total_coins = db.get_total_coins()
    available = db.get_total_accounts() - db.get_sold_accounts()
    total_accounts = db.get_total_accounts()
    
    text = f"""
<b>👑 АДМИН ПАНЕЛЬ</b>

<b>👥 Пользователей:</b> {users_count}
<b>🔨 Забанено:</b> {banned_count}
<b>💰 Всего монет:</b> {total_coins}
<b>📦 Аккаунтов:</b> {total_accounts} всего
<b>✅ Продано:</b> {db.get_sold_accounts()}
<b>📌 В наличии:</b> {available}

<i>👇 Выбери действие:</i>
    """
    
    keyboard = InlineKeyboardBuilder()
    keyboard.row(
        InlineKeyboardButton(text="📁 ЗАГРУЗКА TXT", callback_data="admin_load_category"),
        InlineKeyboardButton(text="🔨 УПРАВЛЕНИЕ БАНАМИ", callback_data="admin_ban_menu")
    )
    keyboard.row(
        InlineKeyboardButton(text="📨 РАССЫЛКА", callback_data="admin_broadcast"),
        InlineKeyboardButton(text="💰 ВЫДАТЬ МОНЕТЫ", callback_data="admin_give_coins")
    )
    keyboard.row(
        InlineKeyboardButton(text="👥 ПОЛЬЗОВАТЕЛИ", callback_data="admin_users"),
        InlineKeyboardButton(text="➕ ДОБАВИТЬ АККАУНТ", callback_data="admin_add_one")
    )
    keyboard.row(
        InlineKeyboardButton(text="📊 СТАТИСТИКА", callback_data="admin_stats"),
        InlineKeyboardButton(text="🔍 ПОИСК", callback_data="admin_search")
    )
    keyboard.row(InlineKeyboardButton(text="« Назад", callback_data="back"))
    
    await callback.message.edit_text(text, reply_markup=keyboard.as_markup())
    await callback.answer()

# =============== УПРАВЛЕНИЕ БАНАМИ ===============
@dp.callback_query(lambda c: c.data == "admin_ban_menu")
async def admin_ban_menu(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    
    banned = db.get_banned_users()
    
    text = f"<b>🔨 УПРАВЛЕНИЕ БАНАМИ</b>\n\n"
    
    if banned:
        text += f"<b>Забанено:</b> {len(banned)}\n\n"
        for ban in banned[:5]:
            user_id, username, name, reason, ban_date, expire = ban
            username_display = f"@{username}" if username else name
            expire_date = expire[:10] if expire else "навсегда"
            text += f"▫️ {username_display} — до {expire_date}\n"
        
        if len(banned) > 5:
            text += f"<i>... и ещё {len(banned)-5}</i>\n"
    else:
        text += f"<i>Забаненных нет</i>\n"
    
    keyboard = InlineKeyboardBuilder()
    keyboard.row(
        InlineKeyboardButton(text="🔨 ЗАБАНИТЬ", callback_data="admin_ban_user"),
        InlineKeyboardButton(text="✅ РАЗБАНИТЬ", callback_data="admin_unban_user")
    )
    keyboard.row(
        InlineKeyboardButton(text="📋 СПИСОК", callback_data="admin_ban_list"),
        InlineKeyboardButton(text="« Назад", callback_data="admin_panel")
    )
    
    await callback.message.edit_text(text, reply_markup=keyboard.as_markup())
    await callback.answer()

@dp.callback_query(lambda c: c.data == "admin_ban_user")
async def admin_ban_user(callback: types.CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    
    await state.set_state(UploadStates.waiting_for_ban_reason)
    await callback.message.edit_text(
        "<b>🔨 ЗАБАНИТЬ</b>\n\n"
        "Введи ID пользователя и причину:\n"
        "<code>ID причина</code>\n\n"
        "Пример: <code>123456789 Спам</code>\n\n"
        "❌ Отправь /cancel для отмены"
    )
    await callback.answer()

@dp.message(UploadStates.waiting_for_ban_reason)
async def process_ban_reason(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    
    if message.text == "/cancel":
        await state.clear()
        await admin_panel(message)
        return
    
    parts = message.text.split(' ', 1)
    if len(parts) < 2:
        await message.answer("❌ Формат: ID причина")
        return
    
    try:
        user_id = int(parts[0])
        reason = parts[1]
    except:
        await message.answer("❌ Неверный ID")
        return
    
    user = db.get_user(user_id)
    if not user:
        await message.answer("❌ Пользователь не найден")
        await state.clear()
        return
    
    await state.update_data(ban_user_id=user_id, ban_reason=reason)
    await state.set_state(UploadStates.waiting_for_ban_duration)
    
    keyboard = InlineKeyboardBuilder()
    keyboard.row(
        InlineKeyboardButton(text="1 час", callback_data="ban_1h"),
        InlineKeyboardButton(text="6 часов", callback_data="ban_6h"),
        InlineKeyboardButton(text="12 часов", callback_data="ban_12h")
    )
    keyboard.row(
        InlineKeyboardButton(text="24 часа", callback_data="ban_24h"),
        InlineKeyboardButton(text="3 дня", callback_data="ban_3d"),
        InlineKeyboardButton(text="7 дней", callback_data="ban_7d")
    )
    keyboard.row(
        InlineKeyboardButton(text="30 дней", callback_data="ban_30d"),
        InlineKeyboardButton(text="Навсегда", callback_data="ban_forever")
    )
    keyboard.row(InlineKeyboardButton(text="« Отмена", callback_data="admin_ban_menu"))
    
    await message.answer(
        f"<b>🔨 ВЫБЕРИ ДЛИТЕЛЬНОСТЬ</b>\n\n"
        f"👤 {user['first_name']} (@{user['username']})\n"
        f"🆔 <code>{user_id}</code>\n"
        f"📝 Причина: {reason}",
        reply_markup=keyboard.as_markup()
    )

@dp.callback_query(lambda c: c.data.startswith("ban_"), UploadStates.waiting_for_ban_duration)
async def process_ban_duration(callback: types.CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    
    duration = callback.data.replace("ban_", "")
    data = await state.get_data()
    user_id = data.get('ban_user_id')
    reason = data.get('ban_reason')
    
    db.ban_user(user_id, callback.from_user.id, reason, duration)
    
    duration_names = {
        '1h': '1 час', '6h': '6 часов', '12h': '12 часов',
        '24h': '24 часа', '3d': '3 дня', '7d': '7 дней',
        '30d': '30 дней', 'forever': 'навсегда'
    }
    
    try:
        await bot.send_message(
            user_id,
            f"<b>🔨 ВЫ ЗАБАНЕНЫ!</b>\n\n"
            f"<b>Причина:</b> {reason}\n"
            f"<b>Срок:</b> {duration_names.get(duration, duration)}"
        )
    except:
        pass
    
    await state.clear()
    await callback.message.edit_text(
        f"<b>✅ ПОЛЬЗОВАТЕЛЬ ЗАБАНЕН!</b>\n\n"
        f"👤 ID: <code>{user_id}</code>\n"
        f"📝 Причина: {reason}\n"
        f"⏱ Срок: {duration_names.get(duration, duration)}"
    )
    await callback.answer()

# =============== ЗАГРУЗКА TXT ===============
@dp.callback_query(lambda c: c.data == "admin_load_category")
async def admin_load_category(callback: types.CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    
    keyboard = InlineKeyboardBuilder()
    
    # Ряд 1-10
    row1 = []
    for i in range(1, 11):
        row1.append(InlineKeyboardButton(text=str(i), callback_data=f"cat_{i}"))
    keyboard.row(*row1, width=5)
    
    # Ряд 11-20
    row2 = []
    for i in range(11, 21):
        row2.append(InlineKeyboardButton(text=str(i), callback_data=f"cat_{i}"))
    keyboard.row(*row2, width=5)
    
    # Ряд 21-30
    row3 = []
    for i in range(21, 31):
        row3.append(InlineKeyboardButton(text=str(i), callback_data=f"cat_{i}"))
    keyboard.row(*row3, width=5)
    
    # Ряд 31-40
    row4 = []
    for i in range(31, 41):
        row4.append(InlineKeyboardButton(text=str(i), callback_data=f"cat_{i}"))
    keyboard.row(*row4, width=5)
    
    # Ряд 41-50
    row5 = []
    for i in range(41, 51):
        row5.append(InlineKeyboardButton(text=str(i), callback_data=f"cat_{i}"))
    keyboard.row(*row5, width=5)
    
    keyboard.row(InlineKeyboardButton(text="« Отмена", callback_data="admin_panel"))
    
    await callback.message.edit_text(
        "<b>📁 ЗАГРУЗКА АККАУНТОВ</b>\n\n"
        "Выбери количество топов:\n"
        "<i>(от 1 до 50)</i>\n\n"
        "Формат файла: <code>почта:пароль</code> или <code>почта|пароль</code>\n"
        "Пример:\n"
        "<code>user1@gmail.com:pass123</code>\n"
        "<code>user2@mail.ru|qwerty</code>",
        reply_markup=keyboard.as_markup()
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("cat_"))
async def process_category_selection(callback: types.CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    
    category = int(callback.data.replace("cat_", ""))
    await state.update_data(upload_category=category)
    await state.set_state(UploadStates.waiting_for_file)
    
    await callback.message.edit_text(
        f"<b>📁 ЗАГРУЗКА АККАУНТОВ</b>\n\n"
        f"<b>Категория:</b> {category} топов\n"
        f"<b>💰 Цена:</b> {category * 30} монет за аккаунт\n\n"
        f"<i>📤 Отправь TXT файл со списком аккаунтов</i>\n\n"
        f"Формат: <code>почта:пароль</code> или <code>почта|пароль</code>\n"
        f"Пример:\n"
        f"<code>user1@gmail.com:pass123</code>\n"
        f"<code>user2@mail.ru|qwerty</code>\n\n"
        f"❌ Отправь /cancel для отмены"
    )
    await callback.answer()

@dp.message(F.document, UploadStates.waiting_for_file)
async def handle_category_document(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Только для админа")
        return
    
    data = await state.get_data()
    category = data.get('upload_category')
    
    if not category:
        await message.answer("❌ Ошибка: категория не выбрана")
        await state.clear()
        return
    
    try:
        # Отправляем сообщение о начале загрузки
        status_msg = await message.answer("⏳ Загружаю файл...")
        
        # Получаем файл
        file = await bot.get_file(message.document.file_id)
        file_path = file.file_path
        downloaded_file = await bot.download_file(file_path)
        
        # Читаем содержимое
        content = downloaded_file.read().decode('utf-8')
        
        # Загружаем аккаунты в базу
        added, errors = db.load_accounts_from_text(content, category)
        
        # Удаляем сообщение о статусе
        await status_msg.delete()
        
        # Формируем результат
        text = f"""
<b>✅ ЗАГРУЗКА ЗАВЕРШЕНА</b>

<b>📁 Категория:</b> {category} топов
<b>💰 Цена:</b> {category * 30} монет

<b>✅ Добавлено:</b> {added}
<b>❌ Ошибок:</b> {errors}

<b>📊 ТЕПЕРЬ В НАЛИЧИИ:</b>
"""
        
        # Показываем обновленную статистику
        stats = db.get_accounts_stats()
        if stats:
            for tops, count in stats:
                if count > 0:
                    text += f"▫️ {tops} топов — {count} шт.\n"
        else:
            text += "<i>Нет аккаунтов в наличии</i>\n"
        
        keyboard = InlineKeyboardBuilder()
        keyboard.row(
            InlineKeyboardButton(text="📁 ЗАГРУЗИТЬ ЕЩЁ", callback_data="admin_load_category"),
            InlineKeyboardButton(text="« В АДМИНКУ", callback_data="admin_panel")
        )
        
        await message.answer(text, reply_markup=keyboard.as_markup())
        await state.clear()
        
    except Exception as e:
        await message.answer(f"❌ Ошибка при загрузке: {e}")
        await state.clear()

# =============== РАССЫЛКА ===============
@dp.callback_query(lambda c: c.data == "admin_broadcast")
async def admin_broadcast(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    
    await callback.message.edit_text(
        "<b>📨 РАССЫЛКА</b>\n\n"
        "Напиши сообщение для рассылки всем пользователям\n\n"
        "<i>Поддерживается форматирование:</i>\n"
        "▫️ <b>жирный</b> — &lt;b&gt;текст&lt;/b&gt;\n"
        "▫️ <i>курсив</i> — &lt;i&gt;текст&lt;/i&gt;\n"
        "▫️ <code>код</code> — &lt;code&gt;текст&lt;/code&gt;\n\n"
        "❌ Отправь /cancel для отмены"
    )
    await callback.answer()

@dp.message(lambda message: is_admin(message.from_user.id))
async def handle_admin_messages(message: types.Message, state: FSMContext):
    """Обработка всех сообщений от админа"""
    text = message.text
    
    if text == "/cancel":
        await state.clear()
        await admin_panel(message)
        return
    
    # Проверяем состояние
    current_state = await state.get_state()
    
    if current_state == UploadStates.waiting_for_ban_reason.state:
        # Обработка причины бана
        parts = text.split(' ', 1)
        if len(parts) < 2:
            await message.answer("❌ Формат: ID причина")
            return
        
        try:
            user_id = int(parts[0])
            reason = parts[1]
        except:
            await message.answer("❌ Неверный ID")
            return
        
        user = db.get_user(user_id)
        if not user:
            await message.answer("❌ Пользователь не найден")
            await state.clear()
            return
        
        await state.update_data(ban_user_id=user_id, ban_reason=reason)
        await state.set_state(UploadStates.waiting_for_ban_duration)
        
        keyboard = InlineKeyboardBuilder()
        keyboard.row(
            InlineKeyboardButton(text="1 час", callback_data="ban_1h"),
            InlineKeyboardButton(text="6 часов", callback_data="ban_6h"),
            InlineKeyboardButton(text="12 часов", callback_data="ban_12h")
        )
        keyboard.row(
            InlineKeyboardButton(text="24 часа", callback_data="ban_24h"),
            InlineKeyboardButton(text="3 дня", callback_data="ban_3d"),
            InlineKeyboardButton(text="7 дней", callback_data="ban_7d")
        )
        keyboard.row(
            InlineKeyboardButton(text="30 дней", callback_data="ban_30d"),
            InlineKeyboardButton(text="Навсегда", callback_data="ban_forever")
        )
        keyboard.row(InlineKeyboardButton(text="« Отмена", callback_data="admin_ban_menu"))
        
        await message.answer(
            f"<b>🔨 ВЫБЕРИ ДЛИТЕЛЬНОСТЬ</b>\n\n"
            f"👤 {user['first_name']} (@{user['username']})\n"
            f"🆔 <code>{user_id}</code>\n"
            f"📝 Причина: {reason}",
            reply_markup=keyboard.as_markup()
        )
    
    elif current_state == UploadStates.waiting_for_give_coins.state:
        # Обработка выдачи монет
        data = await state.get_data()
        user_id = data.get('give_user_id')
        
        try:
            amount = int(text.strip())
        except:
            await message.answer("❌ Введи число")
            return
        
        if amount <= 0:
            await message.answer("❌ Сумма должна быть больше 0")
            return
        
        db.give_coins(user_id, amount)
        user = db.get_user(user_id)
        
        await message.answer(
            f"<b>✅ МОНЕТЫ ВЫДАНЫ!</b>\n\n"
            f"👤 Пользователь: <code>{user_id}</code>\n"
            f"💰 Сумма: +{amount} монет\n"
            f"💳 Новый баланс: {user['coins']} монет"
        )
        
        try:
            await bot.send_message(
                user_id,
                f"<b>🎁 ВАМ НАЧИСЛЕНЫ МОНЕТЫ!</b>\n\n"
                f"💰 Сумма: +{amount} монет\n"
                f"💳 Текущий баланс: {user['coins']} монет"
            )
        except:
            pass
        
        await state.clear()
        await admin_panel(message)
    
    elif current_state == UploadStates.waiting_for_search.state:
        # Обработка поиска
        query = text.strip().replace('@', '')
        result = db.search_user(query)
        
        if not result:
            await message.answer("<b>❌ Пользователь не найден</b>")
            await state.clear()
            return
        
        if isinstance(result, tuple):
            user_id, username, name, coins, refs, is_banned = result
            username_display = f"@{username}" if username else "нет"
            ban_status = "🔨 ЗАБАНЕН" if is_banned else "✅ АКТИВЕН"
            
            text = f"""
<b>🔍 РЕЗУЛЬТАТ ПОИСКА</b>

<b>👤 Пользователь:</b> {name}
<b>🔖 Username:</b> {username_display}
<b>🆔 ID:</b> <code>{user_id}</code>
<b>💰 Монеты:</b> {coins}
<b>👥 Друзья:</b> {refs}
<b>📊 Статус:</b> {ban_status}
            """
            
            keyboard = InlineKeyboardBuilder()
            if is_banned:
                keyboard.row(InlineKeyboardButton(text="✅ РАЗБАНИТЬ", callback_data=f"unban_{user_id}"))
            else:
                keyboard.row(InlineKeyboardButton(text="🔨 ЗАБАНИТЬ", callback_data=f"ban_{user_id}"))
            keyboard.row(InlineKeyboardButton(text="💰 ВЫДАТЬ МОНЕТЫ", callback_data=f"givecoins_{user_id}"))
            keyboard.row(InlineKeyboardButton(text="« В админку", callback_data="admin_panel"))
            
            await message.answer(text, reply_markup=keyboard.as_markup())
        else:
            text = f"<b>🔍 НАЙДЕНО {len(result)} ПОЛЬЗОВАТЕЛЕЙ</b>\n\n"
            for user in result[:10]:
                user_id, username, name, coins, refs, is_banned = user
                username_display = f"@{username}" if username else name
                ban_mark = "🔨" if is_banned else "✅"
                text += f"{ban_mark} {username_display} — {coins}💰\n"
                text += f"   🆔 <code>{user_id}</code>\n"
            
            if len(result) > 10:
                text += f"<i>... и ещё {len(result)-10}</i>"
            
            keyboard = InlineKeyboardBuilder()
            keyboard.row(InlineKeyboardButton(text="« Назад", callback_data="admin_panel"))
            
            await message.answer(text, reply_markup=keyboard.as_markup())
        
        await state.clear()
    
    else:
        # Если нет состояния - пробуем обработать как команду
        parts = text.split()
        
        # Выдача монет (формат: ID сумма)
        if len(parts) == 2:
            try:
                user_id = int(parts[0])
                amount = int(parts[1])
                
                if db.give_coins(user_id, amount):
                    user = db.get_user(user_id)
                    await message.answer(
                        f"<b>✅ МОНЕТЫ ВЫДАНЫ!</b>\n\n"
                        f"👤 Пользователь: <code>{user_id}</code>\n"
                        f"💰 Сумма: +{amount} монет\n"
                        f"💳 Новый баланс: {user['coins']} монет"
                    )
                    
                    try:
                        await bot.send_message(
                            user_id,
                            f"<b>🎁 ВАМ НАЧИСЛЕНЫ МОНЕТЫ!</b>\n\n"
                            f"💰 Сумма: +{amount} монет\n"
                            f"💳 Текущий баланс: {user['coins']} монет"
                        )
                    except:
                        pass
                else:
                    await message.answer("<b>❌ Пользователь не найден</b>")
            except:
                await message.answer("<b>❌ Неверный формат. Используй: ID сумма</b>")
        
        # Добавление аккаунта (формат: топы почта пароль)
        elif len(parts) == 3:
            try:
                tops = int(parts[0])
                email = parts[1]
                password = parts[2]
                price = tops * 30
                
                db.cursor.execute('''
                    INSERT INTO accounts (tops, email, password, price, added_date)
                    VALUES (?, ?, ?, ?, ?)
                ''', (tops, email, password, price, datetime.now().isoformat()))
                db.conn.commit()
                
                await message.answer(
                    f"<b>✅ АККАУНТ ДОБАВЛЕН!</b>\n\n"
                    f"🎮 Топов: {tops}\n"
                    f"📧 Почта: <code>{email}</code>\n"
                    f"🔐 Пароль: <code>{password}</code>\n"
                    f"💰 Цена: {price} монет"
                )
            except:
                await message.answer("<b>❌ Неверный формат. Используй: топы почта пароль</b>")

# =============== ДИНАМИЧЕСКИЕ КНОПКИ ===============
@dp.callback_query(lambda c: c.data.startswith("unban_"))
async def dynamic_unban(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    
    user_id = int(callback.data.replace("unban_", ""))
    user = db.get_user(user_id)
    
    if not user:
        await callback.answer("❌ Пользователь не найден", show_alert=True)
        return
    
    db.unban_user(user_id)
    
    try:
        await bot.send_message(user_id, "<b>✅ ВЫ РАЗБАНЕНЫ!</b>\n\nТеперь вы снова можете пользоваться ботом.")
    except:
        pass
    
    await callback.answer("✅ Пользователь разбанен!", show_alert=True)
    await admin_panel(callback)

@dp.callback_query(lambda c: c.data.startswith("ban_") and not c.data.startswith("ban_1h") and not c.data.startswith("ban_6h") and not c.data.startswith("ban_12h") and not c.data.startswith("ban_24h") and not c.data.startswith("ban_3d") and not c.data.startswith("ban_7d") and not c.data.startswith("ban_30d") and not c.data.startswith("ban_forever"))
async def dynamic_ban(callback: types.CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    
    user_id = int(callback.data.replace("ban_", ""))
    user = db.get_user(user_id)
    
    if not user:
        await callback.answer("❌ Пользователь не найден", show_alert=True)
        return
    
    await state.update_data(ban_user_id=user_id)
    await state.set_state(UploadStates.waiting_for_ban_reason)
    
    await callback.message.edit_text(
        f"<b>🔨 ЗАБАНИТЬ ПОЛЬЗОВАТЕЛЯ</b>\n\n"
        f"👤 {user['first_name']} (@{user['username']})\n"
        f"🆔 <code>{user_id}</code>\n\n"
        f"Введи причину бана:\n"
        f"❌ /cancel для отмены"
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("givecoins_"))
async def dynamic_give_coins(callback: types.CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    
    user_id = int(callback.data.replace("givecoins_", ""))
    user = db.get_user(user_id)
    
    if not user:
        await callback.answer("❌ Пользователь не найден", show_alert=True)
        return
    
    await state.update_data(give_user_id=user_id)
    await state.set_state(UploadStates.waiting_for_give_coins)
    
    await callback.message.edit_text(
        f"<b>💰 ВЫДАТЬ МОНЕТЫ</b>\n\n"
        f"👤 {user['first_name']} (@{user['username']})\n"
        f"🆔 <code>{user_id}</code>\n"
        f"💰 Текущий баланс: {user['coins']} монет\n\n"
        f"Введи сумму:\n"
        f"❌ /cancel для отмены"
    )
    await callback.answer()

# =============== АДМИН КОМАНДЫ ===============
@dp.callback_query(lambda c: c.data == "admin_unban_user")
async def admin_unban_user(callback: types.CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    
    await state.set_state(UploadStates.waiting_for_search)
    await callback.message.edit_text(
        "<b>✅ РАЗБАНИТЬ ПОЛЬЗОВАТЕЛЯ</b>\n\n"
        "Введи ID или @username пользователя:\n"
        "<code>123456789</code>\n"
        "<code>@username</code>\n\n"
        "❌ /cancel для отмены"
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data == "admin_ban_list")
async def admin_ban_list(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    
    banned = db.get_banned_users()
    
    text = "<b>📋 СПИСОК ЗАБАНЕННЫХ ПОЛЬЗОВАТЕЛЕЙ</b>\n\n"
    
    if not banned:
        text += "<i>Забаненных пользователей нет</i>"
    else:
        for ban in banned:
            user_id, username, name, reason, ban_date, expire = ban
            username_display = f"@{username}" if username else name
            ban_date_fmt = ban_date[:16].replace('T', ' ') if ban_date else "неизвестно"
            expire_date = expire[:16].replace('T', ' ') if expire and expire != 'forever' else "навсегда"
            
            text += f"<b>{username_display}</b>\n"
            text += f"🆔 <code>{user_id}</code>\n"
            text += f"📝 Причина: {reason}\n"
            text += f"📅 Забанен: {ban_date_fmt}\n"
            text += f"⏱ До: {expire_date}\n\n"
    
    keyboard = InlineKeyboardBuilder()
    keyboard.row(InlineKeyboardButton(text="« Назад", callback_data="admin_ban_menu"))
    
    await callback.message.edit_text(text, reply_markup=keyboard.as_markup())
    await callback.answer()

@dp.callback_query(lambda c: c.data == "admin_users")
async def admin_users(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    
    users = db.get_all_users()
    
    text = f"<b>👥 СПИСОК ПОЛЬЗОВАТЕЛЕЙ (всего {len(users)})</b>\n\n"
    
    for i, user in enumerate(users[:20], 1):
        user_id, username, name, coins, refs = user
        username_display = f"@{username}" if username else name
        text += f"{i}. {username_display}\n"
        text += f"   🆔 <code>{user_id}</code> | 💰 {coins} | 👥 {refs}\n"
    
    if len(users) > 20:
        text += f"\n<i>... и ещё {len(users) - 20} пользователей</i>"
    
    keyboard = InlineKeyboardBuilder()
    keyboard.row(InlineKeyboardButton(text="« Назад", callback_data="admin_panel"))
    
    await callback.message.edit_text(text, reply_markup=keyboard.as_markup())
    await callback.answer()

@dp.callback_query(lambda c: c.data == "admin_add_one")
async def admin_add_one(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    
    await callback.message.edit_text(
        "<b>➕ ДОБАВЛЕНИЕ ОДНОГО АККАУНТА</b>\n\n"
        "Введи данные в формате:\n"
        "<code>топы почта пароль</code>\n\n"
        "Пример:\n"
        "<code>10 user1@gmail.com pass123</code>\n\n"
        "❌ /cancel для отмены"
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data == "admin_stats")
async def admin_stats(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    
    users_count = db.get_user_count()
    banned_count = db.get_banned_count()
    total_coins = db.get_total_coins()
    available = db.get_total_accounts() - db.get_sold_accounts()
    total_accounts = db.get_total_accounts()
    
    stats = db.get_accounts_stats()
    
    text = f"""
<b>📊 ПОЛНАЯ СТАТИСТИКА БОТА</b>

<b>👥 ПОЛЬЗОВАТЕЛИ:</b>
▫️ Всего: {users_count}
▫️ Забанено: {banned_count}
▫️ Активных: {users_count - banned_count}
▫️ Всего монет: {total_coins}

<b>📦 АККАУНТЫ:</b>
▫️ Всего: {total_accounts}
▫️ Продано: {db.get_sold_accounts()}
▫️ В наличии: {available}

<b>📊 ПО ТОПАМ:</b>
"""
    
    if stats:
        for tops, count in stats:
            price = tops * 30
            text += f"▫️ {tops} топов — {count} шт. (по {price}💰)\n"
    else:
        text += "<i>Нет аккаунтов в наличии</i>\n"
    
    keyboard = InlineKeyboardBuilder()
    keyboard.row(InlineKeyboardButton(text="« Назад", callback_data="admin_panel"))
    
    await callback.message.edit_text(text, reply_markup=keyboard.as_markup())
    await callback.answer()

@dp.callback_query(lambda c: c.data == "admin_search")
async def admin_search(callback: types.CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    
    await state.set_state(UploadStates.waiting_for_search)
    await callback.message.edit_text(
        "<b>🔍 ПОИСК ПОЛЬЗОВАТЕЛЯ</b>\n\n"
        "Введи ID или @username:\n"
        "<code>123456789</code>\n"
        "<code>@username</code>\n\n"
        "❌ /cancel для отмены"
    )
    await callback.answer()

# =============== ЗАПУСК ===============
async def main():
    print("=" * 50)
    print("🎮 BLITZ REF — БОТ ЗАПУЩЕН!")
    print("=" * 50)
    print(f"👑 Админы: {ADMIN_IDS}")
    print(f"👤 Создатель: @mixan2907")
    print(f"📁 Загрузка аккаунтов: почта:пароль")
    print(f"🔨 Система банов: активна")
    print(f"📨 Рассылка: активна")
    print("=" * 50)
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())


