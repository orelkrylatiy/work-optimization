#!/usr/bin/env python3
"""Cron-oriented HH chat reply worker.

The worker prefers the current /common/chats API. Live mode is fail-closed:
it requires an explicit AI configuration, revalidates the last employer message
before sending, and uses a deterministic idempotency key for each employer turn.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

from hh_applicant_tool.automation.reply_worker import (
    HHCLI,
    ReplyWorker,
    ReplyWorkerConfig,
    build_ai_client,
    load_json_config,
)
from hh_applicant_tool.constants import CONFIG_DIR
from hh_applicant_tool.utils.config import resolve_profile_config_dir

DEFAULT_SYSTEM_PROMPT = """Ты соискатель и отвечаешь работодателю в чате HH.ru.
Пиши по-русски, коротко и по существу. Сначала ответь на конкретный вопрос из последнего сообщения.
Не выдумывай факты, опыт, контакты, зарплату или договоренности. Не используй placeholder'ы.
Не используй длинные тире, канцелярит, рекламные формулировки и шаблонные AI-переходы.
Не повторяй уже сказанное кандидатом. Telegram упоминай только если работодатель предлагает перейти в мессенджер
или если это естественно нужно для обмена контактом, а не в каждом сообщении.
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Safe autonomous HH chat replies")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--live", action="store_true", help="Send real replies")
    mode.add_argument("--dry-run", action="store_true", help="Never send replies")
    parser.add_argument("--profile", default=os.environ.get("HH_PROFILE_ID", ""))
    parser.add_argument(
        "--max-chats",
        type=int,
        default=int(os.environ.get("REPLY_CHATS", os.environ.get("CHATS", "100"))),
    )
    return parser.parse_args()


def config_path(profile_id: str) -> Path:
    base_dir = Path(os.environ.get("CONFIG_DIR", str(CONFIG_DIR)))
    return resolve_profile_config_dir(base_dir, profile_id) / "config.json"


def load_system_prompt() -> str:
    configured_path = os.environ.get("REPLY_SYSTEM_PROMPT_FILE")
    if not configured_path:
        return DEFAULT_SYSTEM_PROMPT
    try:
        rendered = Path(configured_path).read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise RuntimeError(f"cannot read reply prompt: {exc}") from exc
    return rendered or DEFAULT_SYSTEM_PROMPT


def main() -> int:
    args = parse_args()
    if args.max_chats <= 0:
        print("--max-chats must be a positive integer", file=sys.stderr)
        return 2

    dry_run = not args.live
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    prompt = load_system_prompt()
    ai = None
    if not dry_run:
        try:
            app_config = load_json_config(config_path(args.profile))
            ai = build_ai_client(app_config, prompt)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            print(f"AI configuration error: {exc}", file=sys.stderr)
            return 2

    worker = ReplyWorker(
        ReplyWorkerConfig(
            profile_id=args.profile,
            dry_run=dry_run,
            max_chats=args.max_chats,
        ),
        hh=HHCLI(args.profile),
        ai=ai,
        system_prompt=prompt,
    )
    stats = worker.run()
    print(json.dumps(stats, ensure_ascii=False, sort_keys=True))
    return 1 if stats["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
