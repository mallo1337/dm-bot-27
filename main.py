# main.py
import asyncio
# ---- KEEP ALIVE SERVER FOR RENDER ----
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
import os

class PingHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b'Bot is alive')

def run_keep_alive_server():
    port = int(os.getenv("PORT", 10000))
    server = HTTPServer(("", port), PingHandler)
    print(f"[Render] Keep-alive HTTP server running on port {port}")
    server.serve_forever()

# запускаем сервер в отдельном потоке
threading.Thread(target=run_keep_alive_server, daemon=True).start()
# ---- END KEEP ALIVE ----
import os
import json
import urllib.request
import urllib.error
from urllib.parse import urlencode
import random
import string
import re
import logging
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    MenuButtonCommands,
    LabeledPrice,
)
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.storage.base import BaseStorage
from decimal import Decimal, ROUND_HALF_UP
from aiogram.exceptions import TelegramBadRequest
from dotenv import load_dotenv
from database import Database
import html

def esc(value):
    """Экранирование текста от пользователя для сообщений с parse_mode='HTML'."""
    return html.escape(str(value), quote=False) if value is not None else ""

def prepare_markdown_v2(text):
    """Экранирует служебные символы MarkdownV2 (. ! - = и т.д.), оставляя * _ ` [ ] ( ) для форматирования."""
    return re.sub(r'(?<!\\)([~>#+\-=|{}.!])', r'\\\1', text)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')
MODERATOR_GROUP_ID = os.getenv('MODERATOR_GROUP_ID')
CHANNEL_ID = os.getenv('CHANNEL_ID')

def _env_int(name, default):
    try:
        return int(os.getenv(name, str(default)).strip())
    except ValueError:
        return default

# Лобби создают игроки. Настройки (можно менять переменными окружения на Render):
MENU_IMAGE_URL = os.getenv('MENU_IMAGE_URL')
PROFILE_IMAGE_URL = os.getenv('PROFILE_IMAGE_URL')
TOP_IMAGE_URL = os.getenv('TOP_IMAGE_URL')
SCREENSHOT_IMAGE_URL = os.getenv('SCREENSHOT_IMAGE_URL')
LOBBY_IMAGE_URL = os.getenv('LOBBY_IMAGE_URL', 'https://example.com/lobby.jpg')
PREMIUM_IMAGE_URL = os.getenv('PREMIUM_IMAGE_URL')
PREMIUM_LOG_CHAT_ID = os.getenv('PREMIUM_LOG_CHAT_ID') or MODERATOR_GROUP_ID
CRYPTOBOT_TOKEN = os.getenv("CRYPTOBOT_TOKEN", "").strip().strip('"').strip("'")
CRYPTOBOT_USE_TESTNET = os.getenv('CRYPTOBOT_USE_TESTNET', 'true').lower() in ('1', 'true', 'yes')

PREMIUM_30_DAYS = 30
PREMIUM_90_DAYS = 90
PREMIUM_PRICE_USD_30 = '1.01'
PREMIUM_PRICE_USD_90 = '2.02'
PREMIUM_STARS_30 = 29
PREMIUM_STARS_90 = 49
PROMO_PREMIUM_BONUS_RATING = 100  # бонус к рейтингу за Premium по промокоду (как при покупке)
FIRST_PURCHASE_DISCOUNT_PERCENT = max(0, min(90, _env_int('FIRST_PURCHASE_DISCOUNT_PERCENT', 20)))  # скидка на первую покупку, %

pending_cryptobot_invoices = {}


# ---- PREMIUM EMOJI ----
# Ключ = сам эмодзи (fallback), значение = (emoji_id, fallback).
PREMIUM_EMOJI = {
    "◀️": ("5256247952564825322", "◀️"),
    "⬅️": ("5465332604121140251", "⬅️"),
    "➡️": ("5375444869965709294", "➡️"),
    "🔄": ("5017470156276761427", "🔄"),
    "🕗": ("5389071572835250888", "🕗"),
    "🔎": ("5429419796988970289", "🔎"),
    "➖": ("5418206758365574104", "➖"),
    "✅": ("5429501538806548545", "✅"),
    "❌": ("5210952531676504517", "❌"),
    "🗑": ("5445267414562389170", "🗑"),
    "✔": ("5352537837986163736", "✔"),
    "🚪": ("5452029295109086676", "🚪"),
    "📸": ("5235837920081887219", "📸"),
    "📝": ("5334882760735598374", "📝"),
    "✏️": ("5395444784611480792", "✏️"),
    "🆔": ("5014902839575577394", "🆔"),
    "📥": ("5433811242135331842", "📥"),
    "🔹": ("5280817506255135006", "🔹"),
    "🎮": ("5467583879948803288", "🎮"),
    "🗺": ("5415803062738504079", "🗺"),
    "⏳": ("5258258882022612173", "⏳"),
    "🎯": ("5310278924616356636", "🎯"),
    "🌍": ("5399898266265475100", "🌍"),
    "🔫": ("5222486447306602688", "🔫"),
    "🎲": ("5400005395634734568", "🎲"),
    "👥": ("5190892530438260422", "👥"),
    "✨": ("5325547803936572038", "✨"),
    "❗️": ("5274099962655816924", "❗️"),
    "⚠️": ("5447644880824181073", "⚠️"),
    "⭐️": ("5447644863644320013", "⭐️"),
    "🌟": ("5064709487953183440", "🌟"),
    "🛒": ("5431499171045581032", "🛒"),
    "💵": ("5409048419211682843", "💵"),
    "💲": ("5285484782791177666", "💲"),
    "📆": ("5431897022456145283", "📆"),
    "🗓": ("5413879192267805083", "🗓"),
    "🔍": ("5231012545799666522", "🔍"),
    "📈": ("5244837092042750681", "📈"),
    "📊": ("5231200819986047254", "📊"),
    "🏆": ("5409008750893734809", "🏆"),
    "🎉": ("5461151367559141950", "🎉"),
    "➕": ("5397916757333654639", "➕"),
    "👤": ("5190892530438260422", "👤"),
    "👋": ("5440431182602842059", "👋"),
    "1️⃣": ("5352618497471983387", "1️⃣"),
    "2️⃣": ("5355062479892294112", "2️⃣"),
    "3️⃣": ("5352735814503670154", "3️⃣"),
    "4️⃣": ("5352943794000016773", "4️⃣"),
    "5️⃣": ("5352548674188652122", "5️⃣"),
    "6️⃣": ("5352844395571880506", "6️⃣"),
    "7️⃣": ("5352666540976156937", "7️⃣"),
    "8️⃣": ("5352932180408448516", "8️⃣"),
    "9️⃣": ("5353050734390715246", "9️⃣"),
    "🔟": ("5353005409600842868", "🔟"),
    "🏁": ("5411520005386806155", "🏁"),
    "🥇": ("5440539497383087970", "🥇"),
    "🥈": ("5447203607294265305", "🥈"),
}

def pe(emoji: str) -> str:
    """Премиум-эмодзи для текстов сообщений (HTML).
    Если ID не задан — возвращает обычный fallback-эмодзи."""
    entry = PREMIUM_EMOJI.get(emoji)
    if not entry:
        return emoji
    eid, fb = entry
    if not eid:
        return fb
    return f'<tg-emoji emoji-id="{eid}">{fb}</tg-emoji>'

def pe_icon(emoji: str):
    """Emoji ID для инлайн-кнопки (icon_custom_emoji_id) или None."""
    entry = PREMIUM_EMOJI.get(emoji)
    if not entry or not entry[0]:
        return None
    return entry[0]

def btn(text: str, callback_data: str = None, url: str = None, icon: str = None):
    """Хелпер для InlineKeyboardButton с премиум-иконкой.

    Важно: если задан icon и для него есть премиум-ID, то ведущий эмодзи
    в тексте кнопки убирается — иначе Telegram нарисует и иконку, и
    обычный эмодзи, получится дубликат.
    """
    kwargs = {}
    if callback_data is not None:
        kwargs["callback_data"] = callback_data
    if url is not None:
        kwargs["url"] = url

    clean_text = text
    if icon:
        eid = pe_icon(icon)
        if eid:
            kwargs["icon_custom_emoji_id"] = eid
            # Убираем ведущий эмодзи (и пробел после него), если он совпадает с иконкой.
            # Учитываем, что у некоторых эмодзи есть variation selector (️).
            if clean_text.startswith(icon):
                clean_text = clean_text[len(icon):].lstrip()
            else:
                for suffix in ("️", ""):
                    pref = icon + suffix
                    if clean_text.startswith(pref):
                        clean_text = clean_text[len(pref):].lstrip()
                        break

    return InlineKeyboardButton(text=clean_text, **kwargs)
# ---- END PREMIUM EMOJI ----

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не найден в .env файле")

class PostgresFSMStorage(BaseStorage):
    """Хранит состояния диалогов (регистрация, создание лобби и т.д.) в базе: перезапуск бота их не сбрасывает."""

    def __init__(self, database):
        self.database = database

    @staticmethod
    def _key(key):
        return (
            f"{key.bot_id}:{key.chat_id}:{key.user_id}:"
            f"{getattr(key, 'thread_id', None) or 0}:{getattr(key, 'destiny', 'default')}"
        )

    async def set_state(self, key, state=None):
        value = state.state if isinstance(state, State) else state
        self.database.fsm_set_state(self._key(key), value)

    async def get_state(self, key):
        return self.database.fsm_get(self._key(key))[0]

    async def set_data(self, key, data):
        self.database.fsm_set_data(self._key(key), json.dumps(dict(data), ensure_ascii=False, default=str))

    async def get_data(self, key):
        try:
            return json.loads(self.database.fsm_get(self._key(key))[1] or "{}")
        except ValueError:
            return {}

    async def close(self):
        pass


bot = Bot(token=BOT_TOKEN)
db = Database()
try:
    storage = PostgresFSMStorage(db)
except Exception as _storage_error:
    logger.error(f"FSM storage in database unavailable, using memory: {_storage_error}")
    storage = MemoryStorage()
dp = Dispatcher(storage=storage)

from collections import OrderedDict

class LRUCache:
    def __init__(self, capacity: int = 1000):
        self.cache = OrderedDict()
        self.capacity = capacity

    def get(self, key):
        if key not in self.cache:
            return None
        self.cache.move_to_end(key)
        return self.cache[key]

    def put(self, key, value):
        if key in self.cache:
            self.cache.move_to_end(key)
        self.cache[key] = value
        if len(self.cache) > self.capacity:
            self.cache.popitem(last=False)

    def delete(self, key):
        if key in self.cache:
            del self.cache[key]

    def clear(self):
        self.cache.clear()

user_lobby_messages = LRUCache(1000)
user_menu_messages = LRUCache(1000)


def load_admins():
    try:
        with open('admins.txt', 'r', encoding='utf-8') as f:
            admins = []
            for line in f:
                line = line.strip()
                if line:
                    try:
                        admins.append(int(line))
                    except ValueError as e:
                        logger.error(f"Invalid admin ID format in admins.txt: {line} - {e}")
            logger.info(f"Loaded {len(admins)} admins")
            return admins
    except FileNotFoundError:
        logger.error("Admins file not found")
        return []
    except Exception as e:
        logger.error(f"Error loading admins: {e}")
        return []

ADMINS = load_admins()
FILE_ADMINS = set(ADMINS)  # админы из admins.txt (из панели их убрать нельзя)

# Владелец бота (доступ к панели /kp). Задаётся переменной OWNER_ID, иначе — первый ID из admins.txt
_owner_env = os.getenv('OWNER_ID', '').strip()
if _owner_env.isdigit():
    OWNER_ID = int(_owner_env)
else:
    OWNER_ID = ADMINS[0] if ADMINS else None

def is_owner(user_id):
    return OWNER_ID is not None and user_id == OWNER_ID

# Админы, добавленные через панель владельца, хранятся в базе
try:
    for _uid in db.get_bot_admin_ids():
        if _uid not in ADMINS:
            ADMINS.append(_uid)
except Exception as _e:
    logger.error(f"Error loading admins from database: {_e}")
if OWNER_ID is not None and OWNER_ID not in ADMINS:
    ADMINS.append(OWNER_ID)

class RegistrationStates(StatesGroup):
    waiting_for_nickname = State()
    waiting_for_game_id = State()
    waiting_for_device = State()
    confirm = State()


class ProfileEditStates(StatesGroup):
    waiting_for_new_nickname = State()
    waiting_for_new_game_id = State()


def get_player_level(rating):
    levels = [
        (1001, "🔟"),
        (871, "9️⃣"),
        (751, "8️⃣"),
        (621, "7️⃣"),
        (521, "6️⃣"),
        (401, "5️⃣"),
        (321, "4️⃣"),
        (221, "3️⃣"),
        (101, "2️⃣"),
        (0, "1️⃣")
    ]
    for threshold, level in levels:
        if rating >= threshold:
            return pe(level)
    return pe("1️⃣")

def get_registration_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[[
        btn("📝 Зарегистрироваться", callback_data="register", icon="📝")
    ]])


def get_back_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[[
        btn("◀️ Назад", callback_data="back_to_main", icon="◀️")
    ]])

def get_cancel_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[[
        btn("❌ Отмена", callback_data="cancel_registration", icon="❌")
    ]])


def get_top_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [btn("◀️ Назад в меню", callback_data="back_to_main", icon="◀️")]
    ])


def get_edit_profile_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [btn("✏️ Изменить никнейм", callback_data="edit_profile_nickname", icon="✏️")],
        [btn("🆔 Изменить игровое ID", callback_data="edit_profile_game_id", icon="🆔")],
        [btn("◀️ К профилю", callback_data="profile", icon="◀️")],
    ])

def get_premium_period_keyboard(user_id=None):
    label_30 = "🗓 30 days — $1.01"
    label_90 = "📆 90 days — $2.02"
    if user_id:
        label_30 = f"🗓 30 days — {price_button_label(user_id, PREMIUM_30_DAYS)}"
        label_90 = f"📆 90 days — {price_button_label(user_id, PREMIUM_90_DAYS)}"
    return InlineKeyboardMarkup(inline_keyboard=[
        [btn(label_30, callback_data="premium_pick_30", icon="🗓")],
        [btn(label_90, callback_data="premium_pick_90", icon="📆")],
        [
            btn("🎟 Промокод", callback_data="promo_enter", icon="🎟"),
            btn("🎁 Подарить Premium", callback_data="gift_start", icon="🎁"),
        ],
        [btn("◀️ Назад", callback_data="back_to_main", icon="◀️")],
    ])

def get_premium_payment_keyboard(days: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            btn("💲 CryptoBot", callback_data=f"premium_pay_crypto_{days}", icon="💲"),
            btn("⭐️ Telegram Stars", callback_data=f"premium_pay_stars_{days}", icon="⭐️"),
        ],
        [btn("◀️ Назад", callback_data="premium_menu", icon="◀️")],
    ])

def get_cancel_edit_profile_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[[
        btn("❌ Отмена", callback_data="cancel_edit_profile", icon="❌")
    ]])


def is_valid_game_id(game_id):
    return Database.is_valid_game_id_format(game_id)

def display_nickname(user_id, nickname):
    name = nickname or ""
    if is_admin(user_id):
        return f"{name} {pe('✔')}"          # админ — только ✔, без ⭐️
    if db.is_premium(user_id):
        return f"{name} {pe('⭐️')}"         # премиум без админки — только ⭐️
    return name

def premium_until_human(premium_until_str):
    if not premium_until_str:
        return ""
    try:
        dt = datetime.strptime(premium_until_str, "%Y-%m-%d %H:%M:%S")
        return dt.strftime("%d.%m.%Y %H:%M")
    except ValueError:
        return premium_until_str


def post_purchase_menu_caption(first_name: str, days: int) -> str:
    return (
        f"Благодарим за покупку! Вам выдан Premium на {days} дней.\n\n"
        f"{pe('👋')} Привет, {esc(first_name)}!\n\nВыберите действие:"
    )


async def show_post_purchase_main_menu(chat_id: int, user_id: int, first_name: str, days: int):
    caption = post_purchase_menu_caption(first_name or "друг", days)
    await cleanup_user_messages(user_id)
    await send_message_with_image(chat_id, caption, MENU_IMAGE_URL, get_main_keyboard(user_id))


def _cryptobot_flatten_params(params):
    if not params:
        return {}
    out = {}
    for k, v in params.items():
        if v is None:
            continue
        if isinstance(v, (list, tuple)):
            out[k] = ",".join(str(x) for x in v)
        elif isinstance(v, bool):
            out[k] = "true" if v else "false"
        else:
            out[k] = str(v)
    return out


def cryptobot_api_call(method: str, params=None):
    if not CRYPTOBOT_TOKEN:
        return None, "CRYPTOBOT_TOKEN не задан в .env"
    base = (
        "https://testnet-pay.crypt.bot/api"
        if CRYPTOBOT_USE_TESTNET
        else "https://pay.crypt.bot/api"
    )
    flat = _cryptobot_flatten_params(params or {})
    qs = urlencode(flat)
    url = f"{base}/{method}"
    if qs:
        url = f"{url}?{qs}"
    req = urllib.request.Request(
        url,
        headers={
            "Crypto-Pay-API-Token": CRYPTOBOT_TOKEN.strip(),
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (compatible; TelegramBot/1.0)",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            err_body = e.read().decode("utf-8")
        except Exception:
            err_body = str(e)
        msg = f"HTTP {e.code}: {err_body}"
        if e.code == 403 or "1010" in err_body:
            msg += (
                " Токен — из Crypto Pay → «Создать приложение» (@CryptoTestnetBot для testnet). "
                "Если уже так: проверьте .env без пробелов/кавычек вокруг токена."
            )
        return None, msg
    except Exception as e:
        return None, str(e)
    if not data.get("ok"):
        return None, data.get("error", {}).get("name", str(data))
    return data.get("result"), None

def cryptobot_get_invoice(invoice_id: int):
    result, err = cryptobot_api_call(
        "getInvoices", {"invoice_ids": str(invoice_id), "count": 100}
    )
    if err:
        return None, err
    items = []
    if isinstance(result, dict):
        items = result.get("items") or result.get("invoices") or []
    elif isinstance(result, list):
        items = result
    for inv in items:
        iid = inv.get("invoice_id")
        if iid is not None and int(iid) == int(invoice_id):
            return inv, None
    return None, "Счёт не найден в ответе API"

def cryptobot_invoice_is_paid(invoice_id: int):
    inv, err = cryptobot_get_invoice(invoice_id)
    if err:
        return False, err
    return inv.get("status") == "paid", None

async def finalize_premium_purchase(user_id: int, days: int, provider: str, provider_ref: str):
    if not db.is_user_registered(user_id):
        return False
    ok = await asyncio.to_thread(
        db.try_register_premium_payment, user_id, days, provider, provider_ref
    )
    if not ok:
        return False
    try:
        chat = await bot.get_chat(user_id)
        un = chat.username or ""
        line_user = f"{user_id} | @{un}" if un else f"{user_id} |"
        log_text = (
            f"{line_user}\n"
            f"Купил премиум на {days} дней!\n"
            f"Не забудьте выдать покупателю доступ в приватный чат и префикс в чате!\n"
            f"@uglymatthey"
        )
        if PREMIUM_LOG_CHAT_ID:
            await bot.send_message(chat_id=int(PREMIUM_LOG_CHAT_ID), text=log_text)
    except Exception as e:
        logger.error(f"finalize_premium log chat: {e}")
    return True


def is_admin(user_id):
    return user_id in ADMINS

async def safe_delete_message(chat_id, message_id):
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
        return True
    except TelegramBadRequest as e:
        if "message to delete not found" in str(e):
            logger.debug(f"Message {message_id} already deleted")
            return True
        else:
            logger.warning(f"Error deleting message {message_id}: {e}")
            return False
    except Exception as e:
        logger.warning(f"Unexpected error deleting message {message_id}: {e}")
        return False

async def send_message_with_image(chat_id, text, image_url=None, reply_markup=None):
    try:
        if image_url:
            message = await bot.send_photo(chat_id=chat_id, photo=image_url, caption=text, reply_markup=reply_markup, parse_mode='HTML')
        else:
            message = await bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup, parse_mode='HTML')

        user_menu_messages.put(chat_id, message.message_id)
        return message
    except Exception as e:
        logger.error(f"Error sending message with image to {chat_id}: {e}")
        try:
            message = await bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup, parse_mode='HTML')
            user_menu_messages.put(chat_id, message.message_id)
            return message
        except Exception as e2:
            logger.error(f"Error sending fallback message to {chat_id}: {e2}")
            return None

async def edit_message_with_image_safe(message, text, image_url=None, reply_markup=None):
    try:
        await message.delete()
    except Exception as e:
        logger.warning(f"Error deleting message: {e}")
    return await send_message_with_image(message.chat.id, text, image_url, reply_markup)


_bot_username_cache = None

async def get_bot_username():
    """Имя бота для ссылок (берётся у Телеграма, а не зашито в коде)."""
    global _bot_username_cache
    if not _bot_username_cache:
        try:
            me = await bot.get_me()
            _bot_username_cache = me.username
        except Exception as e:
            logger.error(f"Cannot get bot username: {e}")
            _bot_username_cache = (os.getenv('BOT_USERNAME') or '').lstrip('@') or None
    return _bot_username_cache

