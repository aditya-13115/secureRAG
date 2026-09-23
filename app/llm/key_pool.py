from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass


@dataclass(slots=True)
class KeyState:
    """
    Runtime state for one Groq API key.

    The actual key value is never included in repr/log output.
    """

    key: str
    slot: int

    cooldown_until: float = 0.0
    disabled: bool = False
    failure_count: int = 0

    @property
    def available(self) -> bool:
        if self.disabled:
            return False

        return time.monotonic() >= self.cooldown_until


class AllGroqKeysUnavailable(Exception):
    """
    Raised when no key is currently usable.
    """

    def __init__(
        self,
        retry_after: float | None = None,
    ) -> None:
        self.retry_after = retry_after

        message = (
            "All configured Groq API keys are currently unavailable."
        )

        if retry_after is not None:
            message += (
                f" Retry after approximately "
                f"{retry_after:.1f} seconds."
            )

        super().__init__(message)


class GroqKeyPool:
    """
    Thread/async-safe round-robin key pool.

    Each request gets a different available key where possible.

    A key can be:
        - available
        - temporarily rate-limited
        - temporarily unhealthy
        - permanently disabled for the current process
    """

    def __init__(
        self,
        keys: tuple[str, ...],
    ) -> None:
        if not keys:
            raise ValueError(
                "GroqKeyPool requires at least one API key."
            )

        self._states = [
            KeyState(
                key=key,
                slot=index + 1,
            )
            for index, key in enumerate(keys)
        ]

        self._next_index = 0

        self._lock = asyncio.Lock()

    @property
    def size(self) -> int:
        return len(self._states)

    async def acquire(
        self,
        excluded_slots: set[int] | None = None,
    ) -> KeyState:
        """
        Return the next available key.

        `excluded_slots` prevents a single request from retrying
        the exact same key after it already failed.
        """

        excluded_slots = (
            excluded_slots
            or set()
        )

        async with self._lock:
            now = time.monotonic()

            total = len(self._states)

            for offset in range(total):
                index = (
                    self._next_index
                    + offset
                ) % total

                state = self._states[index]

                if state.slot in excluded_slots:
                    continue

                if state.disabled:
                    continue

                if state.cooldown_until > now:
                    continue

                # Advance the round-robin pointer.
                self._next_index = (
                    index + 1
                ) % total

                return state

            retry_after = self._earliest_retry(
                excluded_slots
            )

            raise AllGroqKeysUnavailable(
                retry_after=retry_after
            )

    async def mark_rate_limited(
        self,
        slot: int,
        cooldown_seconds: float,
    ) -> None:
        async with self._lock:
            state = self._get(slot)

            state.cooldown_until = max(
                state.cooldown_until,
                time.monotonic()
                + max(
                    cooldown_seconds,
                    0.0,
                ),
            )

            state.failure_count += 1

    async def mark_transient_failure(
        self,
        slot: int,
        cooldown_seconds: float,
    ) -> None:
        async with self._lock:
            state = self._get(slot)

            state.cooldown_until = max(
                state.cooldown_until,
                time.monotonic()
                + max(
                    cooldown_seconds,
                    0.0,
                ),
            )

            state.failure_count += 1

    async def disable(
        self,
        slot: int,
    ) -> None:
        async with self._lock:
            state = self._get(slot)

            state.disabled = True
            state.failure_count += 1

    async def mark_success(
        self,
        slot: int,
    ) -> None:
        async with self._lock:
            state = self._get(slot)

            state.failure_count = 0

            # Do not clear another explicit cooldown if
            # the state was changed by another request.
            if state.cooldown_until <= time.monotonic():
                state.cooldown_until = 0.0

    async def status(self) -> list[dict[str, object]]:
        """
        Safe diagnostic state.

        Never returns actual API keys.
        """

        async with self._lock:
            now = time.monotonic()

            return [
                {
                    "slot": state.slot,
                    "available": (
                        not state.disabled
                        and state.cooldown_until <= now
                    ),
                    "disabled": state.disabled,
                    "cooldown_remaining": max(
                        0.0,
                        state.cooldown_until - now,
                    ),
                    "failure_count": state.failure_count,
                }
                for state in self._states
            ]

    def _get(
        self,
        slot: int,
    ) -> KeyState:
        for state in self._states:
            if state.slot == slot:
                return state

        raise ValueError(
            f"Unknown Groq key slot: {slot}"
        )

    def _earliest_retry(
        self,
        excluded_slots: set[int],
    ) -> float | None:
        now = time.monotonic()

        candidates = []

        for state in self._states:
            if state.slot in excluded_slots:
                continue

            if state.disabled:
                continue

            if state.cooldown_until > now:
                candidates.append(
                    state.cooldown_until - now
                )

        if not candidates:
            return None

        return min(candidates)