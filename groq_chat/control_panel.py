import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ChatAction
from translate.translate import translate
import db.async_database as db
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.orm.state import AttributeState
from groq_chat.model_changer import model_command_handler, show_model_info
from groq_chat.handlers import (
    new_command_handler,
    show_system_prompt,
    clear_system_prompt,
)

logger = logging.getLogger(__name__)


async def control_panel_builder(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    await update.message.chat.send_action(ChatAction.TYPING)
    button_list = [
        [
            create_key("select_model", await translate("Select a model", context)),
            create_key("model_info", await translate("Model Information", context)),
        ],
        [
            create_key(
                "reset_context",
                await translate("Reset context (delete message history)", context),
            ),
        ],
        [create_key("show_prompt", await translate("Show sytem prompt", context))],
        [
            InlineKeyboardButton(
                text=await translate("Set system prompt", context),
                callback_data="set_system_prompt",
            ),
            create_key("clear_prompt", await translate("Clear system prompt", context)),
        ],
        [
            create_key(
                "code_in_file", await translate("Export text blocks to files", context)
            )
        ],
        [
            create_key(
                "code_in_message",
                await translate("Output text blocks to messages", context),
            )
        ],
        [
            InlineKeyboardButton(
                text=f"Change language / {await translate("Change language", context)}",
                callback_data="change_lang",
            ),
        ],
    ]

    reply_markup = InlineKeyboardMarkup(button_list)
    message = await panel_banner(update, context)
    await update.message.reply_text(message, reply_markup=reply_markup)


async def control_panel_executor(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    query = update.callback_query
    await query.answer()
    command = query.data.replace("ctrl_panel_", "")

    need_execute, detail_command = command_matches_pattern(command, "code_in_")
    if need_execute:
        await change_file_interpreter(update, context, detail_command)

    need_execute, detail_command = command_matches_pattern(command, "select_model")
    if need_execute:
        await model_command_handler(update, context)

    need_execute, detail_command = command_matches_pattern(command, "model_info")
    if need_execute:
        await show_model_info(update, context)

    need_execute, detail_command = command_matches_pattern(command, "reset_context")
    if need_execute:
        await new_command_handler(update, context)

    need_execute, detail_command = command_matches_pattern(command, "show_prompt")
    if need_execute:
        await show_system_prompt(update, context)

    need_execute, detail_command = command_matches_pattern(command, "clear_prompt")
    if need_execute:
        await clear_system_prompt(update, context)


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
    message = await translate("Control panel", context)
    db_user = await db.get_record_by_id(db.Users, context._user_id)
    if db_user:
        message += "\n\n" + await translate("User settings:", context)
        message += await user_settings_baner(db_user)
    return message


def command_matches_pattern(command, pattern):
    if command.startswith(pattern):
        return True, command.replace(pattern, "")
    else:
        return False, None


async def change_file_interpreter(update, context, command):
    setting_id = "file_interpreter"
    db_record = await db.set_user_setting(
        context._user_id, setting_id, command.startswith("file")
    )
    if db_record:
        getattr(db_record, setting_id, None)
        message = message = await panel_banner(update, context)
    else:
        message = await translate(
            "An error occurred while setting a new value", context
        )

    logger.info(message)
    query = update.callback_query
    await query.edit_message_text(text=message, reply_markup=query.message.reply_markup)
