import json
from telegram import Chat, Update
from telegram.ext import Application, ContextTypes, MessageHandler, filters

TOKEN = ""

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
    #вызов аишки
    #отправка результата в чат (читаем документацию)

def main() -> None:
    TextingMachine = Application.builder().token(TOKEN).build()
    TextingMachine.add_handler(MessageHandler(filters.TEXT, trackchat))
    TextingMachine.run_polling(allowed_updates=Update.MESSAGE)

if __name__== "__main__":
    main()
