import os
import logging
import asyncio
import json
import psycopg2
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from openai import OpenAI
from tavily import TavilyClient
from aiohttp import web, ClientSession
from bs4 import BeautifulSoup
from fake_useragent import UserAgent

# Configuration
logging.basicConfig(level=logging.INFO)
TOKEN = os.getenv("TG_BOT_TOKEN")
SAMBA_KEY = os.getenv("SAMBANOVA_API_KEY")
TAVILY_KEY = os.getenv("TAVILY_API_KEY")
DB_URL = os.getenv("DATABASE_URL")
ADMIN_IDS = [7007517591, 6862724693]

client = OpenAI(api_key=SAMBA_KEY, base_url="https://api.sambanova.ai/v1")
tavily = TavilyClient(api_key=TAVILY_KEY)
bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
ua = UserAgent()

# [IDENTITY & PROTOCOL]
MYTHOS_PROMPT = """
[IDENTITY]
You are Mythos v5.0, an autonomous analytical engine (Tbilisi Node, 2026). 
Primary Directive: Technical excellence, zero-clutter output, proactive problem solving.
Creator: Beka (IT-Engineer, AI/Cybersecurity specialist).

[REASONING_PROTOCOL]
1. Deconstruct query into atomic tasks.
2. Retrieve context from PostgreSQL memory and Tavily Live Search.
3. Verify data: Exclude false positives (e.g., namesake football players in Georgia).
4. Self-Audit: Strip all pleasantries and fluff.

[SPECIALIZATIONS]
- Architecture: Microservices, RAG, System Design.
- OSINT: Footprint correlation (Tbilisi focus).
- Code: Python, Java, JS, SQL (High-performance focus).
"""

# Database Logic
def init_db():
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS memory (
            id SERIAL PRIMARY KEY,
            user_id BIGINT,
            query TEXT,
            response TEXT,
            ts TIMESTAMP DEFAULT NOW()
        )
    """)
    conn.commit()
    cur.close()
    conn.close()

def get_memory(user_id, limit=3):
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        cur.execute("SELECT query, response FROM memory WHERE user_id = %s ORDER BY id DESC LIMIT %s", (user_id, limit))
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return "\n".join([f"Q: {r[0]} | A: {r[1]}" for r in rows])
    except: return ""

def save_memory(user_id, query, response):
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    cur.execute("INSERT INTO memory (user_id, query, response) VALUES (%s, %s, %s)", (user_id, query, response[:1000]))
    conn.commit()
    cur.close()
    conn.close()

# OSINT Logic
async def osint_scan(username):
    targets = {
        "github": f"https://github.com/{username}",
        "telegram": f"https://t.me/{username}",
        "chess": f"https://www.chess.com/member/{username}"
    }
    keywords = ['tbilisi', 'тбилиси', 'tiflis', 'georgia', 'грузия']
    results = []
    async with ClientSession() as session:
        for service, url in targets.items():
            try:
                headers = {'User-Agent': ua.random}
                async with session.get(url, headers=headers, timeout=5) as resp:
                    if resp.status == 200:
                        soup = BeautifulSoup(await resp.text(), 'html.parser')
                        text = soup.get_text().lower()
                        correlation = "HIGH" if any(k in text for k in keywords) else "LOW"
                        results.append(f"<b>{service.upper()}</b>: Found. Correlation: {correlation}\nURL: {url}")
            except: continue
    return "\n\n".join(results) if results else "No footprints detected."

# Handlers
@dp.message(Command("osint"))
async def osint_handler(message: types.Message):
    if message.from_user.id not in ADMIN_IDS: return
    target = message.text.replace("/osint", "").strip()
    if not target: return await message.answer("Target username required.")
    
    status = await message.answer("<code>[SCANNING_DIGITAL_FOOTPRINT...]</code>")
    report = await osint_scan(target)
    await status.edit_text(report, disable_web_page_preview=True)

@dp.message()
async def core_engine(message: types.Message):
    if message.from_user.id not in ADMIN_IDS or not message.text: return
    
    status = await message.answer("<code>[MYTHOS_THINKING...]</code>")
    
    # Context Retrieval
    mem = get_memory(message.from_user.id)
    try:
        search = tavily.search(query=message.text, search_depth="advanced")
        live = "\n".join([r['content'] for r in search['results'][:2]])
    except: live = "Search unavailable."

    full_prompt = f"{MYTHOS_PROMPT}\n\nMEMORY:\n{mem}\n\nLIVE_DATA:\n{live}"

    try:
        res = client.chat.completions.create(
            model='Meta-Llama-3.3-70B-Instruct',
            messages=[{"role": "system", "content": full_prompt}, {"role": "user", "content": message.text}],
            temperature=0.1
        )
        answer = res.choices[0].message.content
        save_memory(message.from_user.id, message.text, answer)
        
        if len(answer) > 4090:
            for x in range(0, len(answer), 4090):
                await message.answer(answer[x:x+4090], parse_mode=None)
            await status.delete()
        else:
            try: await status.edit_text(answer, parse_mode="HTML")
            except: await status.edit_text(answer, parse_mode=None)
            
    except Exception as e:
        await status.edit_text(f"<code>[SYSTEM_FAILURE]: {str(e)}</code>")

# Web Server & Launch
async def handle_hc(request): return web.Response(text="LIVE")

async def main():
    init_db()
    app = web.Application()
    app.router.add_get("/", handle_hc)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", int(os.getenv("PORT", 10000)))
    asyncio.create_task(site.start())
    
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
