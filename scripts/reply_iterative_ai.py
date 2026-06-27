#!/usr/bin/env python3
"""
Итеративные AI-ответы работодателям — 5-6 подходов по 50 чатов.
Каждый ответ генерируется через Ollama с учётом истории переписки.
"""
import subprocess
import json
import sys
import time
import requests
from pathlib import Path

TELEGRAM = "@wavemax6"
MAX_ITERATIONS = 6  # Полных итераций
CHATS_PER_ITERATION = 50  # Чатов за итерацию
OLLAMA_URL = "http://localhost:11434/v1/chat/completions"
OLLAMA_MODEL = "qwen2.5:14b"  # Лучшее качество русского языка
DRY_RUN = "--dry-run" in sys.argv
PAUSE_BETWEEN_REQUESTS = 2.0  # Секунды между отправками (rate limiting)
PAUSE_BETWEEN_ITERATIONS = 120  # Секунды между итерациями (2 минуты)
MAX_RETRIES = 3  # Максимум попыток отправки в одном чате

SYSTEM_PROMPT = """Ты — Максим Агофонов, Frontend-разработчик (React/TypeScript/Redux, 5+ лет).
Отвечаешь работодателям в чате HH.ru.

ПРАВИЛА:
1. Пиши ТОЛЬКО на русском языке, без английских вставок
2. 2-4 предложения, кратко и по делу
3. Всегда упоминай Telegram: @wavemax6 для связи
4. Анализируй историю переписки ПЕРЕД ответом:
   - Если работодатель задал вопрос → ответь на КОНКРЕТНЫЙ вопрос
   - Если первое сообщение после отклика → поблагодари + предложи созвон
   - Если тишина 2+ дня → мягкий follow-up
   - Если отказ → вежливо поблагодари
5. НЕ пиши шаблонные фразы вроде "Успехов в поисках" без контекста
6. Обращайся к работодателю на "Вы"
"""


def run_cmd(cmd):
    """Выполняет CLI-команду и возвращает JSON-результат."""
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    try:
        return json.loads(result.stdout) if result.stdout else None
    except json.JSONDecodeError:
        return None


def get_negotiations(page=0, per_page=CHATS_PER_ITERATION):
    """Получает список активных переговоров."""
    data = run_cmd(f'hh-applicant-tool call-api "/negotiations?status=active&per_page={per_page}&page={page}" 2>/dev/null')
    return data.get('items', []) if data else []


def get_messages(neg_id):
    """Получает историю сообщений чата."""
    data = run_cmd(f'hh-applicant-tool call-api "/negotiations/{neg_id}/messages?per_page=20" 2>/dev/null')
    return data.get('items', []) if data else []


def get_vacancy_details_fast(neg):
    """Быстро получает данные о вакансии из объекта переговоров (без API запроса)."""
    vacancy = neg.get('vacancy', {})
    return {
        'name': vacancy.get('name', 'Неизвестно'),
        'employer': vacancy.get('employer', {}).get('name', 'Неизвестно')
    }


def should_reply(messages):
    """
    Проверяет, нужно ли отвечать:
    - Если последнее сообщение от работодателя — нужно отвечать
    - Если последнее от меня — уже ответил, пропускаем
    """
    if not messages:
        return False, None

    # Сортируем по времени (новые сверху)
    sorted_msgs = sorted(messages, key=lambda m: m.get('created_at', ''), reverse=True)
    last_msg = sorted_msgs[0]
    last_author = last_msg.get('participant_type', '')

    # Если последнее сообщение от меня — уже ответил
    if last_author == 'applicant':
        return False, None

    # Последнее от работодателя — нужно отвечать
    # Берём контекст: последние 5-10 сообщений
    context = []
    for m in sorted_msgs[:10]:
        author = "Я" if m.get('participant_type') == 'applicant' else "Работодатель"
        text = m.get('text', '')
        context.append(f"{author}: {text}")

    return True, context


def generate_reply_ai(context, vacancy_name, employer_name):
    """
    Генерирует персонализированный ответ через Ollama AI.
    """
    prompt = f"""Вакансия: {vacancy_name}
Компания: {employer_name}

ИСТОРИЯ ПЕРЕПИСКИ:
{chr(10).join(context)}

Напиши короткий персонализированный ответ работодателю на русском языке."""

    try:
        response = requests.post(OLLAMA_URL, json={
            "model": OLLAMA_MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.3
        }, timeout=30)

        result = response.json()
        reply = result['choices'][0]['message']['content'].strip()

        # Гарантируем наличие Telegram
        if TELEGRAM not in reply:
            reply += f"\n\nTelegram: {TELEGRAM}"

        return reply

    except Exception as e:
        print(f"   ⚠️  Ошибка AI: {e}")
        # Fallback на шаблон
        return f"Здравствуйте! Благодарю за интерес. Готов обсудить детали. Telegram: {TELEGRAM}"


