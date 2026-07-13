#!/usr/bin/env python3
"""
Проверка AI конфигурации для hh-applicant-tool
"""
import json
import os
import sys
from pathlib import Path

from hh_applicant_tool.constants import CONFIG_DIR
from hh_applicant_tool.utils.config import resolve_profile_config_dir


def possible_config_paths() -> list[Path]:
    profile_id = os.environ.get("HH_PROFILE_ID", "").strip()
    base_dir = Path(os.environ.get("CONFIG_DIR", str(CONFIG_DIR)))
    return [
        resolve_profile_config_dir(base_dir, profile_id) / "config.json"
    ]


def check_ai_config():
    # Ищем config.json
    possible_paths = possible_config_paths()
    
    config_path = None
    for path in possible_paths:
        if path.exists():
            config_path = path
            break
    
    if not config_path:
        print("❌ config.json не найден!")
        print("Пути для проверки:")
        for p in possible_paths:
            print(f"  - {p}")
        return False
    
    print(f"✅ config.json найден: {config_path}")
    
    try:
        with config_path.open(encoding="utf-8") as f:
            config = json.load(f)
    except json.JSONDecodeError as e:
        print(f"❌ Ошибка JSON: {e}")
        return False
    
    # Проверяем openai_cover_letter
    cover_letter = config.get("openai_cover_letter", {})
    
    if not cover_letter:
        print("❌ Секция 'openai_cover_letter' не найдена!")
        print("\nДобавь в config.json:")
        print(json.dumps({
            "openai_cover_letter": {
                "api_key": "sk-proj-xxx",
                "base_url": "https://api.openai.com/v1/chat/completions",
                "model": "gpt-4o-mini"
            }
        }, indent=2))
        return False
    
    print("✅ Секция 'openai_cover_letter' найдена")
    
    # Проверяем api_key
    api_key = cover_letter.get("api_key")
    if not api_key:
        print("❌ api_key не задан!")
        return False
    if api_key == "sk-proj-xxx" or api_key.endswith("xxx"):
        print("⚠️  api_key выглядит как шаблон! Замени на реальный ключ.")
        return False
    print("✅ api_key задан")
    
    # Проверяем base_url
    base_url = cover_letter.get("base_url")
    if not base_url:
        print("❌ base_url не задан!")
        return False
    print(f"✅ base_url задан: {base_url}")
    
    # Проверяем model
    model = cover_letter.get("model")
    if not model:
        print("⚠️  model не задан (будет использован gpt-4o-mini по умолчанию)")
    else:
        print(f"✅ model задан: {model}")
    
    # Проверяем openai_reply
    reply = config.get("openai_reply", {})
    if reply:
        print("✅ Секция 'openai_reply' найдена")
    else:
        print("⚠️  Секция 'openai_reply' не найдена (будет использована openai_cover_letter)")
    
    print("\n" + "="*50)
    print("✅ AI конфигурация в порядке!")
    print("="*50)
    print("\nТеперь запусти:")
    print("  hh-applicant-tool apply-vacancies --search \"Frontend\" --ai --dry-run")
    return True

if __name__ == "__main__":
    success = check_ai_config()
    sys.exit(0 if success else 1)
