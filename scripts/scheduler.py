#!/usr/bin/env python3
"""
scheduler.py — Планировщик для hh-applicant-tool

Запускает ежедневные задачи в заданное время:
- boost-resume (поднятие резюме)
- apply-vacancies (отклики)

Использование:
    python scheduler.py --time 09:00
    python scheduler.py --time 09:00 --apply-time 09:15
"""

from __future__ import annotations

import argparse
import logging
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("logs/scheduler.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


def parse_time(time_str: str) -> tuple[int, int]:
    """Парсит время в формате HH:MM"""
    try:
        parts = time_str.split(":")
        hour = int(parts[0])
        minute = int(parts[1]) if len(parts) > 1 else 0
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError()
        return hour, minute
    except (ValueError, IndexError):
        raise ValueError(f"Неверный формат времени: {time_str} (ожидалось HH:MM)")


def get_next_run_time(hour: int, minute: int) -> datetime:
    """Возвращает следующее время запуска"""
    now = datetime.now()
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now:
        # Уже прошло сегодня, запускаем завтра
        target = target.replace(day=target.day + 1)
    return target


def run_command(cmd: list[str], description: str) -> bool:
    """Выполняет команду и возвращает успех"""
    logger.info(f"▶️  Запуск: {description}")
    logger.info(f"   Команда: {' '.join(cmd)}")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,  # 5 минут максимум
        )

        if result.returncode == 0:
            logger.info(f"✅ Успешно: {description}")
            if result.stdout:
                logger.info(f"   Вывод: {result.stdout.strip()}")
            return True
        else:
            logger.error(f"❌ Ошибка: {description}")
            if result.stderr:
                logger.error(f"   Ошибка: {result.stderr.strip()}")
            if result.stdout:
                logger.info(f"   Вывод: {result.stdout.strip()}")
            return False

    except subprocess.TimeoutExpired:
        logger.error(f"❌ Тайм-аут: {description} (>5 мин)")
        return False
    except Exception as e:
        logger.error(f"❌ Исключение: {description} - {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Планировщик для hh-applicant-tool"
    )
    parser.add_argument(
        "--time",
        "-t",
        type=str,
        default="09:00",
        help="Время запуска boost-resume (формат HH:MM, по умолчанию 09:00)",
    )
    parser.add_argument(
        "--apply-time",
        type=str,
        default=None,
        help="Время запуска apply-vacancies (формат HH:MM, по умолчанию +15 мин от boost)",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Выполнить один раз и выйти (для тестирования)",
    )
    parser.add_argument(
        "--no-boost",
        action="store_true",
        help="Не запускать boost-resume",
    )
    parser.add_argument(
        "--no-apply",
        action="store_true",
        help="Не запускать apply-vacancies",
    )
    parser.add_argument(
        "--project-dir",
        type=Path,
        default=Path(__file__).parent.parent,
        help="Директория проекта",
    )

    args = parser.parse_args()

    # Парсинг времени
    boost_hour, boost_minute = parse_time(args.time)

    if args.apply_time:
        apply_hour, apply_minute = parse_time(args.apply_time)
    else:
        # +15 минут от boost
        apply_minute = boost_minute + 15
        apply_hour = boost_hour
        if apply_minute >= 60:
            apply_minute -= 60
            apply_hour += 1
        if apply_hour >= 24:
            apply_hour = 0

    # Директория проекта
    project_dir = args.project_dir.resolve()
    hh_tool = [sys.executable, "-m", "hh_applicant_tool"]

    # Команды
    boost_cmd = hh_tool + ["boost-resume"]
    apply_cmd = (
        hh_tool
        + [
            "apply-vacancies",
            "--search",
            "Frontend разработчик",
            "--letter-file",
            str(project_dir / "letter.txt"),
            "--force-message",
            "--excluded-filter",
            "junior|стажир|bitrix|web3|crypto|blockchain",
            "--skip-tests",
            "--per-page",
            "50",
            "--total-pages",
            "3",
        ]
    )

    # Создание директории для логов
    log_dir = project_dir / "logs"
    log_dir.mkdir(exist_ok=True)

    logger.info("=" * 60)
    logger.info("🕐 Планировщик hh-applicant-tool запущен")
    logger.info(f"📁 Проект: {project_dir}")
    logger.info(f"⏰ Boost-resume: {boost_hour:02d}:{boost_minute:02d}")
    logger.info(f"⏰ Apply-vacancies: {apply_hour:02d}:{apply_minute:02d}")
    if args.once:
        logger.info("🔄 Режим: один запуск (тест)")
    else:
        logger.info("🔄 Режим: постоянный (daemon)")
    logger.info("=" * 60)

    if args.once:
        # Тестовый запуск
        logger.info("\n🧪 ТЕСТОВЫЙ ЗАПУСК")

        if not args.no_boost:
            run_command(boost_cmd, "boost-resume")

        if not args.no_apply:
            run_command(apply_cmd, "apply-vacancies")

        logger.info("\n✅ Тест завершён")
        return

    # Основной цикл
    logger.info("\n🕐 Ожидание заданного времени...")

    while True:
        try:
            now = datetime.now()

            # Проверка boost
            if not args.no_boost:
                boost_target = get_next_run_time(boost_hour, boost_minute)
                if now >= boost_target:
                    run_command(boost_cmd, "boost-resume")
                    # Следующий запуск завтра
                    boost_target = get_next_run_time(boost_hour, boost_minute)

            # Проверка apply
            if not args.no_apply:
                apply_target = get_next_run_time(apply_hour, apply_minute)
                if now >= apply_target:
                    run_command(apply_cmd, "apply-vacancies")
                    # Следующий запуск завтра
                    apply_target = get_next_run_time(apply_hour, apply_minute)

            # Проверка каждую минуту
            time.sleep(60)

        except KeyboardInterrupt:
            logger.info("\n👋 Остановка по сигналу пользователя")
            break
        except Exception as e:
            logger.error(f"❌ Ошибка в цикле: {e}")
            time.sleep(60)


if __name__ == "__main__":
    main()
