"""Unit tests for KBClient — no live server, using httpx MockTransport."""

from __future__ import annotations

import json

import httpx
import pytest

from ogmem_rag_mcp.client import DEFAULT_ACCOUNT_ID, KBClient, KBClientError


def _client_with(handler, **kw) -> KBClient:
    c = KBClient(base_url="http://kb.test:19532", api_token="tok", **kw)
    c._client = httpx.Client(
        base_url=c.base_url, headers=c._headers(), transport=httpx.MockTransport(handler)
    )
    return c


def test_from_env_requires_url():
    with pytest.raises(KBClientError, match="OGMEM_API_URL"):
        KBClient.from_env({})


def test_from_env_maps_the_two_vars_and_defaults_account():
    c = KBClient.from_env({"OGMEM_API_URL": "http://x:1/", "OGMEM_API_TOKEN": "t"})
    assert c.base_url == "http://x:1"  # trailing slash stripped
    assert c.api_token == "t"
    assert c.account_id == DEFAULT_ACCOUNT_ID
    assert c._headers()["X-KB-Token"] == "t"


def test_account_override():
    c = KBClient.from_env({"OGMEM_API_URL": "http://x:1", "OGMEM_ACCOUNT_ID": "other"})
    assert c.account_id == "other"
    assert "X-KB-Token" not in c._headers()  # no token set


def test_search_kb_sends_expected_body_and_returns_hits():
    seen = {}

    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/api/v1/call/search_kb"
        assert req.headers["X-KB-Token"] == "tok"
        seen["body"] = json.loads(req.content)
        return httpx.Response(200, json={"query": "q", "hits": [{"uri": "ctx://a", "score": 0.5, "snippet": "s"}], "stats": {}})

    c = _client_with(handler, account_id="acct-x")
    out = c.search_kb("AbilityStage onCreate", top_k=3, snippet_chars=800)
    assert out["hits"][0]["uri"] == "ctx://a"
    assert seen["body"] == {
        "userId": "ogmem-rag-mcp",
        "sessionId": "ogmem-rag-mcp",
        "account_id": "acct-x",
        "query": "AbilityStage onCreate",
        "top_k": 3,
        "snippet_chars": 800,
    }


def test_empty_query_rejected():
    c = _client_with(lambda r: httpx.Response(200, json={}))
    with pytest.raises(KBClientError, match="query must not be empty"):
        c.search_kb("   ")


def test_403_gives_token_hint():
    c = _client_with(lambda r: httpx.Response(403, json={"error": "forbidden"}))
    with pytest.raises(KBClientError, match="OGMEM_API_TOKEN"):
        c.search_kb("x")


def test_optional_params_included_only_when_set():
    seen = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(req.content)
        return httpx.Response(200, json={"hits": []})

    c = _client_with(handler)
    c.search_kb("x", min_score=0.4, categories=["resource"])
    assert seen["body"]["min_score"] == 0.4
    assert seen["body"]["categories"] == ["resource"]
