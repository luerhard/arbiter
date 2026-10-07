import re

from markdown.extensions import Extension
from markdown.preprocessors import Preprocessor

LIST_ITEM = re.compile(r"^ {0,3}(?:([-*+])|\d+[.)])\s+\S")  # group 1: a bullet
TABLE_ROW = re.compile(r"^\s*\|.*\|\s*$")


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip())


class BlockSpacing(Preprocessor):
    """Start a list or table that directly follows a line of text, as people write them
    in other editors. Markdown only starts one after a blank line, and would otherwise
    show the list items or table rows as part of the paragraph. A line of text right
    after a table ends it, instead of becoming another row."""

    def run(self, lines: list[str]) -> list[str]:
        new_lines = []
        previous = ""
        for line in lines:
            item, previous_item = LIST_ITEM.match(line), LIST_ITEM.match(previous)
            starts_list = item and (
                # a numbered list right after a bulleted one, or the other way round
                (
                    previous_item
                    and bool(item[1]) != bool(previous_item[1])
                    and _indent(line) == _indent(previous)
                )
                or not (previous_item or previous.startswith((" ", "\t")))
            )
            starts_table = TABLE_ROW.match(line) and not TABLE_ROW.match(previous)
            ends_table = TABLE_ROW.match(previous) and line.strip() and not TABLE_ROW.match(line)
            if previous.strip() and (starts_list or starts_table or ends_table):
                new_lines.append("")
            new_lines.append(line)
            previous = line
        return new_lines


class BlockSpacingExtension(Extension):
    def extendMarkdown(self, md):  # noqa: N802 (Markdown API)
        # after the diff markers were moved behind the list markers (preprocess_diffs, -10)
        md.preprocessors.register(BlockSpacing(md), "block_spacing", -20)


def makeExtension(**kwargs):  # noqa: N802 (Markdown API)
    return BlockSpacingExtension(**kwargs)
