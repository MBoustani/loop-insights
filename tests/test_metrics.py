from app.metrics import compute


def pr(author, created, merged, reviews=()):
    return {
        "author": author,
        "created_at": created,
        "merged_at": merged,
        "reviews": [{"author": a, "state": s, "submitted_at": t} for a, s, t in reviews],
    }


# small made-up data where every number is easy to check by hand
PRS = [
    # merged after 24h, first review after 2h
    pr("alice", "2026-09-01T00:00:00Z", "2026-09-02T00:00:00Z", [
        ("bob", "APPROVED", "2026-09-01T02:00:00Z"),
        ("carol", "COMMENTED", "2026-09-01T05:00:00Z"),
    ]),
    # bob comments on his own PR at 0.5h: not a review. first real review is alice at 1h
    pr("bob", "2026-09-03T00:00:00Z", "2026-09-03T10:00:00Z", [
        ("bob", "COMMENTED", "2026-09-03T00:30:00Z"),
        ("alice", "APPROVED", "2026-09-03T01:00:00Z"),
    ]),
    # merged after 4h with no review at all
    pr("alice", "2026-09-04T00:00:00Z", "2026-09-04T04:00:00Z"),
    # merged after 24h, first review after 3h
    pr("dave", "2026-09-05T00:00:00Z", "2026-09-06T00:00:00Z", [
        ("bob", "CHANGES_REQUESTED", "2026-09-05T03:00:00Z"),
        ("bob", "APPROVED", "2026-09-05T06:00:00Z"),
    ]),
]


def test_numbers_match_hand_calculation():
    m = compute(PRS)

    assert m["merged_prs"] == 4
    assert m["total_reviews"] == 5  # bob's comment on his own PR is not counted
    assert m["unique_reviewers"] == 3
    assert m["unreviewed_prs"] == 1
    assert m["unreviewed_share"] == 0.25
    assert m["median_hours_to_merge"] == 17.0  # median of 24, 10, 4, 24
    assert m["median_hours_to_first_review"] == 2.0  # median of 2, 1, 3
    assert m["top_reviewer_share"] == 0.6  # bob did 3 of the 5 reviews
    assert m["top_reviewers"][0] == {"login": "bob", "reviews": 3, "approvals": 2}
    assert m["top_authors"][0] == {"login": "alice", "merged_prs": 2}


def test_empty_period_gives_none_not_zero():
    m = compute([])

    assert m["merged_prs"] == 0
    assert m["unreviewed_share"] is None
    assert m["median_hours_to_merge"] is None
    assert m["top_reviewer_share"] is None
    assert m["top_reviewers"] == []
