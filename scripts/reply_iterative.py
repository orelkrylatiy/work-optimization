#!/usr/bin/env python3
"""
Итеративные ответы работодателям — 5-6 подходов по 50 чатов.
Проверяет контекст: не отвечает, если уже есть ответ после последнего сообщения работодателя.
"""
import subprocess
import json
import sys
import time

TELEGRAM = "@wavemax6"
MAX_ITERATIONS = 6
CHATS_PER_ITERATION = 50

def run_cmd(cmd):
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    try:
        return json.loads(result.stdout)
    except:
        return None

def get_negotiations(page=0, per_page=50):
    data = run_cmd(f'hh-applicant-tool call-api "/negotiations?status=active&per_page={per_page}&page={page}" 2>/dev/null')
    return data.get('items', []) if data else []

def get_messages(neg_id):
    data = run_cmd(f'hh-applicant-tool call-api "/negotiations/{neg_id}/messages?per_page=20" 2>/dev/null')
    return data.get('items', []) if data else []

def should_reply(messages):
    """
    Проверяет, нужно ли отвечать:
    - Если последнее сообщение от работодателя — нужно отвечать
    - Если последнее от меня — уже ответил, пропускаем
    """
    if not messages:
        return False, None, None
    
    # Сортируем по времени (новые сверху)
    sorted_msgs = sorted(messages, key=lambda m: m.get('created_at', ''), reverse=True)
    last_msg = sorted_msgs[0]
    last_author = last_msg.get('participant_type', '')
    
    # Если последнее сообщение от меня — уже ответил
    if last_author == 'applicant':
        return False, None, None
    
    # Последнее от работодателя — нужно отвечать
    # Берём контекст: последние 3-5 сообщений
    context = []
    for m in sorted_msgs[:5]:
        author = "Я" if m.get('participant_type') == 'applicant' else "Работодатель"
        text = m.get('text', '')[:150]
        context.append(f"{author}: {text}")
    
    vacancy_name = "Неизвестно"
    employer_name = "Неизвестно"
    
    return True, context, (vacancy_name, employer_name)

def generate_reply(context, vacancy_name, employer_name):
    """
    Генерирует персонализированный ответ на основе контекста.
    """
    # Анализируем контекст
    employer_messages = [c for c in context if c.startswith("Работодатель:")]
    
    reply = f"Здравствуйте! "
    
    # Если работодатель поблагодарил за отклик
    if any('спасибо' in c.lower() or 'благодар' in c.lower() for c in employer_messages):
        reply += "Благодарю за интерес к моей кандидатуре! "
    
    # Если работодатель задал вопрос
    if any('?' in c for c in employer_messages):
        reply += "Готов ответить на ваши вопросы. "
    
    # Если работодатель предложил обсудить
    if any('обсуд' in c.lower() or 'связ' in c.lower() for c in employer_messages):
        reply += "Готов обсудить детали сотрудничества. "
    
    # Добавляем контакт
    reply += f"Оперативно отвечаю в Telegram: {TELEGRAM}. Буду рад сотрудничеству!"
    
    return reply

def send_reply(neg_id, message):
    cmd = f'hh-applicant-tool call-api -X POST "/negotiations/{neg_id}/messages" -d \'{{"message": {json.dumps(message)}}}\' 2>/dev/null'
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return result.returncode == 0

def process_iteration(iteration_num, start_idx):
    print(f"\n{'='*60}")
    print(f"📬 ИТЕРАЦИЯ {iteration_num} — обработка чатов {start_idx+1}-{start_idx+CHATS_PER_ITERATION}")
    print(f"{'='*60}")
    
    negotiations = get_negotiations(page=0, per_page=CHATS_PER_ITERATION)
    
    if not negotiations:
        print("❌ Нет активных переговоров")
        return 0
    
    replied_count = 0
    skipped_count = 0
    
    for i, neg in enumerate(negotiations):
        neg_id = neg.get('id')
        if not neg_id:
            continue
        
        vacancy = neg.get('vacancy', {})
        vacancy_name = vacancy.get('name', 'Неизвестно')[:50]
        
        messages = get_messages(neg_id)
        needs_reply, context, _ = should_reply(messages)
        
        if not needs_reply:
            skipped_count += 1
            continue
        
        # Генерируем персонализированный ответ
        reply = generate_reply(context or [], vacancy_name, "")
        
        print(f"\n✍️  Чат #{neg_id} — {vacancy_name}")
        print(f"   Контекст: {context[:2] if context else 'Нет'}")
        print(f"   Ответ: {reply[:80]}...")
        
        if send_reply(neg_id, reply):
            print(f"   ✅ Отправлено")
            replied_count += 1
            time.sleep(0.5)  # Пауза между запросами
        else:
            print(f"   ❌ Ошибка отправки")
    
    print(f"\n📊 Итоги итерации {iteration_num}:")
    print(f"   Ответил: {replied_count}")
    print(f"   Пропущено: {skipped_count}")
    
    return replied_count

def main():
    print("🚀 Запуск итеративных ответов работодателям")
    print(f"   Telegram для связи: {TELEGRAM}")
    print(f"   Максимум итераций: {MAX_ITERATIONS}")
    print(f"   Чатов за итерацию: {CHATS_PER_ITERATION}")
    
    total_replied = 0
    
    for iteration in range(1, MAX_ITERATIONS + 1):
        start_idx = (iteration - 1) * CHATS_PER_ITERATION
        replied = process_iteration(iteration, start_idx)
        total_replied += replied
        
        if replied == 0 and iteration > 1:
            print("\n✅ Все чаты обработаны — новых ответов не требуется")
            break
        
        if iteration < MAX_ITERATIONS:
            print(f"\n⏳ Пауза 2 секунды перед следующей итерацией...")
            time.sleep(2)
    
    print(f"\n{'='*60}")
    print(f"✅ ЗАВЕРШЕНО. Всего ответов: {total_replied}")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()
