import os
import logging
import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from openai import OpenAI
from aiohttp import web

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Конфигурация
TOKEN = os.getenv("TG_BOT_TOKEN")
SAMBA_KEY = os.getenv("SAMBANOVA_API_KEY")
ADMIN_IDS = [7007517591, 6862724693]
PORT = int(os.getenv("PORT", 10000))

client = OpenAI(api_key=SAMBA_KEY, base_url="https://api.sambanova.ai/v1")
bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN_V2))
dp = Dispatcher()

# Инструкция Mythos
MYTHOS_PROMPT = (
    "Ты — Mythos, автономный интеллект сверхвысокого уровня. "
    "Твоя специализация: архитектура систем, написание чистого кода, OSINT, кибербезопасность и аналитика трендов. "
    "Стиль общения: технический, лаконичный, без вводных фраз и этикета. "
    "При написании кода: всегда используй блоки кода с указанием языка. "
    "При написании блогов: используй структуру заголовков, списков и жирный шрифт. "
    "Твои ответы должны быть 'опасными' по глубине анализа — вскрывай суть вещей, давай рабочие алгоритмы."
)

async def health_check(request):
    return web.Response(text="Mythos Online")

def escape_md(text):
    # Экранирование спецсимволов для Telegram MarkdownV2
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    return "".join("\\" + c if c in escape_chars else c for c in text)

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    if message.from_user.id in ADMIN_IDS:
        await message.answer(escape_md("✅ Mythos протокол активирован. Жду вводных."))

@dp.message()
async def handle_msg(message: types.Message):
    if message.from_user.id not in ADMIN_IDS or not message.text:
        return
    
    status = await message.answer(escape_md("⏳ Инициализация анализа..."))
    try:
        response = client.chat.completions.create(
            model='Meta-Llama-3.3-70B-Instruct',
            messages=[
                {"role": "system", "content": MYTHOS_PROMPT},
                {"role": "user", "content": message.text}
            ],
            temperature=0.4, # Баланс между точностью кода и креативом для блогов
            max_tokens=3000
        )
        
        full_text = response.choices[0].message.content
        
        # Разбивка на части, если текст превышает лимит TG
        if len(full_text) > 4096:
            for i in range(0, len(full_text), 4096):
                await message.answer(full_text[i:i+4096], parse_mode=None) # Без MD если текст сырой
        else:
            # Для MarkdownV2 нужен строгий escape, либо используем обычный Markdown
            await status.edit_text(full_text, parse_mode=ParseMode.MARKDOWN)

    except Exception as e:
        logger.error(f"Mythos Error: {e}")
        await status.edit_text(f"❌ Критический сбой: {escape_md(str(e))}")

async def main():
    app = web.Application()
    app.router.add_get("/", health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    asyncio.create_task(site.start())

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
