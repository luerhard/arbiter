from markdown.inlinepatterns import InlineProcessor
from markdown.extensions import Extension
import xml.etree.ElementTree as etree


class DelInlineProcessor(InlineProcessor):
    def handleMatch(self, m, data):
        el = etree.Element('del')
        el.set('class', 'text-danger bg-danger-subtle rounded')
        el.text = m.group(1)
        return el, m.start(0), m.end(0)


class DelExtension(Extension):
    def extendMarkdown(self, md):
        DEL_PATTERN = r'\[\-(.*?)\-\]'  # like [-text-]
        md.inlinePatterns.register(DelInlineProcessor(DEL_PATTERN, md), 'del', 175)


def makeExtension(**kwargs):
    return DelExtension(**kwargs)
