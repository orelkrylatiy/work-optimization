import base64
import logging
import time
from dataclasses import KW_ONLY, dataclass, field
from email.utils import parsedate_to_datetime
from threading import Lock

import requests

from .base import AIError

logger = logging.getLogger(__package__)


class OpenAIError(AIError):
    pass


@dataclass
class ChatOpenAI:
    """Клиент для OpenAI-совместимых API (OpenAI, OpenRouter, Ollama и др.).

    Поддерживает:
    - rate limiting с настраиваемым лимитом запросов в минуту
    - автоматический retry при ответе 429 с учётом заголовка Retry-After
    - генерацию текста (complete) и распознавание капчи (solve_captcha)
    """

    api_key: str

    _: KW_ONLY

    base_url: str
    system_prompt: str | None = None
    timeout: float = 15.0
    max_retries: int = 5
    temperature: float = 0.0
    max_completion_tokens: int = 1000
    model: str | None = None
    rate_limit: int = 40  # запросов в минуту, 0 = отключено

    session: requests.Session = field(default_factory=requests.Session)

    _previous_request_time: float = field(default=0.0, init=False)
    _lock: Lock = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._lock = Lock()

    def _default_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}"}

    @property
    def _min_request_interval(self) -> float:
        return 60.0 / self.rate_limit if self.rate_limit > 0 else 0.0

    def _request(self, payload: dict) -> requests.Response:
        """Выполняет POST-запрос с соблюдением минимального интервала между запросами."""
        with self._lock:
            if self._previous_request_time > 0:
                delay = (
                    self._min_request_interval
                    - time.monotonic()
                    + self._previous_request_time
                )
                if delay > 0:
                    logger.debug("Wait %.2fs before OpenAI request", delay)
                    time.sleep(delay)

            try:
                return self.session.post(
                    self.base_url,
                    json=payload,
                    headers=self._default_headers(),
                    timeout=self.timeout,
                )
            finally:
                self._previous_request_time = time.monotonic()

    def _get_retry_delay(self, response: requests.Response, attempt: int) -> float:
        """Вычисляет задержку перед повторным запросом при 429."""
        min_interval = self._min_request_interval or 1.0
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            try:
                return max(float(retry_after), min_interval)
            except ValueError:
                try:
                    retry_at = parsedate_to_datetime(retry_after).timestamp()
                    return max(retry_at - time.time(), min_interval)
                except (TypeError, ValueError, OverflowError):
                    pass
        return max(min_interval * (attempt + 1), 1.0)

    def _execute_with_retry(self, payload: dict) -> dict:
        """Отправляет payload и повторяет запрос при 429 вплоть до max_retries раз.

        Returns:
            Распарсенный JSON-ответ от API.

        Raises:
            OpenAIError: при сетевой ошибке, исчерпании попыток или невалидном ответе.
        """
        for attempt in range(self.max_retries + 1):
            try:
                response = self._request(payload)
            except requests.exceptions.RequestException as ex:
                raise OpenAIError(f"Network error: {ex}") from ex

            if response.status_code == 429:
                if attempt >= self.max_retries:
                    raise OpenAIError("OpenAI rate limit exceeded")
                delay = self._get_retry_delay(response, attempt)
                logger.warning(
                    "OpenAI returned 429 Too Many Requests, retry in %.2fs", delay
                )
                time.sleep(delay)
                continue

            try:
                response.raise_for_status()
                data = response.json()
            except requests.exceptions.RequestException as ex:
                raise OpenAIError(f"Network error: {ex}") from ex
            except ValueError as ex:
                raise OpenAIError(f"Invalid JSON response: {ex}") from ex

            if "error" in data:
                raise OpenAIError(data["error"]["message"])

            return data

        raise OpenAIError("OpenAI request failed after retries")

    def complete(self, message: str) -> str:
        """Генерирует текст через OpenAI-совместимый API.

        Args:
            message: пользовательский промпт.

        Returns:
            Текст ответа модели.
        """
        messages = []
        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})
        messages.append({"role": "user", "content": message})

        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("AI запрос: %s", message)

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_completion_tokens": self.max_completion_tokens,
            "stream": False,
        }

        data = self._execute_with_retry(payload)
        try:
            content = data["choices"][0]["message"]["content"]
            return content if content is not None else ""
        except (KeyError, IndexError) as ex:
            raise OpenAIError(f"Invalid response format: {ex}") from ex

    def solve_captcha(self, image_data: bytes) -> str:
        """Распознаёт текст на изображении капчи через vision-модель.

        Args:
            image_data: бинарные данные изображения в формате PNG.

        Returns:
            Распознанный текст капчи.
        """
        image_base64 = base64.b64encode(image_data).decode("utf-8")

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Ты должен распознать текст на изображении. "
                        "Верни ТОЛЬКО текст, без каких-либо объяснений или дополнительных символов."
                    ),
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{image_base64}"
                            },
                        },
                        {
                            "type": "text",
                            "text": "Распознай текст на изображении. Верни только результат распознавания.",
                        },
                    ],
                },
            ],
            "temperature": 0.0,
            "max_completion_tokens": 20,
            "stream": False,
        }

        logger.debug("AI запрос на распознавание капчи: %d bytes", len(image_data))

        data = self._execute_with_retry(payload)
        try:
            captcha_text = data["choices"][0]["message"]["content"]
            captcha_text = captcha_text.strip() if captcha_text else ""
            logger.debug("Распознанный текст капчи: %s", captcha_text)
            return captcha_text
        except (KeyError, IndexError) as ex:
            raise OpenAIError(f"Invalid response format: {ex}") from ex
