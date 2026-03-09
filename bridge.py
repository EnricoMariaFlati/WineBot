import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters

# Il mio URL Ngrok (quello che funziona)
RASA_URL = "https://tricarpellary-presumingly-benita.ngrok-free.dev/webhooks/rest/webhook"
# Il mio Token
BOT_TOKEN = "8551553989:AAFULNWr4PwV8C33x37Wb5Zs_sRA0B-nOYc"

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    # Inoltra a Rasa
    response = requests.post(RASA_URL, json={"sender": str(update.effective_chat.id), "message": user_text})
    
    # Invia la risposta di Rasa a Telegram
    for r in response.json():
        if "text" in r:
            await update.message.reply_text(r["text"])

app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
app.run_polling()