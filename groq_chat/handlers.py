import json
import logging
import traceback
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ParseMode
from groq_chat.groq_chat import get_groq_models, get_default_model
from translate.translate import translate
from groq_chat.groq_chat import generate_response
from groq_chat.llm_conversation import send_response
import groq_chat.command_descriptions as com_descr

logger = logging.getLogger(__name__)
SYSTEM_PROMPT_SP = 1
CANCEL_SP = 2


def new_chat(context: ContextTypes.DEFAULT_TYPE) -> None:
    if context.user_data.get("system_prompt") is not None:
        context.user_data["messages"] = [
            {
                "role": "system",
                "content": context.user_data.get("system_prompt"),
            },
        ]
    else:
        context.user_data["messages"] = []


async def start(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    user = update.effective_user
    message = await translate(
        (
            f"**Hi {user.mention_markdown()}!**\n"
            "Start sending messages with me to generate a response\n"
            f"{com_descr.new}\n"
            f"{com_descr.model}\n"
            f"{com_descr.help}"
        )
    )
    await update.message.reply_markdown(message)


async def help_command(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    help_text = await translate(
        (
            "Available commands:\n"
            f"{com_descr.new}\n"
            f"{com_descr.help}\n\n"
            f"{com_descr.model}\n"
            f"{com_descr.info}\n"
            f"{com_descr.system_prompt}\n\n"
            "Send a message to the bot to generate a response"
        )
    )
    await update.message.reply_text(help_text)


async def new_command_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Start a new chat session"""
    new_chat(context)
    message = await translate(f"New chat started.\n{com_descr.model}")
    await update.message.reply_text(message)


def create_model_key(model_name: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(model_name, callback_data="change_model_" + model_name)


async def model_command_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:

    models = await get_groq_models()
    button_list = [
        [create_model_key(models[i]), create_model_key(models[i + 1])]
        for i in range(0, len(models) - len(models) % 2, 2)
    ]
    if len(models) % 2 == 1:
        button_list.append([create_model_key(models[-1])])
    reply_markup = InlineKeyboardMarkup(button_list)
    message = await translate("select_model")
    await update.message.reply_text(message, reply_markup=reply_markup)


async def change_model_callback_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Change the model used to generate responses"""
    query = update.callback_query
    model = query.data.replace("change_model_", "")

    context.user_data["model"] = model
    message = await translate(f"Model changed to `{model}`")
    about = await get_model_info(context)

    if about:
        message += "\n\n" + about

    new_chat(context)

    await query.edit_message_text(
        message,
        parse_mode=ParseMode.MARKDOWN,
    )


async def get_model_info(context):
    who_are_you = await translate("Tell me about yourself in two sentences")
    about = await generate_response(who_are_you, context)

    if about.lower().startswith("error"):
        try:
            error_json = json.loads(
                about[about.find("{") : about.rfind("}") + 1].replace("'", '"')
            )
            about = error_json.get("error", about).get("message", about)
            about = await translate(about) + "\n\n"
            about += await translate(
                "Send /model to change the model used to generate responses"
            )
        except:
            pass

    return about


async def start_system_prompt(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Start a system prompt"""
    message = await translate("system_prompt_instructions")
    await update.message.reply_text(message)
    return SYSTEM_PROMPT_SP


async def cancelled_system_prompt(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Cancel the system prompt"""
    message = await translate("System prompt change cancelled.")
    await update.message.reply_text(message)
    return ConversationHandler.END


async def get_system_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Get the system prompt"""
    system_prompt = update.message.text
    if system_prompt.lower().strip() == "clear":
        context.user_data.pop("system_prompt", None)
        message = await translate("System prompt cleared.")
        await update.message.reply_text(message)
    else:
        context.user_data["system_prompt"] = system_prompt
        message = await translate("System prompt changed.")
        await update.message.reply_text(message)
    new_chat(context)
    return ConversationHandler.END


async def info_command_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Get info about the bot"""
    message = (
        f"**__Model Info:__**\n"
        f"**Model**: `{context.user_data.get("model", await get_default_model())}`"
    )
    message = await translate(message)
    about = await get_model_info(context)
    if about:
        message += "\n\n" + about
    await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log the error and send a telegram message to notify the developer."""
    logger.error("Exception while handling an update:", exc_info=context.error)
    tb_list = traceback.format_exception(
        None, context.error, context.error.__traceback__
    )
    tb_string = "".join(tb_list)
    update_str = update.to_dict() if isinstance(update, Update) else str(update)
    message = f"```update_str\n{update_str}```\n\n```e./rror\n{tb_string}\n```\n"

    await send_response(message, update, context)

    # await update.message.reply_text(text=message, parse_mode=ParseMode.HTML)
