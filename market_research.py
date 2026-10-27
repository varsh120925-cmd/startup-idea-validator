
import os
from dotenv import load_dotenv
from tavily import TavilyClient

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def research_market(idea, industry, customers):
    api_key = os.getenv("TAVILY_API_KEY")

    if not api_key:
        raise ValueError(
            "TAVILY_API_KEY is missing from the .env file."
        )

    client = TavilyClient(api_key=api_key)

    queries = [
        (
            "Market trends",
            f"Current market trends and demand in {industry} "
            f"related to this startup idea: {idea}",
        ),
        (
            "Competitors",
            f"Existing businesses, products, and alternatives "
            f"for {idea} in the {industry} industry",
        ),
        (
            "Customer needs",
            f"Problems, reviews, and unmet needs of "
            f"{customers} related to {industry}",
        ),
        (
            "Indian government support",
            f"site:gov.in OR site:startupi ndia.gov.in "
            f"startup schemes and official support for {industry}",
        ),
    ]

    results = []
    seen_urls = set()

    for category, query in queries:
        response = client.search(
            query=query,
            search_depth="advanced",
            max_results=5,
            include_answer=False,
        )

        for item in response.get("results", []):
            url = item.get("url", "")

            if not url or url in seen_urls:
                continue

            seen_urls.add(url)

            results.append({
                "category": category,
                "title": item.get("title", ""),
                "url": url,
                "content": item.get("content", ""),
                "published_date": item.get("published_date"),
            })

    return results
