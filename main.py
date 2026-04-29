import os
import logging
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from openai import OpenAI
from aiohttp import web

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Config
TOKEN = os.getenv("TG_BOT_TOKEN")
SAMBA_KEY = os.getenv("SAMBANOVA_API_KEY")
ADMIN_IDS = [7007517591, 6862724693]
PORT = int(os.getenv("PORT", 10000))

client = OpenAI(api_key=SAMBA_KEY, base_url="https://api.sambanova.ai/v1")
bot = Bot(token=TOKEN)
dp = Dispatcher()

async def health_check(request):
    return web.Response(text="OK")

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    if message.from_user.id in ADMIN_IDS:
        await message.answer("✅ Система активна и авторизована.")

@dp.message()
async def handle_msg(message: types.Message):
    if message.from_user.id not in ADMIN_IDS or not message.text:
        return
    
    status = await message.answer("⏳ Анализ...")
    try:
        res = client.chat.completions.create(
            model='Llama-3.1-Tulu-3-405B',
            messages=[
                {"role": "system", "content": "Ты врач-дерматолог. Отвечай кратко."},
                {"role": "user", "content": message.text}
            ],
            temperature=0.1
        )
        await status.edit_text(res.choices[0].message.content)
    except Exception as e:
        logger.error(f"Error: {e}")
        await status.edit_text("❌ Ошибка авторизации SambaNova или лимит запросов.")

async def main():
    # Web server для Render (Fix Timed Out)
    app = web.Application()
    app.router.add_get("/", health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    asyncio.create_task(site.start())

    # Polling (Fix 409 Conflict)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
