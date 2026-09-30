"""
test_page_verdict.py
Unit tests for the page -> verdict loop (page_verdict.PageVerdict).

Collaborators are stubbed, so no OCR model, Excel file, or network is
needed. These pin the loop semantics that used to live untested in main:
crop-variant iteration, early exit at high confidence, best-pick, and
the unmatched path.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from page_verdict import PageVerdict  # noqa: E402

MATCHED = {
    "matched": True,
    "confidence": 100.0,
    "stl_id": "1590EC",
    "billing_number": "0055978",
    "billing_period": "0426",
    "name": "1590 ENERGY CORPORATION",
    "amount": 1888.44,
}


class FakeOCR:
    """Returns canned words per image_to_text call; counts calls."""

    def __init__(self, words_per_call):
        self.words_per_call = list(words_per_call)
        self.calls = 0

    def pdf_to_image(self, page):
        return object()

    def image_to_text(self, image):
        words = (
            self.words_per_call[self.calls]
            if self.calls < len(self.words_per_call)
            else []
        )
        self.calls += 1
        return words


class FakeCropper:
    def __init__(self, n_variants=4):
        self.n_variants = n_variants

    def get_crop_variants(self, image):
        return [object() for _ in range(self.n_variants)]


class FakeExtractor:
    def __init__(self, candidates):
        self.candidates = candidates

    def extract(self, words):
        return self.candidates


class FakeMatcher:
    """Returns one canned result per match() call."""

    def __init__(self, results_by_call):
        self.results_by_call = list(results_by_call)
        self.calls = 0

    def match(self, candidate):
        result = (
            self.results_by_call[self.calls]
            if self.calls < len(self.results_by_call)
            else {"matched": False, "reason": "no more results"}
        )
        self.calls += 1
        return result


class FakeRenamer:
    def build_filename(self, match):
        return (
            f"SI_DASURECO_{match['stl_id']}_{match['billing_number']}_"
            f"{match['billing_period']}_20260804.pdf"
        )


def make_verdict(ocr, matcher, candidates=None):
    cropper = FakeCropper()
    extractor = FakeExtractor(candidates if candidates is not None else [MATCHED])
    return PageVerdict(ocr, cropper, extractor, matcher, FakeRenamer())


def test_early_exit_stops_after_first_variant():
    ocr = FakeOCR([["words"]])
    matcher = FakeMatcher([MATCHED])
    verdict = make_verdict(ocr, matcher)

    result = verdict.verdict_for(Path("page.pdf"))

    assert result["matched"] is True
    assert ocr.calls == 1, "early exit must stop after the first variant"
    assert result["confidence"] == 100.0
    assert result["filename"] == (
        "SI_DASURECO_1590EC_0055978_0426_20260804.pdf"
    )


def test_all_variants_tried_when_below_early_exit():
    ocr = FakeOCR([["a"], ["b"], ["c"], ["d"]])
    matcher = FakeMatcher([
        {**MATCHED, "confidence": 85.0},
        {**MATCHED, "confidence": 86.0},
        {**MATCHED, "confidence": 87.0},
        {**MATCHED, "confidence": 88.0},
    ])
    verdict = make_verdict(ocr, matcher)

    result = verdict.verdict_for(Path("page.pdf"))

    assert ocr.calls == 4, "all four variants must be tried below the threshold"
    assert result["confidence"] == 88.0, "best match must win"



def test_best_match_wins_within_a_variant():
    ocr = FakeOCR([["words"]])
    matcher = FakeMatcher([
        {**MATCHED, "confidence": 80.0},
        {**MATCHED, "confidence": 97.0},
    ])
    verdict = make_verdict(ocr, matcher, candidates=[MATCHED, MATCHED])

    result = verdict.verdict_for(Path("page.pdf"))

    assert result["confidence"] == 97.0


def test_match_found_on_later_variant():
    # Variants 1-2 produce no words; variant 3 hits a 100% match.
    ocr = FakeOCR([[], [], ["words"]])
    matcher = FakeMatcher([MATCHED])
    verdict = make_verdict(ocr, matcher)

    result = verdict.verdict_for(Path("page.pdf"))

    assert result["matched"] is True
    assert ocr.calls == 3, "loop must keep going past silent variants"


def test_no_words_is_unmatched():
    ocr = FakeOCR([[]])
    matcher = FakeMatcher([])
    verdict = make_verdict(ocr, matcher)

    result = verdict.verdict_for(Path("page.pdf"))

    assert result == {"matched": False, "reason": "No matching company found."}


def test_no_candidates_is_unmatched():
    ocr = FakeOCR([["words"]])
    matcher = FakeMatcher([])
    verdict = make_verdict(ocr, matcher, candidates=[])

    result = verdict.verdict_for(Path("page.pdf"))

    assert result["matched"] is False


def test_no_match_is_unmatched():
    ocr = FakeOCR([["words"]])
    matcher = FakeMatcher([{"matched": False, "reason": "Low confidence (60.0%)"}])
    verdict = make_verdict(ocr, matcher)

    result = verdict.verdict_for(Path("page.pdf"))

    assert result == {"matched": False, "reason": "No matching company found."}


def main():
    tests = [
        test_early_exit_stops_after_first_variant,
        test_all_variants_tried_when_below_early_exit,
        test_best_match_wins_within_a_variant,
        test_match_found_on_later_variant,
        test_no_words_is_unmatched,
        test_no_candidates_is_unmatched,
        test_no_match_is_unmatched,
    ]

    failed = 0
    for test in tests:
        try:
            test()
            print(f"PASS  {test.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL  {test.__name__}: {e}")

    print(f"\n{len(tests) - failed}/{len(tests)} tests passed")
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
