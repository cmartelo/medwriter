"""MedWriter MCP Server — Streamable HTTP transport"""
import asyncio

from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

import config  # validates all env vars on import
from veeva import search_veeva_auto as _veeva_search, get_session, get_document_content as _get_content


# ---------------------------------------------------------------------------
# MCP server
# ---------------------------------------------------------------------------

mcp = FastMCP(
    name="MedWriter",
    instructions=(
        "MedWriter searches Veeva MedComms Vault for internal medical/regulatory "
        "documents and records. Use search_veeva_documents to find documents and "
        "search_veeva_records to find object records."
    ),
    # Stateless mode: each request is self-contained (required for claude.ai connector)
    stateless_http=True,
    # Disable DNS rebinding protection so the server works behind ngrok/reverse proxies
    transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
)


@mcp.tool()
async def search_veeva_documents(query: str, max_results: int = 5) -> str:
    """
    Search Veeva MedComms Vault for internal medical/regulatory documents.

    Args:
        query: Search terms (e.g. "Natevba prescribing information dosage")
        max_results: Maximum number of documents to return (1-20, default 5)

    Returns:
        Formatted list of Veeva documents with document number, title, and summary.
    """
    docs = await asyncio.to_thread(_veeva_search, query, max(1, min(max_results, 20)))
    if not docs:
        return "No Veeva documents found for this query."
    lines = [
        f"[Document: {d['document_number'] or d['id']}] (id={d['id']}, v{d['major_version']}.{d['minor_version']})\n"
        f"Name: {d['name']}\n"
        f"Link: {d['url']}"
        for d in docs
    ]
    return "\n---\n".join(lines)


@mcp.tool()
async def get_veeva_document_content(document_id: int, major_version: int = 1, minor_version: int = 0) -> str:
    """
    Retrieve the full text content of a Veeva Vault document.

    Args:
        document_id: The numeric Vault document ID (from search_veeva_documents results)
        major_version: Major version number (from search results, default 1)
        minor_version: Minor version number (from search results, default 0)

    Returns:
        Full plain-text content of the document.
    """
    content = await asyncio.to_thread(_get_content, document_id, major_version, minor_version)
    if not content:
        return "Document has no extractable text content."
    return content


# ---------------------------------------------------------------------------
# Custom route handlers (health + bootstrap)
# ---------------------------------------------------------------------------

async def health(request: Request) -> JSONResponse:
    return JSONResponse({"status": "ok", "server": "MedWriter MCP"})


async def bootstrap(request: Request) -> JSONResponse:
    base = str(request.base_url).rstrip("/")
    return JSONResponse({
        "mcp_servers": [
            {
                "url": f"{base}/mcp",
                "label": "MedWriter",
            }
        ]
    })


# ---------------------------------------------------------------------------
# App assembly
# ---------------------------------------------------------------------------

app = mcp.streamable_http_app()

app.router.routes.extend([
    Route("/health", health, methods=["GET"]),
    Route("/bootstrap", bootstrap, methods=["GET"]),
])

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://pivot.claude.ai", "https://claude.ai"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
    allow_credentials=False,
)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000)
