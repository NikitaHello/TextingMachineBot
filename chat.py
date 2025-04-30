import json
import statistics

from telegram.ext import ContextTypes
from telegram import Update
from datetime import datetime

from db import (get_chat_cache, get_chat_history, clear_chat_cache,
                get_random_prompt)
from bot import Client, Message, db


# This function is fed a JSON slice (referenced as cache) and uses it to
# prompt a Gemini API
# The response genereated by AI is then sent to the chat
async def process_messages(messages_json: str, chat_id: int,
                           context: ContextTypes.DEFAULT_TYPE) -> None:
    prompt_template = await get_random_prompt()
    prompt_body = load_prompt("prompt_body.txt")
    response = Client.models.generate_content(
        model="gemini-2.0-flash",
        contents="Your response have to be less than 2000 symbols and in "
                 "Russian." + prompt_template + prompt_body + messages_json
    )
    context.chat_data["last_response"] = response.text
    await context.bot.send_message(chat_id, text=response.text)


# This function serves as a main endpoint for storing the data (be it from
# text, photo or video).First it inserts the message and its metadata into
# DB and then checks for a trigger (see below).
# When trigger is met it calls "process_messages" function and clears cache.
# It also keeps track of history (required for implementing dynamic trigger) so
# it does not exceed 100 messages.
async def add_message(chat_id, sender, text,
                      context: ContextTypes.DEFAULT_TYPE):
    entry = {
        "chat_id": chat_id,
        "sender": sender,
        "text": text,
        "timestamp": datetime.now().isoformat()
    }

    db.insert({**entry, "type": "cache"})

    db.insert({**entry, "type": "history"})

    cache = sorted(get_chat_cache(chat_id),
                   key=lambda m: m["timestamp"])
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

    history = db.search((Message.chat_id == chat_id) &
                        (Message.type == "history"))
    if len(history) > 100:
        history.sort(key=lambda m: m["timestamp"])
        to_delete = history[:len(history) - 100]
        for msg in to_delete:
            db.remove(doc_ids=[msg.doc_id])


# This function handles text messages and calls the *add_message* function to
# store the data and check for trigger
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
        and update.effective_message.reply_to_message.from_user.id == \
        context.bot.id

    text_final = f"replied to you the following: {text}" if is_reply_to_bot \
        else text

    await add_message(chat_id, sender, text_final, context)


# The dynamic trigger is determined based on the time intervals between 20 last
# messages in the chat. If the the interval between the messages is low (high
# posting speed), it dynamically adapts, and vice versa. The minimum number
# (20) and other numbers can be adjusted. This mechanism still needs some
# improvements. The "trigger" number itself represents the number of messages
# required for the *add_message* function to call the
# *process_messages* function.
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


# Utility functions
def get_origin_name(forwarded) -> str:
    origin = getattr(forwarded, "sender_user", None) or \
                getattr(forwarded, "chat", None) or \
                getattr(forwarded, "sender_chat", None)

    return getattr(origin, "first_name", None) or \
        getattr(origin, "title", None) or "unknown"


def clamp(val, min_val, max_val):
    return max(min_val, min(val, max_val))


def load_prompt(path: str) -> str:
    with open(path, 'r', encoding='utf-8') as file:
        return file.read()
