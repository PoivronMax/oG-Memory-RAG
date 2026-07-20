"""HTTP client for a remote oG-Memory knowledge-base server.

Talks to the read-only retrieval endpoint (`/api/v1/call/search_kb`) exposed
by an oG-Memory deployment behind a token-gated reverse proxy. Kept free of
any MCP SDK import so it can be unit-tested and reused without the optional
`mcp` dependency installed.

Configuration is entirely environment-driven — the only two variables a user
must set are OGMEM_API_URL and OGMEM_API_TOKEN.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

import httpx

DEFAULT_TIMEOUT = 60.0
DEFAULT_USER_ID = "ogmem-rag-mcp"
# The client is a stateless read-only surface, so all calls share one nominal
# session rather than fabricating one per call.
SESSION_ID = "ogmem-rag-mcp"
# The shared Cangjie KB account on the reference deployment. Override with
# OGMEM_ACCOUNT_ID to point at a different account on the same server.
DEFAULT_ACCOUNT_ID = "compatibility-sdk-5.1.1"


class KBClientError(RuntimeError):
    """Remote server returned an error or an unusable payload."""


@dataclass
class KBClient:
    """Thin HTTP client over an oG-Memory server's search_kb endpoint."""

    base_url: str
    api_token: str | None = None
    account_id: str = DEFAULT_ACCOUNT_ID
    user_id: str = DEFAULT_USER_ID
    timeout: float = DEFAULT_TIMEOUT
    _client: httpx.Client | None = field(default=None, repr=False)

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> "KBClient":
        """Build a client from environment variables.

        Required:
          OGMEM_API_URL     e.g. http://110.40.165.184:19532
        Optional:
          OGMEM_API_TOKEN   team token; sent as the X-KB-Token header
          OGMEM_ACCOUNT_ID  KB account (default: compatibility-sdk-5.1.1)
          OGMEM_USER_ID     caller id recorded in retrieval signals
          OGMEM_TIMEOUT     per-request timeout seconds (default: 60)
        """
        env = env if env is not None else dict(os.environ)
        base_url = (env.get("OGMEM_API_URL") or "").strip().rstrip("/")
        if not base_url:
            raise KBClientError(
                "OGMEM_API_URL is not set — point it at the oG-Memory KB server, "
                "e.g. http://110.40.165.184:19532"
            )
        try:
            timeout = float(env.get("OGMEM_TIMEOUT", "") or DEFAULT_TIMEOUT)
        except ValueError:
            timeout = DEFAULT_TIMEOUT
        return cls(
            base_url=base_url,
            api_token=(env.get("OGMEM_API_TOKEN") or "").strip() or None,
            account_id=(env.get("OGMEM_ACCOUNT_ID") or "").strip() or DEFAULT_ACCOUNT_ID,
            user_id=(env.get("OGMEM_USER_ID") or "").strip() or DEFAULT_USER_ID,
            timeout=timeout,
        )

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_token:
            headers["X-KB-Token"] = self.api_token
        return headers

    def _http(self) -> httpx.Client:
        if self._client is None:
            # trust_env=False: ignore proxy env vars so a corporate/clash proxy
            # doesn't hijack the direct call to the KB server.
            self._client = httpx.Client(
                base_url=self.base_url,
                headers=self._headers(),
                timeout=self.timeout,
                trust_env=False,
            )
        return self._client

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None

    @staticmethod
    def _parse(resp: httpx.Response) -> object:
        try:
            payload = resp.json()
        except ValueError as exc:
            raise KBClientError(
                f"non-JSON response (HTTP {resp.status_code}) from {resp.request.url} — "
                "check OGMEM_API_URL and that the endpoint is whitelisted on the proxy"
            ) from exc
        if resp.status_code >= 400:
            detail = payload.get("error") if isinstance(payload, dict) else payload
            hint = ""
            if resp.status_code == 403:
                hint = " (403 — missing/wrong OGMEM_API_TOKEN?)"
            raise KBClientError(f"HTTP {resp.status_code}: {detail}{hint}")
        return payload

    def search_kb(
        self,
        query: str,
        top_k: int = 8,
        snippet_chars: int = 1500,
        min_score: float | None = None,
        categories: list[str] | None = None,
    ) -> dict:
        """Query the KB, returning structured ranked hits (no LLM synthesis)."""
        if not (query or "").strip():
            raise KBClientError("query must not be empty")
        body: dict = {
            "userId": self.user_id,
            "sessionId": SESSION_ID,
            "account_id": self.account_id,
            "query": query,
            "top_k": top_k,
            "snippet_chars": snippet_chars,
        }
        if min_score is not None:
            body["min_score"] = min_score
        if categories:
            body["categories"] = categories
        payload = self._parse(self._http().post("/api/v1/call/search_kb", json=body))
        if not isinstance(payload, dict):
            raise KBClientError(f"unexpected search_kb payload: {type(payload).__name__}")
        return payload

    def health(self) -> dict:
        """Probe the server's health endpoint."""
        payload = self._parse(self._http().get("/api/v1/health"))
        return payload if isinstance(payload, dict) else {"raw": payload}
