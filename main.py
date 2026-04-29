import os
import logging
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from openai import OpenAI

logging.basicConfig(level=logging.INFO)
TOKEN = os.getenv("TG_BOT_TOKEN")
SAMBA_KEY = os.getenv("SAMBANOVA_API_KEY")
ADMIN_IDS = [7007517591, 6862724693]

client = OpenAI(api_key=SAMBA_KEY, base_url="https://api.sambanova.ai/v1")
bot = Bot(token=TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def start(message: types.Message):
    if message.from_user.id in ADMIN_IDS:
        await message.answer("✅ Бот активен! Теперь я отвечаю только вам.")

@dp.message()
async def handle(message: types.Message):
    if message.from_user.id not in ADMIN_IDS or not message.text:
        return
    msg = await message.answer("⏳ Минутку, советуюсь с ИИ...")
    try:
        res = client.chat.completions.create(
            model='Llama-3.1-Tulu-3-405B',
            messages=[
                {"role": "system", "content": "Ты профессиональный дерматолог. Отвечай кратко и на русском языке."},
                {"role": "user", "content": message.text}
            ],
            temperature=0.1
        )
        await msg.edit_text(res.choices[0].message.content)
    except Exception as e:
        await msg.edit_text(f"❌ Ошибка: {e}")

async def main():
    # Эта строчка магически лечит ошибку 409
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
