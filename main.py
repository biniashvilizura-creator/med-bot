import os, telebot, threading, time, requests
from openai import OpenAI
from fastapi import FastAPI
import uvicorn

app = FastAPI()

@app.get("/")
def health():
    return {"status": "Online"}

# Ключи берем из настроек (потом впишем их в Render)
TG_BOT_TOKEN = os.environ.get("TG_BOT_TOKEN")
SAMBANOVA_KEY = os.environ.get("SAMBANOVA_API_KEY")

bot = telebot.TeleBot(TG_BOT_TOKEN)
client = OpenAI(base_url="https://api.sambanova.ai/v1", api_key=SAMBANOVA_KEY)

# Доступ только для тебя и жены
ADMIN_IDS = [7007517591, 6862724693]

@bot.message_handler(func=lambda m: True)
def handle_message(message):
    uid = message.from_user.id
    if uid not in ADMIN_IDS:
        bot.reply_to(message, "Доступ закрыт.")
        return

    msg = bot.reply_to(message, "⏳ Анализирую...")
    try:
        response = client.chat.completions.create(
            model="Llama-4-Maverick-17B-128E-Instruct",
            messages=[{"role": "user", "content": message.text}]
        )
        bot.edit_message_text(response.choices[0].message.content, message.chat.id, msg.message_id)
    except Exception as e:
        bot.edit_message_text(f"Ошибка: {e}", message.chat.id, msg.message_id)

def run_bot():
    requests.get(f"https://api.telegram.org/bot{TG_BOT_TOKEN}/deleteWebhook")
    bot.infinity_polling()

if __name__ == "__main__":
    threading.Thread(target=run_bot, daemon=True).start()
    uvicorn.run(app, host="0.0.0.0", port=10000)
