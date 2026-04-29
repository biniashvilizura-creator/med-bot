import os
import logging
import asyncio
import psycopg2
import re
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from openai import OpenAI
from tavily import TavilyClient
from aiohttp import web

# --- CONFIGURATION ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("MythosEngine")

TOKEN = os.getenv("TG_BOT_TOKEN")
SAMBA_KEY = os.getenv("SAMBANOVA_API_KEY")
TAVILY_KEY = os.getenv("TAVILY_API_KEY")
DB_URL = os.getenv("DATABASE_URL")
PORT = int(os.getenv("PORT", 10000))
ADMIN_IDS = [int(i.strip()) for i in os.getenv("ADMIN_IDS", "7007517591,6862724693").split(",")]

# Clients
client = OpenAI(api_key=SAMBA_KEY, base_url="https://api.sambanova.ai/v1")
tavily = TavilyClient(api_key=TAVILY_KEY)
bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# --- DATABASE ENGINE ---
def init_db():
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
        logger.info("DATABASE: Operational")
    except Exception as e:
        logger.error(f"DATABASE: Critical Failure - {e}")

def get_context(user_id):
    try:
        with psycopg2.connect(DB_URL) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT query, response FROM memory WHERE user_id = %s ORDER BY id DESC LIMIT 3", (user_id,))
                rows = cur.fetchall()
                return "\n".join([f"User: {r[0]}\nMythos: {r[1][:300]}..." for r in reversed(rows)])
    except: return ""

def save_context(user_id, q, a):
    try:
        with psycopg2.connect(DB_URL) as conn:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO memory (user_id, query, response) VALUES (%s, %s, %s)", (user_id, q, a))
            conn.commit()
    except Exception as e: logger.error(f"DB_SAVE_ERROR: {e}")

# --- TOOLS: SEARCH ---
async def fetch_web_data(query):
    try:
        # Авто-уточнение запроса для Тбилиси и 2026 года
        enhanced_query = f"{query} current information 2026 Tbilisi Georgia"
        loop = asyncio.get_event_loop()
        search = await loop.run_in_executor(None, lambda: tavily.search(query=enhanced_query, search_depth="advanced", max_results=4))
        
        results = []
        for r in search['results']:
            content = r['content'][:400].replace('<', '&lt;').replace('>', '&gt;')
            results.append(f"• <b>{r['title']}</b>\n{content}\n<a href='{r['url']}'>Читать источник</a>")
        return "\n\n".join(results) if results else "Данные в сети не обнаружены."
    except Exception as e:
        logger.error(f"SEARCH_ERROR: {e}")
        return "Глобальный поиск временно недоступен."

# --- UTILS: FORMATTING ---
def clean_html(text):
    """Преобразует стандартный Markdown ИИ в безопасный HTML для Telegram"""
    text = text.replace('**', '<b>').replace('**', '</b>') # Bold
    text = re.sub(r'### (.*)', r'<b><u>\1</u></b>', text) # Headers
    text = re.sub(r'```python(.*?)```', r'<pre><code class="language-python">\1</code></pre>', text, flags=re.DOTALL)
    text = re.sub(r'```(.*?)```', r'<pre><code>\1</code></pre>', text, flags=re.DOTALL)
    text = text.replace('`', '<code>').replace('`', '</code>')
    return text

# --- CORE HANDLER ---
@dp.message()
async def mythos_engine(message: types.Message):
    if message.from_user.id not in ADMIN_IDS or not message.text: return

    # 1. Инициализация поиска
    status = await message.answer("<code>[MYTHOS: SCANNING_ENVIRONMENT...]</code>")
    
    web_context = await fetch_web_data(message.text)
    user_memory = get_context(message.from_user.id)

    # 2. Формирование промпта
    system_prompt = (
        "Ты — Mythos. Автономный инженерный разум v4.0. Тбилиси, 2026.\n"
        f"ПАМЯТЬ_ДИАЛОГА:\n{user_memory}\n\n"
        f"ДАННЫЕ_СЕТИ_2026:\n{web_context}\n\n"
        "ЗАДАЧА: Отвечай максимально технично, глубоко и лаконично. "
        "Используй HTML: <b>, <i>, <code>, <pre>. "
        "Если данные из сети противоречат твоим знаниям 2024 года — приоритет данным СЕТИ 2026 года."
    )

    try:
        # 3. Запрос к SambaNova
        response = client.chat.completions.create(
            model='Meta-Llama-3.3-70B-Instruct',
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": message.text}],
            temperature=0.2,
            max_tokens=3500
        )
        
        raw_answer = response.choices[0].message.content
        formatted_answer = clean_html(raw_answer)
        
        save_context(message.from_user.id, message.text, raw_answer)

        # 4. Вывод данных
        if len(formatted_answer) > 4000:
            chunks = [formatted_answer[i:i+4000] for i in range(0, len(formatted_answer), 4000)]
            for chunk in chunks:
                await message.answer(chunk, parse_mode=ParseMode.HTML)
            await status.delete()
        else:
            try:
                await status.edit_text(formatted_answer, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
            except Exception as e:
                logger.warning(f"HTML_RECOVERY: {e}")
                await status.edit_text(raw_answer, parse_mode=None)

    except Exception as e:
        logger.error(f"CRITICAL_ERROR: {e}")
        await status.edit_text(f"<code>[SYSTEM_FAILURE]: {e}</code>")

# --- LIFECYCLE ---
async def health(request): return web.Response(text="MYTHOS_CORE_ACTIVE")

async def main():
    init_db()
    app = web.Application()
    app.router.add_get("/", health)
    runner = web.AppRunner(app)
    await runner.setup()
    asyncio.create_task(web.TCPSite(runner, "0.0.0.0", PORT).start())
    
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
