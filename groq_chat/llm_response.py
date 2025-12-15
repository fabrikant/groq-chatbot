import logging
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ChatAction
from groq_chat.groq_chat import generate_response
import telegramify_markdown
from telegramify_markdown.interpreters import (
    TextInterpreter,
    FileInterpreter,
    MermaidInterpreter,
    InterpreterChain,
)
from telegramify_markdown.type import ContentTypes

import io  # Необходимо добавить в ваш файл
from telegram import InputFile  # Необходимо добавить в ваш файл

from telegramify_markdown.customize import get_runtime_config


logger = logging.getLogger(__name__)

get_runtime_config().markdown_symbol.head_level_1 = "#"
get_runtime_config().markdown_symbol.head_level_2 = "##"
get_runtime_config().markdown_symbol.head_level_3 = "###"
get_runtime_config().markdown_symbol.head_level_4 = "####"


async def send_llm_response(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if "messages" not in context.user_data:
        context.user_data["messages"] = []

    message = update.message.text
    if not message:
        return

    await update.message.chat.send_action(ChatAction.TYPING)

    full_output_message = await generate_response(message, context)

    if True:
        interpreter_chain = InterpreterChain(
            [
                TextInterpreter(),
                MermaidInterpreter(session=None),
            ]
        )
    else:
        # Это нужно чтобы получать код в отдельных файлах
        interpreter_chain = InterpreterChain(
            [
                TextInterpreter(),
                FileInterpreter(),
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
            await update.message.reply_text(item.content, parse_mode="MarkdownV2")
        elif item.content_type == ContentTypes.PHOTO:
            await context.bot.send_photo(
                chat_id=update.effective_chat.id,
                photo=InputFile(io.BytesIO(item.file_data), filename=item.file_name),
                caption=item.caption,
                parse_mode="MarkdownV2",
            )
        elif item.content_type == ContentTypes.FILE:
            await context.bot.send_document(
                chat_id=update.effective_chat.id,
                document=InputFile(io.BytesIO(item.file_data), filename=item.file_name),
                caption=item.caption,
                parse_mode="MarkdownV2",
            )

    context.user_data["messages"].append(
        {"role": "assistant", "content": full_output_message}
    )
