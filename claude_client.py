import anthropic
from config import ANTHROPIC_API_KEY

_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
MODEL = "claude-sonnet-4-6"


def draft_response(
    question: str,
    pubmed_articles: list[dict],
    veeva_docs: list[dict],
) -> str:
    literature_block = _build_literature_block(pubmed_articles, veeva_docs)
    system_prompt = (
        "You are a medical information specialist. Your role is to draft accurate, "
        "evidence-based responses to medical questions for healthcare professionals. "
        "Always cite specific sources by PMID or document number. "
        "Use clear, professional medical language."
    )
    user_message = (
        f"A healthcare professional has submitted the following question:\n\n"
        f"QUESTION: {question}\n\n"
        f"{literature_block}\n\n"
        "Draft a concise, accurate medical information response that:\n"
        "1. Directly answers the question\n"
        "2. Cites specific supporting literature (by PMID or Veeva document number)\n"
        "3. Notes any limitations or gaps in the evidence\n"
        "4. Uses professional medical language appropriate for HCP audiences"
    )

    response = _client.messages.create(
        model=MODEL,
        max_tokens=2000,
        system=system_prompt,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": user_message,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
            }
        ],
    )
    return response.content[0].text


def _build_literature_block(pubmed_articles: list[dict], veeva_docs: list[dict]) -> str:
    sections = []

    if pubmed_articles:
        lines = ["=== PubMed Literature ==="]
        for art in pubmed_articles:
            authors_str = ", ".join(art["authors"][:3])
            if len(art["authors"]) > 3:
                authors_str += " et al."
            lines.append(
                f"\n[PMID: {art['pmid']}]\n"
                f"Title: {art['title']}\n"
                f"Authors: {authors_str}\n"
                f"Year: {art['year']}\n"
                f"Abstract: {art['abstract']}"
            )
        sections.append("\n".join(lines))
    else:
        sections.append("=== PubMed Literature ===\nNo articles retrieved.")

    if veeva_docs:
        lines = ["=== Veeva MedComms Documents ==="]
        for doc in veeva_docs:
            lines.append(
                f"\n[Document: {doc['document_number'] or doc['id']}]\n"
                f"Title: {doc['title']}\n"
                f"Summary: {doc['summary'] or 'No summary available.'}"
            )
        sections.append("\n".join(lines))
    else:
        sections.append("=== Veeva MedComms Documents ===\nNo documents retrieved.")

    return "\n\n".join(sections)
