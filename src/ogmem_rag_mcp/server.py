"""MCP stdio server exposing a remote oG-Memory knowledge base for RAG.

Any MCP-capable agent (Claude Code, Cursor, …) that launches this server and
sets OGMEM_API_URL + OGMEM_API_TOKEN gets a `search_kb` tool to query the
shared knowledge base — no local install of oG-Memory, no vector DB, nothing
but two environment variables.

Run:  ogmem-rag-mcp            (stdio MCP server)
      ogmem-rag-mcp --check    (probe the server and exit)
"""

from __future__ import annotations

import argparse
import json
import sys

from ogmem_rag_mcp.client import KBClient, KBClientError

_INSTRUCTIONS = """\
Query a shared oG-Memory knowledge base (a remote RAG service).

Use `search_kb` for any question the knowledge base might answer. It returns
ranked hits, each with a source uri (provenance), a relevance score, a short
abstract, and a query-centered snippet. Results are precise excerpts, not a
whole-document dump — when a hit looks right but its snippet is truncated,
call search_kb again with distinctive terms from that document and a larger
snippet_chars (up to 20000) to read deeper. Prefer specific API/component
names in queries; overly broad terms return noise."""


def build_server(client: KBClient):
    from mcp.server.fastmcp import FastMCP

    mcp = FastMCP("ogmem-rag", instructions=_INSTRUCTIONS)

    @mcp.tool()
    def search_kb(
        query: str,
        top_k: int = 8,
        snippet_chars: int = 1500,
        min_score: float | None = None,
        categories: list[str] | None = None,
    ) -> dict:
        """Search the oG-Memory knowledge base and return ranked hits.

        Args:
            query: Natural-language question or keywords. Precise API/component
                names work best; avoid overly broad single words.
            top_k: Max hits to return (1-50, default 8).
            snippet_chars: Per-hit excerpt length (100-20000, default 1500).
                Raise it to read more of a promising document.
            min_score: Optional relevance floor.
            categories: Optional list of KB categories to restrict to.

        Returns a dict with `hits`: a list of {uri, score, category, abstract,
        snippet, truncated}. `truncated=true` means the source has more text —
        search again with that document's distinctive terms to read further.
        """
        return client.search_kb(
            query=query,
            top_k=top_k,
            snippet_chars=snippet_chars,
            min_score=min_score,
            categories=categories,
        )

    return mcp


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="ogmem-rag-mcp",
        description="MCP stdio server for a remote oG-Memory knowledge base",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="probe the remote server (health) and exit",
    )
    args = parser.parse_args()

    try:
        client = KBClient.from_env()
    except KBClientError as exc:
        print(f"ogmem-rag-mcp: {exc}", file=sys.stderr)
        return 2

    if args.check:
        try:
            health = client.health()
        except Exception as exc:  # noqa: BLE001 — CLI probe reports anything
            print(f"ogmem-rag-mcp: probe failed: {exc}", file=sys.stderr)
            return 1
        print(json.dumps(
            {"base_url": client.base_url, "account_id": client.account_id, "health": health},
            ensure_ascii=False,
        ))
        return 0

    build_server(client).run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
