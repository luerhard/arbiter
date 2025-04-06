from markdown.inlinepatterns import InlineProcessor
from markdown.extensions import Extension
import xml.etree.ElementTree as etree


class InsertionInlineProcessor(InlineProcessor):
    def handleMatch(self, m, data):
        el = etree.Element('text')
        el.set('class', 'text-success-emphasis bg-success-subtle rounded')
        el.text = m.group(1)
        return el, m.start(0), m.end(0)


class InsertionExtension(Extension):
    def extendMarkdown(self, md):
        INSERTION_PATTERN = r'\{\+(.*?)\+\}'  # like {+text+}
        md.inlinePatterns.register(InsertionInlineProcessor(INSERTION_PATTERN, md), 'text', 175)


def makeExtension(**kwargs):
    return InsertionExtension(**kwargs)
