import io
import logging
from telegram import Update
from telegram.ext import ContextTypes
from groq_chat.groq_chat import generate_tts_response
from translate.translate import translate
from telegram.constants import ChatAction
from telegram.ext import ConversationHandler

from groq_chat.handlers import START_TTS, CANCEL_TTS
from groq_chat.llm_conversation import send_response


logger = logging.getLogger(__name__)


async def tts_command_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:

    if update.callback_query:
        query = update.callback_query
        chat_id = query.message.chat.id
        query.answer()
    else:
        chat_id = update.effective_chat.id

    await context.bot.send_chat_action(chat_id, ChatAction.TYPING)

    message = await translate(
        "The next text message will be converted to a sound . To exit TTS mode, use the /cancel command.",
        context,
    )
    await context.bot.send_message(chat_id=chat_id, text=message)
    return START_TTS


async def cancelled_tts_mode(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    message = await translate("TTS mode cancelled", context)
    await update.message.reply_text(message)
    return CANCEL_TTS


async def get_tts_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_message = update.message.text

    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id, action=ChatAction.RECORD_VOICE
    )

    response_audio = await generate_tts_response(
        user_message,
        context,
    )

    if isinstance(response_audio, str):
        # Это сообщение об ошибке
        await send_response(response_audio, update, context)
        return ConversationHandler.END

    audio_bytes: bytes = await response_audio.read()
    audio_io = io.BytesIO(audio_bytes)
    audio_io.name = "response.wav"  # <-- подгоните под ваш формат

    # # Пример с voice‑сообщением (рекомендовано для коротких TTS‑ответов):
    # await context.bot.send_voice(
    #     chat_id=update.effective_chat.id,
    #     voice=audio_io,
    #     caption=await translate("Here is the audio response:", context),
    # )

    await context.bot.send_audio(
        chat_id=update.effective_chat.id,
        audio=audio_io,
        caption=await translate("Here is the audio response:", context),
    )

    return ConversationHandler.END
