import json
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from groq_chat.groq_chat import get_groq_models, generate_response, get_default_model
from translate.translate import translate
import groq_chat.command_descriptions as com_descr
from groq_chat.context import new_chat
from telegram.constants import ChatAction

logger = logging.getLogger(__name__)


def create_model_key(model_name: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(model_name, callback_data="change_model_" + model_name)


async def model_command_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:

    query = update.callback_query
    chat_id = query.message.chat.id
    await context.bot.send_chat_action(chat_id, ChatAction.TYPING)

    models = await get_groq_models()
    button_list = [
        [create_model_key(models[i]), create_model_key(models[i + 1])]
        for i in range(0, len(models) - len(models) % 2, 2)
    ]
    if len(models) % 2 == 1:
        button_list.append([create_model_key(models[-1])])
    reply_markup = InlineKeyboardMarkup(button_list)
    message = await translate("select_model")

    try:
        await query.message.delete()
    except Exception as exc:  # сообщение могло уже быть удалено
        logger.warning("Не удалось удалить сообщение: %s", exc)

    await context.bot.send_message(
        chat_id=chat_id, text=message, reply_markup=reply_markup
    )


async def change_model_callback_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    query = update.callback_query
    chat_id = query.message.chat.id
    await context.bot.send_chat_action(chat_id, ChatAction.TYPING)

    model = query.data.replace("change_model_", "")

    if update.message:
        await update.message.chat.send_action(ChatAction.TYPING)

    context.user_data["model"] = model
    message = await translate(f"Model changed to `{model}`")
    about = await get_model_info(update, context)

    if about:
        message += "\n\n" + about

    new_chat(context)

    await query.edit_message_text(
        message,
        reply_markup=query.message.reply_markup,
        parse_mode=ParseMode.MARKDOWN,
    )


async def get_model_info(update, context):
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


async def show_model_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    chat_id = query.message.chat.id
    await context.bot.send_chat_action(chat_id, ChatAction.TYPING)

    """Get info about the bot"""
    message = (
        f"**__Model Info:__**\n"
        f"**Model**: `{context.user_data.get("model", await get_default_model())}`"
    )
    message = await translate(message)
    about = await get_model_info(update, context)
    if about:
        message += "\n\n" + about
    # await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)

    await context.bot.send_message(chat_id=chat_id, text=message, parse_mode="Markdown")
