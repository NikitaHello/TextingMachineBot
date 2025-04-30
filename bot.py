import os

from dotenv import load_dotenv
from google import genai
from telegram import Update
from telegram.ext import Application, MessageHandler
from telegram.ext import filters
from huggingface_hub import InferenceClient
from tinydb import TinyDB, Query
from twelvelabs import TwelveLabs


# Enviromental constants
load_dotenv()
TOKEN = os.getenv("TOKEN")
API_KEY = os.getenv("API_KEY")
HF_TOKEN = os.getenv("HF_TOKEN")
TL_KEY = os.getenv("TL_KEY")


# Setting up necessary clientss
Client = genai.Client(api_key=API_KEY)
tfClient = TwelveLabs(api_key=TL_KEY)

hfClient = InferenceClient(
                provider="hf-inference",
                api_key=HF_TOKEN
                )

# Setting up databases
db = TinyDB("messages.json", sort_keys=True,
            indent=4, separators=(',', ':'),
            ensure_ascii=False
            )

prompts_db = TinyDB("prompts.json", sort_keys=True,
                    indent=4, separators=(',', ':'),
                    ensure_ascii=False
                    )

Message = Query()
Prompt = Query()


# Starting the bot and activating handlers
def main() -> None:

    # Importing inside function to avoid import loop
    from chat import trackchat
    from media import photoCaption, videoCaption

    TextingMachine = Application.builder().token(TOKEN).build()
    TextingMachine.add_handler(MessageHandler(filters.VIDEO,
                                              videoCaption))
    TextingMachine.add_handler(MessageHandler(filters.PHOTO,
                                              photoCaption))
    TextingMachine.add_handler(
        MessageHandler(filters.TEXT | filters.FORWARDED,
                       trackchat))
    TextingMachine.run_polling(allowed_updates=Update.MESSAGE)


if __name__ == "__main__":
    main()
