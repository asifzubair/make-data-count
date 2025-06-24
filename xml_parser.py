import re
from bs4 import BeautifulSoup
import os
from pprint import pprint
from tqdm import tqdm

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
        """
        self.xml_path = xml_path
        self.soup = None
        self._bib_map = None # Use for caching the parsed bibliography
        
        if not os.path.exists(xml_path):
            return

        try:
            with open(xml_path, 'r', encoding='utf-8') as f:
                content = f.read()
            # Use the robust lxml-xml parser with BeautifulSoup
            self.soup = BeautifulSoup(content, 'lxml-xml')
        except Exception:
            self.soup = None

    def _parse_bib_jats(self) -> dict:
        """Strategy 1: Attempts to parse the bibliography using the JATS schema."""
        if not self.soup: return {}
        bibliography_map = {}
        ref_list = self.soup.find('ref-list')
        if not ref_list: return {}
        
        references = ref_list.find_all('ref')
        for ref in references:
            label_element = ref.find('label')
            if label_element and label_element.text:
                key = label_element.text.strip('.')
                citation_element = ref.find('mixed-citation')
                if citation_element:
                    value = ' '.join(citation_element.get_text(separator=' ', strip=True).split())
                    bibliography_map[key] = value
        return bibliography_map

    def _parse_bib_tei(self) -> dict:
        """Strategy 2: Attempts to parse the bibliography using the TEI schema."""
        if not self.soup: return {}
        bibliography_map = {}
        bib_list = self.soup.find(lambda tag: tag.name.lower() == 'listbibl')
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

