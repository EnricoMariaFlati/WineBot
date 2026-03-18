import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, CallbackQueryHandler, filters, CommandHandler

# Il tuo URL Ngrok
RASA_URL = "https://scholarless-lashay-treacly.ngrok-free.dev/webhooks/rest/webhook"
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
            
            # Se non c'è reply_markup, invia solo il testo (CON GRASSETTO)
            if not reply_markup:
                await update.message.reply_text(text, parse_mode='Markdown')
            else:
                # PROVA A INVIARE IL MESSAGGIO CON I BOTTONI (CON GRASSETTO)
                try:
                    await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')
                except Exception as e:
                    # Se i bottoni sono ancora "invalidi" per Telegram, invia solo il testo
                    print(f"⚠️ Errore pulsanti Telegram: {e}")
                    await update.message.reply_text(text, parse_mode='Markdown')

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
                
            # INVIA RISPOSTA AL CLICK (CON GRASSETTO)
            await query.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')

if __name__ == '__main__':
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", handle_message))

    # Handler per messaggi di testo
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    # Handler per i clic sui bottoni
    app.add_handler(CallbackQueryHandler(button_click))
    
    app.run_polling()