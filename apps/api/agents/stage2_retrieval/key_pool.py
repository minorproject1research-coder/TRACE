# apps/api/agents/stage2_retrieval/key_pool.py
import itertools
import time


class KeyPool:
    def __init__(self, keys: list[str], cooldown_seconds: int = 60):
        keys = [k.strip() for k in keys if k.strip()]
        if not keys:
            raise ValueError("KeyPool needs at least one key")
        self._keys = keys
        self._cycle = itertools.cycle(keys)
        self._cooldown_until: dict[str, float] = {}
        self._cooldown_seconds = cooldown_seconds

    def get_key(self) -> str | None:
        """It tries one key; if that key is on cooldown, it moves to the next one — this is the rotation/fallback logic where, once one key reaches its limit, another key is used."""
        for _ in range(len(self._keys)):
            key = next(self._cycle)
            if time.time() >= self._cooldown_until.get(key, 0):
                return key
        return None 

    def mark_rate_limited(self, key: str):
        self._cooldown_until[key] = time.time() + self._cooldown_seconds