import os
import logging
import asyncio
import psycopg2
import re
import html
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
                        id SERIAL PRIMARY KEY, user_id BIGINT, query TEXT, response TEXT, ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
            conn.commit()
    except Exception as e:
        logger.error(f"DATABASE_ERROR: {e}")

def get_context(user_id):
    try:
        with psycopg2.connect(DB_URL) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT query, response FROM memory WHERE user_id = %s ORDER BY id DESC LIMIT 3", (user_id,))
                rows = cur.fetchall()
                return "\n".join([f"Q: {r[0]}\nA: {r[1][:200]}..." for r in reversed(rows)])
    except: return ""

def save_context(user_id, q, a):
    try:
        with psycopg2.connect(DB_URL) as conn:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO memory (user_id, query, response) VALUES (%s, %s, %s)", (user_id, q, a))
            conn.commit()
    except Exception as e: logger.error(f"DB_SAVE_ERROR: {e}")

# --- TOOLS ---
async def fetch_web_data(query):
    try:
        refined = f"{query} current information 2026 Tbilisi Georgia"
        loop = asyncio.get_event_loop()
        search = await loop.run_in_executor(None, lambda: tavily.search(query=refined, search_depth="advanced", max_results=4))
        results = []
        for r in search['results']:
            safe_content = html.escape(r['content'][:300])
            results.append(f"• <b>{html.escape(r['title'])}</b>\n{safe_content}\n<a href='{r['url']}'>Источник</a>")
        return "\n\n".join(results) if results else "Данные не найдены."
    except Exception as e:
        return f"Search error: {e}"

def clean_html(text):
    text = html.escape(text)
    text = text.replace('**', '<b>').replace('**', '</b>')
    text = re.sub(r'
