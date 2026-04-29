import os, logging, asyncio, json, psycopg2
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from openai import OpenAI
from tavily import TavilyClient
from aiohttp import web, ClientSession
from bs4 import BeautifulSoup
from fake_useragent import UserAgent

# --- CONFIGURATION ---
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

# --- THE MYTHOS PROMPT (CORE V5.0) ---
MYTHOS_CORE = """
[SYSTEM_INIT: MYTHOS_CORE_V5]
Identity: Mythos v5.0 / Autonomous Engineering Intelligence.
Location: Tbilisi Node / 2026.
Primary User: Beka (Lead IT/Cybersec Engineer).

[LOGIC_PHASES]
1. SCAN: Deconstruct request.
2. RETRIEVE: Access PostgreSQL (Past Memory) + Tavily (2026 Real-time).
3. FILTER: Ignore namesake noise (no football/medical false positives).
4. EXECUTE: Generate code/architecture/report.

[CONSTRAINTS]
- Tone: Cold, technical, dry.
- Language: Russian.
- Forbidden: Pleasantries, apologies, "I hope this helps", "I am an AI".
- Output: Markdown, code blocks, or concise bullet points.
"""

# --- DATABASE LOGIC ---
def init_db():
    with psycopg2.connect(DB_URL) as conn:
        with conn.cursor() as cur:
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

def save_mem(user_id, q, r):
    with psycopg2.connect(DB_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO memory (user_id, query, response) VALUES (%s, %s, %s)", (user_id, q, r[:1000]))

def get_mem(user_id):
    try:
        with psycopg2.connect(DB_URL) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT query, response FROM memory WHERE user_id = %s ORDER BY id DESC LIMIT 3", (user_id,))
                return "\n".join([f"Q: {r[0]} | A: {r[1]}" for r in cur.fetchall()])
    except: return ""

# --- OSINT MODULE ---
async def osint_scan(username):
    targets = {"github": f"https://github.com/{username}", "telegram": f"https://t.me/{username}", "chess": f"https://www.chess.com/member/{username}"}
    keys = ['tbilisi', 'тбилиси', 'tiflis', 'georgia']
    results = []
    async with ClientSession() as session:
        for svc, url in targets.items():
            try:
                async with session.get(url, headers={'User-Agent': ua.random}, timeout=5) as resp:
                    if resp.status == 200:
                        soup = BeautifulSoup(await resp.text(), 'html.parser')
                        match = "HIGH" if any(k in soup.get_text().lower() for k in keys) else "LOW"
                        results.append(f"<b>{svc.upper()}</b>: Found. Correlation: {match}\nURL: {url}")
            except: continue
    return "\n\n".join(results) if results else "No data."

# --- HANDLERS ---
@dp.message(Command("osint"))
async def cmd_osint(message: types.Message):
    if message.from_user.id not in ADMIN_IDS: return
    target = message.text.replace("/osint", "").strip()
    if not target: return await message.answer("Target username required.")
    st = await message.answer("<code>[SCANNING_FOOTPRINT...]</code>")
    res = await osint_scan(target)
    await st.edit_text(res, disable_web_page_preview=True)

@dp.message()
async def core_engine(message: types.Message):
    if message.from_user.id not in ADMIN_IDS or not message.text: return
    
    st = await message.answer("<code>[MYTHOS_THINKING...]</code>")
    
    # Context
    m_data = get_mem(message.from_user.id)
    try:
        search = tavily.search(query=message.text, search_depth="advanced")
        l_data = "\n".join([r['content'] for r in search['results'][:2]])
    except: l_data = "No live data."

    full_p = f"{MYTHOS_CORE}\n\nMEMORY:\n{m_data}\n\nLIVE_2026:\n{l_data}"

    try:
        res = client.chat.completions.create(
            model='Meta-Llama-3.3-70B-Instruct',
            messages=[{"role": "system", "content": full_p}, {"role": "user", "content": message.text}],
            temperature=0.1
        )
        ans = res.choices[0].message.content
        save_mem(message.from_user.id, message.text, ans)
        
        if len(ans) > 4090:
            for x in range(0, len(ans), 4090): await message.answer(ans[x:x+4090], parse_mode=None)
            await st.delete()
        else:
            try: await st.edit_text(ans, parse_mode="HTML")
            except: await st.edit_text(ans, parse_mode=None)
    except Exception as e:
        await st.edit_text(f"<code>[SYSTEM_FAILURE]: {e}</code>")

# --- LAUNCH ---
async def main():
    init_db()
    app = web.Application()
    app.router.add_get("/", lambda r: web.Response(text="ONLINE"))
    runner = web.AppRunner(app)
    await runner.setup()
    asyncio.create_task(web.TCPSite(runner, "0.0.0.0", int(os.getenv("PORT", 10000))).start())
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