def send_reply(neg_id, message, tool_instance=None):
    """
    Отправляет сообщение используя cookie-сессию hh-applicant-tool.
    """
    if DRY_RUN:
        print(f"   🧪 DRY-RUN: не отправлено")
        return True, None
    
    import subprocess
    import base64
    
    # Кодируем сообщение в base64 чтобы избежать проблем с экранированием
    message_b64 = base64.b64encode(message.encode('utf-8')).decode('ascii')
    
    try:
        # Используем Python-скрипт который импортирует hh-applicant-tool напрямую
        send_script = f'''import sys
import base64
sys.path.insert(0, '/Users/m.s.agafonov/Desktop/work-optimization/src')
from hh_applicant_tool.main import HHApplicantTool
import logging

logging.getLogger('urllib3').setLevel(logging.ERROR)

tool = HHApplicantTool()
try:
    tool.run(['whoami'])

    # Проверяем состояние переговоров
    neg_info = tool.api_client.get('/negotiations/{neg_id}')
    if not neg_info:
        print("NOT_FOUND")
        sys.exit(2)

    state = neg_info.get('state', {{}}).get('name', '')
    if state == 'discard':
        print("DISCARDED")
        sys.exit(3)

    # Декодируем сообщение
    message_text = base64.b64decode('{message_b64}').decode('utf-8')
    if not message_text.strip():
        print("EMPTY")
        sys.exit(4)

    # Отправляем
    result = tool.api_client.post('/negotiations/{neg_id}/messages', message=message_text)
    if result:
        print("SUCCESS")
        sys.exit(0)
    else:
        print("FAILED")
        sys.exit(1)

except Exception as e:
    print("ERROR: " + type(e).__name__ + ": " + str(e))
    sys.exit(1)
'''
        
        result = subprocess.run(
            ['python3', '-c', send_script],
            capture_output=True,
            text=True,
            timeout=30,
            cwd='/Users/m.s.agafonov/Desktop/work-optimization'
        )
        
        output = result.stdout.strip()
        
        if result.returncode == 0 or 'SUCCESS' in output:
            return True, None
        
        # Маппинг ошибок
        error_map = {
            'NOT_FOUND': 'Чат не найден',
            'DISCARDED': 'Отказ/закрыто',
            'EMPTY': 'Пустое сообщение',
            'FAILED': 'API вернул ошибку',
            'PERMISSION_DENIED': 'Нет прав',
        }
        
        error_msg = error_map.get(output, output or result.stderr.strip()[:100] or 'Неизвестная ошибка')
        return False, error_msg
        
    except subprocess.TimeoutExpired:
        return False, 'Таймаут (30 сек)'
    except Exception as e:
        return False, f'Ошибка: {type(e).__name__}: {e}'


