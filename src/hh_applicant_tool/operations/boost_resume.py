from __future__ import annotations

import argparse
import logging
from typing import TYPE_CHECKING

from ..api import ApiError, datatypes
from ..main import BaseNamespace, BaseOperation

if TYPE_CHECKING:
    from ..main import HHApplicantTool


logger = logging.getLogger(__package__)


class Namespace(BaseNamespace):
    resume_id: str | None


class Operation(BaseOperation):
    """Поднять резюме в топ выдачи (автоподнятие).
    
    HH.ru позволяет поднимать резюме в поиске работодателей.
    После поднятия резюме показывается выше в результатах поиска.
    Доступно 1 раз в 24 часа для каждого резюме.
    """

    __aliases__ = ["boost", "raise-resume"]

    def setup_parser(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--resume-id",
            help="ID резюме для поднятия. Если не указан, поднимутся все доступные резюме.",
            type=str,
            default=None,
        )

    def run(self, tool: HHApplicantTool, args: Namespace) -> None:
        resumes: list[datatypes.Resume] = tool.get_resumes()
        
        if args.resume_id:
            resumes = [r for r in resumes if r["id"] == args.resume_id]
            if not resumes:
                logger.error(f"Резюме с ID {args.resume_id} не найдено")
                return
        
        if not resumes:
            logger.warning("Нет резюме для поднятия")
            return

        boosted_count = 0
        skipped_count = 0
        
        for resume in resumes:
            if not resume.get("can_publish_or_update"):
                logger.warning(f"⛔ Нельзя поднять: {resume['title']}")
                skipped_count += 1
                continue
            
            try:
                tool.api_client.post(f"/resumes/{resume['id']}/publish")
                print(f"✅ Поднято: {resume['title']}")
                print(f"   URL: {resume['alternate_url']}")
                boosted_count += 1
            except ApiError as ex:
                logger.error(f"Ошибка при поднятии резюме {resume['id']}: {ex}")
                skipped_count += 1

        print(f"\n📊 Итог: поднято {boosted_count}, пропущено {skipped_count}")
