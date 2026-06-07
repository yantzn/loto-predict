"""Deterministic seed helpers.

strategy名、対象回、history_limit、seed、ticket indexなどから安定した乱数seedを作ります。
同一条件の完全再現と、異なるseed/profileでの差異を両立するための共通部品です。
"""

from __future__ import annotations

import hashlib


def stable_seed(*parts: object) -> int:
    """Build a deterministic RNG seed from run context.

    Python's built-in hash is randomized per process, so strategy/ticket seeds
    must use a stable digest to keep backtests reproducible across executions.
    """
    text = "|".join(str(part) for part in parts)
    digest = hashlib.blake2b(text.encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(digest, byteorder="big", signed=False)
