import argparse
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

import config  # validates env vars on import
from pubmed import search_pubmed
from veeva import authenticate, search_veeva
from claude_client import draft_response


def main():
    parser = argparse.ArgumentParser(
        description="Draft a medical information response from PubMed and Veeva MedComms."
    )
    parser.add_argument("question", help="The medical question to answer")
    parser.add_argument("--max-pubmed", type=int, default=5, metavar="N",
                        help="Max PubMed articles to retrieve (default: 5)")
    parser.add_argument("--max-veeva", type=int, default=5, metavar="N",
                        help="Max Veeva documents to retrieve (default: 5)")
    parser.add_argument("--output", metavar="FILE",
                        help="Save the response to a file instead of stdout")
    args = parser.parse_args()

    print(f"Authenticating with Veeva Vault...", file=sys.stderr)
    try:
        session_id = authenticate()
    except Exception as e:
        print(f"Error: Veeva authentication failed — {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Searching PubMed and Veeva MedComms...", file=sys.stderr)
    pubmed_articles = []
    veeva_docs = []
    errors = []

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = {
            executor.submit(search_pubmed, args.question, args.max_pubmed): "pubmed",
            executor.submit(search_veeva, args.question, session_id, args.max_veeva): "veeva",
        }
        for future in as_completed(futures):
            source = futures[future]
            try:
                result = future.result()
                if source == "pubmed":
                    pubmed_articles = result
                    print(f"  PubMed: {len(result)} article(s) retrieved", file=sys.stderr)
                else:
                    veeva_docs = result
                    print(f"  Veeva:  {len(result)} document(s) retrieved", file=sys.stderr)
            except Exception as e:
                errors.append(f"{source}: {e}")
                print(f"  Warning — {source} search failed: {e}", file=sys.stderr)

    if not pubmed_articles and not veeva_docs:
        print("Error: No literature retrieved from either source. Cannot draft response.",
              file=sys.stderr)
        sys.exit(1)

    print("Drafting response with Claude...", file=sys.stderr)
    try:
        response = draft_response(args.question, pubmed_articles, veeva_docs)
    except Exception as e:
        print(f"Error: Claude API call failed — {e}", file=sys.stderr)
        sys.exit(1)

    output = _format_output(args.question, pubmed_articles, veeva_docs, response)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Response saved to {args.output}", file=sys.stderr)
    else:
        print(output)


def _format_output(
    question: str,
    pubmed_articles: list[dict],
    veeva_docs: list[dict],
    response: str,
) -> str:
    lines = [
        "=" * 72,
        "MEDICAL INFORMATION RESPONSE",
        "=" * 72,
        f"\nQUESTION:\n{question}\n",
        "-" * 72,
        "\nRESPONSE:\n",
        response,
        "\n" + "-" * 72,
        "\nSOURCES CONSULTED:",
    ]

    if pubmed_articles:
        lines.append("\nPubMed Articles:")
        for art in pubmed_articles:
            authors_str = ", ".join(art["authors"][:2])
            if len(art["authors"]) > 2:
                authors_str += " et al."
            lines.append(f"  [{art['pmid']}] {art['title']} — {authors_str} ({art['year']})")

    if veeva_docs:
        lines.append("\nVeeva MedComms Documents:")
        for doc in veeva_docs:
            ref = doc["document_number"] or doc["id"]
            lines.append(f"  [{ref}] {doc['title']}")

    lines.append("\n" + "=" * 72)
    return "\n".join(lines)


if __name__ == "__main__":
    main()
