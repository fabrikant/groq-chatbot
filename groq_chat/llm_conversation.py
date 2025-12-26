import logging
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ChatAction
from telegram.error import BadRequest
from groq_chat.groq_chat import (
    generate_response,
    generate_ocr_response,
    generate_stt_response,
)
from translate.translate import translate
import telegramify_markdown
from telegramify_markdown.interpreters import (
    TextInterpreter,
    FileInterpreter,
    MermaidInterpreter,
    InterpreterChain,
)
from telegram.constants import ParseMode
from telegramify_markdown.type import ContentTypes
import io
from telegram import InputFile
from telegramify_markdown.customize import get_runtime_config
import db.async_database as db
import base64
from io import BytesIO

logger = logging.getLogger(__name__)


# get_runtime_config().markdown_symbol.head_level_1 = "#"
# get_runtime_config().markdown_symbol.head_level_2 = "##"
# get_runtime_config().markdown_symbol.head_level_3 = "###"
# get_runtime_config().markdown_symbol.head_level_4 = "####"


async def llm_audio_request(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.chat.send_action(ChatAction.TYPING)
    try:
        tg_file = await context.bot.get_file(
            update.effective_message.voice
            or update.effective_message.audio
            or update.effective_message.document
        )
        message = update.message.caption

        bio = BytesIO()
        await tg_file.download_to_memory(bio)
        bio.name = "audio_message.ogg"

        full_output_message = await generate_stt_response(bio, message, context)
        await send_response(full_output_message, update, context)
    except Exception as e:
        if hasattr(e, "message"):
            await send_response(e.message, update, context)
        else:
            raise e


async def llm_image_request(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message

    if message.photo:
        file_id = message.photo[-1].file_id
    elif message.document and message.document.mime_type.startswith("image/"):
        file_id = message.document.file_id
    else:
        text = await translate("This is not an image. Send an image.", context)
        await message.reply_text(text)
        return

    await update.message.chat.send_action(ChatAction.TYPING)

    tg_file = await context.bot.get_file(file_id)
    file_bytes = await tg_file.download_as_bytearray()

    b64_bytes = base64.b64encode(file_bytes)
    b64_str = b64_bytes.decode("utf-8")
    message = update.message.caption
    if not message:
        message = await translate("Describe what is shown in the picture", context)

    full_output_message = await generate_ocr_response(b64_str, message, context)
    await send_response(full_output_message, update, context)


async def llm_request(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if "messages" not in context.user_data:
        context.user_data["messages"] = []

    message = update.message.text
    if not message:
        return

    await update.message.chat.send_action(ChatAction.TYPING)

    full_output_message = await generate_response(message, context)
    await send_response(full_output_message, update, context)


async def send_response(
    full_output_message: str, update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:

    if await db.get_user_setting(context._user_id, "file_interpreter", False):
        interpreter_chain = InterpreterChain(
            [
                TextInterpreter(),
                FileInterpreter(),
                MermaidInterpreter(session=None),
            ]
        )
    else:
        interpreter_chain = InterpreterChain(
            [
                TextInterpreter(),
                MermaidInterpreter(session=None),
            ]
        )

    MAX_LEN = 4000
    # Use the custom interpreter chain
    boxs = await telegramify_markdown.telegramify(
        content=full_output_message,
        interpreters_use=interpreter_chain,
        latex_escape=True,
        normalize_whitespace=True,
        max_word_count=MAX_LEN,  # The maximum number of words in a single message.
    )

    for item in boxs:

        if item.content_type == ContentTypes.TEXT:
            try:
                await update.message.reply_text(
                    item.content, parse_mode=ParseMode.MARKDOWN_V2
                )
            except BadRequest as e:
                if "parse" in str(e).lower():
                    # Если ошибки форматирования, отправляем без него
                    await update.message.reply_text(item.content, parse_mode=None)

        elif item.content_type == ContentTypes.PHOTO:
            await context.bot.send_photo(
                chat_id=update.effective_chat.id,
                photo=InputFile(io.BytesIO(item.file_data), filename=item.file_name),
                caption=item.caption,
                parse_mode=ParseMode.MARKDOWN_V2,
            )
        elif item.content_type == ContentTypes.FILE:
            await context.bot.send_document(
                chat_id=update.effective_chat.id,
                document=InputFile(io.BytesIO(item.file_data), filename=item.file_name),
                caption=item.caption,
                parse_mode=ParseMode.MARKDOWN_V2,
            )

    context.user_data["messages"].append(
        {"role": "assistant", "content": full_output_message}
    )
