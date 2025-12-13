import re
from html import escape

def wrap_tables_in_pre(text):
    """
    Детектирует блоки ASCII-таблиц и оборачивает их в <pre>.
    Предполагается, что экранирование < и > выполняется внешним кодом.
    """
    
    # Регулярное выражение:
    # Ищет последовательность строк (минимум 2), которые начинаются и заканчиваются 
    # на символы разметки (+, -, |) или содержат их в характерных сочетаниях.
    table_pattern = re.compile(
        r'((?:^[ \t]*[|+\-].*[|+\-][ \t]*$\n?){2,})', 
        re.MULTILINE
    )

    def replacement(match):
        # Получаем найденную таблицу
        table_content = match.group(1).rstrip('\n')
        
        # Оборачиваем в теги <pre>. 
        # Добавляем переносы строк для визуального отделения в коде.
        return f"<pre>\n{table_content}\n</pre>"

    # Проводим замену
    result = table_pattern.sub(replacement, text)
    
    return result

def apply_hand_points(text: str) -> str:
    """Replaces markdown bullet points (*) with right hand point emoji.

    Arguments:
    text (str): The text to modify.

    Returns:
    str: The text with markdown bullet points replaced with emoji.
    """
    pattern = r"(?<=\n)\*\s(?!\*)|^\*\s(?!\*)"

    replaced_text = re.sub(pattern, "👉 ", text)

    return replaced_text


def apply_bold(text: str) -> str:
    """Replaces markdown bold formatting with HTML bold tags.

    Arguments:
    text (str): The text to modify.

    Returns:
    str: The text with markdown bold replaced by HTML tags.
    """
    pattern = r"\*\*(.*?)\*\*"
    replaced_text = re.sub(pattern, r"<b>\1</b>", text)
    return replaced_text


def apply_italic(text: str) -> str:
    """Replaces markdown italic formatting with HTML italic tags.

    Arguments:
    text (str): The text to modify.

    Returns:
    str: The text with markdown italic replaced by HTML tags.
    """
    pattern = r"(?<!\*)\*(?!\*)(?!\*\*)(.*?)(?<!\*)\*(?!\*)"
    replaced_text = re.sub(pattern, r"<i>\1</i>", text)
    return replaced_text


def apply_code(text: str) -> str:
    """Replace markdown code blocks with HTML <pre> tags.

    Arguments:
    text (str): The text to modify.

    Returns:
    str: The text with markdown code blocks replaced by HTML tags.
    """
    pattern = r"```([\w]*?)\n([\s\S]*?)```"
    replaced_text = re.sub(pattern, r"<pre lang='\1'>\2</pre>", text, flags=re.DOTALL)
    return replaced_text


def apply_monospace(text: str) -> str:
    """Replaces markdown monospace backticks with HTML <code> tags.

    Arguments:
    text (str): The input text containing markdown monospace formatting.

    Returns:
    str: The text with monospace sections replaced with HTML tags.
    """
    pattern = r"(?<!`)`(?!`)(.*?)(?<!`)`(?!`)"
    replaced_text = re.sub(pattern, r"<code>\1</code>", text)
    return replaced_text


def apply_link(text: str) -> str:
    """Replace markdown links with HTML anchor tags.

    Arguments:
    text (str): The input text containing markdown links.

    Returns:
    str: The text with markdown links replaced by HTML anchor tags.
    """
    pattern = r"\[(.*?)\]\((.*?)\)"
    replaced_text = re.sub(pattern, r'<a href="\2">\1</a>', text)
    return replaced_text


def apply_underline(text: str) -> str:
    """Replace markdown underline with HTML underline tags.

    Arguments:
    text (str): The input text to modify.

    Returns:
    str: The text with markdown underlines replaced with HTML tags."""
    pattern = r"__(.*?)__"
    replaced_text = re.sub(pattern, r"<u>\1</u>", text)
    return replaced_text


def apply_strikethrough(text: str) -> str:
    """Replace markdown strikethrough with HTML strikethrough tags.

    Arguments:
    text (str): The input text to modify.

    Returns:
    str: The text with markdown strikethroughs replaced with HTML tags.
    """
    pattern = r"~~(.*?)~~"
    replaced_text = re.sub(pattern, r"<s>\1</s>", text)
    return replaced_text


def apply_header(text: str) -> str:
    """Replace markdown header # with HTML header tags.

    Arguments:
    text (str): The input text to modify.

    Returns:
    str: The text with markdown headers replaced with HTML tags.
    """
    pattern = r"^(#{1,6})\s+(.*)"
    replaced_text = re.sub(pattern, r"<b><u>\2</u></b>", text, flags=re.DOTALL)
    return replaced_text


def apply_exclude_code(text: str) -> str:
    """Apply text formatting to non-code lines.

    Iterates through each line, checking if it is in a code block.
    If not, applies header, link, bold, italic, underline, strikethrough, monospace, and hand-point
    text formatting.
    """
    lines = text.split("\n")
    in_code_block = False

    for i, line in enumerate(lines):
        if line.startswith("```"):
            in_code_block = not in_code_block

        if not in_code_block:
            formatted_line = lines[i]
            formatted_line = apply_header(formatted_line)
            formatted_line = apply_link(formatted_line)
            formatted_line = apply_bold(formatted_line)
            formatted_line = apply_italic(formatted_line)
            formatted_line = apply_underline(formatted_line)
            formatted_line = apply_strikethrough(formatted_line)
            formatted_line = apply_monospace(formatted_line)
            formatted_line = apply_hand_points(formatted_line)
            lines[i] = formatted_line

    return "\n".join(lines)


def format_message(text: str) -> str:
    """Format the given message text from markdown to HTML.

    Escapes HTML characters, applies link, code, and other rich text formatting,
    and returns the formatted HTML string.

    Args:
      message (str): The plain text message to format.

    Returns:
      str: The formatted HTML string.
    """
    formatted_text = escape(text)
    # formatted_text = wrap_tables_in_pre(text)
    formatted_text = apply_exclude_code(formatted_text)
    formatted_text = apply_code(formatted_text)
    return formatted_text
