from __future__ import annotations

import hashlib
import os
import sys
from functools import partial
from pathlib import Path


def calc_hash(data: str) -> str:
    return hashlib.sha256(data.encode()).hexdigest()


def expand_env_placeholders(value: str) -> str:
    return os.path.expandvars(value)


def load_prompt(value: str | None) -> str | None:
    """Разрешает значение промпта: строка или ссылка на файл.

    - ``@path`` — всегда читать файл (ошибка, если файла нет);
    - ``path`` к существующему файлу — прочитать его содержимое;
    - ``path`` к существующему, но не файлу (например, директория) — ошибка;
    - в остальных случаях вернуть строку как есть (инлайн-промпт).

    Позволяет писать ``--prompt prompts/reply_employer.txt`` вместо того,
    чтобы вставлять весь текст промпта в командную строку.

    Raises:
        FileNotFoundError: если файл с промптом не найден
        ValueError: если путь указывает на директорию вместо файла
    """
    if not value:
        return value
    if value.startswith("@"):
        file_path = Path(value[1:]).expanduser()
        if not file_path.exists():
            raise FileNotFoundError(f"Prompt file not found: {file_path}")
        if not file_path.is_file():
            raise ValueError(f"Prompt path is not a file: {file_path}")
        return expand_env_placeholders(
            file_path.read_text(encoding="utf-8").strip()
        )
    candidate = Path(value).expanduser()
    if candidate.is_file():
        return expand_env_placeholders(
            candidate.read_text(encoding="utf-8").strip()
        )
    if candidate.exists():
        raise ValueError(f"Prompt path is not a file: {value}")
    return expand_env_placeholders(value)


print_err = partial(print, file=sys.stderr, flush=True)
