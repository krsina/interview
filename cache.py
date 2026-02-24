import threading
import time
import uuid
from typing import Any

from config import settings

# Key: (flag_id, user_id) as tuple; value: (expiry_ts, result_dict)
_cache: dict[tuple[uuid.UUID, str], tuple[float, dict[str, Any]]] = {}
_lock = threading.Lock()
_max_size = settings.cache_max_size
_ttl = settings.cache_ttl_seconds


def _make_key(flag_id: uuid.UUID, user_id: str) -> tuple[uuid.UUID, str]:
    return (flag_id, user_id)


def _is_expired(expiry_ts: float) -> bool:
    return time.monotonic() > expiry_ts


def get(flag_id: uuid.UUID, user_id: str) -> dict[str, Any] | None:
    key = _make_key(flag_id, user_id)
    with _lock:
        entry = _cache.get(key)
        if entry is None:
            return None
        expiry_ts, result = entry
        if _is_expired(expiry_ts):
            del _cache[key]
            return None
        return result


def set_result(flag_id: uuid.UUID, user_id: str, result: dict[str, Any]) -> None:
    key = _make_key(flag_id, user_id)
    expiry_ts = time.monotonic() + _ttl
    with _lock:
        if len(_cache) >= _max_size and key not in _cache:
            # Evict one expired entry if any, else skip set (or evict oldest)
            for k, (exp, _) in list(_cache.items()):
                if _is_expired(exp):
                    del _cache[k]
                    break
            else:
                # No expired; evict arbitrary (first key)
                if _cache and key not in _cache:
                    _cache.pop(next(iter(_cache)))
        _cache[key] = (expiry_ts, result)


def invalidate_override(flag_id: uuid.UUID, user_id: str) -> None:
    key = _make_key(flag_id, user_id)
    with _lock:
        _cache.pop(key, None)


def invalidate_flag(flag_id: uuid.UUID) -> None:
    with _lock:
        to_remove = [k for k in _cache if k[0] == flag_id]
        for k in to_remove:
            del _cache[k]