async def make_bot_link(start_param=None):
    username = await get_bot_username()
    if not username:
        return None
    return f"https://t.me/{username}" + (f"?start={start_param}" if start_param else "")


async def cleanup_user_messages(user_id):
    old_message_id = user_menu_messages.get(user_id)
    if old_message_id:
        try:
            await safe_delete_message(chat_id=user_id, message_id=old_message_id)
            user_menu_messages.delete(user_id)
        except Exception as e:
            logger.warning(f"Error cleaning up user message for {user_id}: {e}")

async def cleanup_lobby_messages(user_id):
    try:
        old_message_id = user_lobby_messages.get(user_id)
        user_lobby_messages.delete(user_id)
        if old_message_id:
            await safe_delete_message(chat_id=user_id, message_id=old_message_id)
    except Exception as e:
        logger.warning(f"Error in cleanup_lobby_messages for {user_id}: {e}")

async def set_menu_button(user_id):
    try:
        await bot.set_chat_menu_button(
            chat_id=user_id,
            menu_button=MenuButtonCommands(type="commands")
        )
    except Exception as e:
        logger.error(f"Error setting menu button: {e}")

async def set_bot_commands_for_user(user_id):
    commands = [
        types.BotCommand(command="start", description="🎮 Главное меню"),
        types.BotCommand(command="profile", description="👤 Мой профиль"),
        types.BotCommand(command="ticket", description="🎫 Тикет (жалоба / поддержка)"),
    ]

    if is_admin(user_id):
        commands.extend([
            types.BotCommand(command="post", description="📢 Рассылка"),
            types.BotCommand(command="botstat", description="📊 Статистика бота"),
            types.BotCommand(command="kd", description="🎯 Внести K/D игроков матча")
        ])

    if is_owner(user_id):
        commands.append(types.BotCommand(command="kp", description="🛠 Панель владельца"))

    try:
        await bot.set_my_commands(commands, scope=types.BotCommandScopeChat(chat_id=user_id))
    except Exception as e:
        logger.warning(f"Error setting commands for user {user_id}: {e}")
        try:
            await bot.set_my_commands(commands)
        except Exception as e2:
            logger.error(f"Error setting global commands: {e2}")

async def send_broadcast_message(user_id, text, parse_mode=None):
    try:
        await bot.send_message(
            chat_id=user_id,
            text=text,
            parse_mode=parse_mode,
            disable_web_page_preview=True
        )
        return True
    except Exception as e:
        logger.warning(f"Не удалось отправить сообщение пользователю {user_id}: {e}")
        return False


@dp.message(Command("profile"))
async def cmd_profile(message: types.Message):
    await show_profile_from_message(message)


@dp.message(Command("post"))
async def cmd_post(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer(f"{pe('❌')} Нет прав для этой команды.", parse_mode='HTML')
        return

    args = message.text.split(' ', 1)
    if len(args) < 2:
        await message.answer(
            "📢 Используйте:\n"
            "/post ваш текст\n\n"
            "Поддерживаемое форматирование:\n"
            "• *жирный*\n"
            "• _курсив_\n"
            "• `моноширинный`\n"
            "• [ссылка](https://example.com)"
        )
        return

    broadcast_text = prepare_markdown_v2(args[1])

    await state.update_data(broadcast_text=broadcast_text)

    try:
        await message.answer(f"📢 Тестовое сообщение:\n\n{broadcast_text}", parse_mode='MarkdownV2', disable_web_page_preview=True)
    except Exception as e:
        await message.answer(f"{pe('❌')} Ошибка в форматировании Markdown: {str(e)}\n\nУбедитесь, что вы правильно используете * _ ` для форматирования.", parse_mode='HTML')
        return

    confirm_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            btn("✅ Да, отправить", callback_data="confirm_broadcast", icon="✅"),
            btn("❌ Отмена", callback_data="cancel_broadcast", icon="❌")
        ]
    ])

    await message.answer(
        f"📢 Подтвердите рассылку:\n\n"
        f"Текст: {broadcast_text}\n\n"
        f"Будет отправлено всем пользователям бота.",
        reply_markup=confirm_keyboard
    )

@dp.message(Command("botstat"))
async def cmd_botstat(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer(f"{pe('❌')} Нет прав для этой команды.", parse_mode='HTML')
        return

    try:
        db.cursor.execute("SELECT COUNT(*) FROM players")
        total_users = db.cursor.fetchone()[0]

        today = datetime.now().strftime("%Y-%m-%d")
        db.cursor.execute("SELECT COUNT(*) FROM players WHERE registration_date >= %s", (today,))
        new_users_today = db.cursor.fetchone()[0]

        db.cursor.execute("SELECT COUNT(*) FROM fc_lobbies WHERE status = 'finished'")
        total_lobbies = db.cursor.fetchone()[0]

        stat_text = (
            f"{pe('👥')} Пользователи:\n"
            f"• Всего пользователей: {total_users}\n"
            f"• Новых за сегодня: {new_users_today}\n\n"
            f"{pe('🎮')} Матчи:\n"
            f"• Всего сыгранных матчей: {total_lobbies}"
        )

        await message.answer(stat_text, parse_mode='HTML')

    except Exception as e:
        logger.error(f"Error getting bot stats: {e}")
        await message.answer(f"{pe('❌')} Ошибка при получении статистики: {str(e)}", parse_mode='HTML')

@dp.callback_query(lambda c: c.data == "confirm_broadcast")
async def confirm_broadcast(callback_query: types.CallbackQuery, state: FSMContext):
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer("❌ Нет прав для этой команды.", show_alert=True)
        return

    data = await state.get_data()
    broadcast_text = data.get('broadcast_text')

    if not broadcast_text:
        await callback_query.message.edit_text("❌ Ошибка: текст рассылки не найден")
        return

    await callback_query.message.edit_text("🔄 Начинаю рассылку...")

    db.cursor.execute("SELECT user_id FROM players")
    users = db.cursor.fetchall()

    total_users = len(users)
    successful_sends = 0
    failed_sends = 0

    progress_message = await callback_query.message.edit_text(
        f"📢 Рассылка начата...\n"
        f"Всего пользователей: {total_users}\n"
        f"✅ Успешно: 0\n"
        f"❌ Ошибок: 0\n"
        f"🔄 В процессе..."
    )

    for i, (user_id,) in enumerate(users):
        success = await send_broadcast_message(user_id, broadcast_text, parse_mode='MarkdownV2')

        if success:
            successful_sends += 1
        else:
            failed_sends += 1

        if (i + 1) % 10 == 0 or (i + 1) == total_users:
            try:
                await progress_message.edit_text(
                    f"📢 Рассылка...\n"
                    f"Всего пользователей: {total_users}\n"
                    f"✅ Успешно: {successful_sends}\n"
                    f"❌ Ошибок: {failed_sends}\n"
                    f"🔄 Прогресс: {i + 1}/{total_users} ({((i + 1) / total_users * 100):.1f}%)"
                )
            except Exception as e:
                logger.warning(f"Error updating progress message: {e}")

        await asyncio.sleep(0.1)

    await progress_message.edit_text(
        f"📬 Рассылка завершена.\n"
        f"Успешно: {successful_sends}\n"
        f"Не доставлено: {failed_sends}"
    )

    await state.clear()
    await callback_query.answer()

@dp.callback_query(lambda c: c.data == "cancel_broadcast")
async def cancel_broadcast(callback_query: types.CallbackQuery, state: FSMContext):
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer("❌ Нет прав для этой команды.", show_alert=True)
        return

    await callback_query.message.edit_text("❌ Рассылка отменена.")
    await state.clear()
    await callback_query.answer()


# ======================================================================
# PREMIUM: цены и скидки, промокоды, подарки, оплата (заказы хранятся в базе)
# ======================================================================
class PromoStates(StatesGroup):
    waiting_for_code = State()


class GiftStates(StatesGroup):
    waiting_for_recipient = State()


def compute_price(user_id, days):
    """Цена для конкретного покупателя с учётом скидки (первая покупка / активированный промокод).
    Скидки не складываются: берётся лучшая."""
    base_usd = Decimal(PREMIUM_PRICE_USD_30 if days == PREMIUM_30_DAYS else PREMIUM_PRICE_USD_90)
    base_stars = PREMIUM_STARS_30 if days == PREMIUM_30_DAYS else PREMIUM_STARS_90
    percent, reason, promo_code = 0, None, None
    if FIRST_PURCHASE_DISCOUNT_PERCENT > 0 and not db.has_paid_premium(user_id):
        percent, reason = FIRST_PURCHASE_DISCOUNT_PERCENT, "первая покупка"
    promo = db.get_best_pending_promo_discount(user_id)
    if promo and promo[1] > percent:
        promo_code, percent, reason = promo[0], promo[1], f"промокод {promo[0]}"
    factor = Decimal(100 - percent) / Decimal(100)
    usd = max(Decimal("0.01"), (base_usd * factor).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
    stars = max(1, int((Decimal(base_stars) * factor).to_integral_value(rounding=ROUND_HALF_UP)))
    return {
        "usd": usd, "stars": stars, "base_usd": base_usd, "base_stars": base_stars,
        "percent": percent, "reason": reason, "promo_code": promo_code,
    }


def price_button_label(user_id, days):
    p = compute_price(user_id, days)
    label = f"${p['usd']}"
    if p["percent"]:
        label += f" (−{p['percent']}%)"
    return label


def player_nick(user_id):
    p = db.get_player_profile(user_id)
    return p[2] if p else str(user_id)


def premium_payment_text(uid, days, recipient_id=None):
    price = compute_price(uid, days)
    lines = [f"{pe('🛒')} Покупка: Premium Status ({days} дней)"]
    if recipient_id and recipient_id != uid:
        lines.append(f"🎁 Подарок для: {esc(player_nick(recipient_id))}")
    lines.append(f"{pe('💵')} Цена: ${price['usd']} / {price['stars']} Stars (звёзды в Telegram)")
    if price["percent"]:
        lines.append(
            f"🎁 Скидка {price['percent']}% ({esc(price['reason'])}). "
            f"Без скидки: ${price['base_usd']} / {price['base_stars']} Stars"
        )
    lines += ["", "Выберите способ оплаты:"]
    return "\n".join(lines)


async def send_premium_menu(uid):
    await cleanup_user_messages(uid)
    caption = f"{pe('🌟')} <b>Premium Status</b>\n\nНа сколько ты хочешь купить подписку?"
    p = compute_price(uid, PREMIUM_30_DAYS)
    if p["percent"]:
        caption += f"\n\n🎁 Ваша скидка: {p['percent']}% ({esc(p['reason'])})"
    await send_message_with_image(uid, caption, PREMIUM_IMAGE_URL, get_premium_period_keyboard(uid))


@dp.callback_query(lambda c: c.data == "premium_menu")
async def premium_menu(callback_query: types.CallbackQuery, state: FSMContext):
    uid = callback_query.from_user.id
    if not db.is_user_registered(uid):
        await callback_query.answer("Сначала зарегистрируйтесь в боте.", show_alert=True)
        return
    await state.clear()
    await send_premium_menu(uid)
    await callback_query.answer()


@dp.callback_query(lambda c: c.data in ("premium_pick_30", "premium_pick_90"))
async def premium_pick_period(callback_query: types.CallbackQuery):
    uid = callback_query.from_user.id
    if not db.is_user_registered(uid):
        await callback_query.answer("Сначала зарегистрируйтесь.", show_alert=True)
        return
    days = PREMIUM_30_DAYS if callback_query.data.endswith("30") else PREMIUM_90_DAYS
    await cleanup_user_messages(uid)
    await send_message_with_image(uid, premium_payment_text(uid, days), None, get_premium_payment_keyboard(days))
    await callback_query.answer()


@dp.callback_query(lambda c: c.data.startswith("premium_pick_back_"))
async def premium_pick_back(callback_query: types.CallbackQuery):
    uid = callback_query.from_user.id
    try:
        days = int(callback_query.data.replace("premium_pick_back_", ""))
    except ValueError:
        await callback_query.answer()
        return
    if days not in (PREMIUM_30_DAYS, PREMIUM_90_DAYS):
        await callback_query.answer()
        return
    await cleanup_user_messages(uid)
    await send_message_with_image(uid, premium_payment_text(uid, days), None, get_premium_payment_keyboard(days))
    await callback_query.answer()


# ---------- оплата: общие функции ----------
async def start_crypto_payment(callback_query, days, recipient_id=None):
    uid = callback_query.from_user.id
    recipient_id = recipient_id or uid
    if not db.is_user_registered(uid):
        await callback_query.answer("Сначала зарегистрируйтесь.", show_alert=True)
        return
    if days not in (PREMIUM_30_DAYS, PREMIUM_90_DAYS):
        await callback_query.answer()
        return
    if recipient_id != uid and not db.is_user_registered(recipient_id):
        await callback_query.answer("Получатель не найден.", show_alert=True)
        return
    if not CRYPTOBOT_TOKEN:
        await callback_query.answer(
            "Оплата через CryptoBot не настроена (CRYPTOBOT_TOKEN в .env).",
            show_alert=True,
        )
        return
    price = compute_price(uid, days)
    order_id = db.create_premium_order(
        "cryptobot", uid, recipient_id, days, price["usd"], price["stars"], price["percent"], price["promo_code"]
    )
    if not order_id:
        await callback_query.answer("Не удалось создать заказ, попробуйте позже.", show_alert=True)
        return
    body = {
        "currency_type": "fiat",
        "fiat": "USD",
        "amount": str(price["usd"]),
        "description": f"Premium Status {days} дней",
        "expires_in": 600,
    }
    result, err = await asyncio.to_thread(cryptobot_api_call, "createInvoice", body)
    if err or not result:
        await callback_query.answer(f"CryptoBot: {err or 'ошибка'}", show_alert=True)
        return
    pay_url = result.get("pay_url") or result.get("bot_invoice_url")
    invoice_id = result.get("invoice_id")
    if not pay_url or invoice_id is None:
        await callback_query.answer("Не удалось создать счёт CryptoBot.", show_alert=True)
        return
    db.set_order_invoice(order_id, invoice_id)
    back_cb = f"premium_pick_back_{days}" if recipient_id == uid else f"gift_pick_{recipient_id}_{days}"
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [btn("💲 Оплатить в CryptoBot", url=pay_url, icon="💲")],
            [btn("🔍 Проверить оплату", callback_data=f"pcheck_{order_id}", icon="🔍")],
            [btn("◀️ Назад", callback_data=back_cb, icon="◀️")],
        ]
    )
    lines = [f"{pe('🌟')} Оплата Premium Status ({days} д.)"]
    if recipient_id != uid:
        lines.append(f"🎁 Подарок для: {esc(player_nick(recipient_id))}")
    lines.append(f"{pe('💲')} Сумма: ${price['usd']}")
    lines += ["", f"{pe('⚠️')} У вас 10 минут на оплату."]
    await cleanup_user_messages(uid)
    await bot.send_message(chat_id=uid, text="\n".join(lines), reply_markup=kb, parse_mode='HTML')
    await callback_query.answer()


async def start_stars_payment(callback_query, days, recipient_id=None):
    uid = callback_query.from_user.id
    recipient_id = recipient_id or uid
    if not db.is_user_registered(uid):
        await callback_query.answer("Сначала зарегистрируйтесь.", show_alert=True)
        return
    if days not in (PREMIUM_30_DAYS, PREMIUM_90_DAYS):
        await callback_query.answer()
        return
    if recipient_id != uid and not db.is_user_registered(recipient_id):
        await callback_query.answer("Получатель не найден.", show_alert=True)
        return
    price = compute_price(uid, days)
    order_id = db.create_premium_order(
        "telegram_stars", uid, recipient_id, days, price["usd"], price["stars"], price["percent"], price["promo_code"]
    )
    if not order_id:
        await callback_query.answer("Не удалось создать заказ, попробуйте позже.", show_alert=True)
        return
    description = (
        f"Подписка Premium на {days} дней"
        if recipient_id == uid
        else f"Подарок: Premium на {days} дней для {player_nick(recipient_id)}"
    )
    try:
        await bot.send_invoice(
            chat_id=uid,
            title="Premium Status",
            description=description[:250],
            payload=f"order_{order_id}",
            currency="XTR",
            prices=[LabeledPrice(label=f"Premium {days} дней", amount=price["stars"])],
            provider_token="",
        )
    except Exception as e:
        logger.error(f"send_invoice stars: {e}")
        await callback_query.answer("Не удалось выставить счёт Stars.", show_alert=True)
        return
    await callback_query.answer()


async def finalize_premium_order(order, provider_ref):
    """Выдаёт Premium получателю по оплаченному заказу. Идемпотентно по provider_ref."""
    (order_id, provider, _, _, buyer_id, recipient_id, days, _, _, _, promo_code, _) = order
    granted = db.try_register_premium_payment(recipient_id, days, provider, provider_ref)
    if not granted:
        return False
    db.mark_order_paid(order_id, provider_ref)
    if promo_code:
        db.mark_promo_applied(buyer_id, promo_code, order_id)
    try:
        chat = await bot.get_chat(buyer_id)
        un = chat.username or ""
        line_user = f"{buyer_id} | @{un}" if un else f"{buyer_id} |"
        if recipient_id == buyer_id:
            log_text = (
                f"{line_user}\n"
                f"Купил премиум на {days} дней!\n"
                f"Не забудьте выдать покупателю доступ в приватный чат и префикс в чате!\n"
                f"@uglymatthey"
            )
        else:
            log_text = (
                f"{line_user}\n"
                f"Подарил премиум на {days} дней игроку {player_nick(recipient_id)} ({recipient_id})!\n"
                f"Не забудьте выдать получателю доступ в приватный чат и префикс в чате!\n"
                f"@uglymatthey"
            )
        if PREMIUM_LOG_CHAT_ID:
            await bot.send_message(chat_id=int(PREMIUM_LOG_CHAT_ID), text=log_text)
    except Exception as e:
        logger.error(f"finalize_premium_order log chat: {e}")
    if recipient_id != buyer_id:
        try:
            await bot.send_message(
                chat_id=recipient_id,
                text=(
                    f"{pe('🎁')} Игрок {esc(player_nick(buyer_id))} подарил вам Premium на {days} дней!\n"
                    f"{pe('⭐️')} Приятной игры!"
                ),
                parse_mode='HTML',
            )
        except Exception as e:
            logger.info(f"Cannot notify gift recipient {recipient_id}: {e}")
    return True


async def after_order_paid(chat_id, order, first_name):
    buyer_id, recipient_id, days = order[4], order[5], order[6]
    if recipient_id == buyer_id:
        await show_post_purchase_main_menu(chat_id, buyer_id, first_name, days)
    else:
        await cleanup_user_messages(buyer_id)
        await send_message_with_image(
            chat_id,
            f"{pe('🎁')} Подарок отправлен! Игрок {esc(player_nick(recipient_id))} получил Premium на {days} дней.",
            MENU_IMAGE_URL,
            get_main_keyboard(buyer_id),
        )


@dp.callback_query(lambda c: c.data.startswith("premium_pay_crypto_"))
async def premium_pay_crypto(callback_query: types.CallbackQuery):
    try:
        days = int(callback_query.data.replace("premium_pay_crypto_", ""))
    except ValueError:
        await callback_query.answer()
        return
    await start_crypto_payment(callback_query, days)


@dp.callback_query(lambda c: c.data.startswith("premium_pay_stars_"))
async def premium_pay_stars(callback_query: types.CallbackQuery):
    try:
        days = int(callback_query.data.replace("premium_pay_stars_", ""))
    except ValueError:
        await callback_query.answer()
        return
    await start_stars_payment(callback_query, days)


@dp.callback_query(lambda c: c.data.startswith("pcheck_"))
async def premium_order_check(callback_query: types.CallbackQuery):
    try:
        order_id = int(callback_query.data.replace("pcheck_", ""))
    except ValueError:
        await callback_query.answer()
        return
    uid = callback_query.from_user.id
    order = db.get_premium_order(order_id)
    if not order or order[4] != uid:
        await callback_query.answer("Это не ваш счёт.", show_alert=True)
        return
    _, provider, _, invoice_id, _, _, days, price_usd, _, _, _, status = order
    if status == "paid":
        await callback_query.answer("Платёж уже был учтён.", show_alert=True)
        return
    if provider != "cryptobot" or not invoice_id:
        await callback_query.answer("Счёт не найден. Создайте новый из меню Premium.", show_alert=True)
        return
    inv, err = await asyncio.to_thread(cryptobot_get_invoice, invoice_id)
    if err or not inv:
        await callback_query.answer(f"Ошибка: {err or 'счёт не найден'}", show_alert=True)
        return
    inv_status = inv.get("status")
    if inv_status == "expired":
        await callback_query.answer("Счёт истёк. Создайте новый из меню Premium.", show_alert=True)
        return
    if inv_status != "paid":
        await callback_query.answer("Оплата ещё не поступила.", show_alert=True)
        return
    try:
        amount_ok = Decimal(str(inv.get("amount"))).quantize(Decimal("0.01")) == Decimal(str(price_usd)).quantize(Decimal("0.01"))
        if inv.get("currency_type") == "fiat" and inv.get("fiat") != "USD":
            amount_ok = False
    except Exception:
        amount_ok = False
    if not amount_ok:
        logger.warning(f"CryptoBot invoice {invoice_id}: amount mismatch: {inv.get('amount')} {inv.get('fiat')} vs {price_usd}")
        await callback_query.answer("Сумма счёта не совпадает с заказом.", show_alert=True)
        return
    ok = await finalize_premium_order(order, f"cryptobot_{invoice_id}")
    if ok:
        try:
            await callback_query.message.delete()
        except Exception:
            pass
        await after_order_paid(callback_query.message.chat.id, order, callback_query.from_user.first_name)
        await callback_query.answer()
    else:
        await callback_query.answer("Платёж уже был учтён.", show_alert=True)


