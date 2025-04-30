import random

from bot import prompts_db, Message, db


def get_chat_cache(chat_id):
    return db.search((Message.chat_id == chat_id) & (Message.type == "cache"))


def get_chat_history(chat_id):
    return db.search((Message.chat_id == chat_id) &
                     (Message.type == "history"))


def clear_chat_cache(chat_id):
    db.remove((Message.chat_id == chat_id) & (Message.type == "cache"))


async def get_random_prompt():
    prompts = prompts_db.all()

    templates = [t["template"] for t in prompts]
    if not templates:
        return "Behave as if you were a sexy cat-wife companion."
    return random.choice(templates)
