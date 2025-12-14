import html
import re
import json
import logging
import traceback
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ChatAction, ParseMode
from groq_chat.groq_chat import generate_response
from groq_chat.groq_chat import get_groq_models, get_default_model
from translate.translate import translate

logger = logging.getLogger(__name__)
SYSTEM_PROMPT_SP = 1
CANCEL_SP = 2

# Захватываем блоки кода, жирный, подчеркивание, зачеркивание, спойлер, курсив и инлайн-код
MARKDOWN_PATTERN = re.compile(r"(```[a-zA-Z]*|\*\*|__|~~|\|\||[_*`])")


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if "messages" not in context.user_data:
        context.user_data["messages"] = []

    message = update.message.text
    if not message:
        return

    await update.message.chat.send_action(ChatAction.TYPING)

    full_output_message = ""
    buffer = ""
    markdown_stack = (
        []
    )  # Здесь храним полные открывающие теги, например ['```python', '**']

    async for chunk in generate_response(message, context):
        if chunk:
            full_output_message += chunk
            buffer += chunk

            # Лимит Telegram 4096, но с учетом запаса на теги берем 3500
            while len(buffer) > 3500:

                # 1. Сначала пытаемся найти последний перенос строки
                split_index = buffer.rfind("\n")

                # 2. Если переноса строки нет, ищем последний пробел
                if split_index == -1:
                    split_index = buffer.rfind(" ")

                # 3. Если нет ни переноса, ни пробела, режем по лимиту
                if split_index == -1:
                    split_index = len(buffer)

                chunk_to_send = buffer[:split_index]
                buffer = buffer[split_index:].lstrip()

                await send_chunk(update, chunk_to_send, markdown_stack)

    if buffer:
        await send_chunk(update, buffer, markdown_stack)

    context.user_data["messages"].append(
        {"role": "assistant", "content": full_output_message}
    )


def sanitaze_stack(stack: list) -> None:
    prefix_parts = []
    for tag in stack:
        if tag.startswith("```"):
            prefix_parts.append(f"\n{tag}\n")
        else:
            prefix_parts.append(tag)
    return prefix_parts


async def send_chunk(update: Update, text: str, stack: list) -> None:
    # 1. Формируем префикс из открытых ранее тегов
    prefix = "".join(sanitaze_stack(stack))

    # 2. Анализируем текст по частям
    # Мы разбиваем текст на токены и обычный текст между ними
    last_pos = 0
    for match in MARKDOWN_PATTERN.finditer(text):
        token = match.group(0)

        # Проверяем, находимся ли мы СЕЙЧАС внутри блока кода
        is_in_block_code = stack and stack[-1].startswith("```")

        if is_in_block_code:
            # Если мы внутри блока кода, нас интересует ТОЛЬКО закрывающий тег кода
            if token.startswith("```"):
                stack.pop()
            else:
                # Все остальные токены (** , __ и т.д.) игнорируем, пока не выйдем из кода
                continue
        else:
            # Если мы снаружи, обрабатываем все теги
            if stack and (
                (token.startswith("```") and stack[-1].startswith("```"))
                or (token == stack[-1])
            ):
                stack.pop()
            else:
                stack.append(token)

    # 3. Формируем постфикс (LIFO)
    closing_tags = []
    for tag in reversed(stack):
        if tag.startswith("```"):
            closing_tags.append("```")  # Всегда закрываем просто тремя кавычками
        else:
            closing_tags.append(tag)

    postfix = "".join(sanitaze_stack(closing_tags))

    # 4. Сборка и отправка
    final_text = f"{prefix}{text}{postfix}"

    try:
        await update.message.reply_text(
            final_text, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True
        )
    except Exception as e:
        logger.warning(f"MarkdownV2 parse error: {e}, sending without parse mode.")
        await update.message.reply_text(final_text, parse_mode=None)


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
    message = await translate("select_model")
    await update.message.reply_text(message, reply_markup=reply_markup)


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


async def info_command_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Get info about the bot"""
    message = (
        f"**__Conversation Info:__**\n"
        f"**Model**: `{context.user_data.get("model", await get_default_model())}`"
    )
    message = await translate(message)
    # if context.user_data.get("system_prompt") is not None:
    #     message += f"\n**System Prompt**: \n```\n{context.user_data.get("system_prompt")}\n```"
    await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log the error and send a telegram message to notify the developer."""
    # Log the error before we do anything else, so we can see it even if something breaks.
    logger.error("Exception while handling an update:", exc_info=context.error)

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
