from __future__ import annotations

import hashlib
import sys
from functools import partial
from pathlib import Path


def calc_hash(data: str) -> str:
    return hashlib.sha256(data.encode()).hexdigest()


def load_prompt(value: str | None) -> str | None:
    """Разрешает значение промпта: строка или ссылка на файл.

    - ``@path`` — всегда читать файл (ошибка, если файла нет);
    - ``path`` к существующему файлу — прочитать его содержимое;
    - в остальных случаях вернуть строку как есть (инлайн-промпт).

    Позволяет писать ``--prompt prompts/reply_employer.txt`` вместо того,
    чтобы вставлять весь текст промпта в командную строку.
    """
    if not value:
        return value
    if value.startswith("@"):
        return Path(value[1:]).expanduser().read_text(encoding="utf-8").strip()
    candidate = Path(value).expanduser()
    if candidate.is_file():
        return candidate.read_text(encoding="utf-8").strip()
    return value


print_err = partial(print, file=sys.stderr, flush=True)
