from collections import Counter
from datetime import datetime
from statistics import median


def compute(prs, top_n=10):
    reviews_by = Counter()
    approvals_by = Counter()
    merged_by = Counter()
    hours_to_merge = []
    hours_to_first_review = []
    unreviewed = 0

    for pr in prs:
        created = datetime.fromisoformat(pr["created_at"])
        merged = datetime.fromisoformat(pr["merged_at"])
        hours_to_merge.append((merged - created).total_seconds() / 3600)
        merged_by[pr["author"]] += 1

        # authors replying on their own PR show up as reviews, skip those
        peer_reviews = [r for r in pr["reviews"] if r["author"] != pr["author"]]
        if not peer_reviews:
            unreviewed += 1
            continue

        first_review = min(datetime.fromisoformat(r["submitted_at"]) for r in peer_reviews)
        hours_to_first_review.append((first_review - created).total_seconds() / 3600)
        for r in peer_reviews:
            reviews_by[r["author"]] += 1
            if r["state"] == "APPROVED":
                approvals_by[r["author"]] += 1

    total_reviews = sum(reviews_by.values())
    top_reviewers = reviews_by.most_common(top_n)

    return {
        "merged_prs": len(prs),
        "total_reviews": total_reviews,
        "unique_reviewers": len(reviews_by),
        "unreviewed_prs": unreviewed,
        "unreviewed_share": round(unreviewed / len(prs), 3) if prs else None,
        "median_hours_to_merge": round(median(hours_to_merge), 1) if hours_to_merge else None,
        "median_hours_to_first_review": round(median(hours_to_first_review), 1) if hours_to_first_review else None,
        "top_reviewer_share": round(top_reviewers[0][1] / total_reviews, 3) if top_reviewers else None,
        "top_reviewers": [
            {"login": login, "reviews": count, "approvals": approvals_by[login]}
            for login, count in top_reviewers
        ],
        "top_authors": [
            {"login": login, "merged_prs": count}
            for login, count in merged_by.most_common(top_n)
        ],
    }
