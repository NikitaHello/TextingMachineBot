import json
import os
import sys
from dotenv import load_dotenv
from google import genai
from telegram import Update
from telegram.ext import Application, ContextTypes, MessageHandler
from telegram.ext import CommandHandler, filters
from aiotinydb import AIOTinyDB, Query
from datetime import datetime
import statistics


load_dotenv()
TOKEN = os.getenv("TOKEN")
API_KEY = os.getenv("API_KEY")

db = AIOTinyDB("messages.json")
prompts_db = AIOTinyDB("prompts.json")
Message = Query()
Prompt = Query()

async def trackchat(update: Update, 
                    context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    sender = update.effective_message.from_user.first_name
    text = update.effective_message.text
    
    await add_message(chat_id, sender, text)

    cache = await get_chat_cache(chat_id)
    trigger = await get_dynamic_trigger(chat_id)

    if len(cache) >= trigger:
        messages_json = json.dumps(
            [{"sender": m["sender"], "text": m["text"]} for m in cache],
            ensure_ascii=False,
            indent=2
        )

        await process_messages(messages_json, update.effective_message.chat_id,
                               context)
        
        await clear_chat_cache(chat_id)

async def process_messages(messages_json: str, chat_id: int,
                          context: ContextTypes.DEFAULT_TYPE) -> None:
    client = genai.Client(api_key=API_KEY)
    prompt_template = await get_random_prompt()
    response = client.models.generate_content(
        model="gemini-2.0-flash", 
        contents="Your response have to be less than 2000 symbols and in " \
                 "Russian." + prompt_template + \
                 "Try to respond more closely to the text. Here's what " \
                 "has been written before in chat:" + messages_json
    )
    await context.bot.send_message(chat_id, text = response.text) #вроде должно работать...
    print(response.text)

async def add_message(chat_id, sender, text):
    entry={
        "chat_id": chat_id,
        "sender": sender,
        "text": text,
        "timestamp": datetime.now().isoformat()
    }

    await db.insert({**entry, "type": "cache"})

    await db.insert({**entry, "type": "history"})

    history = await db.search((Message.chat_id == chat_id) & (Message.type == "history"))
    if len(history) > 100:
        history.sort(key=lambda m: m["timestamp"])
        to_delete = history[:len(history) - 100]
        for msg in to_delete:
            await db.remove(doc_ids=[msg.doc_id])

async def get_chat_cache(chat_id):
    return await db.search((Message.chat_id == chat_id) & (Message.type == "cache"))

async def get_chat_history(chat_id):
    return await db.search((Message.chat_id == chat_id) & (Message.type == "history"))

async def clear_chat_cache(chat_id):
    await db.remove((Message.chat_id == chat_id) & (Message.type == "cache"))

async def get_random_prompt():
    prompts = await prompts_db.all()
    if not prompts:
        return "Placeholder prompt. Behave as you wish."
    return random.choice(prompts)

def clamp(val, min_val, max_val):
    return max(min_val, min(val, max_val))

async def get_dynamic_trigger(chat_id: int) -> int:
    messages = await get_chat_history(chat_id)
    if len(messages) < 5:
        return 5

    sorted_msgs = sorted(messages[-20:], key=lambda m: m["timestamp"])
    times = [datetime.fromisofromat(m["timestamp"]) for m in sorted_msgs]
    intervals = [(t2 - t1).total_seconds() for t1, t2 in zip(times, times[1:])]
    avg_interval = statistics.mean(intervals) if intervals else 1.0

    return clamp(round(30 / avg_interval), 5, 40)    

def main() -> None:
    TextingMachine = Application.builder().token(TOKEN).build()
    TextingMachine.add_handler(MessageHandler(filters.TEXT, trackchat))
    TextingMachine.run_polling(allowed_updates=Update.MESSAGE)

if __name__== "__main__":
    main()