def process_iteration(iteration_num):
    """Обрабатывает одну итерацию чатов."""
    print(f"\n{'='*60}")
    print(f"📬 ИТЕРАЦИЯ {iteration_num}/{MAX_ITERATIONS} — обработка {CHATS_PER_ITERATION} чатов")
    print(f"{'='*60}")

    negotiations = get_negotiations(page=0, per_page=CHATS_PER_ITERATION)

    if not negotiations:
        print("❌ Нет активных переговоров")
        return 0, 0, {}

    # Счётчики для статистики
    stats = {
        'replied': 0,
        'skipped_no_reply': 0,
        'skipped_discarded': 0,
        'skipped_error': 0,
        'errors': []
    }

    for i, neg in enumerate(negotiations, 1):
        neg_id = neg.get('id')
        if not neg_id:
            continue

        # Проверяем статус переговоров (фильтруем закрытые)
        state = neg.get('state', {}).get('name', '')
        if state == 'discard':
            stats['skipped_discarded'] += 1
            continue

        # Быстро получаем данные о вакансии (без дополнительного API запроса)
        vacancy_info = get_vacancy_details_fast(neg)
        vacancy_name = vacancy_info['name'][:50]
        employer_name = vacancy_info['employer'][:50]

        messages = get_messages(neg_id)
        needs_reply, context = should_reply(messages)

        if not needs_reply:
            stats['skipped_no_reply'] += 1
            continue

        # Генерируем персонализированный AI-ответ
        print(f"\n✍️  Чат #{i}/{len(negotiations)} — {vacancy_name}")
        print(f"   Компания: {employer_name}")
        print(f"   Статус: {state or 'active'}")
        print(f"   Сообщений в истории: {len(messages)}")

        reply = generate_reply_ai(context or [], vacancy_name, employer_name)

        print(f"   Ответ: {reply[:100]}...")

        # Пробуем отправить с повторами при ошибке
        success = False
        error_msg = None
        for attempt in range(MAX_RETRIES):
            success, error_msg = send_reply(neg_id, reply)
            if success:
                stats['replied'] += 1
                print(f"   ✅ Отправлено (попытка {attempt + 1}/{MAX_RETRIES})")
                break
            else:
                print(f"   ⚠️  Попытка {attempt + 1}/{MAX_RETRIES}: {error_msg}")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(1)  # Пауза перед повтором

        if not success:
            stats['skipped_error'] += 1
            stats['errors'].append({
                'negotiation_id': neg_id,
                'vacancy': vacancy_name,
                'error': error_msg
            })
            print(f"   ❌ Не отправлено после {MAX_RETRIES} попыток")

        # Rate limiting между запросами
        if i < len(negotiations):
            time.sleep(PAUSE_BETWEEN_REQUESTS)

    print(f"\n📊 Итоги итерации {iteration_num}:")
    print(f"   ✅ Ответил: {stats['replied']}")
    print(f"   ⏭️  Пропущено (не требуется ответ): {stats['skipped_no_reply']}")
    print(f"   🚫 Пропущено (отказ/закрыто): {stats['skipped_discarded']}")
    print(f"   ❌ Ошибки отправки: {stats['skipped_error']}")

    return stats['replied'], stats['skipped_no_reply'] + stats['skipped_discarded'] + stats['skipped_error'], stats


def main():
    print("🚀 Запуск итеративных AI-ответов работодателям")
    print(f"   Telegram для связи: {TELEGRAM}")
    print(f"   Максимум итераций: {MAX_ITERATIONS}")
    print(f"   Чатов за итерацию: {CHATS_PER_ITERATION}")
    print(f"   Модель AI: {OLLAMA_MODEL} (Ollama)")
    print(f"   Пауза между запросами: {PAUSE_BETWEEN_REQUESTS} сек (rate limiting)")
    print(f"   Пауза между итерациями: {PAUSE_BETWEEN_ITERATIONS} сек")
    if DRY_RUN:
        print(f"   🧪 РЕЖИМ: DRY-RUN (без отправки)")
    print()

    total_replied = 0
    total_skipped = 0
    all_errors = []
    iterations_completed = 0

    for iteration in range(1, MAX_ITERATIONS + 1):
        iterations_completed = iteration
        replied, skipped, stats = process_iteration(iteration)
        total_replied += replied
        total_skipped += skipped
        if stats and stats.get('errors'):
            all_errors.extend(stats['errors'])

        # Если все чаты обработаны — выходим раньше
        if replied == 0 and iteration > 1:
            print("\n✅ Все чаты обработаны — новых ответов не требуется")
            break

        if iteration < MAX_ITERATIONS:
            print(f"\n⏳ Пауза {PAUSE_BETWEEN_ITERATIONS} сек перед следующей итерацией...")
            time.sleep(PAUSE_BETWEEN_ITERATIONS)

    # Финальная статистика
    print(f"\n{'='*60}")
    print(f"✅ ЗАВЕРШЕНО")
    print(f"   Всего ответов отправлено: {total_replied}")
    print(f"   Всего чатов пропущено: {total_skipped}")
    print(f"   Итераций выполнено: {iterations_completed}")
    
    if all_errors:
        print(f"\n⚠️  Ошибки ({len(all_errors)}):")
        # Группируем ошибки по типу
        error_types = {}
        for err in all_errors:
            err_type = err.get('error', 'Unknown')
            if err_type not in error_types:
                error_types[err_type] = []
            error_types[err_type].append(err)
        
        for err_type, errors in error_types.items():
            print(f"   - {err_type}: {len(errors)} чатов")
    
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
