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
        created = _parse(pr["created_at"])
        hours_to_merge.append(_hours(created, _parse(pr["merged_at"])))
        merged_by[pr["author"]] += 1

        # authors replying on their own PR show up as reviews, skip those
        peer_reviews = [r for r in pr["reviews"] if r["author"] != pr["author"]]
        if not peer_reviews:
            unreviewed += 1
            continue

        first_review = min(_parse(r["submitted_at"]) for r in peer_reviews)
        hours_to_first_review.append(_hours(created, first_review))
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
        "unreviewed_share": _share(unreviewed, len(prs)),
        "median_hours_to_merge": _median(hours_to_merge),
        "median_hours_to_first_review": _median(hours_to_first_review),
        "top_reviewer_share": _share(top_reviewers[0][1], total_reviews) if top_reviewers else None,
        "top_reviewers": [
            {"login": login, "reviews": count, "approvals": approvals_by[login]}
            for login, count in top_reviewers
        ],
        "top_authors": [
            {"login": login, "merged_prs": count}
            for login, count in merged_by.most_common(top_n)
        ],
    }


def _parse(timestamp):
    return datetime.fromisoformat(timestamp)


def _hours(start, end):
    return (end - start).total_seconds() / 3600


def _median(values):
    return round(median(values), 1) if values else None


def _share(part, whole):
    return round(part / whole, 3) if whole else None
