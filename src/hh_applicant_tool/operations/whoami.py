# Этот модуль можно использовать как образец для других
from __future__ import annotations

import argparse
import json
import logging
from typing import TYPE_CHECKING

from ..api import datatypes
from ..main import BaseNamespace, BaseOperation

if TYPE_CHECKING:
    from ..main import HHApplicantTool


logger = logging.getLogger(__package__)


class Namespace(BaseNamespace):
    pass


def fmt_plus(n: int) -> str:
    assert n >= 0
    return f"+{n}" if n else "0"


class Operation(BaseOperation):
    """Выведет текущего пользователя"""

    # Это алиасы команды
    __aliases__: list[str] = ["id"]

    def setup_parser(self, parser: argparse.ArgumentParser) -> None:
        pass

    def run(self, tool: HHApplicantTool, args: Namespace) -> None:
        api_client = tool.api_client
        result: datatypes.User = api_client.get("me")
        if result.get('auth_type') != 'applicant':
            logger.warning("Вы вошли не как соискатель! Попробуйте авторизоваться вручную!!!")
        full_name = " ".join(
            filter(
                None,
                [
                    result.get("last_name"),
                    result.get("first_name"),
                    result.get("middle_name"),
                ],
            )
        ) or 'Анонимный аккаунт'
        with tool.storage.settings as s:
            s.set_value("user.full_name", full_name)
            s.set_value("user.email", result.get("email"))
            s.set_value("user.phone", result.get("phone"))
        counters = result.get("counters", {})
        
        if getattr(args, 'json_output', False):
            # JSON output for programmatic use
            output = {
                "id": result["id"],
                "full_name": full_name,
                "first_name": result.get("first_name"),
                "last_name": result.get("last_name"),
                "email": result.get("email"),
                "phone": result.get("phone"),
                "auth_type": result.get("auth_type"),
                "counters": {
                    "resumes_count": counters.get("resumes_count", 0),
                    "new_resume_views": counters.get("new_resume_views", 0),
                    "unread_negotiations": counters.get("unread_negotiations", 0),
                }
            }
            print(json.dumps(output, ensure_ascii=False, indent=2))
        else:
            # Human-readable output
            print(
                f"🆔 {result['id']} {full_name} "
                f"[ 📄 {counters.get('resumes_count', 0)} "
                f"| 👁️ {fmt_plus(counters.get('new_resume_views', 0))} "
                f"| ✉️ {fmt_plus(counters.get('unread_negotiations', 0))} ]"
            )
