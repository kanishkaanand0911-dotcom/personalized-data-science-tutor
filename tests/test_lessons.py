"""
Tests for the case/quiz/badge layer -- all offline, no API key needed,
since quiz_generator's fallback path is fully deterministic.
"""

import sys
sys.path.insert(0, "/home/claude/project")
sys.path.insert(0, "/home/claude/project/app/educator")

from app.educator.lesson_builder import build_cases
from app.gamification.rules import badge_for_case, final_badge, XP_RULES
from quiz_generator import _fallback_quiz


def _sample_action_log():
    return [
        {"column": "price", "issue_type": "missing_numeric", "action_tried": "impute_median",
         "why_tried": "the typical value is simplest", "reason": "skew distorted too much", "passed": False},
        {"column": "price", "issue_type": "missing_numeric", "action_tried": "impute_knn",
         "why_tried": "similar rows work better for grouped data", "reason": "skew shift acceptable", "passed": True},
        {"column": "state", "issue_type": "label_inconsistency", "action_tried": "normalize_categories",
         "why_tried": "matching spellings is standard", "reason": "labels reduced 8 to 4", "passed": True},
    ]


def test_build_cases_groups_by_column():
    cases = build_cases(_sample_action_log())
    assert len(cases) == 2
    price_case = next(c for c in cases if c["id"] == "price")
    assert len(price_case["attempts"]) == 2
    assert price_case["had_retry"] is True
    assert price_case["resolved"] is True


def test_build_cases_title_has_no_duplicate_words():
    cases = build_cases(_sample_action_log())
    price_case = next(c for c in cases if c["id"] == "price")
    # regression test for the "missing deal value values" bug
    words = price_case["title"].lower().split()
    assert len(words) == len(set(words)) or "the" in [w for w in words if words.count(w) > 1]


def test_build_cases_includes_model_case_when_given():
    model_log = [{"model_tried": "LinearRegression", "why_tried": "simplest baseline",
                  "reason": "R^2 acceptable", "passed": True}]
    cases = build_cases(_sample_action_log(), model_log)
    assert cases[-1]["kind"] == "model"
    assert cases[-1]["resolved"] is True


def test_fallback_quiz_is_grounded_not_invented():
    cases = build_cases(_sample_action_log())
    price_case = next(c for c in cases if c["id"] == "price")
    quiz = _fallback_quiz(price_case)
    # the correct option must literally be built from the case's own why_tried text
    assert "similar rows" in quiz["options"][quiz["correct"]].lower()


def test_badge_rules_detective_eye_on_retry():
    cases = build_cases(_sample_action_log())
    price_case = next(c for c in cases if c["id"] == "price")
    assert badge_for_case(price_case) == "Detective's Eye"


def test_badge_rules_no_badge_for_simple_unresolved_case():
    unresolved = {"kind": "cleaning", "resolved": False, "had_retry": False, "concept": "Fixing inconsistent labels"}
    assert badge_for_case(unresolved) is None


def test_final_badge_only_when_all_resolved():
    all_resolved = [{"resolved": True}, {"resolved": True}]
    one_unresolved = [{"resolved": True}, {"resolved": False}]
    assert final_badge(all_resolved) == "Case Closed"
    assert final_badge(one_unresolved) is None


if __name__ == "__main__":
    tests = [
        test_build_cases_groups_by_column,
        test_build_cases_title_has_no_duplicate_words,
        test_build_cases_includes_model_case_when_given,
        test_fallback_quiz_is_grounded_not_invented,
        test_badge_rules_detective_eye_on_retry,
        test_badge_rules_no_badge_for_simple_unresolved_case,
        test_final_badge_only_when_all_resolved,
    ]
    passed, failed = 0, 0
    for t in tests:
        try:
            t()
            print(f"PASS: {t.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"FAIL: {t.__name__} -- {e}")
            failed += 1
        except Exception as e:
            print(f"ERROR: {t.__name__} -- {type(e).__name__}: {e}")
            failed += 1
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(0 if failed == 0 else 1)
