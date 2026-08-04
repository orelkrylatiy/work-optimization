#!/usr/bin/env python3
"""
Итеративные AI-ответы работодателям — 5-6 подходов по 50 чатов.
Каждый ответ генерируется через Ollama с учётом истории переписки.
"""
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import requests

from hh_applicant_tool.constants import CONFIG_DIR
from hh_applicant_tool.utils.config import resolve_profile_config_dir

NAME = (os.environ.get("HH_NAME") or "").strip()
TELEGRAM = (os.environ.get("HH_TELEGRAM") or os.environ.get("TELEGRAM") or "").strip()
MAX_ITERATIONS = int(os.environ.get("ITERATIONS") or os.environ.get("REPLY_ITERATIONS") or "6")
CHATS_PER_ITERATION = int(os.environ.get("CHATS") or os.environ.get("REPLY_CHATS") or "50")
if "--live" in sys.argv and "--dry-run" in sys.argv:
    raise SystemExit("Use either --live or --dry-run, not both.")

# This worker can also be invoked directly, so it must fail closed rather than
# relying on reply.sh to supply a dry-run flag.
DRY_RUN = "--live" not in sys.argv
PAUSE_BETWEEN_REQUESTS = 2.0
PAUSE_BETWEEN_ITERATIONS = 120
MAX_RETRIES = 3

# Мультиаккаунт: профиль из env или --profile аргумента
PROFILE_ID = os.environ.get('HH_PROFILE_ID', '')
for _i, _arg in enumerate(sys.argv[1:]):
    if _arg == '--profile' and _i + 2 < len(sys.argv):
        PROFILE_ID = sys.argv[_i + 2]
        break


def _hh_cmd(*args):
    """Собирает команду hh-applicant-tool с профилем если задан."""
    cmd = ['hh-applicant-tool', '--no-auto-auth']
    if PROFILE_ID:
        cmd += ['--profile-id', PROFILE_ID]
    cmd += list(args)
    return cmd


def _get_config_path() -> Path:
    """Возвращает тот же config.json, который выбрал основной CLI."""
    base_dir = Path(os.environ.get("CONFIG_DIR", str(CONFIG_DIR)))
    return resolve_profile_config_dir(base_dir, PROFILE_ID) / "config.json"


def _load_ai_config():
    """Читает AI-конфиг выбранного профиля."""
    try:
        cfg_path = _get_config_path()
        with cfg_path.open(encoding="utf-8") as f:
            cfg = json.load(f)
        return cfg.get('openai_reply') or cfg.get('openai_cover_letter') or {}
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"❌ Не удалось загрузить AI-конфиг выбранного профиля: {exc}")
        return {}


_ai_cfg = _load_ai_config()
AI_URL = _ai_cfg.get('base_url', 'http://localhost:11434/v1/chat/completions')
AI_MODEL = _ai_cfg.get('model', 'qwen2.5:14b')
AI_API_KEY = _ai_cfg.get('api_key', 'ollama')

_candidate_identity = (
    f"Ты — {NAME}, Frontend-разработчик (React/TypeScript/Redux, 5+ лет)."
    if NAME
    else "Ты — Frontend-разработчик (React/TypeScript/Redux, 5+ лет)."
)
_contact_rule = (
    f"3. При необходимости можешь указать Telegram для связи: {TELEGRAM}"
    if TELEGRAM
    else "3. Не выдумывай контактные данные и не обещай связь в стороннем мессенджере"
)

DEFAULT_SYSTEM_PROMPT = f"""{_candidate_identity}
Отвечаешь работодателям в чате HH.ru.

ПРАВИЛА:
1. Пиши ТОЛЬКО на русском языке, без английских вставок
2. 2-4 предложения, кратко и по делу
{_contact_rule}
4. Анализируй историю переписки ПЕРЕД ответом:
   - Если работодатель задал вопрос → ответь на КОНКРЕТНЫЙ вопрос
   - Если первое сообщение после отклика → поблагодари + предложи созвон
   - Если тишина 2+ дня → мягкий follow-up
   - Если отказ → вежливо поблагодари
5. НЕ пиши шаблонные фразы вроде "Успехов в поисках" без контекста
6. Обращайся к работодателю на "Вы"
7. Не используй placeholder'ы или заготовки вроде [ваш город], {{название компании}}, <имя>
8. Если точных данных нет, ответь нейтрально и без выдумок
"""


