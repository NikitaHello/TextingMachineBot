import json
import os
import sys
from dotenv import load_dotenv
from google import genai
from telegram import Update
from telegram.ext import Application, ContextTypes, MessageHandler, CommandHandler, filters

load_dotenv()
TOKEN = os.getenv("TOKEN")
API_KEY = os.getenv("API_KEY")

messages = []

async def trackchat(update: Update , context: ContextTypes.DEFAULT_TYPE) -> None:
    global messages
    sender = update.effective_message.from_user.first_name
    text = update.effective_message.text
    messages.append({"sender": sender, "text": text})
    if len(messages) >= 100:
        messages_json = json.dumps(messages, ensure_ascii=False, indent=2)
        await process_messages(messages_json)

    messages.clear()

async def process_messages(messages_json: str) -> None:
    client = genai.Client(api_key=API_KEY)
    response = client.models.generate_content(
        model="gemini-2.0-flash", contents="Your response have to be less than 100 symbols. Behave if you were a human Imperor from Warhammer 40000 and taking part in coference of Primarchs. Here's what they say:\n"+messages_json
    )
    print(response.text)

def main() -> None:
    TextingMachine = Application.builder().token(TOKEN).build()
    TextingMachine.add_handler(MessageHandler(filters.TEXT, trackchat))
    TextingMachine.run_polling(allowed_updates=Update.MESSAGE)

if __name__== "__main__":
    main()