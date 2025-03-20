import json
import os
import sys
from dotenv import load_dotenv
from google import genai
from telegram import Update
from telegram.ext import Application, ContextTypes, MessageHandler
from telegram.ext import CommandHandler, filters

load_dotenv()
TOKEN = os.getenv("TOKEN")
API_KEY = os.getenv("API_KEY")

messages = []
a = 0 # счетчик сообщений

async def trackchat(update: Update, 
                    context: ContextTypes.DEFAULT_TYPE) -> None:
    global messages
    global a
    sender = update.effective_message.from_user.first_name
    text = update.effective_message.text
    messages.append({"sender": sender, "text": text})
    if len(messages) >= 20:
        messages_json = json.dumps(messages, ensure_ascii=False, indent=2)
        await process_messages(messages_json, update.effective_message.chat_id,
                               context)
        messages.clear()
    a += 1
    print (a)

async def process_messages(messages_json: str, chat_id: int,
                          context: ContextTypes.DEFAULT_TYPE) -> None:
    client = genai.Client(api_key=API_KEY)
    response = client.models.generate_content(
        model="gemini-2.0-flash", 
        contents="Your response have to be less than 2000 symbols and in " \
                 "Russian. Behave if you were a sexy cat-wife companion. " \
                 "Try to respond more closely to the text. Here's what " \
                 "has been written before in chat:" + messages_json
    )
    await context.bot.send_message(chat_id, text = response.text) #вроде должно работать...
    print(response.text)

def main() -> None:
    TextingMachine = Application.builder().token(TOKEN).build()
    TextingMachine.add_handler(MessageHandler(filters.TEXT, trackchat))
    TextingMachine.run_polling(allowed_updates=Update.MESSAGE)

if __name__== "__main__":
    main()