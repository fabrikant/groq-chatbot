import html
import json
import logging
import traceback
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ChatAction, ParseMode
from groq_chat.html_format import format_message
from groq_chat.groq_chat import generate_response
from groq_chat.groq_chat import get_groq_models, get_default_model
from translate.translate import translate

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
            f"Hi {user.mention_html()}!\n\n"
            "Start sending messages with me to generate a response.\n\n"
            "Send /new to start a new chat session."
        )
    )
    await update.message.reply_html(message)


async def help_command(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    help_text = await translate(
        (
            "Basic commands:\n"
            "/start - Start the bot\n"
            "/help - Get help. Shows this message\n\n"
            "Chat commands:\n"
            "/new - Start a new chat session (model will forget previously generated messages)\n"
            "/model - Change the model used to generate responses.\n"
            "/system_prompt - Change the system prompt used for new chat sessions.\n"
            "/info - Get info about the current chat session.\n\n"
            "Send a message to the bot to generate a response."
        )
    )
    await update.message.reply_text(help_text)


async def new_command_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Start a new chat session"""
    new_chat(context)
    message = await translate("New chat session started.\n\nSwitch models with /model.")
    await update.message.reply_text(message)


def create_model_key(model_name: str) -> InlineKeyboardMarkup:
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
    await update.message.reply_text("select_model", reply_markup=reply_markup)


async def change_model_callback_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Change the model used to generate responses"""
    query = update.callback_query
    model = query.data.replace("change_model_", "")

    context.user_data["model"] = model
    message = await translate(
        f"Model changed to `{model}`. \n\nSend /new to start a new chat session."
    )

    await query.edit_message_text(
        message,
        parse_mode=ParseMode.MARKDOWN,
    )


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


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle messages"""
    if "model" not in context.user_data:
        context.user_data["model"] = await get_default_model()

    if "messages" not in context.user_data:
        context.user_data["messages"] = []

    message = update.message.text
    if not message:
        return

    await update.message.chat.send_action(ChatAction.TYPING)
    full_output_message = ""
    buffer = ""
    async for chunk in generate_response(message, context):
        if chunk:
            full_output_message += chunk
            buffer += chunk
            if len(buffer) > 3000:  # Send message when buffer exceeds 3000 chars
                formatted_buffer = format_message(buffer)
                await update.message.reply_text(
                    formatted_buffer,
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True,
                )
                buffer = ""  # Reset buffer
    # Send remaining buffer if any
    if buffer:
        formatted_buffer = format_message(buffer)
        await update.message.reply_text(
            formatted_buffer,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )
    # Add full response to context
    context.user_data["messages"] = context.user_data.get("messages", []) + [
        {
            "role": "assistant",
            "content": full_output_message,
        }
    ]


async def info_command_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Get info about the bot"""
    message = f"""**__Conversation Info:__**
**Model**: `{context.user_data.get("model", await get_default_model())}`
"""

    # if context.user_data.get("system_prompt") is not None:
    #     message += f"\n**System Prompt**: \n```\n{context.user_data.get("system_prompt")}\n```"
    await update.message.reply_text(format_message(message), parse_mode=ParseMode.HTML)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log the error and send a telegram message to notify the developer."""
    # Log the error before we do anything else, so we can see it even if something breaks.
    logging.getLogger(__name__).error(
        "Exception while handling an update:", exc_info=context.error
    )

    # traceback.format_exception returns the usual python message about an exception, but as a
    # list of strings rather than a single string, so we have to join them together.
    tb_list = traceback.format_exception(
        None, context.error, context.error.__traceback__
    )
    tb_string = "".join(tb_list)

    # Build the message with some markup and additional information about what happened.
    # You might need to add some logic to deal with messages longer than the 4096 character limit.
    update_str = update.to_dict() if isinstance(update, Update) else str(update)
    message = (
        "An exception was raised while handling an update\n"
        f"<pre>update = {html.escape(json.dumps(update_str, indent=2, ensure_ascii=False))}"
        "</pre>\n\n"
        f"<pre>{html.escape(tb_string)}</pre>"
    )

    # Finally, send the message
    await update.message.reply_text(text=message, parse_mode=ParseMode.HTML)
