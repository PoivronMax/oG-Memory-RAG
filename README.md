# oG-Memory RAG MCP

An [MCP](https://modelcontextprotocol.io) server that gives any agent a
`search_kb` tool over a **remote** [oG-Memory](https://gitcode.com/Maxime_Hao/oG-Memory)
knowledge base.

Install this MCP, set two environment variables — `OGMEM_API_URL` and
`OGMEM_API_TOKEN` — and your agent can query the shared knowledge base
directly. **No local oG-Memory install, no vector DB, nothing else.** The
knowledge base runs on a server; this is just the thin client that connects
your agent to it.

```
agent (Claude Code / Cursor / …)
  └─ ogmem-rag-mcp  ──HTTP──►  oG-Memory server  (search_kb, token-gated)
        tool: search_kb            └─ vector + BM25 retrieval over the KB
```

## What the agent gets

One tool:

- **`search_kb(query, top_k=8, snippet_chars=1500, min_score=None, categories=None)`**
  — searches the KB and returns ranked hits. Each hit carries:
  `uri` (source/provenance), `score`, `category`, `abstract`, and a
  query-centered `snippet` (with a `truncated` flag). Results are precise
  excerpts, not whole-document dumps.

## Configure (the only two required variables)

| Variable | Required | Meaning |
|---|---|---|
| `OGMEM_API_URL` | ✅ | The KB server, e.g. `http://110.40.165.184:19532` |
| `OGMEM_API_TOKEN` | ✅ for shared servers | Team token, sent as the `X-KB-Token` header |
| `OGMEM_ACCOUNT_ID` | optional | KB account (default `compatibility-sdk-5.1.1`) |
| `OGMEM_USER_ID` | optional | Caller id recorded in retrieval signals |
| `OGMEM_TIMEOUT` | optional | Per-request seconds (default `60`) |

## Install & wire into your agent

No clone needed — `uvx` runs it straight from GitHub. Add an MCP server entry
to your host's config.

### Claude Code

`~/.claude.json` (or via `claude mcp add`), under `mcpServers`:

```json
{
  "mcpServers": {
    "ogmem-rag": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/PoivronMax/oG-Memory-RAG", "ogmem-rag-mcp"],
      "env": {
        "OGMEM_API_URL": "http://110.40.165.184:19532",
        "OGMEM_API_TOKEN": "<team-token>"
      }
    }
  }
}
```

Or one line:

```bash
claude mcp add ogmem-rag \
  --env OGMEM_API_URL=http://110.40.165.184:19532 \
  --env OGMEM_API_TOKEN=<team-token> \
  -- uvx --from git+https://github.com/PoivronMax/oG-Memory-RAG ogmem-rag-mcp
```

### Cursor / Windsurf / other MCP hosts

`.cursor/mcp.json` (or the host's equivalent) — same shape:

```json
{
  "mcpServers": {
    "ogmem-rag": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/PoivronMax/oG-Memory-RAG", "ogmem-rag-mcp"],
      "env": {
        "OGMEM_API_URL": "http://110.40.165.184:19532",
        "OGMEM_API_TOKEN": "<team-token>"
      }
    }
  }
}
```

### Pinned install (offline / reproducible)

```bash
pip install git+https://github.com/PoivronMax/oG-Memory-RAG
# then in mcp config: "command": "ogmem-rag-mcp", "args": []
```

## Verify it can reach the server

```bash
OGMEM_API_URL=http://110.40.165.184:19532 OGMEM_API_TOKEN=<team-token> \
  uvx --from git+https://github.com/PoivronMax/oG-Memory-RAG ogmem-rag-mcp --check
# -> {"base_url": "...", "account_id": "compatibility-sdk-5.1.1", "health": {"status": "ok", ...}}
```

If `--check` prints `status: ok`, the tool is ready. A `403` means the token
is missing or wrong; a connection error means `OGMEM_API_URL` is unreachable
(check the address / that you're on a network that can reach it).

## How it talks to the server

- Calls only `POST /api/v1/call/search_kb` (retrieval) and `GET /api/v1/health`
  (probe) — both read-only and both whitelisted on the server's reverse proxy.
  No write path is exposed.
- Sends the token as `X-KB-Token`; ignores system proxy env vars so a
  corporate/local proxy won't hijack the direct call.
- Stateless: every call is independent; no session or memory is created on the
  server.

## Develop

```bash
uv venv && uv pip install -e ".[dev]"
pytest            # unit tests use httpx MockTransport, no live server needed
```

## Relationship to oG-Memory

The server side (ingestion, chunking, embedding, the `search_kb` endpoint)
lives in [oG-Memory](https://gitcode.com/Maxime_Hao/oG-Memory). This repo is
**only** the MCP client surface, deliberately kept standalone so it can be
installed anywhere without pulling in the full engine.
