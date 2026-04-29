import os
import logging
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from openai import OpenAI

# Настройка логов, чтобы видеть ошибки в панели Render
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Берем ключи из настроек Render
TOKEN = os.getenv("TG_BOT_TOKEN")
SAMBA_KEY = os.getenv("SAMBANOVA_API_KEY")

# Твой ID и ID жены
ADMIN_IDS = [7007517591, 6862724693]

# Настройка ИИ
client = OpenAI(
    api_key=SAMBA_KEY,
    base_url="https://api.sambanova.ai/v1",
)

bot = Bot(token=TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def start(message: types.Message):
    if message.from_user.id in ADMIN_IDS:
        await message.answer("✅ Бот ожил! Я тебя узнал. Жду медицинский вопрос.")

@dp.message()
async def handle(message: types.Message):
    if message.from_user.id not in ADMIN_IDS or not message.text:
        return

    msg = await message.answer("⏳ Думаю...")
    try:
        completion = client.chat.completions.create(
            model='Llama-3.1-Tulu-3-405B',
            messages=[
                {"role": "system", "content": "Ты врач-дерматолог. Отвечай кратко."},
                {"role": "user", "content": message.text}
            ],
            temperature=0.1
        )
        await msg.edit_text(completion.choices[0].message.content)
    except Exception as e:
        logger.error(f"Ошибка ИИ: {e}")
        await msg.edit_text(f"❌ Ошибка в ключе SambaNova. Проверь его в настройках.")

async def main():
    # Эта строка убивает ошибку 409 Conflict
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
