import logging
import traceback
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ParseMode
from groq_chat.groq_chat import get_default_model
from translate.translate import translate
from groq_chat.llm_conversation import send_response
import groq_chat.command_descriptions as com_descr
from groq_chat.context import new_chat
from db.async_database import set_user_setting

import telegramify_markdown
from telegramify_markdown.interpreters import (
    TextInterpreter,
    InterpreterChain,
)

logger = logging.getLogger(__name__)
SYSTEM_PROMPT_SP, CANCEL_SP, START_CHANGE_LANG, CANCEL_CHANGE_LANG = range(4)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    user = update.effective_user
    message = await translate(
        (
            f"**Hi {user.mention_markdown()}!**\n"
            "Start sending messages with me to generate a response\n"
            f"{com_descr.panel}\n"
            f"{com_descr.new}\n"
            f"{com_descr.model}"
            f"{com_descr.info}"
        ),
        context,
    )
    await update.message.reply_markdown(message)


async def new_command_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    new_chat(context)
    message = await translate(f"New chat started.\n{com_descr.model}", context)
    if update.callback_query:
        query = update.callback_query
        chat_id = query.message.chat.id
    else:
        chat_id = update.effective_chat.id

    await context.bot.send_message(
        chat_id=chat_id, text=message, parse_mode=ParseMode.MARKDOWN
    )


async def start_system_prompt(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    if update.callback_query:
        query = update.callback_query
        chat_id = query.message.chat.id
        await query.answer()
    else:
        chat_id = update.effective_chat.id
    message = await translate(
        "Enter the system prompt. If you want to clear the prompt, send clear. To exit prompt - editing mode, send /cancel.",
        context,
    )
    await context.bot.send_message(chat_id=chat_id, text=message)
    return SYSTEM_PROMPT_SP


async def cancelled_system_prompt(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    message = await translate("System prompt change cancelled", context)
    await update.message.reply_text(message)
    return ConversationHandler.END


async def clear_system_prompt(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    if update.callback_query:
        query = update.callback_query
        chat_id = query.message.chat.id
        await query.answer()
    else:
        chat_id = update.effective_chat.id
    current_prompt = context.user_data.pop("system_prompt", None)
    message = await translate(
        "The system prompt has been cleared. Value before clearing:", context
    )
    message += f"\n\n{current_prompt}"
    await context.bot.send_message(chat_id=chat_id, text=message)


async def get_system_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    system_prompt = update.message.text
    if system_prompt.lower().strip() == "clear":
        await clear_system_prompt(update, context)
    else:
        context.user_data["system_prompt"] = system_prompt
        message = await translate("System prompt changed", context)
        await update.message.reply_text(message)
    new_chat(context)
    return ConversationHandler.END


async def show_system_prompt(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    if update.callback_query:
        query = update.callback_query
        chat_id = query.message.chat.id
        await query.answer()
    else:
        chat_id = update.effective_chat.id

    if "system_prompt" in context.user_data and context.user_data["system_prompt"]:
        message = context.user_data["system_prompt"]
    else:
        message = await translate("System prompt not set", context)

    await context.bot.send_message(chat_id=chat_id, text=message)


#     start_change_lang,
# get_new_lang,
# cancelled_change_lang,


async def start_change_lang(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.callback_query:
        query = update.callback_query
        chat_id = query.message.chat.id
        await query.answer()
    else:
        chat_id = update.effective_chat.id
    message = "Enter the language code (en, ru, fr, cn ...). To exit language - editing mode, send /cancel"
    await context.bot.send_message(chat_id=chat_id, text=message)
    return START_CHANGE_LANG


async def get_new_lang(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lang = update.message.text
    if update.callback_query:
        query = update.callback_query
        chat_id = query.message.chat.id
    else:
        chat_id = update.effective_chat.id

    await set_user_setting(chat_id, "lang", lang)
    context.user_data["LANG"] = lang

    message = "The language code installed is"
    message_trans = None
    if lang != "en":
        message_trans = f"{await translate(message, context)}: {lang}"
    message += f": {lang}"
    if message_trans:
        message += f"\n{message_trans}"

    await update.message.reply_text(message)
    return ConversationHandler.END


async def cancelled_change_lang(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    message = "Language change cancelled"
    if message != "en":
        message = f"\n{await translate(message, context)}"
    await update.message.reply_text(message)
    return ConversationHandler.END


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log the error and send a telegram message to notify the developer."""
    logger.error("Exception while handling an update:", exc_info=context.error)
    tb_list = traceback.format_exception(
        None, context.error, context.error.__traceback__
    )
    tb_string = "".join(tb_list)
    update_str = update.to_dict() if isinstance(update, Update) else str(update)
    message = f"```update_str\n{update_str}```\n\n\n```error_str\n\n{tb_string}\n```\n"

    interpreter_chain = InterpreterChain(
        [
            TextInterpreter(),
        ]
    )

    MAX_LEN = 4000
    # Use the custom interpreter chain
    boxs = await telegramify_markdown.telegramify(
        content=message,
        interpreters_use=interpreter_chain,
        latex_escape=True,
        normalize_whitespace=True,
        max_word_count=MAX_LEN,  # The maximum number of words in a single message.
    )
    if update.callback_query:
        query = update.callback_query
        chat_id = query.message.chat.id
    else:
        chat_id = update.effective_chat.id

    for item in boxs:
        await context.bot.send_message(
            chat_id=chat_id, text=item.content, parse_mode=ParseMode.MARKDOWN_V2
        )
