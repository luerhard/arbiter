from markdown.extensions import Extension
from markdown.preprocessors import Preprocessor
import re


class PreprocessDiffs(Preprocessor):
    """Make sure that Git Diff syntax does not collide with normal MD syntax."""
    FIX_PATTERN_START = r"\{\+((?:\-|\d*\.|\>|\#*) ?)(.*?)\+\}"
    FIX_PATTERN_WRAP = r"\{\+(\*\*|\*|\_\_|\_|\`)(.*?)(\*\*|\*|\_\_|\_|\`)\+\}"

    def run(self, lines: list[str]) -> list[str]:
        new_lines = []
        for line in lines:
            # Takes the MD start syntax (#, -, >, 1.) and puts it outside of Diff syntax
            # Example: {+## Examples+} -> ## {+Examples+}
            modified_line = re.sub(self.FIX_PATTERN_START, r"\1{+\2+}", line)
            # Takes the MD wrapping syntax (``, **, ****, __, ____) and puts it outside of Diff syntax
            # Example {+`Examples`+} -> `{+Examples+}`
            modified_line = re.sub(self.FIX_PATTERN_WRAP, r"\1{+\2+}\3", modified_line)
            new_lines.append(modified_line)
        return new_lines


class PreProcessDiffsExtension(Extension):
    def extendMarkdown(self, md):
        md.preprocessors.register(PreprocessDiffs(md), "preprocess_diffs", -10)


def makeExtension(**kwargs):
    return PreProcessDiffsExtension(**kwargs)