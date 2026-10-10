"""Turning a fetched terms page into text whose pinned passages can be
compared word for word, whatever else the page changes on every load."""

import pytest
from conftest import DELETION, REFUND, page

from redline_text import excerpts, normalize, page_text, passage_error, passage_present, strip_markup, unescape


def test_markup_comments_and_hidden_elements_are_not_text():
    html = '<p>Keep <b>this</b></p><!-- not this --><script>var x = "not this";</script><style>p{}</style><noscript>no</noscript><p>and this</p>'
    assert normalize(strip_markup(html)) == "keep this and this"
    assert normalize(strip_markup("<p>a</p><!-- x > not this --><p>b</p>")) == "a b"


def test_entities_and_typography_fold_to_one_form():
    assert unescape("&amp;&lt;&#39;&#x2014;&nbsp;&bogus;") == "&<'\u2014 &bogus;"
    assert normalize("30‑day “refund” — within  7 days") == normalize('30-day "refund" - within 7 days')


def test_a_page_rebuilt_with_new_ids_and_stamps_keeps_every_pinned_passage():
    for name in ("terms-v1.html", "terms-v1-rebuilt.html"):
        text = page_text(page(name))
        assert passage_present(text, REFUND) and passage_present(text, DELETION)
        assert "b-81f3a2" not in text and "window.__build__" not in text and "cookie{" not in text


@pytest.mark.parametrize("name,refund,deletion", [
    ("terms-reworded.html", False, True),
    ("terms-narrowed.html", False, True),
    ("terms-deletion-removed.html", True, False),
])
def test_an_edit_to_a_pinned_passage_is_seen_and_nothing_else_is(name, refund, deletion):
    text = page_text(page(name))
    assert (passage_present(text, REFUND), passage_present(text, DELETION)) == (refund, deletion)


def test_one_changed_word_or_number_is_a_change():
    text = page_text(page("terms-v1.html"))
    assert not passage_present(text, REFUND.replace("30 days", "31 days"))
    assert not passage_present(text, REFUND.replace("full", "partial"))
    assert passage_present(text, REFUND.upper())  # case and spacing are not words


def test_plain_text_and_oversized_pages_are_handled():
    assert page_text(b"Plain   TEXT terms") == "plain text terms"
    huge = b"<html><body>" + b"a " * 1_500_000 + b"</body></html>"
    assert len(page_text(huge)) <= 2_000_000


def test_a_pinned_passage_must_say_something_and_not_too_much():
    assert "at least" in passage_error("Refunds apply.")
    assert "at most" in passage_error("word " * 200)
    assert passage_error(REFUND) == ""


def test_the_jury_is_shown_the_parts_of_the_page_most_like_the_passage():
    text = page_text(page("terms-narrowed.html"))
    shown = excerpts(text, REFUND, 300)
    assert "7 days of purchase" in shown[0]
    assert excerpts(text, REFUND, 300) == shown  # deterministic
    assert excerpts("short page", REFUND) == ["short page"] and excerpts("", REFUND) == []
