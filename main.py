import os
import logging
import asyncio
import psycopg2
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from openai import OpenAI
from tavily import TavilyClient
from aiohttp import web

# Логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Конфигурация из Environment Variables
TOKEN = os.getenv("TG_BOT_TOKEN")
SAMBA_KEY = os.getenv("SAMBANOVA_API_KEY")
TAVILY_KEY = os.getenv("TAVILY_API_KEY")
DB_URL = os.getenv("DATABASE_URL")
ADMIN_IDS = [int(id) for id in os.getenv("ADMIN_IDS", "7007517591,6862724693").split(",")]
PORT = int(os.getenv("PORT", 10000))

# Инициализация клиентов
client = OpenAI(api_key=SAMBA_KEY, base_url="https://api.sambanova.ai/v1")
tavily = TavilyClient(api_key=TAVILY_KEY)
bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# --- БЛОК РАБОТЫ С ПАМЯТЬЮ (PostgreSQL) ---

def init_db():
    """Инициализация таблицы памяти"""
    try:
        with psycopg2.connect(DB_URL) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS memory (
                        id SERIAL PRIMARY KEY,
                        user_id BIGINT,
                        query TEXT,
                        response TEXT,
                        ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
            conn.commit()
        logger.info("Database initialized.")
    except Exception as e:
        logger.error(f"DB Init Error: {e}")

def get_mem(user_id, limit=3):
    """Извлечение последних диалогов"""
    try:
        with psycopg2.connect(DB_URL) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT query, response FROM memory WHERE user_id = %s ORDER BY id DESC LIMIT %s", (user_id, limit))
                res = cur.fetchall()
                return "\n".join([f"Q: {m[0]} | A: {m[1][:200]}..." for m in res])
    except: return "No past memory found."

def save_mem(user_id, query, response):
    """Сохранение нового опыта"""
    try:
        with psycopg2.connect(DB_URL) as conn:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO memory (user_id, query, response) VALUES (%s, %s, %s)", 
                           (user_id, query, response[:1000]))
            conn.commit()
    except Exception as e:
        logger.error(f"Save Memory Error: {e}")

# --- БЛОК ПОИСКА (Tavily) ---

async def search_live(query):
    """Поиск данных в реальном времени (2026)"""
    try:
        loop = asyncio.get_event_loop()
        res = await loop.run_in_executor(None, lambda: tavily.search(query=query, search_depth="advanced"))
        return "\n".join([f"- {r['content'][:300]} [Source: {r['url']}]" for r in res['results'][:3]])
    except Exception as e:
        logger.error(f"Search Error: {e}")
        return "Live search unavailable."

# --- ОБРАБОТКА СООБЩЕНИЙ ---

@dp.message()
async def mythos_core(message: types.Message):
    if message.from_user.id not in ADMIN_IDS or not message.text:
        return
    
    status = await message.answer("<code>[MYTHOS: ANALYZING_SYSTEM...]</code>")
    
    # Сбор контекста
    mem_context = get_mem(message.from_user.id)
    live_context = await search_live(message.text)
    
    sys_prompt = (
        f"Ты — Mythos, автономный инженерный разум. Специализация: Архитектура, Чистый код, OSINT, ИБ, Тренды 2026.\n"
        f"ПАМЯТЬ_ПРОШЛОГО: {mem_context}\n"
        f"АКТУАЛЬНЫЕ_ДАННЫЕ: {live_context}\n"
        f"ПРАВИЛА: Ответ только технический. Без приветствий и вежливости. Используй Markdown для кода."
    )

    try:
        response = client.chat.completions.create(
            model='Meta-Llama-3.3-70B-Instruct',
            messages=[{"role": "system", "content": sys_prompt}, {"role": "user", "content": message.text}],
            temperature=0.3,
            max_tokens=3000
        )
        ans = response.choices[0].message.content
        
        # Сохранение в БД
        save_mem(message.from_user.id, message.text, ans)
        
        # Логика отправки с защитой от ошибок парсинга
        if len(ans) > 4000:
            for i in range(0, len(ans), 4000):
                await message.answer(ans[i:i+4000], parse_mode=None)
            await status.delete()
        else:
            try:
                await status.edit_text(ans, parse_mode=ParseMode.MARKDOWN)
            except:
                await status.edit_text(ans, parse_mode=None) # Резервный сброс без форматирования
                
    except Exception as e:
        logger.error(f"Core Error: {e}")
        await status.edit_text(f"<code>[CRITICAL_FAILURE]: {e}</code>")

# --- ЗАПУСК СЕРВИСА ---

async def handle_health(request):
    return web.Response(text="MYTHOS_ONLINE")

async def main():
    init_db()
    app = web.Application()
    app.router.add_get("/", handle_health)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    asyncio.create_task(site.start())

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
