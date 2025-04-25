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
from twelvelabs import TwelveLabs


#Enviromental variables
load_dotenv()
TOKEN = os.getenv("TOKEN")
API_KEY = os.getenv("API_KEY")
HF_TOKEN = os.getenv("HF_TOKEN")
TL_KEY = os.getenv("TL_KEY")
INDEX_ID = os.getenv("INDEX_ID")

#Setting up necessary clients
tfClient = TwelveLabs(api_key=TL_KEY)

hfClient = InferenceClient(
                provider="hf-inference",
                api_key=HF_TOKEN
                )

# Setting up databases
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

#This function handles text messages and calls the *add_message* function to store the data
#and check for trigger
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

    is_reply_to_bot = update.effective_message.reply_to_message is not None \
                        and update.effective_message.reply_to_message.from_user.id == context.bot.id

    text_final = f"replied to you the following: {text}" if is_reply_to_bot else text

    await add_message(chat_id, sender, text_final, context)

#This function is fed a JSON slice (referenced as cache) and uses it to prompt a Gemini API
#The response genereated by AI is then sent to the chat
async def process_messages(messages_json: str, chat_id: int,
                          context: ContextTypes.DEFAULT_TYPE) -> None:
    client = genai.Client(api_key=API_KEY)
    prompt_template = await get_random_prompt()
    response = client.models.generate_content(
        model="gemini-2.0-flash", 
        contents="Your response have to be less than 2000 symbols and in " \
                 "Russian." + prompt_template + \
                 "Try to respond more closely to the text." \
                 "Users may sometimes send images or videos (there will be a description)." \
                 "Users may also forward something from Telegram channels." \
                 "You are able to see your last message and when user respond to it." \
                 "You have multiple personalities prompted via 'Behave as if you were...'' part." \
                 "Ignore the style and formatting of your last message, this may be your another personality." \
                 "Minus bonus points if you mix up personalities." \
                 "Here's what has been going on before in chat:" + messages_json
    )
    context.chat_data["last_response"] = response.text
    await context.bot.send_message(chat_id, text = response.text)
    

#This function serves as a main endpoint for storing the data (be it from text, photo or video).
#First it inserts the message and its metadata into DB and then checks for a trigger (see below).
#When trigger is met it calls "process_messages" function and clears cache.
#It also keeps track of history (required for implementing dynamic trigger) so it does not exceed 100 messages.
async def add_message(chat_id, sender, text, context: ContextTypes.DEFAULT_TYPE):
    entry={
        "chat_id": chat_id,
        "sender": sender,
        "text": text,
        "timestamp": datetime.now().isoformat()
    }

    db.insert({**entry, "type": "cache"})

    db.insert({**entry, "type": "history"})

    cache = sorted(get_chat_cache(chat_id), key=lambda m: m["timestamp"])
    trigger = await get_dynamic_trigger(chat_id)

    if len(cache) >= trigger:
        
        last_response = context.chat_data.get("last_response")

        if last_response:
            cache.insert(0, {
                "sender": "Your last response",
                "text": last_response
            })

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

    history = db.search((Message.chat_id == chat_id) & (Message.type == "history"))
    if len(history) > 100:
        history.sort(key=lambda m: m["timestamp"])
        to_delete = history[:len(history) - 100]
        for msg in to_delete:
            db.remove(doc_ids=[msg.doc_id])

#DB and other helper functions
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

#The dynamic trigger is determined based on the time intervals between 20 last messages in the chat.
#If the the interval between the messages is low (high posting speed), it dynamically adapts,
#and vice versa. The minimum number (20) and other numbers can be adjusted.
#This mechanism still needs some improvements.
#The "trigger" number itself represents the number of messages required for the *add_message*
#function to call the *process_messages* function.
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

#This function handles photo messages and calls the *add_message* function to store the data
#and check for trigger
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
        print("Image API error:",e)
        image_description = "there is something"

    prefix = f"forwarded from {origin_name}: " if origin_name else ""
    suffix = f" (captioned: {user_text})" if user_text else ""
    description = f"Sent a photo {prefix}in which {image_description}{suffix}"

    await add_message(chat_id, sender, description, context)


#This function handles video messages and calls the *add_message* function to store the data
#and check for trigger
async def videoCaption(update: Update,
                context: ContextTypes.DEFAULT_TYPE) -> None:
    
    chat_id = update.effective_chat.id
    sender = update.effective_message.from_user.first_name
    
    forwarded = update.effective_message.forward_origin
    origin_name = get_origin_name(forwarded) if forwarded else ""

    user_text = update.effective_message.caption or ""

    video = update.message.video
    file = await video.get_file()
    video_url = file.file_path

    try:
        tf_task = tfClient.task.create(
            index_id=INDEX_ID,
            url=video_url
        )

        tf_task.wait_for_done()

        video_summary = tfClient.generate.summarize(
            tf_task.id,
            type="summary",
            prompt="Generate a summary in no more than 100 words."
        ).summary

        tfClient.task.delete(
            index_id=INDEX_ID,
            id=tf_task.id
        )

    except Exception as e:
        print("Video API error:",e)
        video_summary = "there is something"

    prefix = f"forwarded from {origin_name}: " if origin_name else ""
    suffix = f" (captioned: {user_text})" if user_text else ""
    description = f"Sent a video {prefix}{video_summary}{suffix}"

    await add_message(chat_id, sender, description, context)

#Starting the bot and activating handlers
def main() -> None:
    TextingMachine = Application.builder().token(TOKEN).build()
    TextingMachine.add_handler(MessageHandler(filters.VIDEO, videoCaption))
    TextingMachine.add_handler(MessageHandler(filters.PHOTO, photoCaption))
    TextingMachine.add_handler(MessageHandler(filters.TEXT | filters.FORWARDED, trackchat))
    TextingMachine.run_polling(allowed_updates=Update.MESSAGE)

if __name__== "__main__":
    main()
