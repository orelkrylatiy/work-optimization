from __future__ import annotations

import argparse
import asyncio
import logging
import random
from pathlib import Path
from typing import TYPE_CHECKING, Literal

import requests

from ..ai.base import AIError
from ..api import BadResponse, Redirect, datatypes
from ..api.errors import ApiError, CaptchaRequired, LimitExceeded
from ..main import BaseNamespace, BaseOperation
from ..storage.repositories.errors import RepositoryError
from ..utils.string import rand_text, unescape_string
from .apply_vacancies_ai import ApplyVacanciesAIMixin
from .apply_vacancies_helpers import ApplyVacanciesHelpersMixin

if TYPE_CHECKING:
    from ..main import HHApplicantTool


logger = logging.getLogger(__package__)


class Namespace(BaseNamespace):
    resume_id: str | None
    letter_file: Path | None
    ignore_employers: Path | None
    force_message: bool
    use_ai: bool
    ai_filter: Literal["heavy", "light"] | None
    ai_rate_limit: int
    system_prompt: str
    message_prompt: str
    order_by: str
    search: str
    schedule: str
    dry_run: bool
    response_delay_min: float
    response_delay_max: float
    # Пошли доп фильтры, которых не было
    experience: str
    employment: list[str] | None
    area: list[str] | None
    metro: list[str] | None
    professional_role: list[str] | None
    industry: list[str] | None
    employer_id: list[str] | None
    excluded_employer_id: list[str] | None
    currency: str | None
    salary: int | None
    only_with_salary: bool
    label: list[str] | None
    period: int | None
    date_from: str | None
    date_to: str | None
    top_lat: float | None
    bottom_lat: float | None
    left_lng: float | None
    right_lng: float | None
    sort_point_lat: float | None
    sort_point_lng: float | None
    no_magic: bool
    premium: bool
    per_page: int
    total_pages: int
    excluded_filter: str | None
    max_responses: int
    send_email: bool
    skip_tests: bool


