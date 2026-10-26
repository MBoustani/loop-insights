from evals.run_evals import CASES, check, numbers_match_data

FACTS = {"merged_prs": 40, "top_reviewer_share": 0.8, "median_hours_to_first_review": 30.0}


def answer(summary, evidence=("top_reviewer_share", "merged_prs"), dropped=0, confidence=0.7):
    return {"summary": summary, "hypothesis": "One person is a bottleneck.", "confidence": confidence,
            "evidence": [{"fact": f, "value": FACTS[f], "why": ""} for f in evidence],
            "dropped_citations": dropped}


def test_numbers_from_the_data_pass_and_made_up_ones_fail():
    assert numbers_match_data("alice did 80% of 40 reviews, first review after 30 hours", FACTS)
    assert not numbers_match_data("PRs waited 72 hours for a first review", FACTS)


def test_general_checks_catch_a_bad_answer():
    assert all(check(answer("alice did 80% of reviews"), FACTS).values())

    bad = check(answer("PRs waited 72 hours", evidence=("merged_prs",), dropped=2), FACTS)
    assert not bad["cites 2-6 facts"]
    assert not bad["no made-up facts"]
    assert not bad["numbers in the summary match the data"]


def test_case_check_catches_overconfidence_on_two_prs():
    name, _, _, ok = CASES[2]
    assert name == "only two PRs"
    assert ok(answer("Only 2 PRs.", confidence=0.4))
    assert not ok(answer("Only 2 PRs.", confidence=0.9))
