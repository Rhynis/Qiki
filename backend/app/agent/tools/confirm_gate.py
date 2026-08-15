"""Redis-backed pending-confirmation store for ``requires_confirm`` tools.

Generalizes ``AdminChatService``'s "plan -> stash a one-time token in Redis ->
confirm re-validates + claims atomically" pattern
(``backend/app/services/admin_chat_service.py``) so ANY ``requires_confirm``
tool call gets it for free, instead of writing a bespoke Redis-token protocol
per tool the way ``AdminChatService`` did for product mutations.

Deterministic tokens, not ``uuid4()``: LangGraph's ``interrupt()`` re-executes
the WHOLE node from its first line on resume (see
``agent/nodes/tool_executor.py``, and the empirical check in this PR's
description), so the code that stores the pending record runs again on every
resume, before ``interrupt()`` short-circuits with the cached resume value. A
random token would mint a fresh, orphaned Redis key on every resume; a token
derived from the (session, user, tool name, args) tuple converges on the SAME
key across re-executions, so the store call becomes an idempotent "upsert
this pending record and refresh its TTL" instead of leaking keys.

``user_id`` is part of that tuple, not just a field inside the stored
payload: two different users who happen to trigger the identical (session,
tool, args) -- e.g. a client-supplied ``session_id`` a second caller also
knows or guesses -- must NOT derive the same token, or the second caller's
``store_pending`` upsert would silently overwrite the first's pending record
with their own ``user_id``, defeating the "token is scoped to the creating
user" check in ``claim_pending``'s caller before it ever runs.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from redis.asyncio import Redis

PENDING_KEY_PREFIX = "agent_tool:pending:"
PENDING_TTL_SECONDS = 300  # Mirrors AdminChatService.PENDING_TTL_SECONDS.


def derive_pending_token(
    *, session_id: str, user_id: str, tool_name: str, args: dict[str, Any]
) -> str:
    """A stable, opaque token identifying one (session, user, tool, args) tuple.

    Not a secret and not meant to be unguessable to the SAME caller who
    already supplied ``args`` (they're about to see them in the confirm
    prompt) -- its job is letting ``claim_pending`` re-validate that a
    confirm decision is being applied to the exact call it was issued for,
    the same role ``AdminChatService``'s ``before_snapshot`` check plays.
    """
    canonical_args = json.dumps(args, sort_keys=True, default=str)
    digest = hashlib.sha256(
        f"{session_id}:{user_id}:{tool_name}:{canonical_args}".encode()
    ).hexdigest()
    return digest[:32]


class ToolConfirmGate:
    """Store/claim the pending-confirmation record for one tool call."""

    def __init__(self, redis: Redis) -> None:
        self.redis = redis

    @staticmethod
    def _key(token: str) -> str:
        return f"{PENDING_KEY_PREFIX}{token}"

    async def store_pending(
        self,
        *,
        token: str,
        user_id: str,
        tool_name: str,
        args: dict[str, Any],
        before_snapshot: dict[str, Any],
    ) -> None:
        """Upsert the pending record, (re)starting its TTL."""
        payload: dict[str, Any] = {
            "user_id": user_id,
            "tool_name": tool_name,
            "args": args,
            "before_snapshot": before_snapshot,
        }
        await self.redis.setex(self._key(token), PENDING_TTL_SECONDS, json.dumps(payload))

    async def claim_pending(self, token: str) -> dict[str, Any] | None:
        """Atomically read+delete the pending record (GETDEL); None if expired/unknown.

        Mirrors ``AdminChatService._execute_pending``'s GETDEL claim: two
        racing confirms for the same token can't both succeed, because only
        the first GETDEL sees a non-None value.
        """
        raw = await self.redis.getdel(self._key(token))
        if raw is None:
            return None
        payload: dict[str, Any] = json.loads(raw)
        return payload
