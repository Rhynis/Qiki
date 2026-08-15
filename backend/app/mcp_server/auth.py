"""Bearer-token verifier for the MCP resource-server auth mode.

Reuses Qiki's existing JWT/session verification (``AuthService.verify_token``
— the same check ``get_current_user`` relies on for the REST API,
app/api/v1/dependencies/auth.py) instead of building a separate OAuth
issuer. FastMCP calls ``verify_token()`` once per incoming MCP request's
``Authorization`` header; returning ``None`` (rather than raising) tells
FastMCP's bearer-auth middleware to reject the request with 401 — see
docs/mcp.md and tests/mcp/test_server.py.
"""

from functools import lru_cache
from typing import cast

from fastmcp.server.auth import AccessToken, TokenVerifier
from redis.asyncio import Redis

from app.core.config import get_settings
from app.core.exceptions import GasBotException
from app.db.session import AsyncSessionLocal
from app.repositories.user_repository import UserRepository
from app.services.auth_service import AuthService


@lru_cache(maxsize=1)
def _verifier_redis_client() -> Redis:
    """A small, dedicated Redis client for the MCP auth verifier.

    The MCP ASGI sub-app is built at FastAPI route-registration time
    (``app.mcp_server.server.create_mcp_server``, called from
    ``app.main.create_app``), before ``app.state.redis`` exists — that is
    only set once ``app.main.lifespan`` actually runs. So this verifier owns
    a lightweight client of its own (used only for the access-token
    blacklist check inside ``AuthService.verify_token``) rather than reaching
    into ``app.state`` at call time.
    """
    return cast(Redis, Redis.from_url(get_settings().REDIS_URL, decode_responses=True))


class QikiTokenVerifier(TokenVerifier):
    """Validate an MCP client's bearer token against Qiki's own login session.

    This is a "resource server" verifier only (the MCP authorization spec's
    term for validating tokens issued elsewhere): it checks a token issued by
    Qiki's own ``POST /api/v1/auth/login``, exactly as ``get_current_user``
    does for the REST API — same blacklist check, same inactive-user check.
    It does not implement or advertise a new OAuth 2.1 authorization server
    (no ``/authorize``, ``/token``, or dynamic client registration routes):
    Qiki already issues these access tokens itself. See docs/mcp.md for how
    a reviewer obtains one to test against a live server.

    Any authenticated Qiki user (customer, staff, or admin) may call the MCP
    tools — they are read-only and mirror data already reachable through
    Qiki's public storefront and anonymous chat endpoints (see docs/mcp.md
    "Why these tools don't need role-gating").
    """

    async def verify_token(self, token: str) -> AccessToken | None:
        """Return access info for a valid token, or None to refuse the call."""
        async with AsyncSessionLocal() as session:
            auth_service = AuthService(UserRepository(session), _verifier_redis_client())
            try:
                user = await auth_service.verify_token(token)
            except GasBotException:
                return None

        return AccessToken(
            token=token,
            client_id=str(user.id),
            scopes=[],
            subject=str(user.id),
            claims={"role": user.role},
        )
