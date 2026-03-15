import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, CallbackQueryHandler, filters

# Il tuo URL Ngrok
RASA_URL = "https://tricarpellary-presumingly-benita.ngrok-free.dev/webhooks/rest/webhook"
# Il tuo Token
BOT_TOKEN = "8551553989:AAFULNWr4PwV8C33x37Wb5Zs_sRA0B-nOYc"

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    # Inoltra a Rasa
    response = requests.post(RASA_URL, json={"sender": str(update.effective_chat.id), "message": user_text})
    
    for r in response.json():
        if "text" in r:
            text = r["text"]
            reply_markup = None
            
            if "buttons" in r and r["buttons"]:
                keyboard = [
                    [InlineKeyboardButton(b["title"], callback_data=b["payload"])] 
                    for b in r["buttons"]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
            
            # PROVA A INVIARE IL MESSAGGIO CON I BOTTONI
            try:
                await update.message.reply_text(text, reply_markup=reply_markup)
            except Exception as e:
                # Se i bottoni sono ancora "invalidi" per Telegram, invia solo il testo
                print(f"⚠️ Errore pulsanti Telegram: {e}")
                await update.message.reply_text(text)

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    # Invia il payload del bottone (il comando) a Rasa
    response = requests.post(RASA_URL, json={"sender": str(update.effective_chat.id), "message": query.data})
    
    # Rispondi all'utente dopo il clic
    for r in response.json():
        if "text" in r:
            text = r["text"]
            reply_markup = None
            # Gestiamo bottoni anche nella risposta al clic, se necessario
            if "buttons" in r and r["buttons"]:
                keyboard = [
                    [InlineKeyboardButton(b["title"], callback_data=b["payload"])] 
                    for b in r["buttons"]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
            await query.message.reply_text(text, reply_markup=reply_markup)

if __name__ == '__main__':
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    
    # Handler per messaggi di testo
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    # Handler per i clic sui bottoni
    app.add_handler(CallbackQueryHandler(button_click))
    
    app.run_polling()