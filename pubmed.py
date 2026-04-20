import requests
import xml.etree.ElementTree as ET
from config import PUBMED_API_KEY

ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"


def search_pubmed(query: str, max_results: int = 5) -> list[dict]:
    pmids = _esearch(query, max_results)
    if not pmids:
        return []
    return _efetch(pmids)


def _esearch(query: str, max_results: int) -> list[str]:
    resp = requests.get(ESEARCH_URL, params={
        "db": "pubmed",
        "term": query,
        "retmax": max_results,
        "retmode": "json",
        "api_key": PUBMED_API_KEY,
    }, timeout=15)
    resp.raise_for_status()
    return resp.json().get("esearchresult", {}).get("idlist", [])


def _efetch(pmids: list[str]) -> list[dict]:
    resp = requests.get(EFETCH_URL, params={
        "db": "pubmed",
        "id": ",".join(pmids),
        "retmode": "xml",
        "rettype": "abstract",
        "api_key": PUBMED_API_KEY,
    }, timeout=20)
    resp.raise_for_status()

    root = ET.fromstring(resp.text)
    articles = []
    for article in root.findall(".//PubmedArticle"):
        articles.append(_parse_article(article))
    return articles


def _parse_article(article: ET.Element) -> dict:
    pmid = article.findtext(".//PMID") or ""
    title = article.findtext(".//ArticleTitle") or ""

    authors = []
    for author in article.findall(".//Author"):
        last = author.findtext("LastName") or ""
        fore = author.findtext("ForeName") or ""
        if last:
            authors.append(f"{last} {fore}".strip())

    year = (
        article.findtext(".//PubDate/Year")
        or article.findtext(".//PubDate/MedlineDate", "")[:4]
    )

    abstract_parts = [
        (t.get("Label") + ": " if t.get("Label") else "") + (t.text or "")
        for t in article.findall(".//AbstractText")
    ]
    abstract = " ".join(abstract_parts).strip()

    return {
        "pmid": pmid,
        "title": title,
        "authors": authors,
        "year": year,
        "abstract": abstract,
    }