@dp.callback_query(lambda c: c.data.startswith("premium_cbcheck:"))
async def premium_cryptobot_check(callback_query: types.CallbackQuery):
    parts = callback_query.data.split(":")
    if len(parts) not in (3, 4):
        await callback_query.answer()
        return
    try:
        invoice_id = int(parts[1])
        owner_id = int(parts[2])
        days = int(parts[3]) if len(parts) == 4 else None
    except ValueError:
        await callback_query.answer()
        return
    if callback_query.from_user.id != owner_id:
        await callback_query.answer("Это не ваш счёт.", show_alert=True)
        return
    if days is None:
        pend = pending_cryptobot_invoices.get(owner_id)
        if not pend or int(pend["invoice_id"]) != invoice_id:
            await callback_query.answer("Создайте новый счёт из меню Premium.", show_alert=True)
            return
        days = pend["days"]
    if days not in (PREMIUM_30_DAYS, PREMIUM_90_DAYS):
        await callback_query.answer()
        return
    inv, err = await asyncio.to_thread(cryptobot_get_invoice, invoice_id)
    if err or not inv:
        await callback_query.answer(f"Ошибка: {err or 'счёт не найден'}", show_alert=True)
        return
    if inv.get("status") != "paid":
        await callback_query.answer("Оплата ещё не поступила.", show_alert=True)
        return
    expected_usd = PREMIUM_PRICE_USD_30 if days == PREMIUM_30_DAYS else PREMIUM_PRICE_USD_90
    try:
        amount_ok = abs(float(inv.get("amount")) - float(expected_usd)) < 0.001
        if inv.get("currency_type") == "fiat" and inv.get("fiat") != "USD":
            amount_ok = False
    except (TypeError, ValueError):
        amount_ok = False
    if not amount_ok:
        logger.warning(f"CryptoBot invoice {invoice_id}: amount mismatch for {days} days: {inv.get('amount')} {inv.get('fiat')}")
        await callback_query.answer("Сумма счёта не совпадает с выбранным тарифом.", show_alert=True)
        return
    ref = f"cryptobot_{invoice_id}"
    ok = await finalize_premium_purchase(owner_id, days, "cryptobot", ref)
    if ok:
        pending_cryptobot_invoices.pop(owner_id, None)
        first_name = callback_query.from_user.first_name
        try:
            await callback_query.message.delete()
        except Exception:
            pass
        await show_post_purchase_main_menu(
            callback_query.message.chat.id, owner_id, first_name, days
        )
        await callback_query.answer()
    else:
        await callback_query.answer("Платёж уже был учтён.", show_alert=True)


@dp.pre_checkout_query()
async def pre_checkout_handler(pre_checkout_query: types.PreCheckoutQuery):
    payload = pre_checkout_query.invoice_payload or ""
    if payload.startswith("order_"):
        ok = False
        try:
            order = db.get_premium_order(int(payload.replace("order_", "")))
            ok = bool(
                order
                and order[11] == "pending"
                and order[1] == "telegram_stars"
                and order[4] == pre_checkout_query.from_user.id
                and order[8] == pre_checkout_query.total_amount
            )
        except Exception as e:
            logger.error(f"pre_checkout order: {e}")
        if ok:
            await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)
        else:
            await bot.answer_pre_checkout_query(
                pre_checkout_query.id, ok=False, error_message="Заказ не найден или цена изменилась. Создайте счёт заново."
            )
    elif payload.startswith("premium_stars_"):
        # счета, выставленные до обновления
        await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)
    else:
        await bot.answer_pre_checkout_query(
            pre_checkout_query.id,
            ok=False,
            error_message="Неизвестный товар",
        )


async def log_stars_failure(uid, days, charge_id):
    try:
        if PREMIUM_LOG_CHAT_ID:
            await bot.send_message(
                chat_id=int(PREMIUM_LOG_CHAT_ID),
                text=(
                    "⚠️ Платёж Stars не активирован автоматически.\n"
                    f"user_id: {uid}\n"
                    f"Дней: {days}\n"
                    f"charge_id: {charge_id}\n"
                    "Возможно, это повтор уже учтённого платежа — проверьте вручную."
                ),
            )
    except Exception as e:
        logger.error(f"stars failure log: {e}")


@dp.message(F.successful_payment)
async def on_successful_payment(message: types.Message):
    sp = message.successful_payment
    if not sp:
        return
    payload = sp.invoice_payload or ""
    uid = message.from_user.id

    if payload.startswith("order_"):
        try:
            order = db.get_premium_order(int(payload.replace("order_", "")))
        except ValueError:
            order = None
        if not order:
            await log_stars_failure(uid, "?", sp.telegram_payment_charge_id)
            await message.answer("Не удалось найти заказ. Напишите администратору, мы всё проверим.")
            return
        ok = await finalize_premium_order(order, f"stars_{sp.telegram_payment_charge_id}")
        if not ok:
            await log_stars_failure(uid, order[6], sp.telegram_payment_charge_id)
            await message.answer(
                "Не удалось активировать Premium (возможно, платёж уже учтён). "
                "Если Premium не появился, напишите администратору."
            )
            return
        try:
            await message.delete()
        except Exception:
            pass
        await after_order_paid(message.chat.id, order, message.from_user.first_name)
        return

    # счета Stars, выставленные до обновления
    if not payload.startswith("premium_stars_"):
        return
    try:
        days = int(payload.replace("premium_stars_", ""))
    except ValueError:
        return
    if days not in (PREMIUM_30_DAYS, PREMIUM_90_DAYS):
        return
    ref = f"stars_{sp.telegram_payment_charge_id}"
    ok = await finalize_premium_purchase(uid, days, "telegram_stars", ref)
    if not ok:
        await log_stars_failure(uid, days, sp.telegram_payment_charge_id)
        await message.answer(
            "Не удалось активировать Premium (возможно, платёж уже учтён). "
            "Если Premium не появился, напишите администратору."
        )
        return
    try:
        await message.delete()
    except Exception:
        pass
    await show_post_purchase_main_menu(
        message.chat.id, uid, message.from_user.first_name, days
    )


# ---------- промокоды (сторона игрока) ----------
def promo_back_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[[btn("◀️ Назад", callback_data="premium_menu", icon="◀️")]])


@dp.callback_query(lambda c: c.data == "promo_enter")
async def promo_enter(callback_query: types.CallbackQuery, state: FSMContext):
    uid = callback_query.from_user.id
    if not db.is_user_registered(uid):
        await callback_query.answer("Сначала зарегистрируйтесь.", show_alert=True)
        return
    await state.set_state(PromoStates.waiting_for_code)
    await cleanup_user_messages(uid)
    await send_message_with_image(uid, f"{pe('🎟')} Введите промокод:", None, promo_back_keyboard())
    await callback_query.answer()


@dp.message(PromoStates.waiting_for_code)
async def promo_code_entered(message: types.Message, state: FSMContext):
    uid = message.from_user.id
    code = (message.text or "").strip().upper()
    if not re.fullmatch(r"[A-Z0-9_-]{3,20}", code):
        await message.answer("❌ Промокод состоит из букв, цифр, «-» и «_» (3-20 символов). Попробуйте ещё раз.", reply_markup=promo_back_keyboard())
        return
    kind, value, err = db.redeem_promo(uid, code)
    if err:
        await message.answer(f"❌ {err}", reply_markup=promo_back_keyboard())
        return
    await state.clear()
    if kind == "days":
        new_until = db.grant_premium_days(
            uid, value, provider="promo", ref=f"promo_{code}_{uid}", bonus_rating=PROMO_PREMIUM_BONUS_RATING
        )
        if not new_until:
            db.cancel_promo_redemption(uid, code)
            await message.answer("❌ Не удалось начислить Premium, попробуйте ещё раз позже.")
            return
        await message.answer(
            f"🎉 Промокод активирован! Вам начислено {value} дн. Premium (до {fmt_dt(new_until)}) "
            f"и +{PROMO_PREMIUM_BONUS_RATING} рейтинга."
        )
        try:
            chat = await bot.get_chat(uid)
            un = chat.username or ""
            line_user = f"{uid} | @{un}" if un else f"{uid} |"
            if PREMIUM_LOG_CHAT_ID:
                await bot.send_message(
                    chat_id=int(PREMIUM_LOG_CHAT_ID),
                    text=(
                        f"{line_user}\n"
                        f"Активировал промокод {code}: Premium на {value} дней!\n"
                        f"Не забудьте выдать доступ в приватный чат и префикс в чате!\n"
                        f"@uglymatthey"
                    ),
                )
        except Exception as e:
            logger.error(f"promo premium log chat: {e}")
    else:
        await message.answer(f"✅ Промокод активирован: скидка {value}% на следующую покупку Premium.")
    await send_premium_menu(uid)


# ---------- подарок Premium другому игроку ----------
@dp.callback_query(lambda c: c.data == "gift_start")
async def gift_start(callback_query: types.CallbackQuery, state: FSMContext):
    uid = callback_query.from_user.id
    if not db.is_user_registered(uid):
        await callback_query.answer("Сначала зарегистрируйтесь.", show_alert=True)
        return
    await state.set_state(GiftStates.waiting_for_recipient)
    await cleanup_user_messages(uid)
    await send_message_with_image(
        uid,
        f"{pe('🎁')} Кому подарить Premium?\n\n"
        "Отправьте ник, @username или Telegram ID игрока. Он должен быть зарегистрирован в боте.",
        None,
        promo_back_keyboard(),
    )
    await callback_query.answer()


async def show_gift_periods(uid, recipient_id):
    await cleanup_user_messages(uid)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [btn(f"🗓 30 days — {price_button_label(uid, PREMIUM_30_DAYS)}", callback_data=f"gift_pick_{recipient_id}_30", icon="🗓")],
        [btn(f"📆 90 days — {price_button_label(uid, PREMIUM_90_DAYS)}", callback_data=f"gift_pick_{recipient_id}_90", icon="📆")],
        [btn("◀️ Назад", callback_data="premium_menu", icon="◀️")],
    ])
    await send_message_with_image(
        uid,
        f"{pe('🎁')} Подарок для: {esc(player_nick(recipient_id))}\n\nНа сколько подарить Premium?",
        None,
        kb,
    )


@dp.message(GiftStates.waiting_for_recipient)
async def gift_recipient_entered(message: types.Message, state: FSMContext):
    uid = message.from_user.id
    target = db.find_player_id(message.text or "")
    if not target:
        await message.answer("❌ Игрок не найден. Проверьте ник, @username или Telegram ID.", reply_markup=promo_back_keyboard())
        return
    if target == uid:
        await message.answer("Для себя Premium покупается в обычном меню. Отправьте ник друга.", reply_markup=promo_back_keyboard())
        return
    await state.clear()
    await show_gift_periods(uid, target)


@dp.callback_query(lambda c: c.data.startswith("gift_to_"))
async def gift_to(callback_query: types.CallbackQuery):
    uid = callback_query.from_user.id
    try:
        target = int(callback_query.data.replace("gift_to_", ""))
    except ValueError:
        await callback_query.answer()
        return
    if not db.is_user_registered(uid) or not db.is_user_registered(target) or target == uid:
        await callback_query.answer("Получатель недоступен.", show_alert=True)
        return
    await show_gift_periods(uid, target)
    await callback_query.answer()


@dp.callback_query(lambda c: c.data.startswith("gift_pick_"))
async def gift_pick(callback_query: types.CallbackQuery):
    uid = callback_query.from_user.id
    try:
        _, _, target_s, days_s = callback_query.data.split("_")
        target, days = int(target_s), int(days_s)
    except ValueError:
        await callback_query.answer()
        return
    if days not in (PREMIUM_30_DAYS, PREMIUM_90_DAYS) or not db.is_user_registered(uid) \
            or not db.is_user_registered(target) or target == uid:
        await callback_query.answer("Получатель недоступен.", show_alert=True)
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            btn("💲 CryptoBot", callback_data=f"gift_pay_crypto_{target}_{days}", icon="💲"),
            btn("⭐️ Telegram Stars", callback_data=f"gift_pay_stars_{target}_{days}", icon="⭐️"),
        ],
        [btn("◀️ Назад", callback_data=f"gift_to_{target}", icon="◀️")],
    ])
    await cleanup_user_messages(uid)
    await send_message_with_image(uid, premium_payment_text(uid, days, target), None, kb)
    await callback_query.answer()


@dp.callback_query(lambda c: c.data.startswith("gift_pay_crypto_"))
async def gift_pay_crypto(callback_query: types.CallbackQuery):
    try:
        _, _, _, target_s, days_s = callback_query.data.split("_")
        target, days = int(target_s), int(days_s)
    except ValueError:
        await callback_query.answer()
        return
    if target == callback_query.from_user.id:
        await callback_query.answer()
        return
    await start_crypto_payment(callback_query, days, target)


@dp.callback_query(lambda c: c.data.startswith("gift_pay_stars_"))
async def gift_pay_stars(callback_query: types.CallbackQuery):
    try:
        _, _, _, target_s, days_s = callback_query.data.split("_")
        target, days = int(target_s), int(days_s)
    except ValueError:
        await callback_query.answer()
        return
    if target == callback_query.from_user.id:
        await callback_query.answer()
        return
    await start_stars_payment(callback_query, days, target)


@dp.callback_query(lambda c: c.data == "edit_profile")
async def edit_profile_menu(callback_query: types.CallbackQuery):
    uid = callback_query.from_user.id
    if not db.is_user_registered(uid):
        await callback_query.answer("❌ Вы не зарегистрированы!", show_alert=True)
        return
    await cleanup_user_messages(uid)
    await send_message_with_image(
        uid,
        f"{pe('✏️')} Редактирование профиля\n\nВыберите действие:",
        None,
        get_edit_profile_keyboard(),
    )
    await callback_query.answer()


@dp.callback_query(lambda c: c.data == "edit_profile_nickname")
async def edit_profile_nickname_start(callback_query: types.CallbackQuery, state: FSMContext):
    uid = callback_query.from_user.id
    if not db.is_user_registered(uid):
        await callback_query.answer("❌ Вы не зарегистрированы!", show_alert=True)
        return
    rem = await asyncio.to_thread(db.profile_nickname_cooldown_remaining, uid)
    if rem > 0:
        h, m = rem // 3600, (rem % 3600) // 60
        await callback_query.answer(
            f"Смена никнейма доступна через {h}ч {m}м", show_alert=True
        )
        return
    await state.set_state(ProfileEditStates.waiting_for_new_nickname)
    await cleanup_user_messages(uid)
    await send_message_with_image(
        uid,
        f"{pe('✏️')} Введите новый никнейм (как при регистрации):",
        None,
        get_cancel_edit_profile_keyboard(),
    )
    await callback_query.answer()


@dp.callback_query(lambda c: c.data == "edit_profile_game_id")
async def edit_profile_game_id_start(callback_query: types.CallbackQuery, state: FSMContext):
    uid = callback_query.from_user.id
    if not db.is_user_registered(uid):
        await callback_query.answer("❌ Вы не зарегистрированы!", show_alert=True)
        return
    rem = await asyncio.to_thread(db.profile_game_id_cooldown_remaining, uid)
    if rem > 0:
        h, m = rem // 3600, (rem % 3600) // 60
        await callback_query.answer(
            f"Смена игрового ID доступна через {h}ч {m}м", show_alert=True
        )
        return
    await state.set_state(ProfileEditStates.waiting_for_new_game_id)
    await cleanup_user_messages(uid)
    await send_message_with_image(
        uid,
        f"{pe('🆔')} Введите новый игровой ID (2–13 символов: только цифры и латинские буквы):",
        None,
        get_cancel_edit_profile_keyboard(),
    )
    await callback_query.answer()


@dp.callback_query(lambda c: c.data == "cancel_edit_profile")
async def cancel_edit_profile(callback_query: types.CallbackQuery, state: FSMContext):
    await state.clear()
    uid = callback_query.from_user.id
    await cleanup_user_messages(uid)
    await send_message_with_image(
        uid,
        f"{pe('✏️')} Редактирование профиля\n\nВыберите действие:",
        None,
        get_edit_profile_keyboard(),
    )
    await callback_query.answer()


@dp.message(ProfileEditStates.waiting_for_new_nickname)
async def process_profile_new_nickname(message: types.Message, state: FSMContext):
    uid = message.from_user.id
    nickname = (message.text or "").strip()
    if len(nickname) < 3 or len(nickname) > 16:
        await message.answer(f"{pe('❌')} Никнейм должен быть от 3 до 16 символов", parse_mode='HTML')
        return
    if not re.match(r"^[a-zA-Z0-9_]+$", nickname):
        await message.answer(
            f"{pe('❌')} Никнейм должен содержать только английские буквы, цифры и подчёркивания",
            parse_mode='HTML'
        )
        return
    ok, err = await asyncio.to_thread(db.update_player_nickname_if_allowed, uid, nickname)
    if not ok:
        await message.answer(f"{pe('❌')} {err}", parse_mode='HTML')
        return
    await state.clear()
    try:
        await message.delete()
    except Exception:
        pass
    await cleanup_user_messages(uid)
    await message.answer(f"{pe('✅')} Никнейм обновлён!", parse_mode='HTML')
    await show_profile_from_message(message)


@dp.message(ProfileEditStates.waiting_for_new_game_id)
async def process_profile_new_game_id(message: types.Message, state: FSMContext):
    uid = message.from_user.id
    game_id = (message.text or "").strip()
    if not is_valid_game_id(game_id):
        await message.answer(
            f"{pe('❌')} Игровой ID: от 2 до 13 символов, только цифры и латинские буквы",
            parse_mode='HTML'
        )
        return
    ok, err = await asyncio.to_thread(db.update_player_game_id_if_allowed, uid, game_id)
    if not ok:
        await message.answer(f"{pe('❌')} {err}", parse_mode='HTML')
        return
    await state.clear()
    try:
        await message.delete()
    except Exception:
        pass
    await cleanup_user_messages(uid)
    await message.answer(f"{pe('✅')} Игровой ID обновлён!", parse_mode='HTML')
    await show_profile_from_message(message)


@dp.callback_query(lambda c: c.data == "back_to_main")
async def back_to_main(callback_query: types.CallbackQuery, state: FSMContext):
    await state.clear()
    user_id = callback_query.from_user.id
    first_name = callback_query.from_user.first_name

    await cleanup_user_messages(user_id)
    await cleanup_lobby_messages(user_id)

    menu_text = f"{pe('👋')} Привет, {esc(first_name)}!\n\nВыберите действие:"
    await send_message_with_image(user_id, menu_text, MENU_IMAGE_URL, get_main_keyboard(user_id))
    await callback_query.answer()

# ======================================================================
# ПАНЕЛЬ ВЛАДЕЛЬЦА (/kp) — скрытая команда, отвечает только владельцу
# ======================================================================
class OwnerStates(StatesGroup):
    waiting_for_search = State()
    waiting_for_rating = State()
    waiting_for_admin = State()
    waiting_for_promo = State()


def strip_tags(text):
    """Убирает HTML-теги (в т.ч. <tg-emoji>), оставляя обычный эмодзи-запасной вариант."""
    return html.unescape(re.sub(r"<[^>]+>", "", str(text)))


def fmt_dt(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S").strftime("%d.%m.%Y %H:%M")
    except (TypeError, ValueError):
        return value or "—"


def player_label(user_id):
    p = db.get_player_profile(user_id)
    nick = p[2] if p else "?"
    return f"{nick} ({user_id})"


def owner_main_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика", callback_data="own_stats")],
        [InlineKeyboardButton(text="🔍 Найти игрока", callback_data="own_search")],
        [InlineKeyboardButton(text="👮 Админы", callback_data="own_admins")],
        [InlineKeyboardButton(text="🎟 Промокоды", callback_data="own_promos")],
        [InlineKeyboardButton(text="❌ Закрыть", callback_data="own_close")],
    ])


def owner_card_keyboard(uid):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✏️ ELO", callback_data=f"own_rate_{uid}"),
            InlineKeyboardButton(text="🔄 Обновить", callback_data=f"own_card_{uid}"),
        ],
        [
            InlineKeyboardButton(text="⭐ +30 дн.", callback_data=f"own_prem_{uid}_30"),
            InlineKeyboardButton(text="⭐ +90 дн.", callback_data=f"own_prem_{uid}_90"),
            InlineKeyboardButton(text="🗑 Снять", callback_data=f"own_unprem_{uid}"),
        ],
        [InlineKeyboardButton(text="◀️ В панель", callback_data="own_menu")],
    ])


