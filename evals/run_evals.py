import os
import re
import sys
from datetime import date

from fastapi import HTTPException

from app import github, metrics, narrative

# one case on real data: the same repo as the demo, for a fixed past month so it stays stable
REAL_REPO = ("fastapi", "fastapi", date(2026, 9, 1), date(2026, 9, 30))


def report(**changes):
    # a normal, healthy-looking month; each case changes only what it is about
    base = {
        "repo": "acme/widgets", "complete": True,
        "merged_prs": 40, "total_reviews": 85, "unique_reviewers": 6,
        "unreviewed_prs": 2, "unreviewed_share": 0.05,
        "median_hours_to_merge": 20.0, "median_hours_to_first_review": 3.0,
        "top_reviewer_share": 0.25,
        "top_reviewers": [
            {"login": "alice", "reviews": 21, "approvals": 15},
            {"login": "bob", "reviews": 18, "approvals": 12},
            {"login": "carol", "reviews": 16, "approvals": 11},
        ],
        "top_authors": [
            {"login": "dave", "merged_prs": 9},
            {"login": "erin", "merged_prs": 8},
        ],
    }
    base.update(changes)
    return base


CASES = [
    {
        "name": "one reviewer does most of the reviews",
        "report": report(
            top_reviewer_share=0.8, median_hours_to_first_review=30.0,
            top_reviewers=[{"login": "alice", "reviews": 68, "approvals": 60},
                           {"login": "bob", "reviews": 9, "approvals": 5}],
        ),
        "must_cite_one_of": ["top_reviewer_share", "reviewer.alice.reviews"],
        "needs_hypothesis": True,
    },
    {
        "name": "many PRs merged without any review",
        "report": report(unreviewed_prs=24, unreviewed_share=0.6, total_reviews=30),
        "must_cite_one_of": ["unreviewed_share", "unreviewed_prs"],
        "needs_hypothesis": True,
    },
    {
        "name": "only two PRs, too little data to be sure",
        "report": report(
            merged_prs=2, total_reviews=1, unique_reviewers=1, unreviewed_prs=1, unreviewed_share=0.5,
            median_hours_to_merge=5.0, median_hours_to_first_review=1.0, top_reviewer_share=1.0,
            top_reviewers=[{"login": "alice", "reviews": 1, "approvals": 1}],
            top_authors=[{"login": "dave", "merged_prs": 2}],
        ),
        "max_confidence": 0.5,
    },
    {
        "name": "healthy repo, nothing alarming",
        "report": report(),
        "must_not_say": ["bottleneck"],
    },
]


def real_data_case():
    # same path as the app: GitHub -> metrics (no cache, so it always uses fresh data)
    owner, repo, since, until = REAL_REPO
    data = github.get_merged_prs(owner, repo, since, until)
    report = {"repo": f"{owner}/{repo}", "complete": data["complete"], **metrics.compute(data["prs"])}
    return {"name": f"real data: {owner}/{repo}, {since} to {until}", "report": report}


def numbers_match_data(summary, facts):
    """Every number in the summary must be one of our facts (as is, or as a percentage)."""
    values = [float(v) for v in facts.values()]
    for text in re.findall(r"\d+(?:\.\d+)?", summary):
        n = float(text)
        if n.is_integer() and n <= 10:
            continue  # small counts like "2 reviewers" or "1 in 5" are fine
        if not any(abs(n - v) <= 0.05 * max(1, abs(v)) or abs(n - v * 100) <= 1 for v in values):
            return False
    return True


def check(answer, facts, case):
    cited = {e["fact"] for e in answer["evidence"]}
    results = {
        "has a summary": bool(answer["summary"].strip()),
        "cites 2-6 facts": 2 <= len(answer["evidence"]) <= 6,
        "no made-up facts": answer["dropped_citations"] == 0,
        "numbers in the summary match the data": numbers_match_data(answer["summary"], facts),
    }
    if "must_cite_one_of" in case:
        results[f"cites one of {case['must_cite_one_of']}"] = bool(cited & set(case["must_cite_one_of"]))
    if case.get("needs_hypothesis"):
        results["gives a hypothesis"] = bool(answer["hypothesis"])
    if "max_confidence" in case:
        results[f"confidence <= {case['max_confidence']}"] = answer["confidence"] <= case["max_confidence"]
    for word in case.get("must_not_say", []):
        results[f'does not say "{word}"'] = word not in answer["summary"].lower()
    return results


def main():
    if not os.environ.get("OPENAI_API_KEY"):
        sys.exit("Set OPENAI_API_KEY first.")
    print(f"Model: {narrative.MODEL}")
    failed = 0
    cases = list(CASES)
    if os.environ.get("GITHUB_TOKEN"):
        try:
            cases.append(real_data_case())
        except HTTPException as e:
            print(f"\nFAIL  could not load the real-data case: {e.detail}")
            failed += 1
    else:
        print("GITHUB_TOKEN not set, skipping the real-data case")

    for case in cases:
        print(f"\n{case['name']}")
        try:
            answer = narrative.explain(case["report"])
        except HTTPException as e:
            print(f"  FAIL  model call failed: {e.detail}")
            failed += 1
            continue
        print(f"  answer: {answer['summary']}")
        for name, ok in check(answer, narrative.to_facts(case["report"]), case).items():
            print(f"  {'PASS' if ok else 'FAIL'}  {name}")
            failed += not ok
    print(f"\n{failed} check(s) failed" if failed else "\nAll checks passed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
