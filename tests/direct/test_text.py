"""Turning a fetched terms page into text whose pinned passages can be
compared word for word, whatever else the page changes on every load."""

import pytest
from conftest import DELETION, REFUND, page

from redline_text import (
    EXCERPT, WHOLE_PAGE, context_print, excerpts, hidden_selectors, normalize, page_text, passage_error, passage_present,
    strip_markup, unescape,
)


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


def test_a_short_page_is_shown_to_the_jury_whole():
    text = page_text(page("terms-narrowed.html"))
    assert len(text) <= WHOLE_PAGE and excerpts(text, REFUND) == [text]
    assert excerpts("short page", REFUND) == ["short page"] and excerpts("", REFUND) == []


def test_a_long_page_is_shown_in_windows_led_by_the_passage_or_its_subject():
    filler = " ".join("clause %d covers an unrelated matter of law." % i for i in range(1500))
    narrowed = normalize("You may cancel within 7 days of purchase and receive a refund of unused prepaid credit.")
    text = normalize(filler[: len(filler) // 2]) + " " + narrowed + " " + normalize(filler[len(filler) // 2 :])
    assert len(text) > WHOLE_PAGE
    shown = excerpts(text, REFUND)
    assert 1 <= len(shown) <= 3 and all(len(e) <= EXCERPT for e in shown)
    assert narrowed in shown[0]  # the window sharing the most words with the pinned passage
    assert excerpts(text, REFUND) == shown  # deterministic
    # The passage still there word for word: the first window is centred on it.
    kept = text.replace(narrowed, normalize(REFUND))
    first = excerpts(kept, REFUND)[0]
    assert normalize(REFUND) in first and first.index(normalize(REFUND)) > EXCERPT // 4


@pytest.mark.parametrize("html", [
    '<div hidden><p>%s</p></div>',
    '<div hidden="hidden">%s</div>',
    '<p aria-hidden="true">%s</p>',
    '<p style="display: none">%s</p>',
    "<p style='visibility:hidden'>%s</p>",
    '<p style="font-size:0px">%s</p>',
    '<span class="sr-only">%s</span>',
    '<div class="text d-none">%s</div>',
    '<style>.old { display: none }</style><p class="old">%s</p>',
    '<style>@media all { #v1 { visibility: hidden } }</style><section id="v1">%s</section>',
    '<div hidden><div><p>%s</p></div></div>',
    '<div hidden><div>first</div><p>%s</p></div>',
])
def test_text_a_reader_cannot_see_is_not_on_the_page(html):
    page_html = ("<html><body><p>Visible.</p>" + html + "<p>After.</p></body></html>") % REFUND
    text = page_text(page_html)
    assert not passage_present(text, REFUND), html
    assert text.startswith("visible.") and text.endswith("after.")


@pytest.mark.parametrize("html", [
    '<p class="hidden md:block">%s</p>',
    '<p title="hidden">%s</p>',
    '<p data-hidden="1">%s</p>',
    '<p class="hiddenness">%s</p>',
    '<style>.old p { display: none }</style><p class="old">%s</p>',
])
def test_text_a_reader_can_see_stays_on_the_page(html):
    assert passage_present(page_text(("<html><body>" + html + "</body></html>") % REFUND), REFUND), html


def test_only_bare_class_and_id_rules_that_hide_count():
    css = "<style>.a{display:none} .b , #c {visibility : hidden} .d .e{display:none} .f{color:red}</style>"
    assert hidden_selectors(css) == {".a", ".b", "#c"}


def test_the_surroundings_of_a_passage_ignore_dates_and_rebuilds():
    v1 = page_text(page("terms-v1.html"))
    rebuilt = page_text(page("terms-v1-rebuilt.html"))
    for passage in (REFUND, DELETION):
        assert context_print(v1, passage) == context_print(rebuilt, passage) != ""
    assert context_print(v1, REFUND.replace("30", "31")) == ""


def test_a_line_that_voids_a_passage_changes_its_surroundings():
    v1 = page_text(page("terms-v1.html"))
    voided = page_text(page("terms-voided.html"))
    assert passage_present(voided, REFUND)  # still there word for word
    assert context_print(voided, REFUND) != context_print(v1, REFUND)
    # So does a second copy, or a sentence on the same subject far away.
    twice = v1 + " " + normalize(REFUND)
    assert context_print(twice, REFUND) != context_print(v1, REFUND)
    far = v1 + " " + " ".join(["filler words here"] * 200) + " refunds of unused prepaid credit are suspended for every purchase."
    assert context_print(far, REFUND) != context_print(v1, REFUND)
