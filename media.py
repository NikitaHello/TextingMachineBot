import os
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ContextTypes

from chat import get_origin_name, add_message
from bot import tfClient, hfClient

load_dotenv()
INDEX_ID = os.getenv("INDEX_ID")


# This function handles photo messages and calls the *add_message*
# function to store the data and check for trigger
async def photoCaption(update: Update,
                       context: ContextTypes.DEFAULT_TYPE,) -> None:

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
        print("Image API error:", e)
        image_description = "there is something"

    prefix = f"forwarded from {origin_name}: " if origin_name else ""
    suffix = f" (captioned: {user_text})" if user_text else ""
    description = f"Sent a photo {prefix}in which {image_description}{suffix}"

    await add_message(chat_id, sender, description, context)


# This function handles video messages and calls the *add_message*
# function to store the data and check for trigger
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
        print("Video API error:", e)
        if not video_summary:
            video_summary = "there is something"

    prefix = f"forwarded from {origin_name}: " if origin_name else ""
    suffix = f" (captioned: {user_text})" if user_text else ""
    description = f"Sent a video {prefix}{video_summary}{suffix}"

    await add_message(chat_id, sender, description, context)
