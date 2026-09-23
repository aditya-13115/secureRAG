from __future__ import annotations

import logging
import math
import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import groq
from groq import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AsyncGroq,
    AuthenticationError,
    PermissionDeniedError,
    RateLimitError,
)

from app.llm.config import (
    LLMSettings,
    get_llm_settings,
)
from app.llm.key_pool import (
    AllGroqKeysUnavailable,
    GroqKeyPool,
)


logger = logging.getLogger(__name__)


@dataclass(slots=True)
class LLMUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass(slots=True)
class LLMResult:
    text: str
    model: str
    key_slot: int
    usage: LLMUsage


class GroqLLMError(Exception):
    """
    Base error exposed by the LLM layer.
    """


class GroqUnavailableError(
    GroqLLMError
):
    """
    All configured Groq keys are unavailable.
    """

    def __init__(
        self,
        message: str,
        retry_after: float | None = None,
    ) -> None:
        self.retry_after = retry_after
        super().__init__(message)


class GroqRequestError(
    GroqLLMError
):
    """
    Non-retriable LLM request error.
    """


class AsyncLLMClient:
    """
    SecureRAG Groq client.

    Responsibilities:
        - maintain multiple Groq clients
        - rotate API keys
        - handle 429s
        - handle invalid keys
        - handle transient failures
        - avoid SDK-level retries on the same key
        - never expose API keys in logs
    """

    def __init__(
        self,
        settings: LLMSettings | None = None,
    ) -> None:
        self.settings = (
            settings
            or get_llm_settings()
        )

        keys = (
            self.settings.get_groq_keys()
        )

        self.key_pool = GroqKeyPool(
            keys
        )

        self._clients: dict[
            int,
            AsyncGroq,
        ] = {}

    def _get_client(
        self,
        slot: int,
        key: str,
    ) -> AsyncGroq:
        client = self._clients.get(slot)

        if client is not None:
            return client

        client = AsyncGroq(
            api_key=key,
            max_retries=0,
            timeout=self.settings.groq_timeout_seconds,
        )

        self._clients[slot] = client

        return client

    async def complete(
        self,
        messages: list[dict[str, Any]],
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMResult:

        model = (
            model
            or self.settings.groq_model
        )

        temperature = (
            self.settings.groq_temperature
            if temperature is None
            else temperature
        )

        max_tokens = (
            self.settings.groq_max_tokens
            if max_tokens is None
            else max_tokens
        )

        attempted_slots: set[int] = set()
        errors: list[str] = []

        max_attempts = (
            self.key_pool.size
        )

        for _ in range(max_attempts):
            try:
                state = (
                    await self.key_pool.acquire(
                        excluded_slots=attempted_slots
                    )
                )
            except AllGroqKeysUnavailable as exc:
                raise GroqUnavailableError(
                    str(exc),
                    retry_after=exc.retry_after,
                ) from exc

            attempted_slots.add(
                state.slot
            )

            client = self._get_client(
                slot=state.slot,
                key=state.key,
            )

            logger.debug(
                "Attempting Groq request using key slot=%s",
                state.slot,
            )

            try:
                response = (
                    await client.chat.completions.create(
                        model=model,
                        messages=messages,
                        temperature=temperature,
                        max_tokens=max_tokens,
                    )
                )

                text = self._extract_text(
                    response
                )

                usage = self._extract_usage(
                    response
                )

                await self.key_pool.mark_success(
                    state.slot
                )

                logger.debug(
                    "Groq request succeeded with key slot=%s",
                    state.slot,
                )

                return LLMResult(
                    text=text,
                    model=model,
                    key_slot=state.slot,
                    usage=usage,
                )

            except RateLimitError as exc:
                cooldown = (
                    self._get_rate_limit_cooldown(
                        exc
                    )
                )

                await self.key_pool.mark_rate_limited(
                    slot=state.slot,
                    cooldown_seconds=cooldown,
                )

                logger.warning(
                    "Groq key slot=%s rate-limited; "
                    "cooling down for %.2fs and rotating.",
                    state.slot,
                    cooldown,
                )

                errors.append(
                    f"key {state.slot}: rate limited"
                )

                continue

            except (
                AuthenticationError,
                PermissionDeniedError,
            ) as exc:
                await self.key_pool.disable(
                    slot=state.slot
                )

                logger.error(
                    "Groq key slot=%s is invalid "
                    "or not permitted; disabling it.",
                    state.slot,
                )

                errors.append(
                    f"key {state.slot}: "
                    f"authentication/permission failure"
                )

                continue

            except (
                APIConnectionError,
                APITimeoutError,
            ) as exc:
                cooldown = max(
                    self.settings.groq_transient_cooldown_seconds,
                    1.0,
                )

                await self.key_pool.mark_transient_failure(
                    slot=state.slot,
                    cooldown_seconds=cooldown,
                )

                logger.warning(
                    "Groq key slot=%s encountered "
                    "a transient connection error; rotating.",
                    state.slot,
                )

                errors.append(
                    f"key {state.slot}: connection/timeout"
                )

                continue

            except APIStatusError as exc:
                status = (
                    getattr(
                        exc,
                        "status_code",
                        None,
                    )
                )

                if status in {
                    408,
                    409,
                } or (
                    status is not None
                    and status >= 500
                ):
                    cooldown = max(
                        self.settings.groq_transient_cooldown_seconds,
                        1.0,
                    )

                    await self.key_pool.mark_transient_failure(
                        slot=state.slot,
                        cooldown_seconds=cooldown,
                    )

                    logger.warning(
                        "Groq key slot=%s received "
                        "transient HTTP %s; rotating.",
                        state.slot,
                        status,
                    )

                    errors.append(
                        f"key {state.slot}: HTTP {status}"
                    )

                    continue

                # 400/404/422/etc. are generally request/model
                # problems rather than an exhausted key.
                message = self._error_message(
                    exc
                )

                raise GroqRequestError(
                    f"Groq request failed with HTTP "
                    f"{status}: {message}"
                ) from exc

            except groq.APIError as exc:
                raise GroqRequestError(
                    f"Groq API error: {exc}"
                ) from exc

        status = await self.key_pool.status()

        logger.error(
            "All Groq keys failed. "
            "attempted=%s status=%s errors=%s",
            max_attempts,
            status,
            errors,
        )

        retry_after = self._status_retry_after(
            status
        )

        raise GroqUnavailableError(
            "All configured Groq API keys "
            "are currently unavailable.",
            retry_after=retry_after,
        )

    async def close(self) -> None:
        for client in self._clients.values():
            await client.close()

        self._clients.clear()

    @staticmethod
    def _extract_text(
        response: Any,
    ) -> str:
        if not response.choices:
            raise GroqRequestError(
                "Groq returned no completion choices."
            )

        message = (
            response.choices[0].message
        )

        text = (
            message.content
            or ""
        ).strip()

        if not text:
            raise GroqRequestError(
                "Groq returned an empty response."
            )

        return text

    @staticmethod
    def _extract_usage(
        response: Any,
    ) -> LLMUsage:
        usage = getattr(
            response,
            "usage",
            None,
        )

        if usage is None:
            return LLMUsage()

        return LLMUsage(
            prompt_tokens=int(
                getattr(
                    usage,
                    "prompt_tokens",
                    0,
                )
                or 0
            ),
            completion_tokens=int(
                getattr(
                    usage,
                    "completion_tokens",
                    0,
                )
                or 0
            ),
            total_tokens=int(
                getattr(
                    usage,
                    "total_tokens",
                    0,
                )
                or 0
            ),
        )

    @staticmethod
    def _error_message(
        exc: APIStatusError,
    ) -> str:
        response = getattr(
            exc,
            "response",
            None,
        )

        if response is None:
            return str(exc)

        try:
            payload = response.json()

            if isinstance(
                payload,
                dict,
            ):
                error = payload.get(
                    "error"
                )

                if isinstance(
                    error,
                    dict,
                ):
                    message = error.get(
                        "message"
                    )

                    if message:
                        return str(
                            message
                        )

            return str(payload)

        except Exception:
            return str(exc)

    @classmethod
    def _get_rate_limit_cooldown(
        cls,
        exc: RateLimitError,
    ) -> float:
        """
        Prefer Groq's Retry-After header.

        Fallback to reset headers if Retry-After
        is unavailable.
        """

        headers = cls._get_headers(
            exc
        )

        retry_after = cls._parse_duration(
            headers.get(
                "retry-after"
            )
        )

        if retry_after is not None:
            return (
                max(
                    retry_after,
                    0.0,
                )
                + 0.25
            )

        reset_requests = (
            cls._parse_duration(
                headers.get(
                    "x-ratelimit-reset-requests"
                )
            )
        )

        reset_tokens = (
            cls._parse_duration(
                headers.get(
                    "x-ratelimit-reset-tokens"
                )
            )
        )

        resets = [
            value
            for value in (
                reset_requests,
                reset_tokens,
            )
            if value is not None
        ]

        if resets:
            # Choose the longest reset window so we don't immediately
            # retry a key that is known to still be exhausted.
            return (
                max(resets)
                + 0.25
            )

        # Last-resort fallback.
        return 10.0

    @staticmethod
    def _get_headers(
        exc: Exception,
    ) -> dict[str, str]:
        response = getattr(
            exc,
            "response",
            None,
        )

        if response is None:
            return {}

        headers = getattr(
            response,
            "headers",
            None,
        )

        if headers is None:
            return {}

        return {
            str(key).lower(): str(value)
            for key, value in headers.items()
        }

    @staticmethod
    def _parse_duration(
        value: str | None,
    ) -> float | None:
        """
        Parse examples like:

            2
            7.66s
            2m59.56s
            1h
            500ms
        """

        if not value:
            return None

        value = value.strip()

        try:
            return float(value)
        except ValueError:
            pass

        pattern = re.compile(
            r"(?P<value>\d+(?:\.\d+)?)"
            r"(?P<unit>ms|s|m|h|d)"
        )

        matches = pattern.findall(
            value
        )

        if not matches:
            return None

        multipliers = {
            "ms": 0.001,
            "s": 1.0,
            "m": 60.0,
            "h": 3600.0,
            "d": 86400.0,
        }

        total = 0.0

        for numeric, unit in matches:
            total += (
                float(numeric)
                * multipliers[unit]
            )

        return total

    @staticmethod
    def _status_retry_after(
        status: list[dict[str, object]],
    ) -> float | None:
        values = []

        for item in status:
            if item.get("disabled"):
                continue

            remaining = item.get(
                "cooldown_remaining"
            )

            if isinstance(
                remaining,
                (int, float),
            ) and remaining > 0:
                values.append(
                    float(remaining)
                )

        if not values:
            return None

        return math.ceil(
            min(values)
        )


@lru_cache(maxsize=1)
def get_llm_client() -> AsyncLLMClient:
    return AsyncLLMClient()