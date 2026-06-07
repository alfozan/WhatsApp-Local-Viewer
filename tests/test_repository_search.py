from __future__ import annotations

import unittest

from repository_search import search_index_text_matches_query, search_query_variants


def _expect_variants(source: str, expected: list[str]) -> None:
    actual = search_query_variants(source)
    if actual != expected:
        raise AssertionError(f"Expected {expected!r}, got {actual!r}")


def _expect_search_index_match(index_text: str, query_variants: list[str], expected: bool) -> None:
    actual = search_index_text_matches_query(index_text, query_variants)
    if actual != expected:
        raise AssertionError(f"Expected {expected!r}, got {actual!r}")


class SearchQueryVariantsTest(unittest.TestCase):
    def test_arabic_indic_digits_fold_to_ascii(self) -> None:
        _expect_variants("٥٥١٣٥٣١١٠", ["٥٥١٣٥٣١١٠", "551353110"])

    def test_persian_digits_fold_to_ascii(self) -> None:
        _expect_variants("۵۵۱۳۵۳۱۱۰", ["۵۵۱۳۵۳۱۱۰", "551353110"])

    def test_formatted_phone_adds_compact_digits(self) -> None:
        _expect_variants("+٩٦٦ ٥٥ ١٣٥ ٣١١٠", ["+٩٦٦ ٥٥ ١٣٥ ٣١١٠", "+966 55 135 3110", "966551353110"])


class SearchIndexTextMatchesQueryTest(unittest.TestCase):
    def test_arabic_term_matches_standalone_token(self) -> None:
        _expect_search_index_match("وياك عبدالرحمن 🙏", ["عبدالرحمن"], True)

    def test_arabic_term_matches_standalone_token_after_prefix_word(self) -> None:
        _expect_search_index_match("ويستاهل الثقه ابو عبدالرحمن", ["عبدالرحمن"], True)

    def test_arabic_term_does_not_match_arbitrary_glued_text(self) -> None:
        _expect_search_index_match("هلاعبدالرحمن", ["عبدالرحمن"], False)

    def test_arabic_term_does_not_match_glued_prefix_text(self) -> None:
        _expect_search_index_match("تستاهل ابوعبدالرحمن ماشاء الله", ["عبدالرحمن"], False)


if __name__ == "__main__":
    unittest.main()
