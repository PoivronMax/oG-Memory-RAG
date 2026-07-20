# oG-Memory RAG MCP

[![PyPI](https://img.shields.io/pypi/v/ogmem-rag-mcp.svg)](https://pypi.org/project/ogmem-rag-mcp/)
[![CI](https://github.com/PoivronMax/oG-Memory-RAG/actions/workflows/ci.yml/badge.svg)](https://github.com/PoivronMax/oG-Memory-RAG/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

An [MCP](https://modelcontextprotocol.io) server that gives any agent a
`search_kb` tool over a **remote** [oG-Memory](https://gitcode.com/Maxime_Hao/oG-Memory)
knowledge base.

Install this MCP, set two environment variables — `OGMEM_API_URL` and
`OGMEM_API_TOKEN` — and your agent can query the shared knowledge base
directly. **No local oG-Memory install, no vector DB, nothing else.** The
knowledge base runs on a server; this is just the thin client that connects
your agent to it.

```
agent (Claude Code / Cursor / VS Code / …)
  └─ ogmem-rag-mcp  ──HTTP──►  oG-Memory server  (search_kb, token-gated)
        tool: search_kb            └─ vector + BM25 retrieval over the KB
```

## Requirements

- [`uv`](https://docs.astral.sh/uv/) on PATH (provides `uvx`). Nothing else —
  `uvx` fetches and runs the server on demand.
- An oG-Memory KB server URL and its team token (ask your admin).

## Configuration (the only two you must set)

| Variable | Required | Meaning |
|---|---|---|
| `OGMEM_API_URL` | ✅ | The KB server, e.g. `http://110.40.165.184:19532` |
| `OGMEM_API_TOKEN` | ✅ for shared servers | Team token, sent as the `X-KB-Token` header |
| `OGMEM_ACCOUNT_ID` | optional | KB account (default `compatibility-sdk-5.1.1`) |
| `OGMEM_USER_ID` | optional | Caller id recorded in retrieval signals |
| `OGMEM_TIMEOUT` | optional | Per-request seconds (default `60`) |

---

## Install

Every host uses the same command — `uvx ogmem-rag-mcp` — with the two env vars.
Pick your host below.

### Cursor

[![Add to Cursor](https://img.shields.io/badge/Add%20to-Cursor-000?logo=cursor)](https://cursor.com/install-mcp?name=ogmem-rag&config=eyJjb21tYW5kIjogInV2eCIsICJhcmdzIjogWyJvZ21lbS1yYWctbWNwIl0sICJlbnYiOiB7Ik9HTUVNX0FQSV9VUkwiOiAiaHR0cDovLzExMC40MC4xNjUuMTg0OjE5NTMyIiwgIk9HTUVNX0FQSV9UT0tFTiI6ICI8dGVhbS10b2tlbj4ifX0=)

Click the button (then replace `<team-token>` in the installed entry), or add
to `~/.cursor/mcp.json` manually:

```json
{
  "mcpServers": {
    "ogmem-rag": {
      "command": "uvx",
      "args": ["ogmem-rag-mcp"],
      "env": {
        "OGMEM_API_URL": "http://110.40.165.184:19532",
        "OGMEM_API_TOKEN": "<team-token>"
      }
    }
  }
}
```

### Claude Code

One line:

```bash
claude mcp add ogmem-rag \
  --env OGMEM_API_URL=http://110.40.165.184:19532 \
  --env OGMEM_API_TOKEN=<team-token> \
  -- uvx ogmem-rag-mcp
```

### VS Code

[![Install in VS Code](https://img.shields.io/badge/Install-VS%20Code-007ACC?logo=visualstudiocode)](https://insiders.vscode.dev/redirect/mcp/install?name=ogmem-rag&config=%7B%22command%22%3A%20%22uvx%22%2C%20%22args%22%3A%20%5B%22ogmem-rag-mcp%22%5D%2C%20%22env%22%3A%20%7B%22OGMEM_API_URL%22%3A%20%22http%3A//110.40.165.184%3A19532%22%2C%20%22OGMEM_API_TOKEN%22%3A%20%22%24%7Binput%3Aogmem_token%7D%22%7D%7D)

Or add to `.vscode/mcp.json`:

```json
{
  "servers": {
    "ogmem-rag": {
      "command": "uvx",
      "args": ["ogmem-rag-mcp"],
      "env": {
        "OGMEM_API_URL": "http://110.40.165.184:19532",
        "OGMEM_API_TOKEN": "<team-token>"
      }
    }
  }
}
```

### Claude Desktop / Windsurf / Cline / Zed / any other MCP host

Same server entry in the host's MCP config file:

```json
{
  "mcpServers": {
    "ogmem-rag": {
      "command": "uvx",
      "args": ["ogmem-rag-mcp"],
      "env": {
        "OGMEM_API_URL": "http://110.40.165.184:19532",
        "OGMEM_API_TOKEN": "<team-token>"
      }
    }
  }
}
```

> **Before it's on PyPI**, replace `"args": ["ogmem-rag-mcp"]` with
> `"args": ["--from", "git+https://github.com/PoivronMax/oG-Memory-RAG", "ogmem-rag-mcp"]`
> to run straight from GitHub.

---

## Verify it can reach the server

```bash
OGMEM_API_URL=http://110.40.165.184:19532 OGMEM_API_TOKEN=<team-token> \
  uvx ogmem-rag-mcp --check
# -> {"base_url": "...", "account_id": "compatibility-sdk-5.1.1", "health": {"status": "ok", ...}}
```

`status: ok` → ready. `403` → missing/wrong token. Connection error →
`OGMEM_API_URL` unreachable (check the address / your network).

## The tool your agent gets

**`search_kb(query, top_k=8, snippet_chars=1500, min_score=None, categories=None)`**
— searches the KB and returns ranked hits. Each hit carries `uri`
(source/provenance), `score`, `category`, `abstract`, and a query-centered
`snippet` (with a `truncated` flag). Results are precise excerpts, not
whole-document dumps. When a hit looks right but its snippet is truncated,
search again with that document's distinctive terms and a larger
`snippet_chars` (up to 20000) to read deeper.

## How it talks to the server

- Calls only `POST /api/v1/call/search_kb` (retrieval) and `GET /api/v1/health`
  (probe) — both read-only and whitelisted on the server's reverse proxy. No
  write path is exposed.
- Sends the token as `X-KB-Token`; ignores system proxy env vars so a
  corporate/local proxy won't hijack the direct call.
- Stateless: every call is independent; nothing is created on the server.

## Develop

```bash
uv venv && uv pip install -e ".[dev]"
pytest            # unit tests use httpx MockTransport, no live server needed
```

## Publishing (maintainers)

Releases go to PyPI via **Trusted Publishing** (OIDC — no stored token). One-time:

1. On [PyPI](https://pypi.org/manage/account/publishing/), add a *pending*
   trusted publisher: project `ogmem-rag-mcp`, owner `PoivronMax`, repo
   `oG-Memory-RAG`, workflow `publish.yml`, environment `pypi`.
2. In the GitHub repo settings, create an environment named `pypi`.

Then each release is just:

```bash
# bump version in pyproject.toml + src/ogmem_rag_mcp/__init__.py, commit, then:
git tag v0.1.0 && git push origin v0.1.0
```

The `publish.yml` workflow builds and uploads automatically.

## Relationship to oG-Memory

The server side (ingestion, chunking, embedding, the `search_kb` endpoint)
lives in [oG-Memory](https://gitcode.com/Maxime_Hao/oG-Memory). This repo is
**only** the MCP client surface, kept standalone so it installs anywhere
without pulling in the full engine.
