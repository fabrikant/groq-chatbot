import html
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
import db.async_database as db
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.orm.state import AttributeState

logger = logging.getLogger(__name__)


def create_key(id: str, descriptipn: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=descriptipn, callback_data="ctrl_panel_" + id)


async def user_settings_baner(db_record):
    result = ""
    mapper = sa_inspect(db_record)
    for attr in mapper.attrs:
        if isinstance(attr, AttributeState) and attr.key != "id":
            result += f"\n{attr.key} = {getattr(db_record, attr.key)}"
    return result


async def panel_banner(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = await translate("Control panel")
    db_user = await db.get_record_by_id(db.Users, context._user_id)
    if db_user:
        message += "\n\n" + await translate("User settings:")
        message += await user_settings_baner(db_user)
    return message


async def control_panel_builder(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    pass
    button_list = [
        [
            create_key("code_in_file", await translate("Code in file")),
            create_key("code_in_message", await translate("Code in message")),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(button_list)
    message = await panel_banner(update, context)
    await update.message.reply_text(message, reply_markup=reply_markup)


async def control_panel_executor(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    pass
    query = update.callback_query
    command = query.data.replace("ctrl_panel_", "")

    if command.startswith("code_in_"):
        command = command.replace("code_in_", "")
        setting_id = "file_interpreter"
        db_record = await db.set_user_setting(
            context._user_id, setting_id, command.startswith("file")
        )
        if db_record:
            getattr(db_record, setting_id, None)
            message = message = await panel_banner(update, context)
        else:
            message = await translate("An error occurred while setting a new value")

        logger.info(message)
        query = update.callback_query

        try:
            await query.edit_message_text(
                text=message, reply_markup=query.message.reply_markup
            )
        except Exception as e:
            logger.error(e)
