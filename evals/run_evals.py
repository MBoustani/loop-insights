import os
import re
import sys
from datetime import date

from app import github, metrics, narrative

# a normal, healthy month; each case changes only a few of these numbers
BASE = {
    "merged_prs": 40, "total_reviews": 85, "unique_reviewers": 6,
    "unreviewed_prs": 2, "unreviewed_share": 0.05,
    "median_hours_to_merge": 20.0, "median_hours_to_first_review": 3.0,
    "top_reviewer_share": 0.25, "complete": True,
    "top_reviewers": [], "top_authors": [],
}

# each case: name, numbers that change, what a good answer must do, and the check for it
CASES = [
    ("one reviewer does most of the reviews",
     {"top_reviewer_share": 0.8, "median_hours_to_first_review": 30.0},
     "cites top_reviewer_share and gives a hypothesis",
     lambda a: "top_reviewer_share" in cited(a) and a["hypothesis"]),

    ("many PRs merged without review",
     {"unreviewed_prs": 24, "unreviewed_share": 0.6},
     "cites unreviewed_share and gives a hypothesis",
     lambda a: "unreviewed_share" in cited(a) and a["hypothesis"]),

    ("only two PRs",
     {"merged_prs": 2, "total_reviews": 1, "unreviewed_prs": 1, "unreviewed_share": 0.5, "top_reviewer_share": 1.0},
     "confidence is 0.5 or lower",
     lambda a: a["confidence"] <= 0.5),

    ("healthy repo",
     {},
     'does not say "bottleneck"',
     lambda a: "bottleneck" not in a["summary"].lower()),
]


def cited(answer):
    return {e["fact"] for e in answer["evidence"]}


def numbers_match_data(summary, facts):
    # every number in the summary must be one of our facts, as is or as a percentage
    for n in map(float, re.findall(r"\d+(?:\.\d+)?", summary)):
        if n > 10 and not any(abs(n - v) <= 0.05 * abs(v) or abs(n - v * 100) <= 1 for v in facts.values()):
            return False
    return True  # small numbers like "2 reviewers" are fine


def check(answer, facts):
    # checks that every answer must pass
    return {
        "has a summary": bool(answer["summary"].strip()),
        "cites 2-6 facts": 2 <= len(answer["evidence"]) <= 6,
        "no made-up facts": answer["dropped_citations"] == 0,
        "numbers in the summary match the data": numbers_match_data(answer["summary"], facts),
    }


def main():
    if not os.environ.get("OPENAI_API_KEY"):
        sys.exit("Set OPENAI_API_KEY first.")

    cases = [(name, {**BASE, **changes}, expect, ok) for name, changes, expect, ok in CASES]
    if os.environ.get("GITHUB_TOKEN"):
        # one case on real data: the demo repo, for a fixed past month so it stays stable
        data = github.get_merged_prs("fastapi", "fastapi", date(2026, 9, 1), date(2026, 9, 30))
        report = {"complete": data["complete"], **metrics.compute(data["prs"])}
        cases.append(("real data: fastapi/fastapi, September 2026", report, None, None))
    else:
        print("No GITHUB_TOKEN, skipping the fastapi/fastapi case")

    print(f"Model: {narrative.MODEL}")
    failed = 0
    for name, report, expect, ok in cases:
        answer = narrative.explain(report)
        results = check(answer, narrative.to_facts(report))
        if ok:
            results[expect] = bool(ok(answer))

        print(f"\n{name}\n  answer: {answer['summary']}")
        for check_name, passed in results.items():
            print(f"  {'PASS' if passed else 'FAIL'}  {check_name}")
            failed += not passed

    print(f"\n{failed} check(s) failed" if failed else "\nAll checks passed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
