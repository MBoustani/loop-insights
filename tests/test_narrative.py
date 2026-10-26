from app.narrative import Evidence, Insight, check_evidence

FACTS = {"merged_prs": 40, "top_reviewer_share": 0.6, "reviewer.bob.reviews": 24}


def test_made_up_facts_are_dropped_and_real_values_are_used():
    answer = Insight(
        summary="Bob does most of the reviews.",
        hypothesis="Review work depends on one person.",
        confidence=0.8,
        evidence=[
            Evidence(fact="top_reviewer_share", why="one person does most reviews"),
            Evidence(fact="reviewer.bob.reviews", why="bob's count"),
            Evidence(fact="made_up_number", why="the model invented this"),
        ],
    )
    result = check_evidence(answer, FACTS)

    assert [(e["fact"], e["value"]) for e in result["evidence"]] == [
        ("top_reviewer_share", 0.6),
        ("reviewer.bob.reviews", 24),
    ]
    assert result["dropped_citations"] == 1
    assert result["confidence"] == 0.8


def test_answer_without_real_evidence_gets_low_confidence():
    answer = Insight(
        summary="Something is wrong.",
        hypothesis="No idea.",
        confidence=0.95,
        evidence=[Evidence(fact="not_a_real_fact", why="made up")],
    )
    result = check_evidence(answer, FACTS)

    assert result["evidence"] == []
    assert result["confidence"] == 0.2
