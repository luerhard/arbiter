from markdown.extensions import Extension
from markdown.treeprocessors import Treeprocessor
from xml.etree.ElementTree import Element
import logging 

log = logging.getLogger(__name__)

class SectionCollector(Treeprocessor):
    def __init__(self, md, target_section):
        super().__init__(md)
        self.target_section = target_section
        self.in_section = False
        self.section_content = []

    def run(self, root):
        for element in root.iter():
            if element.tag == 'h2':
                if self.clean_text(element.text) == self.target_section:
                    self.in_section = True
                elif self.in_section:
                    break  
            elif self.in_section:
                self.section_content.append(element)
        return root

    def clean_text(self, text):
        cleaned_text = text.strip().lower()
        log.debug(f"Original text: '{text}', Cleaned text: '{cleaned_text}'")
        return cleaned_text

class SectionExtension(Extension):
    def __init__(self, target_section):
        super().__init__()
        self.target_section = target_section

    def extendMarkdown(self, md):
        collector = SectionCollector(md, self.target_section)
        md.treeprocessors.register(collector, 'section_collector', 0)
        md.section_content = collector.section_content