"""MedWriter MCP Server — Streamable HTTP transport"""
import asyncio

from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

import config  # validates all env vars on import
from pubmed import search_pubmed as _pubmed_search
from veeva import search_veeva_auto as _veeva_search, get_session
from claude_client import draft_response as _draft


# ---------------------------------------------------------------------------
# MCP server
# ---------------------------------------------------------------------------

mcp = FastMCP(
    name="MedWriter",
    instructions=(
        "MedWriter searches PubMed and Veeva MedComms to help medical writers "
        "draft evidence-based responses. Use search_pubmed for peer-reviewed "
        "literature, search_veeva for internal regulatory/medical documents, "
        "and draft_medical_response to run the full pipeline."
    ),
    # Stateless mode: each request is self-contained (required for claude.ai connector)
    stateless_http=True,
    # Disable DNS rebinding protection so the server works behind ngrok/reverse proxies
    transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
)


@mcp.tool()
async def search_pubmed(query: str, max_results: int = 5) -> str:
    """
    Search PubMed for peer-reviewed medical literature.

    Args:
        query: Medical topic or question (e.g. "metformin HbA1c reduction type 2 diabetes")
        max_results: Maximum number of articles to return (1-20, default 5)

    Returns:
        Formatted list of articles with PMID, title, authors, year, and abstract.
    """
    articles = await asyncio.to_thread(_pubmed_search, query, max(1, min(max_results, 20)))
    if not articles:
        return "No PubMed articles found for this query."
    lines = [
        f"[PMID: {a['pmid']}]\n"
        f"Title: {a['title']}\n"
        f"Authors: {', '.join(a['authors'][:3])}{' et al.' if len(a['authors']) > 3 else ''}\n"
        f"Year: {a['year']}\n"
        f"Abstract: {a['abstract']}"
        for a in articles
    ]
    return "\n---\n".join(lines)


@mcp.tool()
async def search_veeva(query: str, max_results: int = 5) -> str:
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
        f"[Document: {d['document_number'] or d['id']}]\n"
        f"Title: {d['title']}\n"
        f"Summary: {d['summary'] or 'No summary available.'}"
        for d in docs
    ]
    return "\n---\n".join(lines)


@mcp.tool()
async def draft_medical_response(
    question: str,
    max_pubmed: int = 5,
    max_veeva: int = 5,
) -> str:
    """
    Run the full MedWriter pipeline: search PubMed + Veeva in parallel, then
    draft a synthesized, cited medical information response using Claude.

    Args:
        question: The medical question from the healthcare professional
        max_pubmed: Max PubMed articles to retrieve (default 5)
        max_veeva: Max Veeva documents to retrieve (default 5)

    Returns:
        A fully drafted, evidence-based medical information response with citations.
    """
    import logging; _log = logging.getLogger(__name__)
    p = max(1, min(max_pubmed, 20))
    v = max(1, min(max_veeva, 20))
    _log.warning("draft_medical_response called: question=%r p=%d v=%d", question, p, v)

    articles, docs = await asyncio.gather(
        asyncio.to_thread(_pubmed_search, question, p),
        asyncio.to_thread(_veeva_search, question, v),
        return_exceptions=True,
    )
    _log.warning("gather done: articles=%r docs=%r", articles, docs)

    if isinstance(articles, Exception):
        import logging; logging.getLogger(__name__).error("PubMed error: %s", articles)
        articles = []
    if isinstance(docs, Exception):
        import logging; logging.getLogger(__name__).error("Veeva error: %s", docs)
        docs = []

    if not articles and not docs:
        return "Could not retrieve literature from PubMed or Veeva. Please try again."

    try:
        return await asyncio.to_thread(_draft, question, articles, docs)
    except Exception as exc:
        import logging; logging.getLogger(__name__).error("Draft error: %s", exc, exc_info=True)
        raise


# ---------------------------------------------------------------------------
# Custom route handlers (health + bootstrap)
# ---------------------------------------------------------------------------

async def health(request: Request) -> JSONResponse:
    return JSONResponse({"status": "ok", "server": "MedWriter MCP"})


async def bootstrap(request: Request) -> JSONResponse:
    """
    Enterprise Claude for Word bootstrap endpoint.
    Point the Word add-in manifest bootstrap URL here; it returns the MCP server
    config so users receive the connector automatically without manual setup.
    """
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

# Build the MCP Starlette app (initialises the session manager, registers /mcp route)
app = mcp.streamable_http_app()

# Add health and bootstrap routes directly to the existing Starlette router
app.router.routes.extend([
    Route("/health", health, methods=["GET"]),
    Route("/bootstrap", bootstrap, methods=["GET"]),
])

# Wrap with CORS middleware (claude.ai and Claude for Word origins)
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
