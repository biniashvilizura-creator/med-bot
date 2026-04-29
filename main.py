import os
import logging
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from openai import OpenAI

# 1. ЛОГИРОВАНИЕ
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 2. ПЕРЕМЕННЫЕ (Берутся из настроек Render)
TOKEN = os.getenv("TG_BOT_TOKEN")
SAMBANOVA_API_KEY = os.getenv("SAMBANOVA_API_KEY")

# Список разрешенных ID (Ты и Жена)
ADMIN_IDS = [7007517591, 6862724693] 

# 3. КЛИЕНТЫ
client = OpenAI(
    api_key=SAMBANOVA_API_KEY,
    base_url="https://api.sambanova.ai/v1",
)

bot = Bot(token=TOKEN)
dp = Dispatcher()

# ЗАПРОС К LLAMA-4
async def get_ai_answer(user_message):
    try:
        response = client.chat.completions.create(
            model='Llama-3.1-Tulu-3-405B',
            messages=[
                {"role": "system", "content": "Ты опытный врач-дерматолог и трихолог. Отвечай кратко, профессионально, на русском языке."},
                {"role": "user", "content": user_message}
            ],
            temperature=0.1
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"SambaNova Error: {e}")
        return "⚠️ Ошибка ИИ. Проверьте SAMBANOVA_API_KEY."

# КОМАНДА /START
@dp.message(Command("start"))
async def start_command(message: types.Message):
    if message.from_user.id in ADMIN_IDS:
        await message.answer("✅ Доступ разрешен. Я готов помогать в вопросах дерматологии.")
    else:
        logger.warning(f"Попытка доступа от чужого ID: {message.from_user.id}")

# ОБРАБОТКА СООБЩЕНИЙ
@dp.message()
async def handle_message(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return

    if not message.text:
        return

    status_msg = await message.answer("⏳ Думаю...")
    answer = await get_ai_answer(message.text)
    await status_msg.edit_text(answer)

# ЗАПУСК
async def main():
    # drop_pending_updates=True убивает ошибку 409 Conflict
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