class Operation(ApplyVacanciesAIMixin, ApplyVacanciesHelpersMixin, BaseOperation):
    """Откликнуться на все подходящие вакансии."""

    __aliases__ = ("apply", "apply-similar")

    def setup_parser(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--resume-id", help="Идентефикатор резюме")
        parser.add_argument(
            "--search",
            help="Строка поиска для фильтрации вакансий. Если указана, то поиск будет производиться по вакансиям. В остальных случаях отклики будут производиться по списку рекомендованных вакансий.",  # noqa: E501
            type=str,
        )
        parser.add_argument(
            "-L",
            "--letter-file",
            "--letter",
            help="Путь до файла с текстом сопроводительного письма.",
            type=Path,
        )
        parser.add_argument(
            "-f",
            "--force-message",
            "--force",
            help="Всегда отправлять сообщение при отклике",
            action=argparse.BooleanOptionalAction,
        )
        parser.add_argument(
            "--use-ai",
            "--ai",
            help="Использовать AI для генерации сообщений",
            action=argparse.BooleanOptionalAction,
        )
        parser.add_argument(
            "--ai-filter",
            help="Использовать AI для фильтрации вакансий. Режимы: heavy - полный анализ вакансии и резюме, light - быстрый анализ по названию и навыкам",
            choices=["heavy", "light"],
            default=None,
        )
        parser.add_argument(
            "--ai-rate-limit",
            help="Лимит запросов к AI в минуту для фильтрации",
            type=int,
            default=40,
        )
        parser.add_argument(
            "--system-prompt",
            "--ai-system",
            help="Системный промпт для AI генерации сопроводительных писем",
            default="Напиши сопроводительное письмо для отклика на эту вакансию. Не используй placeholder'ы, твой ответ будет отправлен без обработки.",  # noqa: E501
        )
        parser.add_argument(
            "--message-prompt",
            "--prompt",
            help="Промпт для генерации сопроводительного письма",
            default="Сгенерируй сопроводительное письмо не более 5-7 предложений от моего имени для вакансии",  # noqa: E501
        )
        parser.add_argument(
            "--total-pages",
            "--pages",
            help="Количество обрабатываемых страниц поиска",  # noqa: E501
            default=20,
            type=int,
        )
        parser.add_argument(
            "--per-page",
            help="Сколько должно быть результатов на странице",  # noqa: E501
            default=100,
            type=int,
        )
        parser.add_argument(
            "--send-email",
            help="Отправлять письмо на email компании или рекрутера с просьбой рассмотреть резюме",
            action=argparse.BooleanOptionalAction,
        )
        parser.add_argument(
            "--skip-tests",
            help="Пропускать тесты при откликах вместо",
            action=argparse.BooleanOptionalAction,
        )
        parser.add_argument(
            "--excluded-filter",
            type=str,
            help=r"Исключить вакансии, если название или описание не соответствует шаблону. Например, `--excluded-filter 'junior|стажир|bitrix|дружн\w+ коллектив|полиграф|open\s*space|опенспейс|хакатон|конкурс|тестов\w+ задан'`",
        )
        parser.add_argument(
            "--max-responses",
            type=int,
            help="Пропускать отклик на вакансии с более чем N откликов (не реализован)",
        )
        parser.add_argument(
            "--dry-run",
            help="Не отправлять отклики, а только выводить информацию",
            action=argparse.BooleanOptionalAction,
        )
        parser.add_argument(
            "--response-delay",
            "--delay",
            help="Задержка между откликами в секундах (минимум-максимум, напр. '1-3'). По умолчанию 1-3 сек",
            type=str,
            default="1-3",
        )

        # Дальше идут параметры в точности соответствующие параметрам запроса
        # при поиске подходящих вакансий
        api_search_filters = parser.add_argument_group(
            "Фильтры для поиска вакансий",
            "Эти параметры напрямую соответствуют фильтрам поиска HeadHunter API",
        )

        api_search_filters.add_argument(
            "--order-by",
            help="Сортировка вакансий",
            choices=[
                "publication_time",
                "salary_desc",
                "salary_asc",
                "relevance",
                "distance",
            ],
            # default="relevance",
        )
        api_search_filters.add_argument(
            "--experience",
            help="Уровень опыта работы (noExperience, between1And3, between3And6, moreThan6)",
            type=str,
            default=None,
        )
        api_search_filters.add_argument(
            "--schedule",
            help="Тип графика (fullDay, shift, flexible, remote, flyInFlyOut)",
            type=str,
        )
        api_search_filters.add_argument(
            "--employment", nargs="+", help="Тип занятости"
        )
        api_search_filters.add_argument(
            "--area", nargs="+", help="Регион (area id)"
        )
        api_search_filters.add_argument(
            "--metro", nargs="+", help="Станции метро (metro id)"
        )
        api_search_filters.add_argument(
            "--professional-role", nargs="+", help="Проф. роль (id)"
        )
        api_search_filters.add_argument(
            "--industry", nargs="+", help="Индустрия (industry id)"
        )
        api_search_filters.add_argument(
            "--employer-id", nargs="+", help="ID работодателей"
        )
        api_search_filters.add_argument(
            "--excluded-employer-id", nargs="+", help="Исключить работодателей"
        )
        api_search_filters.add_argument(
            "--currency", help="Код валюты (RUR, USD, EUR)"
        )
        api_search_filters.add_argument(
            "--salary", type=int, help="Минимальная зарплата"
        )
        api_search_filters.add_argument(
            "--only-with-salary",
            default=False,
            action=argparse.BooleanOptionalAction,
        )
        api_search_filters.add_argument(
            "--label", nargs="+", help="Метки вакансий (label)"
        )
        api_search_filters.add_argument(
            "--period", type=int, help="Искать вакансии за N дней"
        )
        api_search_filters.add_argument(
            "--date-from", help="Дата публикации с (YYYY-MM-DD)"
        )
        api_search_filters.add_argument(
            "--date-to", help="Дата публикации по (YYYY-MM-DD)"
        )
        api_search_filters.add_argument(
            "--top-lat", type=float, help="Гео: верхняя широта"
        )
        api_search_filters.add_argument(
            "--bottom-lat", type=float, help="Гео: нижняя широта"
        )
        api_search_filters.add_argument(
            "--left-lng", type=float, help="Гео: левая долгота"
        )
        api_search_filters.add_argument(
            "--right-lng", type=float, help="Гео: правая долгота"
        )
        api_search_filters.add_argument(
            "--sort-point-lat",
            type=float,
            help="Координата lat для сортировки по расстоянию",
        )
        api_search_filters.add_argument(
            "--sort-point-lng",
            type=float,
            help="Координата lng для сортировки по расстоянию",
        )
        api_search_filters.add_argument(
            "--no-magic",
            action="store_true",
            help="Отключить авторазбор текста запроса",
        )
        api_search_filters.add_argument(
            "--premium",
            default=False,
            action=argparse.BooleanOptionalAction,
            help="Только премиум вакансии",
        )
        api_search_filters.add_argument(
            "--search-field",
            nargs="+",
            help="Поля поиска (name, company_name и т.п.)",
        )

    cover_letter: str = "{Здравствуйте|Добрый день}, меня зовут %(first_name)s. {Прошу|Предлагаю} рассмотреть {мою кандидатуру|мое резюме «%(resume_title)s»} на вакансию «%(vacancy_name)s». С уважением, %(first_name)s."

    @property
    def api_client(self):
        return self.tool.api_client

    @property
    def args(self) -> Namespace:
        return self._args

    def run(
        self,
        tool: HHApplicantTool,
        args: Namespace,
    ) -> None:
        self.tool = tool
        self._args = args
        self.cover_letter = (
            args.letter_file.read_text(encoding="utf-8", errors="ignore")
            if args.letter_file
            else self.cover_letter
        )
        self.area = args.area
        self.bottom_lat = args.bottom_lat
        self.currency = args.currency
        self.date_from = args.date_from
        self.date_to = args.date_to
        self.dry_run = args.dry_run
        self.employer_id = args.employer_id
        self.employment = args.employment
        self.excluded_employer_id = args.excluded_employer_id
        self.excluded_filter = args.excluded_filter
        self.experience = args.experience
        self.force_message = args.force_message
        self.industry = args.industry
        self.label = args.label
        self.left_lng = args.left_lng
        self.max_responses = args.max_responses
        self.metro = args.metro
        self.no_magic = args.no_magic
        self.only_with_salary = args.only_with_salary
        self.order_by = args.order_by
        self.per_page = args.per_page
        self.period = args.period
        self.message_prompt = args.message_prompt
        self.premium = args.premium
        self.professional_role = args.professional_role
        self.resume_id = args.resume_id
        self.right_lng = args.right_lng
        self.salary = args.salary
        self.schedule = args.schedule
        self.search = args.search
        self.search_field = args.search_field
        self.sort_point_lat = args.sort_point_lat
        self.sort_point_lng = args.sort_point_lng
        self.top_lat = args.top_lat
        self.total_pages = args.total_pages

        # Парсим задержку между откликами
        delay_parts = args.response_delay.split("-")
        try:
            self.response_delay_min = float(delay_parts[0])
            self.response_delay_max = float(delay_parts[1]) if len(delay_parts) > 1 else self.response_delay_min
        except (ValueError, IndexError):
            logger.warning(
                f"Неверный формат задержки '{args.response_delay}', используем по умолчанию 1-3 сек"
            )
            self.response_delay_min = 1.0
            self.response_delay_max = 3.0

        logger.info(
            "Задежка между откликами: %.1f-%.1f сек",
            self.response_delay_min,
            self.response_delay_max,
        )

        self.cover_letter_ai = (
            tool.get_cover_letter_ai(args.system_prompt)
            if args.use_ai
            else None
        )
        self.ai_filter = args.ai_filter
        self.vacancy_filter_ai = None
        self._resume_analysis_cache: dict[tuple[str | None, str], str] = {}

        self._apply_vacancies()

    SEL_CAPTCHA_IMAGE = 'img[data-qa="account-captcha-picture"]'
    SEL_CAPTCHA_INPUT = 'input[data-qa="account-captcha-input"]'

    # Даже куки не грузятся, исправь
    async def _solve_captcha_async(self, captcha_url: str) -> bool:
        from playwright.async_api import async_playwright

        captcha_ai = self.tool.get_captcha_ai()

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            try:
                context = await browser.new_context()
                page = await context.new_page()

                await page.goto(captcha_url, timeout=30000)

                captcha_element = await page.wait_for_selector(
                    self.SEL_CAPTCHA_IMAGE, timeout=10000, state="visible"
                )

                img_bytes = await captcha_element.screenshot()

                captcha_text = await asyncio.to_thread(
                    captcha_ai.solve_captcha, img_bytes
                )

                if not captcha_text:
                    logger.error("AI не смог распознать капчу")
                    return False

                logger.info(f"Распознанный текст капчи: {captcha_text}")

                await page.fill(self.SEL_CAPTCHA_INPUT, captcha_text)
                await page.press(self.SEL_CAPTCHA_INPUT, "Enter")

                await page.wait_for_load_state("networkidle", timeout=15000)

                cookies = await context.cookies()
                for c in cookies:
                    self.tool.session.cookies.set(
                        c["name"],
                        c["value"],
                        domain=c.get("domain", ""),
                        path=c.get("path", "/"),
                    )

                return True
            finally:
                await browser.close()

        return False

    def _apply_vacancies(self) -> None:
        resumes: list[datatypes.Resume] = self.tool.get_resumes()
        try:
            self.tool.storage.resumes.save_batch(resumes)
        except RepositoryError as ex:
            logger.exception(ex)
        resumes = (
            list(filter(lambda x: x["id"] == self.resume_id, resumes))
            if self.resume_id
            else resumes
        )
        # Выбираем только опубликованные
        resumes = list(
            filter(lambda x: x["status"]["id"] == "published", resumes)
        )
        if not resumes:
            logger.warning("У вас нет опубликованных резюме")
            return

        me: datatypes.User = self.tool.get_me()
        seen_employers = set()

        for resume in resumes:
            self._apply_resume(
                resume=resume,
                user=me,
                seen_employers=seen_employers,
            )

        # Синхронизация откликов
        for neg in self.tool.get_negotiations():
            try:
                # Пропускаем отклики с удаленными работодателями (employer_id = null)
                vacancy = neg.get("vacancy")
                if not vacancy or not vacancy.get("employer") or not vacancy["employer"].get("id"):
                    logger.debug(
                        "Пропуск отклика: вакансия или работодатель удален"
                    )
                    continue
                self.tool.storage.negotiations.save(neg)
            except RepositoryError as e:
                logger.warning(e)

        print("📝 Отклики на вакансии разосланы!")

    def _apply_resume(
        self,
        resume: datatypes.Resume,
        user: datatypes.User,
        seen_employers: set[str],
    ) -> None:
        logger.info(
            "Начинаю рассылку откликов для резюме: %s (%s)",
            resume["alternate_url"],
            resume["title"],
        )
        print("🚀 Начинаю рассылку откликов для резюме:", resume["title"])

        placeholders = {
            "first_name": user.get("first_name") or "",
            "last_name": user.get("last_name") or "",
            "email": user.get("email") or "",
            "phone": user.get("phone") or "",
            "resume_hash": resume.get("id") or "",
            "resume_title": resume.get("title") or "",
            "resume_url": resume.get("alternate_url") or "",
        }

        do_apply = True
        storage = self.tool.storage
        site_emails = {}

        if self.ai_filter:
            if self.ai_filter == "heavy":
                system_prompt = self._build_filter_system_prompt_heavy(
                    self._analyze_resume_heavy(resume)
                )
            elif self.ai_filter == "light":
                system_prompt = self._build_filter_system_prompt_light(
                    self._analyze_resume_light(resume)
                )
            else:
                raise ValueError(
                    f"Неизвестный режим AI фильтра: {self.ai_filter}"
                )

            logger.debug(
                "AI системный промпт (%s): %s",
                self.ai_filter,
                system_prompt,
            )

            self.vacancy_filter_ai = self.tool.get_vacancy_filter_ai(
                system_prompt
            )

            if self.args.ai_rate_limit:
                self.vacancy_filter_ai.rate_limit = self.args.ai_rate_limit

        for vacancy in self._get_vacancies(resume_id=resume["id"]):
            try:
                employer = vacancy.get("employer", {})

                message_placeholders = {
                    "vacancy_name": vacancy.get("name", ""),
                    "employer_name": employer.get("name", ""),
                    **placeholders,
                }

                try:
                    storage.vacancies.save(vacancy)
                except RepositoryError as ex:
                    logger.debug(ex)

                # По факту контакты можно получить только здесь?!
                if vacancy.get("contacts"):
                    logger.debug(
                        f"Найдены контакты в вакансии: {vacancy['alternate_url']}"
                    )

                    try:
                        # logger.debug(vacancy)
                        storage.vacancy_contacts.save(vacancy)
                    except RepositoryError as ex:
                        logger.exception(ex)

                if not do_apply:
                    continue

                vacancy_id = vacancy["id"]
                relations = vacancy.get("relations", [])

                if relations:
                    logger.debug(
                        "Пропускаем вакансию с откликом: %s",
                        vacancy["alternate_url"],
                    )
                    if "got_rejection" in relations:
                        logger.debug(
                            "Вы получили отказ от %s",
                            vacancy["alternate_url"],
                        )
                        print("⛔ Пришел отказ от", vacancy["alternate_url"])
                    continue

                if vacancy.get("archived"):
                    logger.debug(
                        "Пропускаем вакансию в архиве: %s",
                        vacancy["alternate_url"],
                    )
                    continue

                if vacancy.get("has_test") and self.args.skip_tests:
                    logger.debug(
                        "Пропускаю вакансию с тестом %s",
                        vacancy["alternate_url"],
                    )
                    continue

                if redirect_url := vacancy.get("response_url"):
                    logger.debug(
                        "Пропускаем вакансию %s с перенаправлением: %s",
                        vacancy["alternate_url"],
                        redirect_url,
                    )
                    continue

                if self._is_excluded(vacancy):
                    logger.info(
                        "Вакансия попала под фильтр: %s",
                        vacancy["alternate_url"],
                    )

                    self._save_skipped_vacancy(
                        vacancy, "excluded_filter", resume["id"]
                    )

                    self.api_client.put(
                        f"/vacancies/blacklisted/{vacancy['id']}"
                    )
                    logger.info(
                        "Вакансия добавлена в черный список: %s",
                        vacancy["alternate_url"],
                    )
                    continue

                # AI фильтрация вакансий
                if self.ai_filter and self.vacancy_filter_ai:
                    if self._is_vacancy_already_skipped(vacancy, resume["id"]):
                        logger.debug(
                            "Вакансия уже была отклонена ранее: %s",
                            vacancy["alternate_url"],
                        )
                        print(
                            "⏩ Вакансия уже отклонена ранее",
                            vacancy["alternate_url"],
                        )
                        continue

                    if self.ai_filter == "heavy":
                        is_suitable = self._is_vacancy_suitable_heavy(vacancy)
                    elif self.ai_filter == "light":
                        is_suitable = self._is_vacancy_suitable_light(vacancy)
                    else:
                        raise ValueError(
                            f"Неизвестный режим AI фильтра: {self.ai_filter}"
                        )

                    if not is_suitable:
                        logger.info(
                            "Вакансия отклонена AI фильтром (%s): %s",
                            self.ai_filter,
                            vacancy["alternate_url"],
                        )
                        print(
                            f"🧠 AI ({self.ai_filter}) посчитал неподходящей",
                            vacancy["alternate_url"],
                        )

                        self._save_skipped_vacancy(
                            vacancy, "ai_rejected", resume["id"]
                        )
                        continue

                # Перед откликом выгружаем профиль компании
                employer_id = employer.get("id")
                if employer_id and employer_id not in seen_employers:
                    employer_profile: datatypes.Employer = self.api_client.get(
                        f"/employers/{employer_id}"
                    )

                    try:
                        storage.employers.save(employer_profile)
                    except RepositoryError as ex:
                        logger.exception(ex)

                    # Если есть сайт, то ищем на нем емейлы для отправки письма
                    if self.args.send_email and (
                        site_url := (
                            employer_profile.get("site_url") or ""
                        ).strip()
                    ):
                        site_url = (
                            site_url
                            if "://" in site_url
                            else "https://" + site_url
                        )
                        logger.debug("visit site: %s", site_url)

                        try:
                            site_info = self._parse_site(site_url)
                            site_emails[employer_id] = site_info["emails"]
                        except requests.RequestException as ex:
                            site_info = None
                            logger.error(ex)

                        if site_info:
                            logger.debug("site info: %r", site_info)

                            # try:
                            #     subdomains = self._get_subdomains(site_url)
                            # except requests.RequestException as ex:
                            #     subdomains = []
                            #     logger.error(ex)

                            try:
                                storage.employer_sites.save(
                                    {
                                        "site_url": site_url,
                                        "employer_id": employer_id,
                                        "subdomains": [],
                                        **site_info,
                                    }
                                )
                            except RepositoryError as ex:
                                logger.exception(ex)

                letter = ""

                if self.force_message or vacancy.get(
                    "response_letter_required"
                ):
                    if self.cover_letter_ai:
                        msg = self.message_prompt + "\n\n"
                        msg += (
                            "Название вакансии: "
                            + message_placeholders["vacancy_name"]
                        )
                        msg += (
                            "Мое резюме: "
                            + message_placeholders["resume_title"]
                        )
                        logger.debug("prompt: %s", msg)
                        letter = self.cover_letter_ai.complete(msg)
                    else:
                        letter = (
                            rand_text(self.cover_letter) % message_placeholders
                        )

                    logger.debug(letter)

                logger.debug(
                    "Пробуем откликнуться на вакансию: %s",
                    vacancy["alternate_url"],
                )

                if vacancy.get("has_test"):
                    logger.debug(
                        "Решаем тест: %s",
                        vacancy["alternate_url"],
                    )

                    try:
                        if not self.dry_run:
                            result = self._solve_vacancy_test(
                                vacancy_id=vacancy["id"],
                                resume_hash=resume["id"],
                                letter=letter,
                            )
                            if result.get("success") == "true":
                                print(
                                    "📨 Отправили отклик на вакансию с тестом",
                                    vacancy["alternate_url"],
                                )
                            else:
                                err = result.get("error")

                                if err == "negotiations-limit-exceeded":
                                    do_apply = False
                                    logger.warning("Достигли лимита на отклики")
                                else:
                                    logger.error(
                                        f"Произошла ошибка при отклике на вакансию с тестом: {vacancy['alternate_url']} - {err}"
                                    )
                    except Exception as ex:
                        logger.error(f"Произошла непредвиденная ошибка: {ex}")
                        continue

                else:
                    params = {
                        "resume_id": resume["id"],
                        "vacancy_id": vacancy_id,
                        "message": letter,
                    }
                    try:
                        if not self.dry_run:
                            res = self.api_client.post(
                                "/negotiations",
                                params,
                                delay=random.uniform(self.response_delay_min, self.response_delay_max),
                            )
                            assert res == {}
                            print(
                                "📨 Отправили отклик на вакансию",
                                vacancy["alternate_url"],
                            )
                    except Redirect:
                        logger.warning(
                            f"Игнорирую перенаправление на форму: {vacancy['alternate_url']}"  # noqa: E501
                        )
                        continue
                    except CaptchaRequired as ex:
                        logger.warning(f"Требуется капча: {ex.captcha_url}")
                        try:
                            success = asyncio.run(
                                self._solve_captcha_async(ex.captcha_url)
                            )
                            if success:
                                if not self.dry_run:
                                    res = self.api_client.post(
                                        "/negotiations",
                                        params,
                                        delay=random.uniform(self.response_delay_min, self.response_delay_max),
                                    )
                                    assert res == {}
                                    print(
                                        "📨 Отправили отклик на вакансию после капчи",
                                        vacancy["alternate_url"],
                                    )
                            else:
                                logger.error("Не удалось решить капчу")
                                raise
                        except Exception as e:
                            logger.error(f"Ошибка при решении капчи: {e}")
                            raise

                # Отправка письма на email
                if self.args.send_email:
                    # fix NoneType has no attribute get
                    # contacts может быть null
                    mail_to: str | list[str] | None = (
                        vacancy.get("contacts") or {}
                    ).get("email") or site_emails.get(employer_id)
                    if mail_to:
                        mail_to = (
                            ", ".join(mail_to)
                            if isinstance(mail_to, list)
                            else mail_to
                        )
                        mail_subject = rand_text(
                            self.tool.config.get("apply_mail_subject")
                            or "{Отклик|Резюме} на вакансию %(vacancy_name)s"
                        )
                        mail_body = unescape_string(
                            rand_text(
                                self.tool.config.get("apply_mail_body")
                                or "{Здравствуйте|Добрый день}, {прошу рассмотреть|пожалуйста рассмотрите} мое резюме %(resume_url)s на вакансию %(vacancy_name)s."
                                % message_placeholders
                            )
                        )
                        try:
                            self._send_email(mail_to, mail_subject, mail_body)
                            print(
                                "📧 Отправлено письмо на email по поводу вакансии",
                                vacancy["alternate_url"],
                            )
                        except Exception as ex:
                            logger.error(f"Ошибка отправки письма: {ex}")
            except LimitExceeded:
                do_apply = False
                logger.warning("Достигли лимита на отклики")
            except ApiError as ex:
                logger.warning(ex)
            except (BadResponse, AIError) as ex:
                logger.error(ex)

        logger.info(
            "Закончили рассылку откликов для резюме: %s (%s)",
            resume["alternate_url"],
            resume["title"],
        )
        print("✅️ Закончили рассылку откликов для резюме:", resume["title"])

