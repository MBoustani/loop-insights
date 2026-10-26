import json
import os

import openai
from fastapi import HTTPException
from pydantic import BaseModel

MODEL = os.environ.get("OPENAI_MODEL", "gpt-5.6")

INSTRUCTIONS = """You analyse pull-request review metrics for one GitHub repository.
You get a JSON object of facts (name -> number) for one time period.
Write 2-4 plain sentences on what is interesting or unusual.
If the numbers support a root cause, give ONE hypothesis, otherwise null.
Cite 2-6 facts by their exact name as evidence.
Confidence (0-1) is how strongly the data supports the hypothesis.
Keep it low when there are only a few merged PRs."""


class Evidence(BaseModel):
    fact: str
    why: str


class Insight(BaseModel):
    summary: str
    hypothesis: str | None
    confidence: float
    evidence: list[Evidence]


def explain(report):
    if report["merged_prs"] == 0:
        return {"summary": "No pull requests were merged in this period.", "hypothesis": None,
                "confidence": 1.0, "evidence": [], "dropped_citations": 0}

    facts = to_facts(report)
    try:
        response = openai.OpenAI().responses.parse(
            model=MODEL,
            instructions=INSTRUCTIONS,
            input=json.dumps(facts),
            text_format=Insight,
        )
    except openai.OpenAIError:
        raise HTTPException(502, "The LLM request failed")

    if response.output_parsed is None:  # refusal
        raise HTTPException(502, "The LLM gave no usable answer")
    return check_evidence(response.output_parsed, facts)


def to_facts(report):
    # only numbers + logins go to the model, no PR text (prompt injection)
    facts = {name: value for name, value in report.items() if isinstance(value, (int, float))}
    for r in report["top_reviewers"]:
        facts[f"reviewer.{r['login']}.reviews"] = r["reviews"]
    for a in report["top_authors"]:
        facts[f"author.{a['login']}.merged_prs"] = a["merged_prs"]
    return facts


def check_evidence(insight, facts):
    # drop made-up facts, and always use our value, not the model's
    evidence = [
        {"fact": e.fact, "value": facts[e.fact], "why": e.why}
        for e in insight.evidence
        if e.fact in facts
    ]
    confidence = max(0.0, min(1.0, insight.confidence))
    if not evidence:
        confidence = min(confidence, 0.2)

    return {
        "summary": insight.summary,
        "hypothesis": insight.hypothesis,
        "confidence": round(confidence, 2),
        "evidence": evidence,
        "dropped_citations": len(insight.evidence) - len(evidence),
    }
