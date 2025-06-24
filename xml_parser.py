import re
from bs4 import BeautifulSoup
import os
from pprint import pprint
from tqdm import tqdm
import logging

# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- The XMLParser Class ---
# This class encapsulates all parsing logic for a single XML file.

class XMLParser:
    """
    A robust parser for handling various academic XML formats found in the dataset.
    It initializes with a file path and provides methods to extract key components.
    """
    def __init__(self, xml_path: str):
        """
        Initializes the parser by reading and parsing the XML file with BeautifulSoup.
        Tries 'lxml-xml' first, then falls back to 'html.parser' if 'lxml-xml' fails.
        """
        self.xml_path = xml_path
        self.soup = None
        self._bib_map = None # Use for caching the parsed bibliography
        self.parser_used = None

        if not os.path.exists(xml_path):
            logging.warning(f"File not found: {xml_path}")
            return

        try:
            with open(xml_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Attempt to parse with 'lxml-xml'
            try:
                self.soup = BeautifulSoup(content, 'lxml-xml')
                if self.soup and self.soup.find(): # Check if soup is not empty and has some content
                    self.parser_used = 'lxml-xml'
                    logging.info(f"Successfully parsed {xml_path} with lxml-xml")
                else:
                    logging.warning(f"lxml-xml produced empty soup for {xml_path}. Trying html.parser.")
                    self.soup = None # Ensure soup is None if parsing was not truly successful
            except Exception as e_lxml:
                logging.warning(f"Failed to parse {xml_path} with lxml-xml ({e_lxml}). Trying html.parser.")
                self.soup = None

            # If 'lxml-xml' failed or produced empty soup, try 'html.parser'
            if self.soup is None:
                try:
                    self.soup = BeautifulSoup(content, 'html.parser')
                    if self.soup and self.soup.find(): # Check if soup is not empty
                        self.parser_used = 'html.parser'
                        logging.info(f"Successfully parsed {xml_path} with html.parser")
                    else:
                        logging.warning(f"html.parser also produced empty soup for {xml_path}.")
                        self.soup = None # Explicitly set to None
                except Exception as e_html:
                    logging.error(f"Failed to parse {xml_path} with html.parser as well ({e_html}).")
                    self.soup = None

            if self.soup is None:
                logging.error(f"Could not parse XML file: {xml_path} with any available parser.")

        except Exception as e_file:
            logging.error(f"Error reading file {xml_path}: {e_file}")
            self.soup = None

    def _parse_bib_jats(self) -> dict:
        """Strategy 1: Attempts to parse the bibliography using the JATS schema."""
        if not self.soup: return {}
        bibliography_map = {}
        ref_list = self.soup.find('ref-list')
        if not ref_list: return {}
        
        references = ref_list.find_all('ref')
        for ref in references:
            key = None
            # Try to get key from <label> element first
            label_element = ref.find('label')
            if label_element and label_element.text:
                key = label_element.text.strip().strip('.')

            # If no <label>, try to get key from 'id' attribute of the <ref> tag
            if not key:
                ref_id = ref.get('id')
                if ref_id:
                    key = ref_id.strip()

            if key:
                # Try 'mixed-citation' first
                citation_element = ref.find('mixed-citation')
                # If not found, try 'element-citation'
                if not citation_element:
                    citation_element = ref.find('element-citation')

                if citation_element:
                    value = ' '.join(citation_element.get_text(separator=' ', strip=True).split())
                    bibliography_map[key] = value
                # Optional: Add a log if a key was found but no citation element
                # else:
                #    logging.debug(f"Found key '{key}' but no citation element in {self.xml_path}")
            # Optional: Add a log if no key could be determined for a reference
            # else:
            #    logging.debug(f"Could not determine key for a <ref> tag in {self.xml_path}")
        return bibliography_map

    def _parse_bib_tei(self) -> dict:
        """Strategy 2: Attempts to parse the bibliography using the TEI schema."""
        if not self.soup: return {}
        bibliography_map = {}
        # Ensure tag has a 'name' attribute before calling lower()
        bib_list = self.soup.find(lambda tag: hasattr(tag, 'name') and tag.name and tag.name.lower() == 'listbibl')
        if not bib_list: return {}
        
        references = bib_list.find_all('biblstruct')
        for ref in references:
            ref_id = ref.get('xml:id')
            note = ref.find('note', attrs={'type': 'raw_reference'})
            if ref_id and note and note.string:
                bibliography_map[ref_id] = re.sub(r'\s+', ' ', note.string).strip()
        return bibliography_map

    def get_bibliography_map(self) -> dict:
        """
        Master method to get the bibliography map. It tries multiple strategies
        and caches the result to avoid re-parsing.
        """
        if not self.soup:
            return {}
        if self._bib_map is not None:
            return self._bib_map

        # Try JATS strategy first
        bib_map = self._parse_bib_jats()
        if bib_map:
            self._bib_map = bib_map
            return self._bib_map
        
        # Fallback to TEI strategy
        bib_map = self._parse_bib_tei()
        if bib_map:
            self._bib_map = bib_map
            return self._bib_map
        
        self._bib_map = {}
        return self._bib_map
    
    def get_full_text(self) -> str:
        """Extracts all human-readable text from the parsed document."""
        if not self.soup:
            return ""
        
        text = self.soup.get_text(separator=' ', strip=True)
        return ' '.join(text.split())
        
    def find_pointers_in_text(self) -> dict:
        """Finds all in-text bibliographic pointers and maps their target ID to the citation text."""
        if not self.soup:
            return {}
            
        pointers_map = {}
        pointer_tags = self.soup.find_all('ref', attrs={'type': 'bibr'})
        for tag in pointer_tags:
            target = tag.get('target')
            text = tag.get_text(separator=' ', strip=True)
            if target and text:
                pointers_map[target.lstrip('#')] = ' '.join(text.split())
        return pointers_map

