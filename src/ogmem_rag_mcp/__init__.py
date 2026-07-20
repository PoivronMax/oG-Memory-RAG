"""oG-Memory RAG MCP — a read-only MCP server over a remote oG-Memory KB."""

from ogmem_rag_mcp.client import KBClient, KBClientError

__all__ = ["KBClient", "KBClientError"]
__version__ = "0.1.0"
