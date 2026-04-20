import os
from dotenv import load_dotenv

load_dotenv()

def _require(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value

ANTHROPIC_API_KEY: str = _require("ANTHROPIC_API_KEY")
PUBMED_API_KEY: str = _require("PUBMED_API_KEY")
VEEVA_VAULT_URL: str = _require("VEEVA_VAULT_URL")
VEEVA_USERNAME: str = _require("VEEVA_USERNAME")
VEEVA_PASSWORD: str = _require("VEEVA_PASSWORD")