def _load_system_prompt() -> str:
    prompt_path = os.environ.get("REPLY_SYSTEM_PROMPT_FILE")
    if not prompt_path:
        return DEFAULT_SYSTEM_PROMPT
    try:
        prompt_text = Path(prompt_path).read_text(encoding="utf-8").strip()
    except OSError as exc:
        print(f"   ⚠️  Не удалось прочитать системный промпт: {exc}")
        return DEFAULT_SYSTEM_PROMPT
    return prompt_text or DEFAULT_SYSTEM_PROMPT


SYSTEM_PROMPT = _load_system_prompt()


PLACEHOLDER_PATTERNS = (
    re.compile(r"\[[^\[\]\n]{1,80}\]"),
    re.compile(r"\{[^{}\n]{1,80}\}"),
    re.compile(r"<[^<>\n]{1,80}>"),
)
PLACEHOLDER_PHRASES = (
    "ваш город",
    "вашем городе",
    "ваша компания",
    "название компании",
    "имя рекрутера",
    "ваше имя",
)


def has_unresolved_placeholders(text: str) -> bool:
    normalized = " ".join((text or "").split())
    if not normalized:
        return False
    lowered = normalized.lower()
    if any(phrase in lowered for phrase in PLACEHOLDER_PHRASES):
        return True
    return any(pattern.search(normalized) for pattern in PLACEHOLDER_PATTERNS)


def build_safe_reply(initiated_by_us: bool) -> str:
    contact = f" Telegram: {TELEGRAM}" if TELEGRAM else ""
    if initiated_by_us:
        return (
            f"Здравствуйте! Спасибо за сообщение. Готов обсудить детали вакансии "
            f"и ответить на вопросы.{contact}"
        )
    return (
        f"Здравствуйте! Спасибо за приглашение. Готов обсудить детали вакансии "
        f"и ответить на вопросы.{contact}"
    )


def run_hh(*args):
    """Выполняет hh-applicant-tool команду и возвращает JSON-результат."""
    result = subprocess.run(_hh_cmd(*args), capture_output=True, text=True)
    if result.returncode != 0:
        err = result.stderr.strip() or result.stdout.strip() or "Unknown HH CLI error"
        raise RuntimeError(err)
    if not result.stdout:
        return None
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid HH JSON output: {result.stdout[:200]}") from exc


def get_negotiations(page=0, per_page=CHATS_PER_ITERATION):
    """Получает список активных переговоров."""
    data = run_hh('call-api', f'/negotiations?status=active&per_page={per_page}&page={page}')
    return data.get('items', []) if data else []


def get_messages(neg_id):
    """Получает историю сообщений чата."""
    data = run_hh('call-api', f'/negotiations/{neg_id}/messages?per_page=20')
    return data.get('items', []) if data else []


def message_participant_type(message):
    """Возвращает автора сообщения согласно схеме HH API."""
    return (message.get("author") or {}).get("participant_type", "")


def get_vacancy_details_fast(neg):
    """Быстро получает данные о вакансии из объекта переговоров (без API запроса)."""
    vacancy = neg.get('vacancy', {})
    return {
        'name': vacancy.get('name', 'Неизвестно'),
        'employer': vacancy.get('employer', {}).get('name', 'Неизвестно')
    }


def should_reply(messages):
    """
    Проверяет, нужно ли отвечать и строит контекст для AI.
    - Последнее от работодателя → нужно отвечать
    - Последнее от нас (applicant) → уже ответили, пропускаем
    Возвращает (needs_reply, context_lines, initiated_by_us)
    """
    if not messages:
        return False, None, None

    # Сортируем по времени: старые → новые
    sorted_msgs = sorted(messages, key=lambda m: m.get('created_at', ''))
    last_msg = sorted_msgs[-1]
    last_author = message_participant_type(last_msg)

    # Отвечаем только когда схема явно подтверждает сообщение работодателя.
    # Неизвестный автор безопаснее пропустить, чем отправить дубликат.
    if last_author != 'employer':
        return False, None, None

    # Кто инициировал переписку
    first_author = message_participant_type(sorted_msgs[0])
    initiated_by_us = first_author == 'applicant'

    # Контекст: последние 10 сообщений в хронологическом порядке
    context = []
    for m in sorted_msgs[-10:]:
        participant_type = message_participant_type(m)
        author = "Я" if participant_type == 'applicant' else "Работодатель"
        text = (m.get('text') or '').strip()
        context.append(f"{author}: {text}")

    return True, context, initiated_by_us


