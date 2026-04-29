import os
import logging
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from openai import OpenAI
from aiohttp import web

logging.basicConfig(level=logging.INFO)
TOKEN = os.getenv("TG_BOT_TOKEN")
SAMBA_KEY = os.getenv("SAMBANOVA_API_KEY")
ADMIN_IDS = [7007517591, 6862724693]

# Использование актуальной модели SambaNova 2026
client = OpenAI(api_key=SAMBA_KEY, base_url="https://api.sambanova.ai/v1")
bot = Bot(token=TOKEN)
dp = Dispatcher()

async def handle_health(request):
    return web.Response(text="OK")

@dp.message(Command("start"))
async def start(message: types.Message):
    if message.from_user.id in ADMIN_IDS:
        await message.answer("✅ Бот запущен (Model: Llama-3.3).")

@dp.message()
async def handle(message: types.Message):
    if message.from_user.id not in ADMIN_IDS or not message.text:
        return
    msg = await message.answer("⏳ Генерация ответа...")
    try:
        res = client.chat.completions.create(
            model='Meta-Llama-3.3-70B-Instruct',
            messages=[
                {"role": "system", "content": "Ты врач-дерматолог. Отвечай кратко."},
                {"role": "user", "content": message.text}
            ],
            temperature=0.1
        )
        await msg.edit_text(res.choices[0].message.content)
    except Exception as e:
        await msg.edit_text(f"❌ Ошибка ИИ: {e}")

async def main():
    app = web.Application()
    app.router.add_get("/", handle_health)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 10000)
    asyncio.create_task(site.start())
    
    # Принудительный сброс вебхука для решения конфликта (409)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
