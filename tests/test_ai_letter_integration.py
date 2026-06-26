#!/usr/bin/env python3
"""
Тест: проверяем, что отправляется в LLM для генерации сопроводительного письма
"""
import sys
sys.path.insert(0, '/Users/m.s.agafonov/Desktop/work-optimization/src')

from hh_applicant_tool.main import HHApplicantTool
from hh_applicant_tool.utils.misc import load_prompt

# Создаем инструмент
tool = HHApplicantTool()

# Загружаем системный промпт из файла
system_prompt = load_prompt("prompts/cover_letter_frontend.txt")
print("=" * 60)
print("СИСТЕМНЫЙ ПРОМПТ:")
print("=" * 60)
print(system_prompt)
print()

# Инициализируем AI для cover letters
cover_letter_ai = tool.get_cover_letter_ai(system_prompt)

# Тестовые данные (как в реальной вакансии)
message_prompt = load_prompt("Сгенерируй сопроводительное письмо не более 5-7 предложений от моего имени для вакансии")

vacancy_name = "Frontend-разработчик (React/TypeScript)"
resume_title = "Frontend-разработчик (ReactJS, TypeScript, Redux)"

# Формируем промпт точно так же, как в _build_cover_letter
msg = message_prompt + "\n\n"
msg += "Название вакансии: " + vacancy_name
msg += "Мое резюме: " + resume_title

print("=" * 60)
print("ЗАПРОС К LLM (то, что отправляется):")
print("=" * 60)
print(msg)
print()

# Проверяем, запущена ли Ollama
import requests
try:
    response = requests.get("http://localhost:11434/api/tags", timeout=5)
    models = response.json().get("models", [])
    print("=" * 60)
    print("МОДЕЛИ OLLAMA:")
    print("=" * 60)
    for m in models:
        print(f"  - {m['name']}")
    print()
except requests.exceptions.ConnectionError:
    print("⚠️  OLLAMA НЕ ЗАПУЩЕНА!")
    print("   Запусти: ollama serve")
    print()
    sys.exit(1)

# Генерируем ответ
print("=" * 60)
print("ОТВЕТ ОТ LLM (сопроводительное письмо):")
print("=" * 60)
try:
    ai_answer = cover_letter_ai.complete(msg).strip()
    print(ai_answer)
    print()
    print("✅ AI работает корректно!")
except Exception as e:
    print(f"❌ Ошибка AI: {e}")
    print()
    print("Возможные причины:")
    print("  1. Модель не загружена (запусти: ollama pull qwen2.5:3b)")
    print("  2. Неправильное имя модели в конфиге")
    print("  3. Ollama не отвечает")
