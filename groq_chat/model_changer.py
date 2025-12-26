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
from db.async_database import set_user_setting

logger = logging.getLogger(__name__)


def create_model_key(model_name: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(model_name, callback_data="change_model_" + model_name)


async def model_command_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:

    if update.callback_query:
        query = update.callback_query
        chat_id = query.message.chat.id
        query.answer()
    else:
        chat_id = update.effective_chat.id

    await context.bot.send_chat_action(chat_id, ChatAction.TYPING)

    models = await get_groq_models()
    button_list = [
        [create_model_key(models[i]), create_model_key(models[i + 1])]
        for i in range(0, len(models) - len(models) % 2, 2)
    ]
    if len(models) % 2 == 1:
        button_list.append([create_model_key(models[-1])])
    reply_markup = InlineKeyboardMarkup(button_list)
    message = await translate("Select model", context)

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
    if update.callback_query:
        query = update.callback_query
        chat_id = query.message.chat.id
        await query.answer()
    else:
        chat_id = update.effective_chat.id

    await context.bot.send_chat_action(chat_id, ChatAction.TYPING)
    if update.message:
        await update.message.chat.send_action(ChatAction.TYPING)

    model = query.data.replace("change_model_", "")
    context.user_data["model"] = model
    await show_model_info(update, context)


async def get_model_info(update, context):
    who_are_you = await translate("Tell me about yourself in two sentences", context)
    about = await generate_response(who_are_you, context)

    if about.lower().startswith("error"):
        try:
            error_json = json.loads(
                about[about.find("{") : about.rfind("}") + 1].replace("'", '"')
            )
            about = error_json.get("error", about).get("message", about)
            about = await translate(about, context) + "\n\n"
            about += await translate(
                "Send /model to change the model used to generate responses", context
            )
        except:
            pass

    return about


def create_key(id: str, descriptipn: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=descriptipn, callback_data="set_default_" + id)


async def show_model_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.callback_query:
        query = update.callback_query
        chat_id = query.message.chat.id
        await query.answer()
    else:
        chat_id = update.effective_chat.id

    await context.bot.send_chat_action(chat_id, ChatAction.TYPING)
    model = context.user_data.get("model", await get_default_model())
    message = (
        f"**__{(await translate("Model info", context))}:__**\n"
        f"**{(await translate("Model", context))}**: `{model}`"
    )

    about = await get_model_info(update, context)
    if about:
        message += "\n\n" + about

    button_list = [
        [
            create_key(
                f"ocr_{model}",
                await translate("Set default for OCR", context),
            ),
        ],
        [
            create_key(
                f"tts_{model}",
                await translate("Set default for TTS", context),
            ),
        ],
        [
            create_key(
                f"stt_{model}",
                await translate("Set default for STT", context),
            ),
        ],
    ]

    markup = InlineKeyboardMarkup(button_list)
    await context.bot.send_message(
        chat_id=chat_id,
        text=message,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=markup,
    )


async def set_model_default_executor(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    query = update.callback_query
    await query.answer()
    command = query.data.replace("set_default_", "")
    parts = command.split("_", 1)
    setting_type = parts[0]
    model_name = parts[1]
    user_id = context._user_id
    setting_id = f"{setting_type}_model"
    await set_user_setting(user_id, setting_id, model_name)
    await query.edit_message_text(
        await translate("Default model set successfully", context)
    )
