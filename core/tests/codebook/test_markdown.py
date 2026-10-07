"""How codebook Markdown is shown: the codebook, its diffs and the changes tab."""

from markdownify.templatetags.markdownify import markdownify
import pytest


def _html(text):
    return markdownify(text).replace("\n", "")


TABLE = "| Label | Key |\n|---|---|\n| Positive | p |"


def test_table_is_shown():
    html = _html(TABLE)

    assert "<table><thead><tr><th>Label</th><th>Key</th></tr></thead>" in html
    assert "<td>Positive</td><td>p</td>" in html


@pytest.mark.parametrize(
    "text",
    [f"The labels:\n{TABLE}", f"The labels:\n\n{TABLE}"],
    ids=["right after a line of text", "after a blank line"],
)
def test_table_after_text(text):
    html = _html(text)

    assert html.startswith("<p>The labels:</p><table>")


def test_text_right_after_a_table_ends_it():
    html = _html(f"{TABLE}\nThis is not a row.")

    assert html.endswith("</table><p>This is not a row.</p>")


@pytest.mark.parametrize("marker", ["-", "*", "+", "1."])
def test_list_right_after_a_line_of_text(marker):
    html = _html(f"Labels are:\n{marker} Positive\n{marker} Negative")

    assert html.startswith("<p>Labels are:</p><")
    assert "<li>Positive</li><li>Negative</li>" in html


def test_list_items_keep_their_continuation_lines():
    html = _html("Intro\n- Positive\n  also praise\n- Negative")

    assert "<li>Positive  also praise</li><li>Negative</li>" in html


@pytest.mark.parametrize("gap", ["\n", "\n\n"], ids=["right after", "after a blank line"])
def test_numbered_list_after_a_bulleted_one_is_its_own_list(gap):
    html = _html(f"- a\n- b{gap}1. one\n2. two")

    assert "<ul><li>a</li><li>b</li></ul><ol><li>one</li><li>two</li></ol>" in html


def test_nested_numbered_list_stays_nested():
    html = _html("Steps:\n- read\n    1. first\n    2. second\n- decide")

    assert "<li>read<ol><li>first</li><li>second</li></ol></li><li>decide</li>" in html


def test_added_table_in_a_diff_stays_a_table():
    diff = (
        "Intro\n{+| Label | Key |+}\n{+|---|---|+}\n{+| Positive | p |+}\n| Neutral | [-n-]{+u+} |"
    )

    html = _html(diff)

    assert "<th><text>Label</text></th><th><text>Key</text></th>" in html
    assert "<td><text>Positive</text></td><td><text>p</text></td>" in html
    assert "<td>Neutral</td><td><del>n</del><text>u</text></td>" in html


def test_removed_table_row_in_a_diff():
    html = _html(f"{TABLE}\n[-| Neutral | n |-]")

    assert "<td><del>Neutral</del></td><td><del>n</del></td>" in html


def test_added_list_item_in_a_diff():
    html = _html("Labels are:\n- Positive\n{+- Negative+}")

    assert "<li>Positive</li><li><text>Negative</text></li>" in html


def test_scripts_are_still_removed():
    html = _html("| a |\n|---|\n| <script>alert(1)</script> |")

    assert "<script>" not in html
