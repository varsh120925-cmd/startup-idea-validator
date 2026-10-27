
import os
import json
from pathlib import Path

from groq import Groq
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

MODEL = "openai/gpt-oss-20b"


def analyze_idea(idea, industry, customers, research_results=None):
    api_key = os.getenv("GROQ_API_KEY")

    if not api_key:
        raise ValueError("GROQ_API_KEY is missing from .env.")

    client = Groq(api_key=api_key)
    research_results = research_results or []

    schema = {
        "startup_name": "",
        "score": 0,
        "verdict": "",
        "executive_summary": "",
        "scores": {
            "market": 0,
            "innovation": 0,
            "feasibility": 0,
            "competition": 0,
            "revenue": 0
        },
        "score_explanations": {
            "market": "",
            "innovation": "",
            "feasibility": "",
            "competition": "",
            "revenue": ""
        },
        "startup_overview": "",
        "problem_analysis": "",
        "proposed_solution": "",
        "real_life_example": "",
        "market_analysis": "",
        "customer_analysis": "",
        "customer_personas": [
            {
                "name": "",
                "background": "",
                "problem": "",
                "needs": "",
                "how_to_reach": ""
            }
        ],
        "competitor_analysis": "",
        "unique_value_proposition": "",
        "business_model": "",
        "pricing_strategy": "",
        "cost_considerations": "",
        "technology_requirements": "",
        "team_requirements": "",
        "strengths": [],
        "weaknesses": [],
        "revenue_opportunities": [],
        "mvp_features": [],
        "mvp_development": "",
        "risks_and_solutions": [
            {
                "risk": "",
                "why_it_matters": "",
                "solution": ""
            }
        ],
        "improvements": [],
        "detailed_improvements": [
            {
                "title": "",
                "what_to_change": "",
                "why_it_matters": "",
                "how_to_do_it": "",
                "expected_benefit": ""
            }
        ],
        "action_plan": {
            "week_1": "",
            "week_2": "",
            "week_3": "",
            "week_4": ""
        },
        "roadmap_90_days": {
            "month_1": "",
            "month_2": "",
            "month_3": ""
        },
        "validation_experiments": [],
        "assumptions_to_verify": [],
        "government_schemes": [],
        "legal_considerations": [],
        "estimated_budget": {
            "currency": "INR",
            "low_estimate": "",
            "high_estimate": "",
            "assumptions": ""
        },
        "sources": [],
        "recommendation": ""
    }

    system_message = """
You are an experienced startup advisor and market analyst.

Use simple English suitable for beginners.
Give practical and specific recommendations.
Be honest about uncertainty.
Never invent verified statistics, customer surveys,
competitor facts, source URLs, government benefits, or legal rules.
Use the supplied web research as evidence, not as guaranteed truth.
Distinguish facts, assumptions, and estimates.
Do not guarantee startup success.
Return one valid JSON object only.
"""

    prompt = f"""
Prepare a comprehensive startup validation report.

STARTUP IDEA:
{idea}

INDUSTRY:
{industry}

TARGET CUSTOMERS:
{customers}

LIVE WEB RESEARCH RESULTS:
{json.dumps(research_results, ensure_ascii=False)}

REPORT STRUCTURE:
{json.dumps(schema, ensure_ascii=False, indent=2)}

Requirements:
1. Include every key in the report structure.
2. Give each score as an integer from 0 to 100.
3. Explain why each score was assigned.
4. Analyse market demand, customer needs, competitors,
   differentiation, revenue, costs, feasibility and risks.
5. Recommend a small minimum viable product (MVP).
6. Provide practical improvements and a 90-day roadmap.
7. Give budget ranges in INR, clearly labelled as estimates.
8. Discuss relevant Indian government schemes and legal
   considerations cautiously. Do not claim eligibility is confirmed.
9. Use official government sources for scheme and legal claims
   whenever the supplied research includes them.
10. Never invent source URLs. Use only URLs from the supplied
    research results.
11. In "sources", provide a list of objects with "title", "url",
    "category", and "relevance".
12. In "government_schemes", provide a list of objects with
    "name", "description", "eligibility", and "official_url".
    If details cannot be verified, say so.
13. In "legal_considerations", provide a list of objects with
    "requirement", "why_it_may_apply", and "official_url".
14. If the research does not contain enough evidence, state
    what still needs to be researched or verified.
15. Return valid JSON only, without Markdown fences.
"""

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_message},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
        max_completion_tokens=12000,
    )

    content = response.choices[0].message.content

    if not content or not content.strip():
        raise ValueError("The AI returned an empty response.")

    content = content.strip()

    if content.startswith("```"):
        content = content.split("\n", 1)[-1]
        if content.endswith("```"):
            content = content[:-3].strip()

    analysis = json.loads(content)

    if not isinstance(analysis, dict):
        raise ValueError("The AI response is not a JSON object.")

    for key in schema:
        if key not in analysis:
            raise ValueError(f"The AI report is missing: {key}")

    for key in ["score", "market", "innovation",
                "feasibility", "competition", "revenue"]:
        value = (
            analysis["score"]
            if key == "score"
            else analysis["scores"].get(key)
        )

        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not 0 <= value <= 100
        ):
            raise ValueError(f"Invalid score: {key}")

    return analysis