def build_player_card(user_id):
    p = db.get_player_profile(user_id)
    if not p:
        return None
    _, username, nickname, game_id, reg_date, rating, matches, kills, deaths, _, _, premium_until = p
    rating, matches, kills, deaths = rating or 0, matches or 0, kills or 0, deaths or 0
    kd = kills / deaths if deaths > 0 else kills
    days_left = db.get_premium_days_left(user_id)
    premium_text = f"до {fmt_dt(premium_until)} ({days_left} дн.)" if days_left > 0 else "нет"
    role = " (админ)" if is_admin(user_id) else ""
    return (
        f"👤 {nickname}{role}\n"
        f"Telegram ID: {user_id}\n"
        f"Игровой ID: {game_id}\n"
        f"Username: {username or '—'}\n"
        f"Регистрация: {fmt_dt(reg_date)}\n\n"
        f"🏆 ELO: {rating} {strip_tags(get_player_level(rating))}\n"
        f"🎮 Матчей: {matches}\n"
        f"🎯 Убийств/смертей: {kills}/{deaths} (K/D {kd:.2f})\n\n"
        f"⭐️ Premium: {premium_text}"
    )


async def owner_guard(callback_query):
    if not is_owner(callback_query.from_user.id):
        await callback_query.answer("Только для владельца.", show_alert=True)
        return False
    return True


async def owner_edit(callback_query, text, keyboard):
    try:
        await callback_query.message.edit_text(text, reply_markup=keyboard)
    except TelegramBadRequest as e:
        if "not modified" not in str(e):
            await callback_query.message.answer(text, reply_markup=keyboard)


@dp.message(Command("kp"))
async def cmd_panel(message: types.Message, state: FSMContext):
    if not is_owner(message.from_user.id):
        return  # команда скрытая: остальным бот не отвечает
    if message.chat.type != "private":
        await message.answer("Панель владельца доступна только в личных сообщениях с ботом.")
        return
    await state.clear()
    await message.answer("🛠 Панель владельца", reply_markup=owner_main_keyboard())


@dp.callback_query(lambda c: c.data == "own_menu")
async def own_menu(callback_query: types.CallbackQuery, state: FSMContext):
    if not await owner_guard(callback_query):
        return
    await state.clear()
    await owner_edit(callback_query, "🛠 Панель владельца", owner_main_keyboard())
    await callback_query.answer()


@dp.callback_query(lambda c: c.data == "own_close")
async def own_close(callback_query: types.CallbackQuery, state: FSMContext):
    if not await owner_guard(callback_query):
        return
    await state.clear()
    try:
        await callback_query.message.delete()
    except Exception:
        pass
    await callback_query.answer()


@dp.callback_query(lambda c: c.data == "own_stats")
async def own_stats(callback_query: types.CallbackQuery):
    if not await owner_guard(callback_query):
        return
    s = db.get_admin_stats()
    if not s:
        await callback_query.answer("Ошибка при получении статистики.", show_alert=True)
        return
    text = (
        "📊 Статистика бота\n\n"
        f"👥 Игроков: {s['players_total']}\n"
        f"   • за 24 часа: +{s['players_24h']}\n"
        f"   • за 7 дней: +{s['players_7d']}\n\n"
        f"🎮 Матчей всего: {s['lobbies_total']}\n"
        f"   • сегодня: {s['lobbies_today']}\n"
        f"   • открытых лобби и идущих матчей: {s['lobbies_active']}\n"
        f"   • завершено: {s['lobbies_completed']}\n"
        f"   • игроко-матчей с ELO: {s['stats_entries']}\n\n"
        f"⭐️ Premium активен у: {s['premium_active']}\n"
        f"   • покупок за 30 дней: {s['premium_buys_30d']}\n"
        f"   • покупок всего: {s['premium_buys_total']}"
    )
    await owner_edit(callback_query, text, InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Обновить", callback_data="own_stats")],
        [InlineKeyboardButton(text="◀️ В панель", callback_data="own_menu")],
    ]))
    await callback_query.answer()


@dp.callback_query(lambda c: c.data == "own_search")
async def own_search(callback_query: types.CallbackQuery, state: FSMContext):
    if not await owner_guard(callback_query):
        return
    await state.set_state(OwnerStates.waiting_for_search)
    await owner_edit(
        callback_query,
        "🔍 Отправьте ник, Telegram ID, игровой ID или @username игрока.",
        InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Отмена", callback_data="own_menu")]]),
    )
    await callback_query.answer()


@dp.message(OwnerStates.waiting_for_search)
async def own_search_query(message: types.Message, state: FSMContext):
    if not is_owner(message.from_user.id):
        return
    target = db.find_player_id(message.text or "")
    if not target:
        await message.answer("❌ Игрок не найден. Пришлите другой запрос или откройте /kp.")
        return
    await state.clear()
    await message.answer(build_player_card(target), reply_markup=owner_card_keyboard(target))


@dp.callback_query(lambda c: c.data.startswith("own_card_"))
async def own_card(callback_query: types.CallbackQuery, state: FSMContext):
    if not await owner_guard(callback_query):
        return
    await state.clear()
    try:
        target = int(callback_query.data.replace("own_card_", ""))
    except ValueError:
        await callback_query.answer()
        return
    card = build_player_card(target)
    if not card:
        await callback_query.answer("Игрок не найден.", show_alert=True)
        return
    await owner_edit(callback_query, card, owner_card_keyboard(target))
    await callback_query.answer()


@dp.callback_query(lambda c: c.data.startswith("own_prem_"))
async def own_grant_premium(callback_query: types.CallbackQuery):
    if not await owner_guard(callback_query):
        return
    try:
        _, _, uid_s, days_s = callback_query.data.split("_")
        target, days = int(uid_s), int(days_s)
    except ValueError:
        await callback_query.answer()
        return
    if days not in (30, 90):
        await callback_query.answer()
        return
    new_until = db.grant_premium_days(target, days)
    if not new_until:
        await callback_query.answer("Не удалось выдать Premium.", show_alert=True)
        return
    db.log_admin_action(callback_query.from_user.id, "grant_premium", target, f"+{days} дн. до {new_until}")
    try:
        await bot.send_message(chat_id=target, text=f"⭐️ Вам выдан Premium на {days} дн.")
    except Exception:
        pass
    await owner_edit(callback_query, build_player_card(target), owner_card_keyboard(target))
    await callback_query.answer(f"Выдано {days} дн.")


@dp.callback_query(lambda c: c.data.startswith("own_unprem_"))
async def own_remove_premium(callback_query: types.CallbackQuery):
    if not await owner_guard(callback_query):
        return
    try:
        target = int(callback_query.data.replace("own_unprem_", ""))
    except ValueError:
        await callback_query.answer()
        return
    if db.remove_premium(target):
        db.log_admin_action(callback_query.from_user.id, "remove_premium", target, None)
    await owner_edit(callback_query, build_player_card(target), owner_card_keyboard(target))
    await callback_query.answer("Premium снят")


@dp.callback_query(lambda c: c.data.startswith("own_rate_"))
async def own_rate_start(callback_query: types.CallbackQuery, state: FSMContext):
    if not await owner_guard(callback_query):
        return
    try:
        target = int(callback_query.data.replace("own_rate_", ""))
    except ValueError:
        await callback_query.answer()
        return
    p = db.get_player_profile(target)
    if not p:
        await callback_query.answer("Игрок не найден.", show_alert=True)
        return
    await state.set_state(OwnerStates.waiting_for_rating)
    await state.update_data(rating_target=target)
    await owner_edit(
        callback_query,
        f"✏️ ELO игрока {p[2]}: {p[5] or 0}\n\n"
        "Отправьте новое значение (например 500) или изменение со знаком (+50 / -30).",
        InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Отмена", callback_data=f"own_card_{target}")]]),
    )
    await callback_query.answer()


@dp.message(OwnerStates.waiting_for_rating)
async def own_rate_value(message: types.Message, state: FSMContext):
    if not is_owner(message.from_user.id):
        return
    data = await state.get_data()
    target = data.get("rating_target")
    raw = (message.text or "").strip().replace(" ", "")
    if not target or not re.fullmatch(r"[+-]?\d{1,6}", raw):
        await message.answer("❌ Нужно число, например 500, +50 или -30.")
        return
    p = db.get_player_profile(target)
    if not p:
        await state.clear()
        await message.answer("❌ Игрок не найден.")
        return
    old = p[5] or 0
    new = old + int(raw) if raw[0] in "+-" else int(raw)
    new = max(0, min(new, 100000))
    if not db.set_player_rating(target, new):
        await message.answer("❌ Не удалось изменить ELO.")
        return
    db.log_admin_action(message.from_user.id, "set_rating", target, f"{old} -> {new}")
    await state.clear()
    await message.answer(f"✅ ELO изменено: {old} → {new}")
    await message.answer(build_player_card(target), reply_markup=owner_card_keyboard(target))


# ---------- управление админами ----------
@dp.callback_query(lambda c: c.data == "own_admins")
async def own_admins(callback_query: types.CallbackQuery, state: FSMContext = None):
    if not await owner_guard(callback_query):
        return
    if state is not None:
        await state.clear()
    lines = ["👮 Администраторы бота\n"]
    rows = []
    for uid in ADMINS:
        p = db.get_player_profile(uid)
        nick = p[2] if p else "не зарегистрирован"
        if is_owner(uid):
            tag = " — владелец"
        elif uid in FILE_ADMINS:
            tag = " — из admins.txt"
        else:
            tag = ""
        lines.append(f"• {nick} ({uid}){tag}")
        if not is_owner(uid) and uid not in FILE_ADMINS:
            rows.append([InlineKeyboardButton(text=f"❌ Убрать: {nick}", callback_data=f"own_admin_del_{uid}")])
    lines.append("\nАдмины из admins.txt убираются только правкой файла.")
    rows.append([InlineKeyboardButton(text="➕ Добавить админа", callback_data="own_admin_add")])
    rows.append([InlineKeyboardButton(text="◀️ В панель", callback_data="own_menu")])
    await owner_edit(callback_query, "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=rows))
    await callback_query.answer()


@dp.callback_query(lambda c: c.data == "own_admin_add")
async def own_admin_add(callback_query: types.CallbackQuery, state: FSMContext):
    if not await owner_guard(callback_query):
        return
    await state.set_state(OwnerStates.waiting_for_admin)
    await owner_edit(
        callback_query,
        "➕ Отправьте Telegram ID нового админа (число), либо ник или @username игрока из бота.",
        InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Отмена", callback_data="own_admins")]]),
    )
    await callback_query.answer()


@dp.message(OwnerStates.waiting_for_admin)
async def own_admin_add_value(message: types.Message, state: FSMContext):
    if not is_owner(message.from_user.id):
        return
    raw = (message.text or "").strip()
    if raw.isdigit():
        target = int(raw)   # число считаем Telegram ID
    else:
        target = db.find_player_id(raw)
    if not target:
        await message.answer("❌ Не нашла такого игрока. Пришлите Telegram ID (число) или ник игрока.")
        return
    if target in ADMINS:
        await message.answer("ℹ️ Этот пользователь уже администратор.")
        return
    if not db.add_bot_admin(target, message.from_user.id):
        await message.answer("❌ Не удалось сохранить администратора.")
        return
    ADMINS.append(target)
    db.log_admin_action(message.from_user.id, "add_admin", target, None)
    await state.clear()
    try:
        await bot.send_message(chat_id=target, text="👮 Вам выданы права администратора бота.")
    except Exception:
        pass
    try:
        await set_bot_commands_for_user(target)
    except Exception as e:
        logger.warning(f"Cannot refresh commands for new admin {target}: {e}")
    await message.answer(
        f"✅ Админ добавлен: {player_label(target)}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="👮 К списку админов", callback_data="own_admins")]]),
    )


@dp.callback_query(lambda c: c.data.startswith("own_admin_del_"))
async def own_admin_del(callback_query: types.CallbackQuery, state: FSMContext):
    if not await owner_guard(callback_query):
        return
    try:
        target = int(callback_query.data.replace("own_admin_del_", ""))
    except ValueError:
        await callback_query.answer()
        return
    if is_owner(target) or target in FILE_ADMINS:
        await callback_query.answer("Этого админа нельзя убрать из панели.", show_alert=True)
        return
    if db.remove_bot_admin(target):
        if target in ADMINS:
            ADMINS.remove(target)
        db.log_admin_action(callback_query.from_user.id, "remove_admin", target, None)
        try:
            await bot.send_message(chat_id=target, text="ℹ️ Права администратора бота сняты.")
        except Exception:
            pass
        try:
            await set_bot_commands_for_user(target)
        except Exception as e:
            logger.warning(f"Cannot refresh commands for {target}: {e}")
    await own_admins(callback_query, state)


# ======================================================================
# ИТОГИ МАТЧА В КАНАЛ
# ======================================================================


# ---------- промокоды (панель владельца) ----------
PROMO_KIND_ALIASES = {
    "days": "days", "day": "days", "дни": "days", "дней": "days", "дн": "days",
    "percent": "percent", "процент": "percent", "процентов": "percent", "%": "percent",
}


def generate_promo_code():
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(random.choice(alphabet) for _ in range(8))


def parse_promo_input(text):
    """КОД ТИП ЗНАЧЕНИЕ [ЛИМИТ] [ДНЕЙ_ДЕЙСТВИЯ] -> ((code, kind, value, max_uses, valid_days), None) или (None, ошибка)."""
    parts = (text or "").split()
    if len(parts) < 3:
        return None, "Нужно минимум три слова: КОД ТИП ЗНАЧЕНИЕ"
    code = parts[0].upper()
    if code in ("AUTO", "АВТО"):
        code = generate_promo_code()
    if not re.fullmatch(r"[A-Z0-9_-]{3,20}", code):
        return None, "Код: 3-20 символов, только латинские буквы, цифры, «-» и «_»."
    kind = PROMO_KIND_ALIASES.get(parts[1].lower())
    if not kind:
        return None, "Тип: days (дни Premium) или percent (скидка в %)."
    try:
        value = int(parts[2])
        max_uses = int(parts[3]) if len(parts) > 3 else 1
        valid_days = int(parts[4]) if len(parts) > 4 else None
    except ValueError:
        return None, "Значение, лимит и срок должны быть числами."
    if kind == "days" and not 1 <= value <= 365:
        return None, "Дней Premium должно быть от 1 до 365."
    if kind == "percent" and not 1 <= value <= 90:
        return None, "Скидка должна быть от 1 до 90 процентов."
    if not 0 <= max_uses <= 100000:
        return None, "Лимит использований: от 0 (без лимита) до 100000."
    if valid_days is not None and not 1 <= valid_days <= 3650:
        return None, "Срок действия в днях: от 1 до 3650."
    return (code, kind, value, max_uses, valid_days), None


def format_promo_line(code, kind, value, max_uses, uses, expires_at, active):
    what = f"+{value} дн. Premium" if kind == "days" else f"скидка {value}%"
    limit = f"{uses}/{max_uses}" if max_uses else f"{uses}/∞"
    until = f", до {fmt_dt(expires_at)}" if expires_at else ""
    return f"{'🟢' if active else '🔴'} {code} — {what} — {limit}{until}"


@dp.callback_query(lambda c: c.data == "own_promos")
async def own_promos(callback_query: types.CallbackQuery, state: FSMContext = None):
    if not await owner_guard(callback_query):
        return
    if state is not None:
        await state.clear()
    promos = db.list_promos(15)
    lines = ["🎟 Промокоды (последние 15)\n"]
    rows = []
    if not promos:
        lines.append("Пока нет ни одного промокода.")
    for code, kind, value, max_uses, uses, expires_at, active in promos:
        lines.append(format_promo_line(code, kind, value, max_uses, uses, expires_at, active))
        rows.append([InlineKeyboardButton(
            text=f"{'⏸ Выключить' if active else '▶️ Включить'} {code}",
            callback_data=f"own_promo_tgl_{code}",
        )])
    rows.append([InlineKeyboardButton(text="➕ Создать промокод", callback_data="own_promo_new")])
    rows.append([InlineKeyboardButton(text="◀️ В панель", callback_data="own_menu")])
    await owner_edit(callback_query, "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=rows))
    await callback_query.answer()


@dp.callback_query(lambda c: c.data == "own_promo_new")
async def own_promo_new(callback_query: types.CallbackQuery, state: FSMContext):
    if not await owner_guard(callback_query):
        return
    await state.set_state(OwnerStates.waiting_for_promo)
    await owner_edit(
        callback_query,
        "➕ Новый промокод. Отправьте одной строкой:\n\n"
        "КОД ТИП ЗНАЧЕНИЕ [ЛИМИТ] [ДНЕЙ_ДЕЙСТВИЯ]\n\n"
        "Примеры:\n"
        "SUMMER days 7 50 30 — 7 дней Premium, 50 использований, действует 30 дней\n"
        "SALE percent 20 100 — скидка 20% на покупку, 100 использований\n"
        "auto days 3 — случайный код, 3 дня Premium, одно использование\n\n"
        "Лимит по умолчанию 1, 0 = без лимита. Скидки не суммируются с «первой покупкой»: берётся лучшая.",
        InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Отмена", callback_data="own_promos")]]),
    )
    await callback_query.answer()


@dp.message(OwnerStates.waiting_for_promo)
async def own_promo_value(message: types.Message, state: FSMContext):
    if not is_owner(message.from_user.id):
        return
    parsed, err = parse_promo_input(message.text or "")
    if err:
        await message.answer(f"❌ {err}")
        return
    code, kind, value, max_uses, valid_days = parsed
    ok, create_err = db.create_promo(code, kind, value, max_uses, valid_days, message.from_user.id)
    if not ok:
        await message.answer(f"❌ {create_err}")
        return
    db.log_admin_action(message.from_user.id, "create_promo", None, f"{code} {kind} {value} limit={max_uses}")
    await state.clear()
    await message.answer(
        f"✅ Промокод создан: {code}\n"
        f"{'+' + str(value) + ' дн. Premium' if kind == 'days' else 'Скидка ' + str(value) + '%'}, "
        f"лимит: {max_uses or 'без лимита'}"
        f"{', действует ' + str(valid_days) + ' дн.' if valid_days else ''}\n\n"
        "Игроки вводят его в меню Premium → «Промокод».",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🎟 К списку промокодов", callback_data="own_promos")]]),
    )


@dp.callback_query(lambda c: c.data.startswith("own_promo_tgl_"))
async def own_promo_toggle(callback_query: types.CallbackQuery, state: FSMContext):
    if not await owner_guard(callback_query):
        return
    code = callback_query.data.replace("own_promo_tgl_", "")
    new_state = db.toggle_promo(code)
    if new_state is None:
        await callback_query.answer("Промокод не найден.", show_alert=True)
        return
    db.log_admin_action(callback_query.from_user.id, "toggle_promo", None, f"{code} -> {'on' if new_state else 'off'}")
    await own_promos(callback_query, state)


async def cleanup_old_messages():
    try:
        lobby_size = len(user_lobby_messages.cache)
        menu_size = len(user_menu_messages.cache)
        if lobby_size > 900 or menu_size > 900:
            logger.info(f"Cache sizes - Lobby: {lobby_size}, Menu: {menu_size}")
    except Exception as e:
        logger.error(f"Error in cleanup_old_messages: {e}")


# ======================================================================
# FACEIT: автолобби 2x2 / 5x5, выбор игроков капитанами, матчи и ELO
# ======================================================================
FC_MODES = {
    "2x2": {"team_size": 2, "title": "2×2"},
    "5x5": {"team_size": 5, "title": "5×5"},
}
FC_MAPS = [
    "🏜 Sandstone", "🏘 Province", "🧱 Rust", "🏭 Zone 7", "🏭 Zone 9",
    "🏝️ Breeze", "🌸 Sakura", "🏞 Dune",
]
FC_SIDES = {"ct": "🔵 CT", "t": "🟠 T"}

FC_MIN_OPEN_LOBBIES = max(3, _env_int('FC_MIN_OPEN_LOBBIES', 3))   # минимум открытых лобби на каждый режим
ELO_WIN = _env_int('ELO_WIN', 25)                 # ELO за победу
ELO_LOSS = _env_int('ELO_LOSS', 20)               # ELO за поражение (ниже 0 не опускается)
ELO_PREMIUM_MULT = 1.5                            # множитель ELO за победу для Premium
PICK_TIMEOUT_SEC = _env_int('PICK_TIMEOUT_SEC', 60)   # время капитана на выбор, потом выбор делает бот
HOST_MODE = os.getenv('HOST_MODE', 'random').strip().lower()   # random — случайный игрок, captain — капитан
CLOSE_TOPIC_AFTER_MATCH = os.getenv('CLOSE_TOPIC_AFTER_MATCH', 'true').strip().lower() in ('true', '1', 'yes', 'on')

FC_COLORED_BUTTONS = os.getenv('FC_COLORED_BUTTONS', 'true').strip().lower() in ('true', '1', 'yes', 'on')
_colored_state = {"on": FC_COLORED_BUTTONS}
_topic_icon_cache = {}


class FcStates(StatesGroup):
    waiting_for_result_screenshot = State()


def fc_title(mode):
    return FC_MODES.get(mode, {}).get("title", mode)


def fc_back_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[[btn("◀️ В меню", callback_data="back_to_main", icon="◀️")]])


def kd_value(kills, deaths):
    return (kills / deaths) if deaths and deaths > 0 else float(kills or 0)


def player_kd(p):
    return kd_value(p["total_kills"], p["total_deaths"])


def choose_captains(players):
    """Капитаны: сначала игроки с Premium, затем самые сильные по K/D (дальше ELO, дальше случайно).
    Возвращает (сильнейший_капитан, второй_капитан)."""
    ranked = sorted(
        players,
        key=lambda p: (p["premium"], player_kd(p), p["elo"], random.random()),
        reverse=True,
    )
    return ranked[0], ranked[1]


async def ensure_open_lobbies():
    """Всегда держим минимум FC_MIN_OPEN_LOBBIES (3) открытых лобби каждого режима. Карту выбирают капитаны."""
    for mode, cfg in FC_MODES.items():
        open_lobbies = db.fc_get_open_lobbies(mode)
        for _ in range(max(0, FC_MIN_OPEN_LOBBIES - len(open_lobbies))):
            lobby_id = db.fc_create_lobby(mode, cfg["team_size"], None)
            logger.info(f"Created open lobby {lobby_id} ({mode})")


def build_lobby_list(mode):
    """Список открытых лобби режима для выбора."""
    cap = FC_MODES[mode]["team_size"] * 2
    lobbies = db.fc_get_open_lobbies(mode)
    lines = [f"{pe('🎮')} <b>Режим {fc_title(mode)}</b> — выберите лобби", ""]
    rows = []
    for lobby_id, _map_name, count in lobbies:
        lines.append(f"Лобби #{lobby_id} · {count}/{cap}")
        rows.append([InlineKeyboardButton(text=f"Лобби #{lobby_id} · {count}/{cap}", callback_data=f"fcview_{lobby_id}")])
    if not lobbies:
        lines.append("Лобби создаются, попробуйте через пару секунд.")
    lines += ["", "Карту выберут капитаны после того, как соберут команды."]
    rows.append([btn("🔄 Обновить", callback_data=f"fclist_{mode}", icon="🔄")])
    rows.append([btn("◀️ Назад", callback_data="fcfind", icon="◀️")])
    return "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=rows)


def elo_progress(elo):
    """(следующий уровень, сколько ELO до него) или None на максимальном уровне."""
    thresholds = [101, 221, 321, 401, 521, 621, 751, 871, 1001]
    for i, t in enumerate(thresholds):
        if elo < t:
            return i + 2, t - elo
    return None


# ---------- отрисовка ----------
def parse_bans(raw):
    """'ct:Rust|t:Dune' -> [('ct', 'Rust'), ('t', 'Dune')]"""
    result = []
    for entry in (raw or "").split("|"):
        if ":" in entry:
            team, name = entry.split(":", 1)
            result.append((team, name))
    return result


def map_button(lobby_id, index, name, banned):
    """Кнопка карты: забаненная краснеет (стиль danger + 🔴) и не нажимается второй раз."""
    if banned:
        text = f"🔴 {name}"
        if _colored_state["on"]:
            return InlineKeyboardButton(text=text, callback_data=f"fcmapno_{lobby_id}", style="danger")
        return InlineKeyboardButton(text=text, callback_data=f"fcmapno_{lobby_id}")
    return InlineKeyboardButton(text=name, callback_data=f"fcban_{lobby_id}_{index}")


def team_block(players, team, with_ids=False, mark_captain=True):
    lines = []
    for p in [x for x in players if x["team"] == team]:
        cap = " (Капитан)" if (mark_captain and p["is_captain"]) else ""
        lines.append(
            f"{get_player_level(p['elo'])} {display_nickname(p['user_id'], p['nickname'])} — {p['elo']} ELO{cap}"
        )
        if with_ids:
            lines.append(f"TG_ID:<code>{p['user_id']}</code>")
    return lines


def render_lobby(lobby_id, user_id):
    """Текст и клавиатура сообщения лобби/матча для конкретного игрока."""
    lobby = db.fc_get_lobby(lobby_id)
    if not lobby:
        return f"{pe('❌')} Лобби не найдено.", fc_back_keyboard()
    (_, mode, team_size, map_name, status, cap_ct, cap_t, turn, _, host_id, _, winner, _created, _filled, _finished, veto_banned) = lobby
    players = db.fc_get_players(lobby_id)
    capacity = team_size * 2
    me = next((p for p in players if p["user_id"] == user_id), None)
    title = fc_title(mode)

    if status == "open":
        lines = [
            f"{pe('🎮')} <b>Лобби {title} #{lobby_id}</b>",
            f"{pe('👥')} Игроков: {len(players)}/{capacity}",
            "",
        ]
        for i, p in enumerate(players, 1):
            lines.append(f"{i}. {get_player_level(p['elo'])} {display_nickname(p['user_id'], p['nickname'])} — {p['elo']} ELO")
        for i in range(len(players) + 1, capacity + 1):
            lines.append(f"{i}. —")
        lines += ["", "После заполнения лобби капитаны по очереди выберут игроков в команды, а затем забанят карты."]
        if me:
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [btn("🚪 Выйти из лобби", callback_data=f"fcleave_{lobby_id}", icon="🚪")],
                [btn("🔄 Обновить", callback_data=f"fcview_{lobby_id}", icon="🔄")],
                [btn("◀️ В меню", callback_data="back_to_main", icon="◀️")],
            ])
        else:
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [btn("✅ Присоединиться", callback_data=f"fcjoin_{lobby_id}", icon="✅")],
                [btn("🔄 Обновить", callback_data=f"fcview_{lobby_id}", icon="🔄")],
                [btn("◀️ К списку лобби", callback_data=f"fclist_{mode}", icon="◀️")],
            ])
        return "\n".join(lines), kb

    if status == "draft":
        turn_cap = next((p for p in players if p["user_id"] == (cap_ct if turn == "ct" else cap_t)), None)
        free = [p for p in players if p["team"] is None]
        lines = [
            f"{pe('🏁')} <b>Матч #{lobby_id} — выбор игроков</b>",
            "",
            FC_SIDES["ct"],
            *(team_block(players, "ct") or ["—"]),
            "",
            FC_SIDES["t"],
            *(team_block(players, "t") or ["—"]),
            "",
        ]
        if turn_cap:
            lines.append(f"{pe('⏳')} Выбирает: <b>{display_nickname(turn_cap['user_id'], turn_cap['nickname'])}</b> ({FC_SIDES[turn]})")
        lines.append(f"Осталось выбрать: {len(free)}  ·  на ход даётся {PICK_TIMEOUT_SEC} сек.")
        if me and me["is_captain"] and turn_cap and turn_cap["user_id"] == user_id:
            lines.append(f"\n{pe('👉')} <b>Ваш ход — нажмите на игрока:</b>")
        rows, row = [], []
        for p in sorted(free, key=lambda x: (-player_kd(x), -x["elo"])):
            row.append(InlineKeyboardButton(
                text=f"{p['nickname']} · K/D {player_kd(p):.2f}",
                callback_data=f"fcpick_{lobby_id}_{p['user_id']}",
            ))
            if len(row) == 2:
                rows.append(row)
                row = []
        if row:
            rows.append(row)
        rows.append([btn("🔄 Обновить", callback_data=f"fcview_{lobby_id}", icon="🔄")])
        return "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=rows)

    if status == "veto":
        bans = parse_bans(veto_banned)
        banned_names = [name for _, name in bans]
        turn_cap = next((p for p in players if p["user_id"] == (cap_ct if turn == "ct" else cap_t)), None) if turn else None
        lines = [
            f"{pe('🗺')} <b>Матч #{lobby_id} — бан карт</b>",
            "",
            f"{FC_SIDES['ct']}: " + (", ".join(p['nickname'] for p in players if p['team'] == 'ct') or "—"),
            f"{FC_SIDES['t']}: " + (", ".join(p['nickname'] for p in players if p['team'] == 't') or "—"),
            "",
            "Капитаны по очереди банят карты. Последняя оставшаяся карта будет сыграна.",
        ]
        if turn_cap:
            lines.append(f"\n{pe('⏳')} Банит: <b>{display_nickname(turn_cap['user_id'], turn_cap['nickname'])}</b> ({FC_SIDES[turn]})")
        lines.append(f"Забанено: {len(bans)} из {len(FC_MAPS) - 1}  ·  на ход даётся {PICK_TIMEOUT_SEC} сек.")
        if len(bans) == len(FC_MAPS) - 2:
            lines.append(f"{pe('⚠️')} Осталось две карты: та, которую вы забаните, играться НЕ будет — сыграют оставшуюся.")
        if bans:
            lines.append("Баны: " + " · ".join(f"{i}. {name} ({FC_SIDES.get(team, '')})" for i, (team, name) in enumerate(bans, 1)))
        if me and me["is_captain"] and turn_cap and turn_cap["user_id"] == user_id:
            lines.append(f"\n{pe('👉')} <b>Ваш ход — нажмите на карту, которую хотите забанить:</b>")
        rows, row = [], []
        for i, name in enumerate(FC_MAPS):
            row.append(map_button(lobby_id, i, name, name in banned_names))
            if len(row) == 2:
                rows.append(row)
                row = []
        if row:
            rows.append(row)
        rows.append([btn("🔄 Обновить", callback_data=f"fcview_{lobby_id}", icon="🔄")])
        return "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=rows)

    if status == "live":
        host = next((p for p in players if p["user_id"] == host_id), None)
        my_side = FC_SIDES.get(me["team"], "") if me else ""
        lines = [
            f"{pe('🎮')} <b>Матч #{lobby_id} начался!</b>",
            f"{pe('🗺')} Карта: {map_name}",
        ]
        if host:
            lines.append(f"{pe('👑')} Хост: {display_nickname(host['user_id'], host['nickname'])} | ID: <code>{esc(host['game_id'])}</code>")
        if my_side:
            lines.append(f"Ваша сторона: <b>{my_side}</b>")
        lines += ["", FC_SIDES["ct"], *team_block(players, "ct"), "", FC_SIDES["t"], *team_block(players, "t"), "",
                  "Хост создаёт комнату в игре, остальные заходят по его ID.",
                  f"{pe('📸')} После матча капитан отправляет скриншот результата — модераторы начислят ELO."]
        rows = []
        if me and me["is_captain"]:
            rows.append([btn("📸 Отправить результат", callback_data=f"fcshot_{lobby_id}", icon="📸")])
        rows.append([btn("🔄 Обновить", callback_data=f"fcview_{lobby_id}", icon="🔄")])
        return "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=rows)

    if status == "finished":
        return f"{pe('🏁')} Матч #{lobby_id} уже завершён.", fc_back_keyboard()
    return f"{pe('❌')} Матч #{lobby_id} отменён.", fc_back_keyboard()