def generate_reply_ai(context, vacancy_name, employer_name, initiated_by_us=True):
    """Генерирует персонализированный ответ через AI (OpenAI / Ollama из конфига профиля)."""
    situation = (
        "Я сам откликнулся на вакансию (написал первым)."
        if initiated_by_us else
        "Работодатель написал первым — пригласил меня."
    )

    prompt = f"""Вакансия: {vacancy_name}
Компания: {employer_name}
Ситуация: {situation}

ИСТОРИЯ ПЕРЕПИСКИ:
{chr(10).join(context)}

Напиши короткий персонализированный ответ работодателю на русском языке."""

    try:
        response = requests.post(
            AI_URL,
            headers={'Authorization': f'Bearer {AI_API_KEY}'},
            json={
                "model": AI_MODEL,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.3,
            },
            timeout=30,
        )
        response.raise_for_status()
        result = response.json()
        reply = result['choices'][0]['message']['content'].strip()

        if not reply:
            raise ValueError("AI вернул пустой ответ")

        if has_unresolved_placeholders(reply):
            print("   ⚠️  AI вернул placeholder'ы; ответ не будет отправлен")
            return None

        if TELEGRAM and TELEGRAM not in reply:
            reply += f"\n\nTelegram: {TELEGRAM}"

        return reply

    except Exception as e:
        print(f"   ⚠️  Ошибка AI; ответ не будет отправлен: {e}")
        return None


def send_reply(neg_id, message):
    """Отправляет сообщение через hh-applicant-tool call-api."""
    if DRY_RUN:
        print("   🧪 DRY-RUN: не отправлено")
        return True, None

    if has_unresolved_placeholders(message):
        return False, "Обнаружены неразрешённые placeholder'ы в сообщении"

    try:
        run_hh(
            "call-api",
            f"/negotiations/{neg_id}/messages",
            "--method",
            "POST",
            f"message={message}",
        )
        return True, None
    except Exception as e:
        return False, f'{type(e).__name__}: {e}'


def collect_active_negotiations(max_count: int):
    """Read a bounded snapshot before replying can reorder HH's pages."""
    negotiations = []
    seen_ids = set()
    page = 0
    while len(negotiations) < max_count:
        page_items = get_negotiations(page=page, per_page=CHATS_PER_ITERATION)
        if not page_items:
            break
        for item in page_items:
            neg_id = item.get("id")
            if neg_id and neg_id not in seen_ids:
                negotiations.append(item)
                seen_ids.add(neg_id)
                if len(negotiations) >= max_count:
                    break
        if len(page_items) < CHATS_PER_ITERATION:
            break
        page += 1
    return negotiations


