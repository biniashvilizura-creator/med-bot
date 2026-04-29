import os
import logging
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from openai import OpenAI
from aiohttp import web

# Логи
logging.basicConfig(level=logging.INFO)
TOKEN = os.getenv("TG_BOT_TOKEN")
SAMBA_KEY = os.getenv("SAMBANOVA_API_KEY")
ADMIN_IDS = [7007517591, 6862724693]

client = OpenAI(api_key=SAMBA_KEY, base_url="https://api.sambanova.ai/v1")
bot = Bot(token=TOKEN)
dp = Dispatcher()

# Обманка для Render (чтобы не было Timed Out)
async def handle_health(request):
    return web.Response(text="I am alive")

@dp.message(Command("start"))
async def start(message: types.Message):
    if message.from_user.id in ADMIN_IDS:
        await message.answer("✅ Бот запущен! Теперь Render его не выключит.")

@dp.message()
async def handle(message: types.Message):
    if message.from_user.id not in ADMIN_IDS or not message.text:
        return
    msg = await message.answer("⏳ Минутку...")
    try:
        res = client.chat.completions.create(
            model='Llama-3.1-Tulu-3-405B',
            messages=[{"role": "system", "content": "Ты врач-дерматолог. Отвечай кратко."},
                     {"role": "user", "content": message.text}],
            temperature=0.1
        )
        await msg.edit_text(res.choices[0].message.content)
    except Exception as e:
        await msg.edit_text(f"❌ Ошибка ИИ. Проверь ключи.")

async def main():
    # Запускаем мини-сервер для Render на порту 10000
    app = web.Application()
    app.router.add_get("/", handle_health)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 10000)
    asyncio.create_task(site.start())

    # Запускаем бота
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