async def _push_once(user_id, text, kb, force_new):
    message_id = None if force_new else db.kv_get(f"fcmsg:{user_id}")
    if message_id:
        try:
            await bot.edit_message_text(chat_id=user_id, message_id=int(message_id), text=text,
                                        reply_markup=kb, parse_mode='HTML')
            return True
        except TelegramBadRequest as e:
            if "not modified" in str(e):
                return True
        except Exception as e:
            logger.info(f"Cannot edit lobby message for {user_id}: {e}")
    try:
        message = await bot.send_message(chat_id=user_id, text=text, reply_markup=kb, parse_mode='HTML')
        db.kv_set(f"fcmsg:{user_id}", message.message_id)
        return True
    except Exception as e:
        logger.warning(f"Cannot send lobby message to {user_id}: {e}")
        return False


async def push_lobby_view(lobby_id, user_id, force_new=False):
    """Обновляет (или отправляет) игроку единственное сообщение с лобби/матчем."""
    text, kb = render_lobby(lobby_id, user_id)
    ok_sent = await _push_once(user_id, text, kb, force_new)
    if not ok_sent and _colored_state["on"]:
        lobby = db.fc_get_lobby(lobby_id)
        if lobby and lobby[4] == "veto":
            # возможно, клиент/Телеграм не принял цветные кнопки: отключаем их и пробуем ещё раз
            _colored_state["on"] = False
            logger.warning("Coloured buttons rejected, switching to plain buttons (🔴 emoji only)")
            text, kb = render_lobby(lobby_id, user_id)
            ok_sent = await _push_once(user_id, text, kb, force_new)
    return ok_sent


async def refresh_lobby_for_all(lobby_id, force_new=False):
    for p in db.fc_get_players(lobby_id):
        await push_lobby_view(lobby_id, p["user_id"], force_new=force_new)


async def open_lobby_for_user(user_id, lobby_id):
    """Показывает лобби новым сообщением (старое меню убираем)."""
    await cleanup_user_messages(user_id)
    old = db.kv_get(f"fcmsg:{user_id}")
    if old:
        await safe_delete_message(chat_id=user_id, message_id=int(old))
        db.kv_delete(f"fcmsg:{user_id}")
    await push_lobby_view(lobby_id, user_id, force_new=True)


# ---------- вход в лобби ----------
@dp.callback_query(lambda c: c.data == "fcfind")
async def fc_find(callback_query: types.CallbackQuery):
    """«Найти матч»: выбор режима 2 на 2 / 5 на 5 (или возврат в текущее лобби/матч)."""
    user_id = callback_query.from_user.id
    if not db.is_user_registered(user_id):
        await callback_query.answer("❌ Сначала зарегистрируйтесь.", show_alert=True)
        return
    active = db.fc_get_user_active_lobby(user_id)
    if active:
        await open_lobby_for_user(user_id, active)
        await callback_query.answer()
        return
    await ensure_open_lobbies()
    await cleanup_user_messages(user_id)
    waiting = {mode: sum(row[2] for row in db.fc_get_open_lobbies(mode)) for mode in FC_MODES}
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            btn(f"2 на 2 · в очереди: {waiting['2x2']}", callback_data="fcmode_2x2", icon="🎮"),
            btn(f"5 на 5 · в очереди: {waiting['5x5']}", callback_data="fcmode_5x5", icon="🎮"),
        ],
        [btn("◀️ Назад", callback_data="back_to_main", icon="◀️")],
    ])
    await send_message_with_image(user_id, f"{pe('🎮')} <b>Найти матч</b>\n\nВыберите режим:", None, kb)
    await callback_query.answer()


