from tinydb import TinyDB, Query
import random


def get_chat_cache(chat_id, db: TinyDB, message: Query):
    return db.search((message.chat_id == chat_id) & (message.type == "cache"))


def get_chat_history(chat_id, db: TinyDB, message: Query):
    return db.search((message.chat_id == chat_id) &
                     (message.type == "history"))


def clear_chat_cache(chat_id, db: TinyDB, message: Query):
    db.remove((message.chat_id == chat_id) & (message.type == "cache"))


async def get_random_prompt(prompts_db: TinyDB):
    prompts = prompts_db.all()

    templates = [t["template"] for t in prompts]
    if not templates:
        return "Behave as if you were a sexy cat-wife companion."
    return random.choice(templates)