def process_iteration(iteration_num, negotiations):
    """Process one already-snapshotted batch of conversations."""
    print(f"\n{'='*60}")
    print(f"📬 ИТЕРАЦИЯ {iteration_num}/{MAX_ITERATIONS} — обработка {len(negotiations)} чатов")
    print(f"{'='*60}")

    if not negotiations:
        return 0, 0, {}

    # Счётчики для статистики
    stats = {
        'replied': 0,
        'planned': 0,
        'skipped_no_reply': 0,
        'skipped_discarded': 0,
        'skipped_error': 0,
        'errors': []
    }

    for i, neg in enumerate(negotiations, 1):
        neg_id = neg.get('id')
        if not neg_id:
            continue

        # Проверяем статус переговоров (фильтруем отказы)
        state_obj = neg.get('state', {})
        state_id = state_obj.get('id', '')
        state_name = state_obj.get('name', '')
        if state_id == 'discard' or state_name in ('Отказ', 'discard'):
            stats['skipped_discarded'] += 1
            continue

        # Быстро получаем данные о вакансии (без дополнительного API запроса)
        vacancy_info = get_vacancy_details_fast(neg)
        vacancy_name = vacancy_info['name'][:50]
        employer_name = vacancy_info['employer'][:50]

        messages = get_messages(neg_id)
        needs_reply, context, initiated_by_us = should_reply(messages)

        if not needs_reply:
            stats['skipped_no_reply'] += 1
            continue

        # A dry run does not send employer chat data to an AI provider.  It
        # still exposes a deterministic draft for operator review.
        initiator = "мы откликнулись" if initiated_by_us else "нас пригласили"
        print(f"\n✍️  Чат #{i}/{len(negotiations)} — {vacancy_name}")
        print(f"   Компания: {employer_name}")
        print(f"   Статус: {state_name or state_id or 'active'} | Инициатор: {initiator}")
        print(f"   Сообщений в истории: {len(messages)}")

        reply = (
            build_safe_reply(initiated_by_us)
            if DRY_RUN
            else generate_reply_ai(context or [], vacancy_name, employer_name, initiated_by_us)
        )

        if not reply:
            stats['skipped_error'] += 1
            stats['errors'].append({
                'negotiation_id': neg_id,
                'vacancy': vacancy_name,
                'error': 'AI did not produce a safe contextual reply',
            })
            continue

        print(f"   Ответ: {reply[:100]}...")

        # Пробуем отправить с повторами при ошибке
        success = False
        error_msg = None
        for attempt in range(MAX_RETRIES):
            success, error_msg = send_reply(neg_id, reply)
            if success:
                if DRY_RUN:
                    stats['planned'] += 1
                    print("   🧪 Запланировано (без отправки)")
                else:
                    stats['replied'] += 1
                    print(f"   ✅ Отправлено (попытка {attempt + 1}/{MAX_RETRIES})")
                break
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
        if not DRY_RUN and i < len(negotiations):
            time.sleep(PAUSE_BETWEEN_REQUESTS)

    print(f"\n📊 Итоги итерации {iteration_num}:")
    if DRY_RUN:
        print(f"   🧪 Запланировано: {stats['planned']}")
    else:
        print(f"   ✅ Ответил: {stats['replied']}")
    print(f"   ⏭️  Пропущено (не требуется ответ): {stats['skipped_no_reply']}")
    print(f"   🚫 Пропущено (отказ/закрыто): {stats['skipped_discarded']}")
    print(f"   ❌ Ошибки отправки: {stats['skipped_error']}")

    completed = stats['planned'] if DRY_RUN else stats['replied']
    return completed, stats['skipped_no_reply'] + stats['skipped_discarded'] + stats['skipped_error'], stats


def main() -> int:
    profile_label = f" [{PROFILE_ID}]" if PROFILE_ID else ""
    print(f"🚀 Запуск итеративных AI-ответов работодателям{profile_label}")
    print(f"   Telegram для связи: {TELEGRAM or 'не настроен'}")
    print(f"   Максимум итераций: {MAX_ITERATIONS}")
    print(f"   Чатов за итерацию: {CHATS_PER_ITERATION}")
    print(f"   Модель AI: {AI_MODEL} ({AI_URL})")
    print(f"   Пауза между запросами: {PAUSE_BETWEEN_REQUESTS} сек")
    print(f"   Пауза между итерациями: {PAUSE_BETWEEN_ITERATIONS} сек")
    if DRY_RUN:
        print("   🧪 РЕЖИМ: DRY-RUN (без отправки)")
    print()

    total_replied = 0
    total_skipped = 0
    all_errors = []
    iterations_completed = 0

    try:
        snapshot_limit = CHATS_PER_ITERATION if DRY_RUN else MAX_ITERATIONS * CHATS_PER_ITERATION
        negotiations = collect_active_negotiations(snapshot_limit)
        if not negotiations:
            print("\n✅ Нет активных переговоров")
            return 0
        print(f"   Снимок активных переговоров: {len(negotiations)}")

        for iteration, start in enumerate(range(0, len(negotiations), CHATS_PER_ITERATION), start=1):
            iterations_completed = iteration
            batch = negotiations[start:start + CHATS_PER_ITERATION]
            replied, skipped, stats = process_iteration(iteration, batch)
            total_replied += replied
            total_skipped += skipped
            if stats and stats.get('errors'):
                all_errors.extend(stats['errors'])

            # Если все чаты обработаны — выходим раньше
            if DRY_RUN:
                print("\n✅ Dry-run завершён после одной итерации")
                break

            if start + CHATS_PER_ITERATION < len(negotiations):
                print(f"\n⏳ Пауза {PAUSE_BETWEEN_ITERATIONS} сек перед следующей итерацией...")
                time.sleep(PAUSE_BETWEEN_ITERATIONS)
    except RuntimeError as exc:
        print(f"\n❌ Ошибка HH API: {exc}")
        return 1

    # Финальная статистика
    print(f"\n{'='*60}")
    print("✅ ЗАВЕРШЕНО")
    total_label = "Всего ответов запланировано" if DRY_RUN else "Всего ответов отправлено"
    print(f"   {total_label}: {total_replied}")
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
    return 0


if __name__ == "__main__":
    sys.exit(main())
