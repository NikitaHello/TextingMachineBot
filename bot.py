import json
import os
import sys
from dotenv import load_dotenv
from google import genai
from telegram import Update
from telegram.ext import Application, ContextTypes, MessageHandler
from telegram.ext import CommandHandler, filters
from huggingface_hub import InferenceClient
from tinydb import TinyDB, Query
from datetime import datetime
import random
import statistics
import os


load_dotenv()
TOKEN = os.getenv("TOKEN")
API_KEY = os.getenv("API_KEY")
HF_TOKEN = os.getenv("HF_TOKEN")
TEMP_DIR = "temp"
os.makedirs(TEMP_DIR, exist_ok=True)

hfClient = InferenceClient(
                provider="hf-inference",
                api_key=HF_TOKEN
                )

db = TinyDB("messages.json", sort_keys=True,
                indent=4, separators=(',',':'),
                ensure_ascii=False
                )

prompts_db = TinyDB("prompts.json", sort_keys=True,
                indent=4, separators=(',',':'),
                ensure_ascii=False
                )

Message = Query()
Prompt = Query()

async def trackchat(update: Update, 
                    context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    sender = update.effective_message.from_user.first_name
    
    forwarded = update.effective_message.forward_origin
    
    if forwarded:
        origin_name = get_origin_name(forwarded)
        text = f"forwarded from {origin_name}: {update.effective_message.text}"
    else:
        text = update.effective_message.text
    
    await add_message(chat_id, sender, text)

    cache = sorted(get_chat_cache(chat_id), key=lambda m: m["timestamp"])
    trigger = await get_dynamic_trigger(chat_id)

    if len(cache) >= trigger:
        messages_json = json.dumps(
            [
                {
                    "sender": m["sender"],
                    "text": m["text"]
                }
                for m in cache
            ],
            ensure_ascii=False,
            indent=2
        )

        await process_messages(messages_json, chat_id,
                               context)
        
        clear_chat_cache(chat_id)

async def process_messages(messages_json: str, chat_id: int,
                          context: ContextTypes.DEFAULT_TYPE) -> None:
    client = genai.Client(api_key=API_KEY)
    prompt_template = await get_random_prompt()
    response = client.models.generate_content(
        model="gemini-2.0-flash", 
        contents="Your response have to be less than 2000 symbols and in " \
                 "Russian." + prompt_template + \
                 "Try to respond more closely to the text." \
                 "Users may sometimes send images (there will be a description). Here's what " \
                 "has been going on before in chat:" + messages_json
    )
    await context.bot.send_message(chat_id, text = response.text) #вроде должно работать...
    print(response.text)

async def add_message(chat_id, sender, text, is_photo=False):
    entry={
        "chat_id": chat_id,
        "sender": sender,
        "text": text,
        "timestamp": datetime.now().isoformat(),
        "is_photo": is_photo
    }

    db.insert({**entry, "type": "cache"})

    db.insert({**entry, "type": "history"})

    history = db.search((Message.chat_id == chat_id) & (Message.type == "history"))
    if len(history) > 100:
        history.sort(key=lambda m: m["timestamp"])
        to_delete = history[:len(history) - 100]
        for msg in to_delete:
            db.remove(doc_ids=[msg.doc_id])

def get_chat_cache(chat_id):
    return db.search((Message.chat_id == chat_id) & (Message.type == "cache"))

def get_chat_history(chat_id):
    return db.search((Message.chat_id == chat_id) & (Message.type == "history"))

def clear_chat_cache(chat_id):
    db.remove((Message.chat_id == chat_id) & (Message.type == "cache"))

async def get_random_prompt():
    prompts = prompts_db.all()

    templates = [t["template"] for t in prompts]
    if not templates:
        return "Behave as if you were a sexy cat-wife companion."
    return random.choice(templates)

def get_origin_name(forwarded) -> str:
    origin = getattr(forwarded, "sender_user", None) or \
                getattr(forwarded, "chat", None) or \
                getattr(forwarded, "sender_chat", None)

    return getattr(origin, "first_name", None) or\
            getattr(origin, "title", None) or "unknown"

def clamp(val, min_val, max_val):
    return max(min_val, min(val, max_val))

async def get_dynamic_trigger(chat_id: int) -> int:
    messages = get_chat_history(chat_id)
    if len(messages) < 20:
        return 20

    sorted_msgs = sorted(messages[-20:], key=lambda m: m["timestamp"])
    times = [datetime.fromisoformat(m["timestamp"]) for m in sorted_msgs]
    intervals = [(t2 - t1).total_seconds() for t1, t2 in zip(times, times[1:])]
    avg_interval = statistics.mean(intervals) if intervals else 1.0
    print(avg_interval)

    return clamp(round(700 / avg_interval), 20, 50)    

async def photoCaption(update: Update,
                context: ContextTypes.DEFAULT_TYPE) -> None:
    
    chat_id = update.effective_chat.id
    sender = update.effective_message.from_user.first_name
    
    forwarded = update.effective_message.forward_origin
    origin_name = get_origin_name(forwarded) if forwarded else ""

    user_text = update.effective_message.caption or ""

    image = update.message.photo[-1]
    file = await image.get_file()
    image_url = file.file_path

    try:
        image_description = hfClient.image_to_text(
                            image_url,
                            model="Salesforce/blip-image-captioning-large"
                            ).generated_text
    except Exception as e:
        print("API error:",e)
        image_description = "there is something"

    prefix = f"forwarded from {origin_name}: " if origin_name else ""
    suffix = f" (captioned: {user_text})" if user_text else ""
    description = f"Sent a photo {prefix}in which {image_description}{suffix}"

    await add_message(chat_id, sender, description, is_photo=True)


def main() -> None:
    TextingMachine = Application.builder().token(TOKEN).build()
    TextingMachine.add_handler(MessageHandler(filters.PHOTO, photoCaption))
    TextingMachine.add_handler(MessageHandler(filters.TEXT | filters.FORWARDED, trackchat))
    TextingMachine.run_polling(allowed_updates=Update.MESSAGE)

if __name__== "__main__":
    main()