@dp.callback_query(lambda c: c.data.startswith("fcmode_"))
async def fc_mode(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    mode = callback_query.data.replace("fcmode_", "")
    if mode not in FC_MODES or not db.is_user_registered(user_id):
        await callback_query.answer("❌ Сначала зарегистрируйтесь.", show_alert=True)
        return
    active = db.fc_get_user_active_lobby(user_id)
    if active:
        await open_lobby_for_user(user_id, active)
        await callback_query.answer()
        return
    await ensure_open_lobbies()
    await cleanup_user_messages(user_id)
    text, kb = build_lobby_list(mode)
    await send_message_with_image(user_id, text, None, kb)
    await callback_query.answer()


@dp.callback_query(lambda c: c.data.startswith("fclist_"))
async def fc_list(callback_query: types.CallbackQuery):
    """Обновляет список лобби прямо в текущем сообщении."""
    user_id = callback_query.from_user.id
    mode = callback_query.data.replace("fclist_", "")
    if mode not in FC_MODES:
        await callback_query.answer()
        return
    db.kv_delete(f"fcmsg:{user_id}")
    await ensure_open_lobbies()
    text, kb = build_lobby_list(mode)
    try:
        await callback_query.message.edit_text(text, reply_markup=kb, parse_mode='HTML')
    except TelegramBadRequest:
        pass
    await callback_query.answer()


@dp.callback_query(lambda c: c.data == "fcmine")
async def fc_mine(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    active = db.fc_get_user_active_lobby(user_id)
    if not active:
        await callback_query.answer("Вы сейчас не в лобби.", show_alert=True)
        return
    await open_lobby_for_user(user_id, active)
    await callback_query.answer()


@dp.callback_query(lambda c: c.data.startswith("fcview_"))
async def fc_view(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    try:
        lobby_id = int(callback_query.data.replace("fcview_", ""))
    except ValueError:
        await callback_query.answer()
        return
    db.kv_set(f"fcmsg:{user_id}", callback_query.message.message_id)
    await push_lobby_view(lobby_id, user_id)
    await callback_query.answer()


@dp.callback_query(lambda c: c.data.startswith("fcjoin_"))
async def fc_join_confirm(callback_query: types.CallbackQuery):
    """Шаг подтверждения перед входом в лобби."""
    user_id = callback_query.from_user.id
    try:
        lobby_id = int(callback_query.data.replace("fcjoin_", ""))
    except ValueError:
        await callback_query.answer()
        return
    lobby = db.fc_get_lobby(lobby_id)
    if not db.is_user_registered(user_id):
        await callback_query.answer("❌ Сначала зарегистрируйтесь.", show_alert=True)
        return
    if not lobby or lobby[4] != "open":
        await callback_query.answer("Это лобби уже недоступно.", show_alert=True)
        return
    if db.fc_get_user_active_lobby(user_id):
        await callback_query.answer("Вы уже участвуете в другом лобби или матче.", show_alert=True)
        return
    count = len(db.fc_get_players(lobby_id))
    text = (
        f"{pe('❓')} <b>Подтвердите вход в лобби</b>\n\n"
        f"{pe('🎮')} Режим: {fc_title(lobby[1])}\n"
        f"{pe('👥')} Игроков сейчас: {count}/{lobby[2] * 2}\n\n"
        f"После входа вы не сможете присоединиться к другому лобби, пока не выйдете или не закончится матч."
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [btn("✅ Подтвердить", callback_data=f"fcjoinok_{lobby_id}", icon="✅"),
         btn("❌ Отмена", callback_data=f"fcview_{lobby_id}", icon="❌")],
    ])
    try:
        await callback_query.message.edit_text(text, reply_markup=kb, parse_mode='HTML')
    except TelegramBadRequest:
        pass
    await callback_query.answer()


@dp.callback_query(lambda c: c.data.startswith("fcjoinok_"))
async def fc_join(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    try:
        lobby_id = int(callback_query.data.replace("fcjoinok_", ""))
    except ValueError:
        await callback_query.answer()
        return
    if not db.is_user_registered(user_id):
        await callback_query.answer("❌ Сначала зарегистрируйтесь.", show_alert=True)
        return
    ok, error, count, capacity = db.fc_join(lobby_id, user_id)
    if not ok:
        await callback_query.answer(f"❌ {error}", show_alert=True)
        return
    db.kv_set(f"fcmsg:{user_id}", callback_query.message.message_id)
    await callback_query.answer("✅ Вы в лобби")
    if count >= capacity:
        await start_draft(lobby_id)
    else:
        await refresh_lobby_for_all(lobby_id)


@dp.callback_query(lambda c: c.data.startswith("fcleave_"))
async def fc_leave(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    try:
        lobby_id = int(callback_query.data.replace("fcleave_", ""))
    except ValueError:
        await callback_query.answer()
        return
    if not db.fc_leave(lobby_id, user_id):
        await callback_query.answer("Выйти нельзя: лобби уже заполнено или вы в нём не состоите.", show_alert=True)
        return
    db.kv_delete(f"fcmsg:{user_id}")
    await callback_query.answer("🚪 Вы вышли из лобби")
    await safe_delete_message(chat_id=user_id, message_id=callback_query.message.message_id)
    await send_message_with_image(
        user_id, f"{pe('👋')} Вы вышли из лобби.\n\nВыберите действие:", MENU_IMAGE_URL, get_main_keyboard(user_id)
    )
    await refresh_lobby_for_all(lobby_id)


# ---------- выбор игроков капитанами ----------
async def start_draft(lobby_id):
    """Лобби заполнено: выбираем капитанов, открываем новое лобби и запускаем драфт."""
    players = db.fc_get_players(lobby_id)
    if len(players) < 2:
        return
    strong, weak = choose_captains(players)
    if random.random() < 0.5:
        ct, t = strong, weak
    else:
        ct, t = weak, strong
    first_turn = "ct" if weak["user_id"] == ct["user_id"] else "t"   # слабейший капитан выбирает первым
    if not db.fc_set_draft(lobby_id, ct["user_id"], t["user_id"], first_turn):
        return
    db.kv_set(f"fc_firstpick:{lobby_id}", first_turn)
    await ensure_open_lobbies()                  # освободили очередь: сразу появилось новое лобби
    await refresh_lobby_for_all(lobby_id)
    for p, side in ((ct, "ct"), (t, "t")):
        try:
            await bot.send_message(
                chat_id=p["user_id"],
                text=f"{pe('👑')} Вы капитан команды {FC_SIDES[side]} в матче #{lobby_id}!",
                parse_mode='HTML',
            )
        except Exception as e:
            logger.info(f"Cannot notify captain {p['user_id']}: {e}")
    for p in players:
        if p["user_id"] not in (ct["user_id"], t["user_id"]):
            try:
                await bot.send_message(
                    chat_id=p["user_id"],
                    text=f"{pe('🏁')} Лобби #{lobby_id} заполнено! Капитаны выбирают игроков в команды.",
                    parse_mode='HTML',
                )
            except Exception as e:
                logger.info(f"Cannot notify {p['user_id']} about the draft: {e}")


async def after_pick(lobby_id, remaining, next_turn):
    if remaining == 1:                           # последнего игрока бот ставит сам
        free = [p for p in db.fc_get_players(lobby_id) if p["team"] is None]
        if free:
            db.fc_assign_player(lobby_id, free[0]["user_id"], next_turn)
            remaining = 0
    if remaining == 0:
        await start_veto(lobby_id)
    else:
        await refresh_lobby_for_all(lobby_id)


@dp.callback_query(lambda c: c.data.startswith("fcpick_"))
async def fc_pick(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    try:
        _, lobby_s, target_s = callback_query.data.split("_")
        lobby_id, target_id = int(lobby_s), int(target_s)
    except ValueError:
        await callback_query.answer()
        return
    ok, error, remaining, next_turn = db.fc_pick(lobby_id, user_id, target_id)
    if not ok:
        await callback_query.answer(f"❌ {error}", show_alert=True)
        return
    await callback_query.answer("✅ Игрок выбран")
    await after_pick(lobby_id, remaining, next_turn)


async def auto_pick(lobby_id):
    """Капитан не успел выбрать — бот выбирает лучшего по K/D."""
    lobby = db.fc_get_lobby(lobby_id)
    if not lobby or lobby[4] != "draft":
        return
    turn = lobby[7]
    captain_id = lobby[5] if turn == "ct" else lobby[6]
    free = [p for p in db.fc_get_players(lobby_id) if p["team"] is None]
    if not free:
        return
    best = max(free, key=lambda p: (player_kd(p), p["elo"]))
    ok, _, remaining, next_turn = db.fc_pick(lobby_id, captain_id, best["user_id"])
    if ok:
        await after_pick(lobby_id, remaining, next_turn)


# ---------- старт матча и тема в группе модераторов ----------
def build_topic_text(lobby_id):
    lobby = db.fc_get_lobby(lobby_id)
    players = db.fc_get_players(lobby_id)
    host = next((p for p in players if p["user_id"] == lobby[9]), None)
    lines = [
        f"{pe('📥')} Новый матч #{lobby_id}",
        "",
        f"{pe('🗺')} Карта: {lobby[3]}",
        f"{pe('🎲')} Режим: {fc_title(lobby[1])}",
    ]
    if host:
        lines.append(f"{pe('👤')} Хостер: {esc(host['nickname'])} | ID: <code>{esc(host['game_id'])}</code>")
    lines += ["", FC_SIDES["ct"], *team_block(players, "ct", with_ids=True), "",
              FC_SIDES["t"], *team_block(players, "t", with_ids=True), "",
              f"{pe('⏳')} Ожидаем скриншот с результатом от капитана."]
    return "\n".join(lines)


def topic_keyboard(lobby_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [btn("🔵 Победа CT", callback_data=f"fcwin_{lobby_id}_ct"),
         btn("🟠 Победа T", callback_data=f"fcwin_{lobby_id}_t")],
        [btn("❌ Отменить матч", callback_data=f"fccancel_{lobby_id}", icon="❌")],
    ])


async def get_topic_icon_id():
    """ID иконки 🎮 для темы форума (берём из стандартных иконок Телеграма)."""
    if "game" in _topic_icon_cache:
        return _topic_icon_cache["game"]
    icon_id = None
    try:
        stickers = await bot.get_forum_topic_icon_stickers()
        for sticker in stickers:
            if getattr(sticker, "emoji", None) == "🎮":
                icon_id = sticker.custom_emoji_id
                break
    except Exception as e:
        logger.warning(f"Cannot load forum topic icons: {e}")
    _topic_icon_cache["game"] = icon_id
    return icon_id


async def create_match_topic(lobby_id):
    if not MODERATOR_GROUP_ID:
        return None
    try:
        icon_id = await get_topic_icon_id()
        kwargs = {"name": f"Матч #{lobby_id}" if icon_id else f"🎮 Матч #{lobby_id}"}
        if icon_id:
            kwargs["icon_custom_emoji_id"] = icon_id
        result = await bot.create_forum_topic(chat_id=int(MODERATOR_GROUP_ID), **kwargs)
        thread_id = result.message_thread_id
        message = await bot.send_message(
            chat_id=int(MODERATOR_GROUP_ID), message_thread_id=thread_id,
            text=build_topic_text(lobby_id), parse_mode='HTML', reply_markup=topic_keyboard(lobby_id),
        )
        db.kv_set(f"fctopicmsg:{lobby_id}", message.message_id)
        return thread_id
    except Exception as e:
        logger.error(f"Error creating match topic for {lobby_id}: {e}")
        return None


async def start_veto(lobby_id):
    """Игроки выбраны: капитаны банят карты. Первым банит тот, кто выбирал игроков вторым."""
    first_pick = db.kv_get(f"fc_firstpick:{lobby_id}") or "ct"
    first_ban = "t" if first_pick == "ct" else "ct"
    if not db.fc_start_veto(lobby_id, first_ban):
        return
    await refresh_lobby_for_all(lobby_id)
    lobby = db.fc_get_lobby(lobby_id)
    for captain_id, side in ((lobby[5], "ct"), (lobby[6], "t")):
        try:
            text = (f"{pe('🗺')} Команды собраны! Начинается бан карт — "
                    + ("ваш ход, вы баните первым." if side == first_ban else "вторым банит ваш соперник."))
            await bot.send_message(chat_id=captain_id, text=text, parse_mode='HTML')
        except Exception as e:
            logger.info(f"Cannot notify captain {captain_id} about veto: {e}")


@dp.callback_query(lambda c: c.data.startswith("fcban_"))
async def fc_ban(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    try:
        _, lobby_s, idx_s = callback_query.data.split("_")
        lobby_id, index = int(lobby_s), int(idx_s)
        map_name = FC_MAPS[index]
    except (ValueError, IndexError):
        await callback_query.answer()
        return
    ok_ban, error, _remaining, _next_turn, final_map = db.fc_ban_map(lobby_id, user_id, map_name, FC_MAPS)
    if not ok_ban:
        await callback_query.answer(f"❌ {error}", show_alert=True)
        return
    await callback_query.answer(f"🔴 Забанена: {map_name}")
    await after_ban(lobby_id, final_map)


@dp.callback_query(lambda c: c.data.startswith("fcmapno_"))
async def fc_map_already_banned(callback_query: types.CallbackQuery):
    await callback_query.answer("🔴 Эта карта уже забанена.", show_alert=True)


async def after_ban(lobby_id, final_map):
    if final_map:
        await finish_veto(lobby_id)
    else:
        await refresh_lobby_for_all(lobby_id)


async def auto_ban(lobby_id):
    """Капитан не успел забанить карту — бот банит случайную из оставшихся."""
    lobby = db.fc_get_lobby(lobby_id)
    if not lobby or lobby[4] != "veto" or not lobby[7]:
        return
    banned = {name for _, name in parse_bans(lobby[15])}
    available = [m for m in FC_MAPS if m not in banned]
    if len(available) < 2:
        return
    captain_id = lobby[5] if lobby[7] == "ct" else lobby[6]
    ok_ban, _, _, _, final_map = db.fc_ban_map(lobby_id, captain_id, random.choice(available), FC_MAPS)
    if ok_ban:
        await after_ban(lobby_id, final_map)


async def finish_veto(lobby_id):
    """Карта определена: выбираем хоста, создаём тему у модераторов, запускаем матч."""
    players = db.fc_get_players(lobby_id)
    lobby = db.fc_get_lobby(lobby_id)
    if not players or not lobby:
        return
    if HOST_MODE == "captain" and lobby[5]:
        host_id = lobby[5]
    else:
        host_id = random.choice(players)["user_id"]
    if not db.fc_set_live(lobby_id, host_id, None):
        return
    thread_id = await create_match_topic(lobby_id)
    if thread_id:
        db.fc_set_topic(lobby_id, thread_id)
    await refresh_lobby_for_all(lobby_id)
    map_name = db.fc_get_lobby(lobby_id)[3]
    for p in players:
        try:
            await bot.send_message(
                chat_id=p["user_id"],
                text=f"{pe('🎮')} Матч #{lobby_id} начался! Карта: {map_name}. Сторона и хост — в сообщении с лобби выше.",
                parse_mode='HTML',
            )
        except Exception as e:
            logger.info(f"Cannot notify {p['user_id']} about match start: {e}")


# ---------- результат матча ----------
@dp.callback_query(lambda c: c.data.startswith("fcshot_") and c.data != "fcshot_cancel")
async def fc_screenshot_start(callback_query: types.CallbackQuery, state: FSMContext):
    user_id = callback_query.from_user.id
    try:
        lobby_id = int(callback_query.data.replace("fcshot_", ""))
    except ValueError:
        await callback_query.answer()
        return
    players = db.fc_get_players(lobby_id)
    me = next((p for p in players if p["user_id"] == user_id), None)
    lobby = db.fc_get_lobby(lobby_id)
    if not me or not me["is_captain"] or not lobby or lobby[4] != "live":
        await callback_query.answer("Скриншот отправляет капитан во время матча.", show_alert=True)
        return
    await state.set_state(FcStates.waiting_for_result_screenshot)
    await state.update_data(fc_lobby_id=lobby_id)
    await callback_query.message.answer(
        f"{pe('📸')} Отправьте скриншот с итоговым счётом матча #{lobby_id} одним фото.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[btn("❌ Отмена", callback_data="fcshot_cancel", icon="❌")]]),
        parse_mode='HTML',
    )
    await callback_query.answer()


@dp.callback_query(lambda c: c.data == "fcshot_cancel")
async def fc_screenshot_cancel(callback_query: types.CallbackQuery, state: FSMContext):
    await state.clear()
    try:
        await callback_query.message.delete()
    except Exception:
        pass
    await callback_query.answer("Отменено")


@dp.message(FcStates.waiting_for_result_screenshot)
async def fc_screenshot_received(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lobby_id = data.get("fc_lobby_id")
    if not message.photo:
        await message.answer("❌ Нужно отправить фото (скриншот).")
        return
    lobby = db.fc_get_lobby(lobby_id) if lobby_id else None
    if not lobby or lobby[4] != "live":
        await state.clear()
        await message.answer("Матч уже завершён или отменён.")
        return
    user_id = message.from_user.id
    me = next((p for p in db.fc_get_players(lobby_id) if p["user_id"] == user_id), None)
    caption = (
        f"📸 Результат матча #{lobby_id}\n"
        f"От капитана: {me['nickname'] if me else user_id} ({FC_SIDES.get(me['team'], '') if me else ''})\n"
        f"TG_ID:{user_id}"
    )
    try:
        if MODERATOR_GROUP_ID:
            await bot.send_photo(
                chat_id=int(MODERATOR_GROUP_ID), message_thread_id=lobby[10],
                photo=message.photo[-1].file_id, caption=caption,
            )
    except Exception as e:
        logger.error(f"Cannot forward result screenshot: {e}")
        await message.answer("❌ Не удалось отправить скриншот модераторам, попробуйте ещё раз.")
        return
    await state.clear()
    await message.answer(f"{pe('✅')} Скриншот отправлен модераторам. Ожидайте начисления ELO.", parse_mode='HTML')


def parse_kd_lines(text, players):
    """Строки 'ник_или_tgid убийства смерти' -> ([(user_id, kills, deaths)], [ошибки])."""
    entries, errors = [], []
    body = (text or "").split("\n")
    first = body[0].split(maxsplit=1)
    lines = ([first[1]] if len(first) > 1 else []) + body[1:]
    for line in lines:
        parts = line.replace(":", " ").split()
        if not parts:
            continue
        if len(parts) != 3 or not parts[1].isdigit() or not parts[2].isdigit():
            errors.append(f"«{line.strip()}» — формат: ник_или_TG_ID убийства смерти")
            continue
        who = parts[0]
        player = next(
            (p for p in players if (who.isdigit() and p["user_id"] == int(who)) or p["nickname"].lower() == who.lower()),
            None,
        )
        if not player:
            errors.append(f"«{who}» — такого игрока нет в матче")
            continue
        entries.append((player["user_id"], int(parts[1]), int(parts[2])))
    return entries, errors


@dp.message(Command("kd"))
async def cmd_kd(message: types.Message):
    """Модераторы вносят убийства/смерти игроков матча: /kd ник 15 7 (можно несколько строк)."""
    if not is_admin(message.from_user.id):
        await message.answer("❌ Нет прав для этой команды.")
        return
    lobby_id = db.fc_get_lobby_by_thread(message.message_thread_id) if message.message_thread_id else None
    if not lobby_id:
        await message.answer("❌ Команда работает только внутри темы матча.")
        return
    players = db.fc_get_players(lobby_id)
    entries, errors = parse_kd_lines(message.text, players)
    if not entries and not errors:
        await message.answer("Формат (можно несколько строк):\n/kd ник_или_TG_ID убийства смерти\n\nПример: /kd Player123 15 7")
        return
    nick = {p["user_id"]: p["nickname"] for p in players}
    done = [f"• {nick[uid]}: {k}/{d}" for uid, k, d in entries if db.fc_set_player_kd(lobby_id, uid, k, d)]
    text = ""
    if done:
        text += "✅ K/D записан:\n" + "\n".join(done)
    if errors:
        text += ("\n\n" if text else "") + "⚠️ Ошибки:\n" + "\n".join(errors)
    await message.answer(text)


@dp.callback_query(lambda c: c.data.startswith("fcwin_"))
async def fc_win_confirm(callback_query: types.CallbackQuery):
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer("Только для администраторов.", show_alert=True)
        return
    try:
        _, lobby_s, team = callback_query.data.split("_")
        lobby_id = int(lobby_s)
    except ValueError:
        await callback_query.answer()
        return
    if team not in FC_SIDES:
        await callback_query.answer()
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        btn("✅ Да, начислить", callback_data=f"fcwinok_{lobby_id}_{team}", icon="✅"),
        btn("◀️ Нет", callback_data=f"fcwinno_{lobby_id}", icon="◀️"),
    ]])
    try:
        await callback_query.message.edit_reply_markup(reply_markup=kb)
    except Exception:
        pass
    await callback_query.answer(f"Подтвердите победу {FC_SIDES[team]}")


@dp.callback_query(lambda c: c.data.startswith("fcwinno_"))
async def fc_win_back(callback_query: types.CallbackQuery):
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer("Только для администраторов.", show_alert=True)
        return
    try:
        lobby_id = int(callback_query.data.replace("fcwinno_", ""))
    except ValueError:
        await callback_query.answer()
        return
    try:
        await callback_query.message.edit_reply_markup(reply_markup=topic_keyboard(lobby_id))
    except Exception:
        pass
    await callback_query.answer()


def build_result_text(lobby_id, results, winner):
    lobby = db.fc_get_lobby(lobby_id)
    lines = [f"{pe('🏁')} Матч #{lobby_id} завершён", f"{pe('🗺')} Карта: {lobby[3]}",
             f"{pe('🏆')} Победа: {FC_SIDES[winner]}", ""]
    for team in ("ct", "t"):
        lines.append(FC_SIDES[team])
        for r in [x for x in results if x["team"] == team]:
            kd = f" · {r['kills']}/{r['deaths']}" if (r["kills"] or r["deaths"]) else ""
            lines.append(
                f"{get_player_level(r['elo_after'])} {display_nickname(r['user_id'], r['nickname'])} — "
                f"{r['elo_before']} → {r['elo_after']} ({r['elo_delta']:+d}){kd}"
            )
        lines.append("")
    return "\n".join(lines).rstrip()


async def notify_match_result(lobby_id, results):
    for r in results:
        db.kv_delete(f"fcmsg:{r['user_id']}")
        kd = f"\n{pe('🎯')} K/D матча: {r['kills']}/{r['deaths']}" if (r["kills"] or r["deaths"]) else ""
        text = (
            f"{pe('🏁')} <b>Матч #{lobby_id} завершён</b>\n"
            f"{pe('🏆') if r['won'] else pe('❌')} {'Победа!' if r['won'] else 'Поражение'}\n"
            f"{pe('📈')} ELO: {r['elo_before']} → <b>{r['elo_after']}</b> ({r['elo_delta']:+d})"
            f"{' · ×1.5 Premium' if r['won'] and r['premium'] else ''}"
            f"{kd}\n{pe('📈')} Уровень: {get_player_level(r['elo_after'])}"
        )
        try:
            await bot.send_message(chat_id=r["user_id"], text=text, parse_mode='HTML',
                                   reply_markup=get_main_keyboard(r["user_id"]))
        except Exception as e:
            logger.info(f"Cannot notify {r['user_id']} about result: {e}")


async def post_match_to_channel(lobby_id, results):
    """Итоги матча в канал (премиум-эмодзи; если канал их не принимает — обычная версия)."""
    if not CHANNEL_ID:
        return
    lobby = db.fc_get_lobby(lobby_id)
    top = sorted(results, key=lambda r: (r["kills"], r["elo_delta"]), reverse=True)[:3]
    medals = [pe("🥇"), pe("🥈"), "🥉"]
    lines = [
        f"{pe('🏁')} Матч #{lobby_id} завершён",
        f"{pe('🎲')} Режим: {fc_title(lobby[1])}",
        f"🗺 Карта: {lobby[3]}",
        f"🏆 Победа: {FC_SIDES[lobby[11]]}",
        "",
    ]
    for i, r in enumerate(top):
        kd = f" — {r['kills']}/{r['deaths']} (K/D {kd_value(r['kills'], r['deaths']):.2f})" if (r["kills"] or r["deaths"]) else ""
        lines.append(f"{medals[i]} {display_nickname(r['user_id'], r['nickname'])}{kd} · {r['elo_delta']:+d} ELO")
    lines += ["", f"{pe('👥')} Игроков: {len(results)}"]
    text = "\n".join(lines)
    link = await make_bot_link()
    kb = plain_kb = None
    if link:
        kb = InlineKeyboardMarkup(inline_keyboard=[[btn("🎮 Играть в боте", url=link, icon="🎮")]])
        plain_kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🎮 Играть в боте", url=link)]])
    try:
        await bot.send_message(chat_id=CHANNEL_ID, text=text, reply_markup=kb, parse_mode='HTML')
    except Exception as e:
        logger.warning(f"Channel post with premium emoji failed ({e}), sending plain version")
        try:
            await bot.send_message(chat_id=CHANNEL_ID, text=html.unescape(re.sub(r"<[^>]+>", "", text)), reply_markup=plain_kb)
        except Exception as e2:
            logger.error(f"Cannot post match result to channel: {e2}")


async def close_match_topic(thread_id):
    if CLOSE_TOPIC_AFTER_MATCH and MODERATOR_GROUP_ID and thread_id:
        try:
            await bot.close_forum_topic(chat_id=int(MODERATOR_GROUP_ID), message_thread_id=thread_id)
        except Exception as e:
            logger.info(f"Cannot close topic {thread_id}: {e}")


@dp.callback_query(lambda c: c.data.startswith("fcwinok_"))
async def fc_win_apply(callback_query: types.CallbackQuery):
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer("Только для администраторов.", show_alert=True)
        return
    try:
        _, lobby_s, team = callback_query.data.split("_")
        lobby_id = int(lobby_s)
    except ValueError:
        await callback_query.answer()
        return
    if team not in FC_SIDES:
        await callback_query.answer()
        return
    results = db.fc_finish(lobby_id, team, ELO_WIN, ELO_LOSS, ELO_PREMIUM_MULT)
    if results is None:
        await callback_query.answer("Матч уже завершён или отменён.", show_alert=True)
        return
    db.log_admin_action(callback_query.from_user.id, "match_result", None, f"match #{lobby_id} winner={team}")
    lobby = db.fc_get_lobby(lobby_id)
    try:
        await callback_query.message.edit_text(
            f"{build_result_text(lobby_id, results, team)}\n\n✅ Подтвердил: {esc(callback_query.from_user.full_name)}\n"
            f"Внести K/D: /kd ник убийства смерти",
            parse_mode='HTML', reply_markup=None,
        )
    except Exception as e:
        logger.warning(f"Cannot edit topic message: {e}")
    await callback_query.answer("ELO начислено")
    await notify_match_result(lobby_id, results)
    await post_match_to_channel(lobby_id, results)
    await close_match_topic(lobby[10])


@dp.callback_query(lambda c: c.data.startswith("fccancel_"))
async def fc_cancel_match(callback_query: types.CallbackQuery):
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer("Только для администраторов.", show_alert=True)
        return
    try:
        lobby_id = int(callback_query.data.replace("fccancel_", ""))
    except ValueError:
        await callback_query.answer()
        return
    lobby = db.fc_get_lobby(lobby_id)
    players = db.fc_get_players(lobby_id)
    if not db.fc_cancel(lobby_id):
        await callback_query.answer("Матч уже завершён или отменён.", show_alert=True)
        return
    db.log_admin_action(callback_query.from_user.id, "match_cancel", None, f"match #{lobby_id}")
    try:
        await callback_query.message.edit_text(
            f"❌ Матч #{lobby_id} отменён — {esc(callback_query.from_user.full_name)}", parse_mode='HTML', reply_markup=None
        )
    except Exception:
        pass
    for p in players:
        db.kv_delete(f"fcmsg:{p['user_id']}")
        try:
            await bot.send_message(
                chat_id=p["user_id"], text=f"{pe('❌')} Матч #{lobby_id} отменён модераторами. ELO не изменилось.",
                parse_mode='HTML', reply_markup=get_main_keyboard(p["user_id"]),
            )
        except Exception as e:
            logger.info(f"Cannot notify {p['user_id']} about cancel: {e}")
    await callback_query.answer("Матч отменён")
    await close_match_topic(lobby[10] if lobby else None)


# ---------- фоновые задачи ----------
async def fc_background_loop():
    """Следит, чтобы всегда были открытые лобби, и выбирает игроков за капитанов, не успевших сделать выбор."""
    while True:
        try:
            await ensure_open_lobbies()
            for lobby_id, status in db.fc_get_turn_timeouts(PICK_TIMEOUT_SEC):
                if status == "draft":
                    await auto_pick(lobby_id)
                else:
                    await auto_ban(lobby_id)
        except Exception as e:
            logger.error(f"Error in fc_background_loop: {e}")
        await asyncio.sleep(5)


# ======================================================================
# ИСТОРИЯ МАТЧЕЙ (как в DM: страницы по 5) + фильтры Premium (режим 2×2/5×5, карта, период)
# ======================================================================
HISTORY_PAGE = 5
HF_MODES = ["2x2", "5x5"]            # фильтр по режиму всегда предлагает оба режима
SEPARATOR = "➖" * 11


def format_history_entry(row):
    lobby_id, mode, map_name, team, winner, elo_delta, kills, deaths, finished_at = row
    try:
        date_text = datetime.strptime(str(finished_at), "%Y-%m-%d %H:%M:%S").strftime("%d.%m.%Y %H:%M")
    except (ValueError, TypeError):
        date_text = str(finished_at)
    won = team == winner
    text = f"{pe('🔹')}Матч #{lobby_id}\n"
    text += f"{pe('🗺')} Карта: {map_name}\n"
    text += f"{pe('🎮')} Режим: {fc_title(mode)}\n"
    text += f"{pe('🏁')} Результат: {pe('✅') if won else pe('❌')} {'Победа' if won else 'Поражение'} ({FC_SIDES.get(team, '')})\n"
    text += f"{pe('📊')} Статистика:\n"
    if kills or deaths:
        text += f"Убийств - {kills}\nСмертей - {deaths}\n"
    else:
        text += f"{pe('🔎')} K/D на модерации\n"
    text += f"{pe('🏆')} ELO: {(elo_delta or 0):+d}\n"
    text += f"{pe('🕗')} Дата: {date_text}\n"
    return text


def build_history_text(rows, offset, total, header_extra=""):
    pages = max(1, (total + HISTORY_PAGE - 1) // HISTORY_PAGE)
    text = f"{pe('🎮')} Сыгранные матчи (страница {offset // HISTORY_PAGE + 1}/{pages}):\n{header_extra}\n"
    for i, row in enumerate(rows, 1):
        text += format_history_entry(row)
        if i < len(rows):
            text += f"{SEPARATOR}\n\n"
    return text


def get_lobby_history_keyboard(user_id, current_offset=0, has_next=False, total_lobbies=0):
    keyboard = []
    nav_buttons = []
    if current_offset > 0:
        nav_buttons.append(btn("⬅️ Назад", callback_data=f"history_prev_{user_id}_{current_offset - HISTORY_PAGE}", icon="⬅️"))
    nav_buttons.append(btn("◀️ К профилю", callback_data="profile", icon="◀️"))
    if has_next:
        nav_buttons.append(btn("Вперед ➡️", callback_data=f"history_next_{user_id}_{current_offset + HISTORY_PAGE}", icon="➡️"))
    keyboard.append(nav_buttons)
    keyboard.append([btn("🔎 Фильтры Premium", callback_data=f"hf|{user_id}|-1|-1|0|0|menu", icon="🔎")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


async def send_history_page(user_id, offset):
    rows = db.fc_history(user_id, HISTORY_PAGE, offset)
    total = db.fc_history_count(user_id)
    await cleanup_user_messages(user_id)
    if not rows:
        text = f"{pe('🎮')} История сыгранных матчей\n\n{pe('❌')} Вы ещё не играли завершённых матчей"
        await send_message_with_image(user_id, text, None, get_back_keyboard())
        return False
    await send_message_with_image(
        user_id, build_history_text(rows, offset, total), None,
        get_lobby_history_keyboard(user_id, current_offset=offset, has_next=total > offset + HISTORY_PAGE, total_lobbies=total),
    )
    return True


@dp.callback_query(lambda c: c.data == "lobby_history")
async def show_lobby_history(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    if not db.is_user_registered(user_id):
        await callback_query.answer("❌ Вы не зарегистрированы!", show_alert=True)
        return
    await send_history_page(user_id, 0)
    await callback_query.answer()


async def _history_page_callback(callback_query, direction):
    try:
        data_parts = callback_query.data.split("_")
        user_id = int(data_parts[2])
        offset = max(0, int(data_parts[3]))
        if callback_query.from_user.id != user_id:
            await callback_query.answer("❌ Вы можете смотреть только свою историю", show_alert=True)
            return
        if not db.fc_history(user_id, 1, offset):
            await callback_query.answer("❌ Больше матчей нет", show_alert=True)
            return
        await send_history_page(user_id, offset)
    except (ValueError, IndexError) as e:
        logger.error(f"Error in history_{direction}: {e}")
        await callback_query.answer("❌ Ошибка при загрузке истории", show_alert=True)
        return
    await callback_query.answer()


@dp.callback_query(lambda c: c.data.startswith("history_prev_"))
async def show_prev_lobby_history(callback_query: types.CallbackQuery):
    await _history_page_callback(callback_query, "prev")


@dp.callback_query(lambda c: c.data.startswith("history_next_"))
async def show_next_lobby_history(callback_query: types.CallbackQuery):
    await _history_page_callback(callback_query, "next")


# ---------- фильтры (Premium) ----------
def _history_filter_state(user_id, mode_idx=-1, map_idx=-1, days=0, offset=0, action="menu", arg=""):
    return f"hf|{user_id}|{mode_idx}|{map_idx}|{days}|{offset}|{action}|{arg}"


def _history_filter_label(mode, map_name, days):
    parts = []
    if mode:
        parts.append(f"режим: {fc_title(mode)}")
    if map_name:
        parts.append(f"карта: {map_name}")
    if days:
        parts.append(f"период: {days} дн.")
    return ", ".join(parts) if parts else "не выбраны"


def _history_filter_menu_keyboard(user_id, mode_idx, map_idx, days, offset):
    return InlineKeyboardMarkup(inline_keyboard=[
        [btn("🎮 Выбрать режим (2×2 / 5×5)", callback_data=_history_filter_state(user_id, mode_idx, map_idx, days, offset, "mode"), icon="🎮")],
        [btn("🗺 Выбрать карту", callback_data=_history_filter_state(user_id, mode_idx, map_idx, days, offset, "map"), icon="🗺")],
        [btn("📅 Период", callback_data=_history_filter_state(user_id, mode_idx, map_idx, days, offset, "period"), icon="📅")],
        [btn("♻️ Сбросить фильтры", callback_data=_history_filter_state(user_id, -1, -1, 0, 0, "apply"), icon="♻️")],
        [btn("📋 Показать матчи", callback_data=_history_filter_state(user_id, mode_idx, map_idx, days, 0, "apply"), icon="📋")],
        [btn("◀️ Назад к истории", callback_data="lobby_history", icon="◀️")],
    ])


@dp.callback_query(lambda c: c.data.startswith("hf|"))
async def handle_lobby_history_filters(callback_query: types.CallbackQuery):
    try:
        parts = callback_query.data.split("|", 7)
        _, user_raw, mode_raw, map_raw, days_raw, offset_raw, action = parts[:7]
        arg = parts[7] if len(parts) > 7 else ""
        user_id = int(user_raw)
        mode_idx, map_idx, days, offset = int(mode_raw), int(map_raw), int(days_raw), int(offset_raw)
        if callback_query.from_user.id != user_id:
            await callback_query.answer("❌ Вы можете смотреть только свою историю", show_alert=True)
            return
        if not db.is_premium(user_id):
            await callback_query.answer("⭐️ Фильтры истории доступны с Premium", show_alert=True)
            return

        modes, maps = HF_MODES, FC_MAPS
        mode = modes[mode_idx] if 0 <= mode_idx < len(modes) else None
        map_name = maps[map_idx] if 0 <= map_idx < len(maps) else None

        async def show(text, keyboard):
            await cleanup_user_messages(user_id)
            await send_message_with_image(user_id, text, None, keyboard)

        if action == "mode":
            rows = [[btn("Все режимы", callback_data=_history_filter_state(user_id, -1, map_idx, days, 0, "setmode"), icon="🎮")]]
            rows += [[btn(fc_title(value), callback_data=_history_filter_state(user_id, mode_idx, map_idx, days, 0, "setmode", str(i)), icon="🎮")] for i, value in enumerate(modes)]
            rows.append([btn("◀️ Назад", callback_data=_history_filter_state(user_id, mode_idx, map_idx, days, offset, "menu"), icon="◀️")])
            await show(f"{pe('🎮')} Выберите режим матча:", InlineKeyboardMarkup(inline_keyboard=rows))
        elif action == "map":
            rows = [[btn("Все карты", callback_data=_history_filter_state(user_id, mode_idx, -1, days, 0, "setmap"), icon="🗺")]]
            rows += [[InlineKeyboardButton(text=str(value)[:50], callback_data=_history_filter_state(user_id, mode_idx, map_idx, days, 0, "setmap", str(i)))] for i, value in enumerate(maps)]
            rows.append([btn("◀️ Назад", callback_data=_history_filter_state(user_id, mode_idx, map_idx, days, offset, "menu"), icon="◀️")])
            await show(f"{pe('🗺')} Выберите карту:", InlineKeyboardMarkup(inline_keyboard=rows))
        elif action == "period":
            rows = [
                [btn("За всё время", callback_data=_history_filter_state(user_id, mode_idx, map_idx, 0, 0, "setdays"), icon="📅")],
                [btn("За 7 дней", callback_data=_history_filter_state(user_id, mode_idx, map_idx, 7, 0, "setdays"), icon="📅")],
                [btn("За 30 дней", callback_data=_history_filter_state(user_id, mode_idx, map_idx, 30, 0, "setdays"), icon="📅")],
                [btn("За 90 дней", callback_data=_history_filter_state(user_id, mode_idx, map_idx, 90, 0, "setdays"), icon="📅")],
                [btn("◀️ Назад", callback_data=_history_filter_state(user_id, mode_idx, map_idx, days, offset, "menu"), icon="◀️")],
            ]
            await show(f"{pe('📅')} Выберите период:", InlineKeyboardMarkup(inline_keyboard=rows))
        elif action == "setmode":
            mode_idx = int(arg) if arg else -1
            mode = modes[mode_idx] if 0 <= mode_idx < len(modes) else None
            await show(f"{pe('🔎')} Фильтры: {_history_filter_label(mode, map_name, days)}", _history_filter_menu_keyboard(user_id, mode_idx, map_idx, days, 0))
        elif action == "setmap":
            map_idx = int(arg) if arg else -1
            map_name = maps[map_idx] if 0 <= map_idx < len(maps) else None
            await show(f"{pe('🔎')} Фильтры: {_history_filter_label(mode, map_name, days)}", _history_filter_menu_keyboard(user_id, mode_idx, map_idx, days, 0))
        elif action == "setdays":
            days = days if days in (7, 30, 90) else 0
            await show(f"{pe('🔎')} Фильтры: {_history_filter_label(mode, map_name, days)}", _history_filter_menu_keyboard(user_id, mode_idx, map_idx, days, 0))
        elif action == "menu":
            await show(f"{pe('🔎')} Фильтры истории матчей\n\nТекущие фильтры: {_history_filter_label(mode, map_name, days)}", _history_filter_menu_keyboard(user_id, mode_idx, map_idx, days, offset))
        elif action == "page":
            await _show_filtered_lobby_history(user_id, mode_idx, map_idx, days, max(0, int(arg or 0)))
        elif action == "apply":
            await _show_filtered_lobby_history(user_id, mode_idx, map_idx, days, 0)
        await callback_query.answer()
    except (ValueError, IndexError) as e:
        logger.error(f"Error in match history filters: {e}")
        await callback_query.answer("❌ Ошибка фильтра истории", show_alert=True)


async def _show_filtered_lobby_history(user_id, mode_idx, map_idx, days, offset):
    mode = HF_MODES[mode_idx] if 0 <= mode_idx < len(HF_MODES) else None
    map_name = FC_MAPS[map_idx] if 0 <= map_idx < len(FC_MAPS) else None
    rows = db.fc_history(user_id, HISTORY_PAGE, offset, mode, map_name, days)
    total = db.fc_history_count(user_id, mode, map_name, days)
    label = _history_filter_label(mode, map_name, days)
    if not rows:
        text = f"{pe('🔎')} По выбранным фильтрам матчей нет.\n\nФильтры: {label}"
    else:
        pages = max(1, (total + HISTORY_PAGE - 1) // HISTORY_PAGE)
        text = f"{pe('🎮')} История матчей ({offset // HISTORY_PAGE + 1}/{pages})\nФильтры: {label}\n\n"
        for row in rows:
            text += format_history_entry(row) + "\n"
    kb_rows = []
    if offset > 0 or offset + HISTORY_PAGE < total:
        nav = []
        if offset > 0:
            nav.append(btn("⬅️", callback_data=_history_filter_state(user_id, mode_idx, map_idx, days, offset, "page", str(max(0, offset - HISTORY_PAGE))), icon="⬅️"))
        if offset + HISTORY_PAGE < total:
            nav.append(btn("➡️", callback_data=_history_filter_state(user_id, mode_idx, map_idx, days, offset, "page", str(offset + HISTORY_PAGE)), icon="➡️"))
        kb_rows.append(nav)
    kb_rows.append([btn("🔎 Изменить фильтры", callback_data=_history_filter_state(user_id, mode_idx, map_idx, days, offset, "menu"), icon="🔎")])
    kb_rows.append([btn("◀️ К истории", callback_data="lobby_history", icon="◀️")])
    await cleanup_user_messages(user_id)
    await send_message_with_image(user_id, text, None, InlineKeyboardMarkup(inline_keyboard=kb_rows))


# ======================================================================
# ТИКЕТЫ (поддержка): жалоба на игрока по матчу → тема в группе модераторов
# ======================================================================
TICKET_DAILY_LIMIT = _env_int('TICKET_DAILY_LIMIT', 3)     # сколько тикетов может подать игрок за сутки
TICKET_REASON_MIN = 5
TICKET_REASON_MAX = 500                                     # подпись к фото в Телеграме ограничена 1024 символами


class TicketStates(StatesGroup):
    waiting_for_reason = State()
    waiting_for_accused = State()
    waiting_for_screenshot = State()


def ticket_cancel_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[[btn("❌ Отмена", callback_data="ticket_cancel", icon="❌")]])


def ticket_number(ticket_id):
    return f"{ticket_id:05d}"


async def begin_ticket(user_id, state):
    """Шаг 1: выбор матча из последних трёх."""
    await state.clear()
    await cleanup_user_messages(user_id)
    if not db.is_user_registered(user_id):
        await send_message_with_image(user_id, f"{pe('❌')} Сначала зарегистрируйтесь через /start.", None, fc_back_keyboard())
        return
    if db.fc_count_recent_tickets(user_id) >= TICKET_DAILY_LIMIT:
        await send_message_with_image(
            user_id, f"{pe('❌')} Лимит тикетов на сегодня исчерпан ({TICKET_DAILY_LIMIT}). Попробуйте завтра.", None, fc_back_keyboard()
        )
        return
    matches = db.fc_recent_matches(user_id, 3)
    if not matches:
        await send_message_with_image(
            user_id, f"{pe('❌')} У вас пока нет матчей, по которым можно подать тикет.", None, fc_back_keyboard()
        )
        return
    rows = [
        [InlineKeyboardButton(text=f"#{lobby_id} · {fc_title(mode)} · {map_name or '—'}", callback_data=f"ticket_m_{lobby_id}")]
        for lobby_id, mode, map_name, _status, _finished in matches
    ]
    rows.append([btn("❌ Отмена", callback_data="ticket_cancel", icon="❌")])
    text = (
        f"{pe('🎫')} <b>Тикет · шаг 1 из 4</b>\n\n"
        f"Выберите матч, в котором произошло нарушение (последние три):"
    )
    await send_message_with_image(user_id, text, None, InlineKeyboardMarkup(inline_keyboard=rows))


@dp.message(Command("ticket"))
async def cmd_ticket(message: types.Message, state: FSMContext):
    try:
        await message.delete()
    except Exception:
        pass
    await begin_ticket(message.from_user.id, state)


@dp.callback_query(lambda c: c.data == "ticket_start")
async def ticket_start(callback_query: types.CallbackQuery, state: FSMContext):
    await begin_ticket(callback_query.from_user.id, state)
    await callback_query.answer()


@dp.callback_query(lambda c: c.data == "ticket_cancel")
async def ticket_cancel(callback_query: types.CallbackQuery, state: FSMContext):
    await state.clear()
    user_id = callback_query.from_user.id
    await cleanup_user_messages(user_id)
    await send_message_with_image(user_id, f"{pe('👋')} Тикет отменён.\n\nВыберите действие:", MENU_IMAGE_URL, get_main_keyboard(user_id))
    await callback_query.answer("Отменено")


@dp.callback_query(lambda c: c.data.startswith("ticket_m_"))
async def ticket_pick_match(callback_query: types.CallbackQuery, state: FSMContext):
    user_id = callback_query.from_user.id
    try:
        lobby_id = int(callback_query.data.replace("ticket_m_", ""))
    except ValueError:
        await callback_query.answer()
        return
    if lobby_id not in [m[0] for m in db.fc_recent_matches(user_id, 3)]:
        await callback_query.answer("Этот матч недоступен для тикета.", show_alert=True)
        return
    await state.set_state(TicketStates.waiting_for_reason)
    await state.update_data(ticket_lobby=lobby_id)
    await cleanup_user_messages(user_id)
    text = (
        f"{pe('🎫')} <b>Тикет · шаг 2 из 4</b>\n\n"
        f"Матч #{lobby_id}.\n"
        f"Опишите суть нарушения своими словами (от {TICKET_REASON_MIN} до {TICKET_REASON_MAX} символов):"
    )
    await send_message_with_image(user_id, text, None, ticket_cancel_keyboard())
    await callback_query.answer()


@dp.message(TicketStates.waiting_for_reason)
async def ticket_reason(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    reason = (message.text or "").strip()
    try:
        await message.delete()
    except Exception:
        pass
    if len(reason) < TICKET_REASON_MIN or len(reason) > TICKET_REASON_MAX:
        await bot.send_message(
            chat_id=user_id,
            text=f"❌ Опишите нарушение текстом от {TICKET_REASON_MIN} до {TICKET_REASON_MAX} символов (сейчас {len(reason)}).",
            reply_markup=ticket_cancel_keyboard(),
        )
        return
    data = await state.get_data()
    await state.update_data(ticket_reason=reason)
    await state.set_state(TicketStates.waiting_for_accused)
    players = [p["nickname"] for p in db.fc_get_players(data["ticket_lobby"]) if p["user_id"] != user_id]
    await cleanup_user_messages(user_id)
    text = (
        f"{pe('🎫')} <b>Тикет · шаг 3 из 4</b>\n\n"
        f"Введите никнейм игрока, на которого вы подаёте жалобу.\n"
        f"Игроки матча: {', '.join(esc(n) for n in players)}"
    )
    await send_message_with_image(user_id, text, None, ticket_cancel_keyboard())


@dp.message(TicketStates.waiting_for_accused)
async def ticket_accused(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    nickname = (message.text or "").strip()
    try:
        await message.delete()
    except Exception:
        pass
    data = await state.get_data()
    players = db.fc_get_players(data["ticket_lobby"])
    accused = next((p for p in players if p["nickname"].lower() == nickname.lower() and p["user_id"] != user_id), None)
    if not accused:
        names = ", ".join(esc(p["nickname"]) for p in players if p["user_id"] != user_id)
        await bot.send_message(
            chat_id=user_id,
            text=f"❌ Игрока «{nickname[:30]}» нет в этом матче. Игроки матча: {names}",
            reply_markup=ticket_cancel_keyboard(),
        )
        return
    await state.update_data(ticket_accused=accused["user_id"])
    await state.set_state(TicketStates.waiting_for_screenshot)
    await cleanup_user_messages(user_id)
    text = (
        f"{pe('🎫')} <b>Тикет · шаг 4 из 4</b>\n\n"
        f"Отправьте скриншот нарушения <b>одним фото</b> (как фото, а не файлом)."
    )
    await send_message_with_image(user_id, text, None, ticket_cancel_keyboard())


def ticket_keyboard(ticket_id):
    return InlineKeyboardMarkup(inline_keyboard=[[
        btn("✅ Принят", callback_data=f"tk_ok_{ticket_id}", icon="✅"),
        btn("❌ Отклонён", callback_data=f"tk_no_{ticket_id}", icon="❌"),
    ]])


def build_ticket_caption(ticket_id, lobby, reporter_nick, accused_nick, reason):
    return (
        f"{pe('📥')} Новый тикет #{ticket_number(ticket_id)}\n\n"
        f"{pe('🗺')} Карта: {lobby[3] or '—'}\n"
        f"{pe('🎮')} Режим: {fc_title(lobby[1])}\n"
        f"🆔 Матч: #{lobby[0]}\n"
        f"{pe('👤')} Никнейм подавшего: {esc(reporter_nick)}\n"
        f"{pe('👤')} Никнейм на которого подается жалоба: {esc(accused_nick)}\n\n"
        f"{pe('⛔️')} Суть жалобы: {esc(reason)}\n\n"
        f"{pe('🖼')} Доказательства приложены в виде скриншота."
    )


@dp.message(TicketStates.waiting_for_screenshot)
async def ticket_screenshot(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    if not message.photo:
        try:
            await message.delete()
        except Exception:
            pass
        await bot.send_message(
            chat_id=user_id, text="❌ Нужен скриншот именно фотографией. Отправьте одно фото.", reply_markup=ticket_cancel_keyboard()
        )
        return
    data = await state.get_data()
    lobby_id, accused_id, reason = data.get("ticket_lobby"), data.get("ticket_accused"), data.get("ticket_reason")
    lobby = db.fc_get_lobby(lobby_id) if lobby_id else None
    if not lobby or not accused_id or not reason:
        await state.clear()
        await message.answer("Данные тикета потерялись, начните заново: /ticket")
        return
    if not MODERATOR_GROUP_ID:
        await state.clear()
        await message.answer("❌ Приём тикетов сейчас недоступен. Напишите администратору.")
        return
    file_id = message.photo[-1].file_id
    ticket_id = db.fc_create_ticket(user_id, accused_id, lobby_id, reason, file_id)
    if not ticket_id:
        await message.answer("❌ Не удалось сохранить тикет, попробуйте позже.")
        return
    reporter = db.get_player_profile(user_id)
    accused = db.get_player_profile(accused_id)
    reporter_nick = reporter[2] if reporter else str(user_id)
    accused_nick = accused[2] if accused else str(accused_id)
    try:
        topic = await bot.create_forum_topic(chat_id=int(MODERATOR_GROUP_ID), name=f"🎫 Тикет #{ticket_number(ticket_id)}")
        thread_id = topic.message_thread_id
        await bot.send_photo(
            chat_id=int(MODERATOR_GROUP_ID), message_thread_id=thread_id, photo=file_id,
            caption=build_ticket_caption(ticket_id, lobby, reporter_nick, accused_nick, reason),
            parse_mode='HTML', reply_markup=ticket_keyboard(ticket_id),
        )
        db.fc_set_ticket_thread(ticket_id, thread_id)
    except Exception as e:
        logger.error(f"Cannot deliver ticket {ticket_id} to moderators: {e}")
        db.fc_resolve_ticket(ticket_id, "failed", 0)
        await state.clear()
        await message.answer("❌ Не удалось отправить тикет модераторам. Попробуйте ещё раз: /ticket")
        return
    await state.clear()
    try:
        await message.delete()
    except Exception:
        pass
    await cleanup_user_messages(user_id)
    await send_message_with_image(
        user_id,
        f"{pe('✅')} Тикет #{ticket_number(ticket_id)} отправлен модераторам. Мы сообщим о решении.",
        MENU_IMAGE_URL, get_main_keyboard(user_id),
    )


@dp.callback_query(lambda c: c.data.startswith("tk_ok_") or c.data.startswith("tk_no_"))
async def ticket_resolve(callback_query: types.CallbackQuery):
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer("Только для администраторов.", show_alert=True)
        return
    accepted = callback_query.data.startswith("tk_ok_")
    try:
        ticket_id = int(callback_query.data.split("_")[2])
    except (ValueError, IndexError):
        await callback_query.answer()
        return
    ticket = db.fc_get_ticket(ticket_id)
    if not ticket:
        await callback_query.answer("Тикет не найден.", show_alert=True)
        return
    if not db.fc_resolve_ticket(ticket_id, "resolved" if accepted else "rejected", callback_query.from_user.id):
        await callback_query.answer("Тикет уже обработан.", show_alert=True)
        return
    db.log_admin_action(callback_query.from_user.id, "ticket_resolved" if accepted else "ticket_rejected", ticket[2], f"ticket #{ticket_number(ticket_id)}")
    verdict = "✅ Принят" if accepted else "❌ Отклонён"
    try:
        base = callback_query.message.html_text if getattr(callback_query.message, "html_text", None) else (callback_query.message.caption or "")
        await callback_query.message.edit_caption(
            caption=f"{base}\n\n{verdict} — {esc(callback_query.from_user.full_name)}", parse_mode='HTML', reply_markup=None
        )
    except Exception as e:
        logger.warning(f"Cannot edit ticket caption: {e}")
    try:
        await bot.send_message(
            chat_id=ticket[1],
            text=(f"{pe('✅')} Ваш тикет #{ticket_number(ticket_id)} рассмотрен: нарушение подтверждено, меры приняты."
                  if accepted else
                  f"{pe('❌')} Ваш тикет #{ticket_number(ticket_id)} рассмотрен и отклонён: нарушений не найдено."),
            parse_mode='HTML',
        )
    except Exception as e:
        logger.info(f"Cannot notify reporter {ticket[1]}: {e}")
    if MODERATOR_GROUP_ID and ticket[7]:
        try:
            await bot.close_forum_topic(chat_id=int(MODERATOR_GROUP_ID), message_thread_id=ticket[7])
        except Exception as e:
            logger.info(f"Cannot close ticket topic: {e}")
    await callback_query.answer("Готово")


# ======================================================================
# РЕГИСТРАЦИЯ (3 шага: ник → игровой ID → подтверждение), ПРОФИЛЬ, ТОП, МЕНЮ
# ======================================================================
NICK_RE = re.compile(r"^[A-Za-z0-9_]{3,16}$")
GAME_ID_RE = re.compile(r"^[A-Za-z0-9]{3,20}$")


DEVICE_LABELS = {"mobile": "📱 Телефон/Планшет", "pc": "💻 ПК"}


def reg_keyboard(back=None):
    rows = []
    if back:
        rows.append([btn("◀️ Назад", callback_data=back, icon="◀️")])
    rows.append([btn("❌ Отмена", callback_data="cancel_registration", icon="❌")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def ask_nickname(user_id, error=None):
    await cleanup_user_messages(user_id)
    text = (
        f"{pe('📝')} <b>Регистрация · шаг 1 из 4</b>\n\n"
        f"Введите ваш игровой никнейм.\n"
        f"Допустимо: латиница, цифры и «_», от 3 до 16 символов."
    )
    if error:
        text = f"{pe('❌')} {error}\n\n" + text
    await send_message_with_image(user_id, text, None, reg_keyboard())


async def ask_game_id(user_id, nickname, error=None):
    await cleanup_user_messages(user_id)
    text = (
        f"{pe('📝')} <b>Регистрация · шаг 2 из 4</b>\n\n"
        f"Ник: <b>{esc(nickname)}</b>\n\n"
        f"Введите ваш игровой ID (из Standoff 2).\n"
        f"Допустимо: латиница и цифры, от 3 до 20 символов."
    )
    if error:
        text = f"{pe('❌')} {error}\n\n" + text
    await send_message_with_image(user_id, text, None, reg_keyboard(back="reg_edit_nick"))


async def ask_device(user_id):
    await cleanup_user_messages(user_id)
    text = (
        f"{pe('📝')} <b>Регистрация · шаг 3 из 4</b>\n\n"
        f"На каком устройстве вы играете?\n"
        f"Это просто отметка в профиле, на подбор лобби не влияет."
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            btn("📱 Телефон/Планшет", callback_data="reg_dev_mobile", icon="📱"),
            btn("💻 ПК", callback_data="reg_dev_pc", icon="💻"),
        ],
        [btn("◀️ Назад", callback_data="reg_edit_id", icon="◀️")],
        [btn("❌ Отмена", callback_data="cancel_registration", icon="❌")],
    ])
    await send_message_with_image(user_id, text, None, kb)


async def ask_confirm(user_id, nickname, game_id, device):
    await cleanup_user_messages(user_id)
    text = (
        f"{pe('📝')} <b>Регистрация · шаг 4 из 4</b>\n\n"
        f"Проверьте данные:\n\n"
        f"{pe('👤')} Никнейм: <b>{esc(nickname)}</b>\n"
        f"🆔 Игровой ID: <code>{esc(game_id)}</code>\n"
        f"🕹 Устройство: {DEVICE_LABELS.get(device, 'не указано')}\n\n"
        f"Всё верно?"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [btn("✅ Подтвердить регистрацию", callback_data="reg_confirm", icon="✅")],
        [
            btn("✏️ Изменить ник", callback_data="reg_edit_nick", icon="✏️"),
            btn("🆔 Изменить ID", callback_data="reg_edit_id"),
        ],
        [btn("📱 Изменить устройство", callback_data="reg_edit_device", icon="📱")],
        [btn("❌ Отмена", callback_data="cancel_registration", icon="❌")],
    ])
    await send_message_with_image(user_id, text, None, kb)


@dp.callback_query(lambda c: c.data == "register")
async def start_registration(callback_query: types.CallbackQuery, state: FSMContext):
    user_id = callback_query.from_user.id
    if db.is_user_registered(user_id):
        await callback_query.answer("Вы уже зарегистрированы.", show_alert=True)
        return
    await state.clear()
    await state.set_state(RegistrationStates.waiting_for_nickname)
    await ask_nickname(user_id)
    await callback_query.answer()


@dp.message(RegistrationStates.waiting_for_nickname)
async def process_nickname(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    nickname = (message.text or "").strip()
    try:
        await message.delete()
    except Exception:
        pass
    if not NICK_RE.fullmatch(nickname):
        await ask_nickname(user_id, "Ник должен состоять из 3-16 символов: латиница, цифры, «_».")
        return
    data = await state.get_data()
    await state.update_data(nickname=nickname)
    if data.get("game_id") and data.get("device"):
        await state.set_state(RegistrationStates.confirm)
        await ask_confirm(user_id, nickname, data["game_id"], data["device"])
    elif data.get("game_id"):
        await state.set_state(RegistrationStates.waiting_for_device)
        await ask_device(user_id)
    else:
        await state.set_state(RegistrationStates.waiting_for_game_id)
        await ask_game_id(user_id, nickname)


@dp.message(RegistrationStates.waiting_for_game_id)
async def process_game_id(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    game_id = (message.text or "").strip()
    data = await state.get_data()
    nickname = data.get("nickname", "")
    try:
        await message.delete()
    except Exception:
        pass
    if not GAME_ID_RE.fullmatch(game_id):
        await ask_game_id(user_id, nickname, "ID должен состоять из 3-20 символов: латиница и цифры.")
        return
    if db.is_game_id_taken(game_id):
        await ask_game_id(user_id, nickname, "Этот игровой ID уже зарегистрирован.")
        return
    await state.update_data(game_id=game_id)
    if data.get("device"):
        await state.set_state(RegistrationStates.confirm)
        await ask_confirm(user_id, nickname, game_id, data["device"])
    else:
        await state.set_state(RegistrationStates.waiting_for_device)
        await ask_device(user_id)


@dp.callback_query(lambda c: c.data in ("reg_dev_mobile", "reg_dev_pc"))
async def process_device(callback_query: types.CallbackQuery, state: FSMContext):
    user_id = callback_query.from_user.id
    data = await state.get_data()
    if not data.get("nickname") or not data.get("game_id"):
        await callback_query.answer("Данные потерялись, начните заново.", show_alert=True)
        await state.clear()
        await state.set_state(RegistrationStates.waiting_for_nickname)
        await ask_nickname(user_id)
        return
    device = "mobile" if callback_query.data == "reg_dev_mobile" else "pc"
    await state.update_data(device=device)
    await state.set_state(RegistrationStates.confirm)
    await ask_confirm(user_id, data["nickname"], data["game_id"], device)
    await callback_query.answer()


@dp.message(RegistrationStates.waiting_for_device)
@dp.message(RegistrationStates.confirm)
async def registration_buttons_only(message: types.Message):
    """На шагах с кнопками текст не нужен — пользуйтесь кнопками."""
    try:
        await message.delete()
    except Exception:
        pass


@dp.callback_query(lambda c: c.data == "reg_edit_nick")
async def reg_edit_nick(callback_query: types.CallbackQuery, state: FSMContext):
    await state.set_state(RegistrationStates.waiting_for_nickname)
    await ask_nickname(callback_query.from_user.id)
    await callback_query.answer()


@dp.callback_query(lambda c: c.data == "reg_edit_id")
async def reg_edit_id(callback_query: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await state.set_state(RegistrationStates.waiting_for_game_id)
    await ask_game_id(callback_query.from_user.id, data.get("nickname", ""))
    await callback_query.answer()


@dp.callback_query(lambda c: c.data == "reg_edit_device")
async def reg_edit_device(callback_query: types.CallbackQuery, state: FSMContext):
    await state.set_state(RegistrationStates.waiting_for_device)
    await ask_device(callback_query.from_user.id)
    await callback_query.answer()


@dp.callback_query(lambda c: c.data == "reg_confirm")
async def reg_confirm(callback_query: types.CallbackQuery, state: FSMContext):
    user_id = callback_query.from_user.id
    data = await state.get_data()
    nickname, game_id, device = data.get("nickname"), data.get("game_id"), data.get("device")
    if not nickname or not game_id or not device:
        await callback_query.answer("Данные потерялись, начните заново.", show_alert=True)
        await state.clear()
        await state.set_state(RegistrationStates.waiting_for_nickname)
        await ask_nickname(user_id)
        return
    if db.is_user_registered(user_id):
        await state.clear()
        await callback_query.answer("Вы уже зарегистрированы.", show_alert=True)
        return
    username = f"@{callback_query.from_user.username}" if callback_query.from_user.username else None
    success, error = db.register_player(user_id, username, nickname, game_id)
    if not success:
        await callback_query.answer(f"❌ {error}", show_alert=True)
        return
    db.fc_set_device(user_id, device)
    await state.clear()
    await callback_query.answer("✅ Регистрация завершена")
    await cleanup_user_messages(user_id)
    text = (
        f"{pe('✅')} Регистрация завершена!\n\n"
        f"{pe('👋')} Добро пожаловать, <b>{esc(nickname)}</b>!\n\n"
        f"Выберите действие:"
    )
    await send_message_with_image(user_id, text, MENU_IMAGE_URL, get_main_keyboard(user_id))


@dp.callback_query(lambda c: c.data == "cancel_registration")
async def cancel_registration(callback_query: types.CallbackQuery, state: FSMContext):
    await state.clear()
    user_id = callback_query.from_user.id
    await cleanup_user_messages(user_id)
    first_name = callback_query.from_user.first_name
    await send_message_with_image(
        user_id,
        f"{pe('👋')} Привет, {esc(first_name)}!\n\nНажмите кнопку ниже, чтобы зарегистрироваться:",
        MENU_IMAGE_URL,
        get_registration_keyboard(),
    )
    await callback_query.answer("Регистрация отменена")


# ---------- профиль ----------
def build_profile_text(user_id):
    p = db.get_player_profile(user_id)
    if not p:
        return None
    _, _, nickname, game_id, _, rating, matches, kills, deaths, _, _, premium_until = p
    elo, kills, deaths = rating or 0, kills or 0, deaths or 0
    wins, losses = db.fc_get_player_wl(user_id)
    winrate = f"{wins / (wins + losses) * 100:.0f}%" if (wins + losses) else "—"
    lines = [
        f"{pe('👤')} <b>{display_nickname(user_id, nickname)}</b>",
        f"🆔 ID: <code>{esc(game_id)}</code>",
        f"🕹 Устройство: {DEVICE_LABELS.get(db.fc_get_device(user_id), 'не указано')}",
        "",
        f"{pe('📈')} Уровень: {get_player_level(elo)} · {elo} ELO",
    ]
    nxt = elo_progress(elo)
    if nxt:
        lines.append(f"🎯 До уровня {nxt[0]}: {nxt[1]} ELO")
    if premium_until and db.is_premium(user_id):
        lines.append(f"{pe('⭐️')} Premium: {db.get_premium_days_left(user_id)} дн.")
    lines += [
        "",
        f"{pe('📊')} K/D: {kd_value(kills, deaths):.2f}",
        f"🔫 Убийства: {kills} · 💀 Смерти: {deaths}",
        f"{pe('🏆')} Винрейт: {winrate}",
    ]
    return "\n".join(lines)


def get_profile_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [btn("🕗 История матчей", callback_data="lobby_history", icon="🕗")],
        [btn("✏️ Редактировать профиль", callback_data="edit_profile", icon="✏️")],
        [btn("◀️ Назад", callback_data="back_to_main", icon="◀️")],
    ])


async def send_profile(user_id):
    text = build_profile_text(user_id)
    if not text:
        return False
    await cleanup_user_messages(user_id)
    await send_message_with_image(user_id, text, PROFILE_IMAGE_URL, get_profile_keyboard())
    return True


@dp.callback_query(lambda c: c.data == "profile")
async def show_profile(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    if not db.is_user_registered(user_id):
        await callback_query.answer("❌ Вы не зарегистрированы!", show_alert=True)
        return
    await send_profile(user_id)
    await callback_query.answer()


async def show_profile_from_message(message: types.Message):
    user_id = message.from_user.id
    if not db.is_user_registered(user_id):
        await message.answer("❌ Вы не зарегистрированы! Нажмите /start для регистрации.")
        return
    try:
        await message.delete()
    except Exception:
        pass
    await send_profile(user_id)


# ---------- топ ----------
@dp.callback_query(lambda c: c.data in ("top", "top_all_time"))
async def show_all_time_top(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    try:
        top_players = db.get_all_time_top_players()
        await cleanup_user_messages(user_id)
        lines = [f"{pe('🏆')} <b>Топ игроков по ELO</b>\n"]
        if not top_players:
            lines.append("Пока никто не сыграл ни одного матча.")
        medals = {1: "🥇", 2: "🥈", 3: "🥉"}
        for i, (uid, nickname, rating, matches, kills, deaths) in enumerate(top_players, 1):
            lines.append(
                f"{medals.get(i, f'{i}.')} {display_nickname(uid, nickname)} — {rating} ELO "
                f"(K/D {kd_value(kills or 0, deaths or 0):.2f}, матчей: {matches})"
            )
        position = db.get_player_all_time_position(user_id)
        if position:
            lines.append(f"\n{pe('📍')} Ваше место: {position}")
        await send_message_with_image(
            user_id, "\n".join(lines), TOP_IMAGE_URL,
            InlineKeyboardMarkup(inline_keyboard=[[btn("◀️ Назад", callback_data="back_to_main", icon="◀️")]]),
        )
        await callback_query.answer()
    except Exception as e:
        logger.error(f"Error showing top: {e}")
        await callback_query.answer("Ошибка при загрузке топа.", show_alert=True)


# ---------- главное меню и /start ----------
def get_main_keyboard(user_id=None):
    """Главное меню: большая «Найти матч», в два столбца «Профиль» и «Топ», затем большие Premium, «Промокод» и «Тикет»."""
    in_match = bool(user_id and db.fc_get_user_active_lobby(user_id))
    find_button = (
        btn("📋 Мой матч / лобби", callback_data="fcfind", icon="📋")
        if in_match else btn("🔍 Найти матч", callback_data="fcfind", icon="🔍")
    )
    return InlineKeyboardMarkup(inline_keyboard=[
        [find_button],
        [
            btn("👤 Мой профиль", callback_data="profile", icon="👤"),
            btn("🏆 Топ игроков", callback_data="top", icon="🏆"),
        ],
        [btn("⭐️ Premium", callback_data="premium_menu", icon="⭐️")],
        [btn("🎟 Промокод", callback_data="promo_enter", icon="🎟")],
        [btn("🎫 Тикет", callback_data="ticket_start", icon="🎫")],
    ])


@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    first_name = message.from_user.first_name or "игрок"
    try:
        await message.delete()
    except Exception:
        pass
    await cleanup_user_messages(user_id)
    try:
        await set_menu_button(user_id)
        await set_bot_commands_for_user(user_id)
    except Exception as e:
        logger.info(f"Cannot set menu for {user_id}: {e}")
    if db.is_user_registered(user_id):
        profile = db.get_player_profile(user_id)
        nickname = profile[2] if profile else first_name
        await send_message_with_image(
            user_id,
            f"{pe('👋')} Привет, <b>{esc(nickname)}</b>!\n\nВыберите действие:",
            MENU_IMAGE_URL,
            get_main_keyboard(user_id),
        )
    else:
        await send_message_with_image(
            user_id,
            f"{pe('👋')} Привет, {esc(first_name)}!\n\nНажмите кнопку ниже, чтобы зарегистрироваться:",
            MENU_IMAGE_URL,
            get_registration_keyboard(),
        )


async def main():
    commands = [
        types.BotCommand(command="start", description="🎮 Главное меню"),
        types.BotCommand(command="profile", description="👤 Мой профиль"),
        types.BotCommand(command="ticket", description="🎫 Тикет (жалоба / поддержка)"),
    ]
    try:
        await bot.set_my_commands(commands)
        logger.info("Bot commands set successfully")
    except Exception as e:
        logger.error(f"Error setting bot commands: {e}")

    print("Бот запущен...")
    logger.info("Bot starting...")

    await ensure_open_lobbies()
    background_task = asyncio.create_task(fc_background_loop())

    try:
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Error in main: {e}")
    finally:
        background_task.cancel()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
