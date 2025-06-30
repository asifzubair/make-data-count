# This file will contain new tests for schema detection, to be merged or run alongside test_xml_parser.py

import unittest
from xml_parser import XMLParser
import tempfile
import os
import logging

# Temporarily elevate logging for these specific tests if needed to see detection logs
# logging.basicConfig(level=logging.INFO)

class TestXMLParserSchemaDetection(unittest.TestCase):

    def setUp(self):
        self.temp_file = tempfile.NamedTemporaryFile(delete=False, mode='w', suffix='.xml', encoding='utf-8')
        self.temp_file_path = self.temp_file.name

    def tearDown(self):
        self.temp_file.close()
        os.unlink(self.temp_file_path)

    def _write_xml_and_parse(self, xml_content):
        self.temp_file.seek(0)
        self.temp_file.truncate()
        self.temp_file.write(xml_content)
        self.temp_file.flush()
        parser = XMLParser(self.temp_file_path)
        return parser

    def test_jats_detection_by_doctype(self):
        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
        <!DOCTYPE article PUBLIC "-//NLM//DTD JATS (Z39.96) Journal Archiving and Interchange DTD v1.2 20190208//EN" "JATS-archivearticle1.dtd">
        <article>
            <front><article-meta><title-group><article-title>JATS Test via DOCTYPE</article-title></title-group></article-meta></front>
            <body><p>Test</p></body>
            <back><ref-list><ref id="r1"><mixed-citation>Ref1</mixed-citation></ref></ref-list></back>
        </article>
        """
        parser = self._write_xml_and_parse(xml_content)
        self.assertEqual(parser.schema_type, "jats", "Failed to detect JATS by DOCTYPE")

    def test_bioc_detection_by_doctype(self):
        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
        <!DOCTYPE collection SYSTEM "BioC.dtd">
        <collection>
            <source>Test</source>
            <document><passage><text>BioC via DOCTYPE</text></passage></document>
        </collection>
        """
        parser = self._write_xml_and_parse(xml_content)
        self.assertEqual(parser.schema_type, "bioc", "Failed to detect BioC by DOCTYPE")

    def test_tei_detection_by_namespace(self):
        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
        <TEI xmlns="http://www.tei-c.org/ns/1.0">
            <teiHeader><fileDesc><titleStmt><title>TEI Test via Namespace</title></titleStmt></fileDesc></teiHeader>
            <text><body><p>Test</p></body></text>
        </TEI>
        """
        parser = self._write_xml_and_parse(xml_content)
        self.assertEqual(parser.schema_type, "tei", "Failed to detect TEI by root element namespace")

    def test_wiley_detection_by_component_namespace(self):
        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
        <component xmlns="http://www.wiley.com/namespaces/wiley" type="serialArticle">
            <head><title>Wiley Test via Component Namespace</title></head>
            <body><p>Test</p></body>
        </component>
        """
        # Note: _detect_schema searches for <component xmlns="http://www.wiley.com/namespaces/wiley">
        # If the root IS component, it should be found.
        parser = self._write_xml_and_parse(xml_content)
        self.assertEqual(parser.schema_type, "wiley", "Failed to detect Wiley by component namespace")

    def test_wiley_detection_by_root_namespace(self):
        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
        <article xmlns="http://www.wiley.com/namespaces/wiley">
            <head><title>Wiley Test via Root Namespace</title></head>
            <body><p>Test</p></body>
        </article>
        """
        parser = self._write_xml_and_parse(xml_content)
        self.assertEqual(parser.schema_type, "wiley", "Failed to detect Wiley by root namespace")


# It's generally better to integrate these into the existing test_xml_parser.py
# For now, this can be run separately or its content merged.
# If running separately:
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(module)s - %(funcName)s - %(message)s')
    unittest.main()
