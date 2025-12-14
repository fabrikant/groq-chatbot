import re
from typing import List

# Регулярные выражения
BORDER_RE = re.compile(r'^\+[-=+]*\+\s*$')
ROW_RE    = re.compile(r'^\|.*\|\s*$')
CODE_BLOCK_RE = re.compile(r'^```') # Начало или конец блока кода

def is_border(line: str) -> bool:
    return bool(BORDER_RE.match(line))

def is_row(line: str) -> bool:
    return bool(ROW_RE.match(line))

def is_code_boundary(line: str) -> bool:
    return bool(CODE_BLOCK_RE.match(line.strip()))

def wrap_ascii_tables(text: str) -> str:
    lines = text.splitlines(keepends=True)
    out: List[str] = []
    table_buf: List[str] = []
    
    inside_table = False
    inside_code_block = False  # Флаг: находимся ли мы уже внутри ```

    for line in lines:
        stripped = line.rstrip('\r\n')
        
        # 1. Проверяем, не входим ли мы или не выходим ли из блока кода
        if is_code_boundary(stripped):
            # Если мы собирали таблицу и вдруг встретили ``` (странный случай, но возможный)
            if inside_table:
                out.extend(table_buf)
                table_buf = []
                inside_table = False
            
            inside_code_block = not inside_code_block
            out.append(line)
            continue

        # 2. Если мы внутри существующего блока кода, ничего не форматируем
        if inside_code_block:
            out.append(line)
            continue

        # 3. Логика поиска таблицы (только если мы НЕ в блоке кода)
        if not inside_table:
            if is_border(stripped):
                inside_table = True
                table_buf = [line]
            else:
                out.append(line)
        else:
            if is_border(stripped) or is_row(stripped):
                table_buf.append(line)
            else:
                # Проверяем, что в буфере не просто куча границ, а есть хоть одна строка с данными |
                if any(is_row(l.rstrip()) for l in table_buf):
                    out.append('```\n')
                    out.extend(table_buf)
                    out.append('```\n')
                else:
                    out.extend(table_buf)
                
                out.append(line)
                inside_table = False
                table_buf = []

    # Обработка хвоста
    if inside_table:
        if any(is_row(l.rstrip()) for l in table_buf):
            out.append('```\n')
            out.extend(table_buf)
            out.append('```\n')
        else:
            out.extend(table_buf)

    return ''.join(out)

