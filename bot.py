import json
import asyncio
import sys
from telegram import Bot

if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

TOKEN = "7828034482:AAGn_gP2fqlXSFm1Tnh49y99GrOR-Q-FtJY"
CHAT_ID = "1725448900"  

async def get_chat_messages():
    bot = Bot(token=TOKEN)
    
    # Получаем обновления (сообщения)
    updates = await bot.get_updates(limit=100)
    
    messages = []
    
    for update in updates:
        if update.message and update.message.chat.id == int(CHAT_ID):
            messages.append({
                "from": update.message.from_user.username,
                "text": update.message.text
            })
    
    print(messages)

    # Сохранение в JSON-файл
    with open("messages.json", "w", encoding="utf-8") as file:
        json.dump(messages, file, indent=4, ensure_ascii=False)
    
    print("✅ Сообщения сохранены в messages.json")

async def main():
    await get_chat_messages()

if __name__ == "__main__":
    asyncio.run(main())