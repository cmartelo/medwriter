# MedWriter: AI-Powered Scientific & Medical Authoring

MedWriter is a specialized orchestration platform designed for scientific and medical writers within the pharmaceutical and medical device industries. It bridges the gap between massive medical literature repositories, advanced Large Language Models (LLMs), and industry-standard authoring tools.

## Overview

MedWriter streamlines the complex workflow of medical writing by automating literature research and drafting. It allows writers to generate high-quality, evidence-based content with automated citations, ensuring that every claim is backed by a verifiable source.

## Key Features

* **Integrated Research:** Conducts deep-dive searches across clinical and academic databases.
* **AI-Assisted Authoring:** Connects to world-class LLMs (Claude, Gemini, GPT-4) to help draft, refine, and summarize medical content.
* **Direct Integration:** Seamlessly works with Microsoft Word and PowerPoint for direct content generation.
* **Evidence-Based:** Automatically handles citations and references to maintain scientific integrity.

## Supported Literature Sources

MedWriter integrates with both public and proprietary data sources:

* **Veeva Vault:** Direct access to MedComms documents and Scientific Communication Platforms (SCP).
* **Academic Databases:** PubMed, Google Scholar, and Elsevier.
* **Global Repositories:** Access to various medical libraries and regulatory documentation.

## User Personas & Use Cases

MedWriter is built for **Scientific and Medical Writers** who need to produce:

* **Field Medical Slide Decks:** Engaging and accurate visuals for Medical Science Liaisons (MSLs).
* **Payor Documents:** Value dossiers and reimbursement arguments for market access.
* **Journal Articles & Congress Posters:** Publication-ready research summaries and abstracts.
* **Standard Responses:** Consistent and compliant answers for Medical Information (MedInfo) inquiries.

## Target Customers

Our primary clients include:
* Global Pharmaceutical Companies
* Biotechnology Firms
* Medical Device Manufacturers
* Contract Research Organizations (CROs)

## Architecture

```
Claude (claude.ai or Claude for Word)
        │  HTTPS  /mcp  (Streamable HTTP, stateless)
        ▼
  server.py  — FastMCP + Starlette
        │
        └─ veeva.py  → Veeva Vault REST API  (session cached 25 min)
```

## MCP Tools

| Tool | Description |
|------|-------------|
| `search_veeva_documents` | Full-text search across Vault documents using VQL FIND(). Returns id, name, document_number, version, and a direct Vault URL. |
| `get_veeva_document_content` | Retrieves plain text of a document via the Vault "Retrieve Document Version Text" endpoint (v26.1). Takes document id + version numbers from search results. |

## Key Files

| File | Purpose |
|------|---------|
| `server.py` | FastMCP server. Defines MCP tools, CORS, health and bootstrap endpoints. |
| `veeva.py` | Veeva Vault integration. Auth, VQL search, keyword extraction, document text retrieval. Session cached with threading.Lock. |
| `config.py` | Loads and validates all required env vars from `.env` on import. |
| `main.py` | Original CLI entry point (still works for local testing). |
| `claude_client.py` | Claude API draft response logic (inactive in server, kept for CLI). |
| `pubmed.py` | PubMed NCBI search (inactive in server, kept for CLI). |

## Starting the Server

```bash
# Start MCP server (port 8000)
.venv/Scripts/python.exe -m uvicorn server:app --host 0.0.0.0 --port 8000 --forwarded-allow-ips='*' --proxy-headers

# Expose via ngrok (separate terminal)
ngrok http 8000
```

Connector URL for claude.ai: `https://<ngrok-id>.ngrok-free.app/mcp`

## Environment Variables (.env)

```
ANTHROPIC_API_KEY=...
PUBMED_API_KEY=...
VEEVA_VAULT_URL=https://<vault>.vaultdev.com
VEEVA_USERNAME=...
VEEVA_PASSWORD=...
```

## Veeva Notes

- API version: `v26.1` (required for the document text endpoint)
- Session TTL: 25 minutes (Vault sessions expire at 30 min)
- Search queries are pre-processed to extract keywords before passing to VQL `FIND()` — avoids 0-result responses when Claude passes full natural-language questions
- Document Vault URL format: `{VEEVA_VAULT_URL}/ui/#doc_info/{doc_id}`
- The `search_veeva` function in `veeva.py` uses `major_version_number__v` / `minor_version_number__v` from the VQL response to construct the correct text endpoint URL
