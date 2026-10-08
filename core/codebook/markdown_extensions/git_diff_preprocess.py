import re

from markdown.extensions import Extension
from markdown.preprocessors import Preprocessor


class PreprocessDiffs(Preprocessor):
    """Make sure that Git Diff syntax does not collide with normal MD syntax."""

    FIX_PATTERN_START_POS = r"\{\+((?:\-|\d*\.|\>|\#*) ?)(.*?)\+\}"
    FIX_PATTERN_START_NEG = r"\[\-((?:\-|\d*\.|\>|\#*) ?)(.*?)\-\]"
    # 1. r"\{\+ ... \+\} is the git diff syntax
    # 2. (\*\*\*\*|\*\*|\*|\_\_\_\_|\_\_|\_|\`\`\`|\`|\~\~|\~)
    #    Match any of the following ****, **, *, ____, __, _, ```, `, ~~, or ~
    #    after {+
    # 3. (.*?)
    # 4. \1 Whatever was matched in step 2. should be matched at the end too.
    FIX_PATTERN_WRAP_POS = r"\{\+(\*\*\*\*|\*\*|\*|\_\_\_\_|\_\_|\_|\`\`\`|\`|\~\~|\~)(.*?)\1\+\}"
    FIX_PATTERN_WRAP_NEG = r"\[\-(\*\*\*\*|\*\*|\*|\_\_\_\_|\_\_|\_|\`\`\`|\`|\~\~|\~)(.*?)\1\-\]"

    # a whole table row added or removed: {+| a | b |+}
    TABLE_ROW = re.compile(r"^(\{\+|\[-)(\s*\|.*\|\s*)(\+\}|-\])$")

    @staticmethod
    def _mark_cells(match: re.Match) -> str:
        """{+| a | b |+} -> | {+a+} | {+b+} |, so the row stays a table row. The row
        below the header (|---|) stays as it is."""
        start, row, end = match.groups()
        cells = row.strip().strip("|").split("|")
        if all(re.fullmatch(r"\s*:?-+:?\s*", cell) for cell in cells):
            return row
        marked = [f" {start}{cell.strip()}{end} " if cell.strip() else cell for cell in cells]
        return "|" + "|".join(marked) + "|"

    def run(self, lines: list[str]) -> list[str]:
        new_lines = []
        for line in lines:
            line = self.TABLE_ROW.sub(self._mark_cells, line)  # noqa: PLW2901
            # Takes the MD start syntax (#, -, >, 1.) and puts it outside of Diff syntax
            # Example: {+## Examples+} -> ## {+Examples+}
            modified_line = re.sub(self.FIX_PATTERN_START_POS, r"\1{+\2+}", line)
            modified_line = re.sub(self.FIX_PATTERN_START_NEG, r"\1[-\2-]", modified_line)
            # Takes the MD wrapping syntax (``, **, ****, __, ____) and puts it outside of Diff syntax
            # Example {+`Examples`+} -> `{+Examples+}`
            modified_line = re.sub(self.FIX_PATTERN_WRAP_POS, r"\1{+\2+}\1", modified_line)
            modified_line = re.sub(self.FIX_PATTERN_WRAP_NEG, r"\1[-\2-]\1", modified_line)
            new_lines.append(modified_line)
        return new_lines


class PreProcessDiffsExtension(Extension):
    def extendMarkdown(self, md):
        md.preprocessors.register(PreprocessDiffs(md), "preprocess_diffs", -10)


def makeExtension(**kwargs):
    return PreProcessDiffsExtension(**kwargs)
