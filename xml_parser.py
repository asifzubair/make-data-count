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
        
        # Fallback to Wiley strategy
        bib_map = self._parse_bib_wiley()
        if bib_map:
            self._bib_map = bib_map
            return self._bib_map

        # Fallback to BioC strategy
        bib_map = self._parse_bib_bioc()
        if bib_map:
            self._bib_map = bib_map
            return self._bib_map

        self._bib_map = {}
        return self._bib_map

    def _parse_bib_wiley(self) -> dict:
        """Strategy 3: Attempts to parse the bibliography using a Wiley XML schema."""
        if not self.soup: return {}
        bibliography_map = {}

        # Wiley references are often in <bib> tags with an xml:id
        # These <bib> tags might be under a general content tag, or a specific "references" section
        # For now, let's find all <bib> tags directly.
        # We might need to make this more specific if it picks up unrelated <bib> tags.
        references = self.soup.find_all('bib')

        if not references:
            # Sometimes Wiley has a <ref-list> like JATS but with <ref> containing <citation-alternatives> and then the <citation>
            # This is a bit of a hybrid, let's check for a simple version of this too if direct <bib> fails.
            ref_list_tag = self.soup.find('ref-list') # Wiley might use 'ref-list'
            if ref_list_tag:
                references = ref_list_tag.find_all('ref') # and 'ref' like JATS

        for ref_tag in references: # This could be a <bib> or <ref> tag depending on above
            key = ref_tag.get('xml:id') or ref_tag.get('id') # Use xml:id first, then id

            if key:
                citation_element = ref_tag.find('citation') # Wiley uses <citation> directly inside <bib> or <ref>

                # Handle cases like <citation-alternatives><citation>...</citation></citation-alternatives>
                if not citation_element:
                    citation_alt_element = ref_tag.find('citation-alternatives')
                    if citation_alt_element:
                        citation_element = citation_alt_element.find('citation')

                if citation_element:
                    # Extract text carefully to reconstruct a readable reference string
                    # This might need more refinement based on Wiley's specific sub-tags within <citation>
                    value = ' '.join(citation_element.get_text(separator=' ', strip=True).split())
                    bibliography_map[key] = value

        if bibliography_map:
            logging.info(f"Parsed bibliography using Wiley strategy for {self.xml_path}")
        return bibliography_map

    def _parse_bib_bioc(self) -> dict:
        """Strategy 4: Attempts to parse bibliography from BioC XML format."""
        if not self.soup: return {}
        bibliography_map = {}

        passages = self.soup.find_all('passage')
        ref_counter = 0

        for passage in passages:
            is_reference_passage = False
            infons = passage.find_all('infon')
            passage_infons = {}
            for infon in infons:
                key = infon.get('key')
                if key:
                    passage_infons[key] = infon.text.strip()
                    if key == 'section_type' and infon.text.strip().upper() == 'REF':
                        is_reference_passage = True

            if is_reference_passage:
                # Heuristic: try to ensure it's a "real" reference, not just a link like "See ref [5]"
                # A simple check: must have some text content OR a 'source' infon.
                passage_text_content = passage.find('text')
                text_content_str = ' '.join(passage_text_content.get_text(separator=' ', strip=True).split()) if passage_text_content else ""

                source = passage_infons.get('source', '')

                # If it only has linking text and no source, skip (this is a basic heuristic)
                if not source and text_content_str.lower().startswith("see ref") and len(passage_infons) < 3 : # arbitrary small number
                    continue
                if not source and not text_content_str and len(passage_infons) < 3: # likely not a real ref if no source, no text, few infons
                    continue


                ref_parts = []
                # Attempt to reconstruct a somewhat ordered reference string
                # This is highly heuristic and may need refinement based on common BioC structures

                # Authors (if available under a known key, e.g. 'authors_str' or similar)
                authors = passage_infons.get('authors_str') # Assuming a key 'authors_str' might exist
                if authors: ref_parts.append(authors)

                title = passage_infons.get('title', '') # Assuming a 'title' key for article/chapter title
                if title: ref_parts.append(title)

                if source: ref_parts.append(f"Source: {source}")

                year = passage_infons.get('year')
                if year: ref_parts.append(f"Year: {year}")

                volume = passage_infons.get('volume')
                if volume: ref_parts.append(f"Vol: {volume}")

                issue = passage_infons.get('issue')
                if issue: ref_parts.append(f"Issue: {issue}")

                fpage = passage_infons.get('fpage')
                lpage = passage_infons.get('lpage')
                if fpage and lpage:
                    ref_parts.append(f"pp. {fpage}-{lpage}")
                elif fpage:
                    ref_parts.append(f"p. {fpage}")

                # Add any other direct text from the passage not captured in specific infons
                if text_content_str and not any(text_content_str in part for part in ref_parts):
                    # Avoid duplicating text if it was already part of a specific infon (e.g. if title was in <text>)
                    # This check is very basic.
                    is_already_present = False
                    for key_info, val_info in passage_infons.items():
                        if val_info == text_content_str:
                            is_already_present = True
                            break
                    if not is_already_present:
                         ref_parts.append(text_content_str)


                if not ref_parts and not source and not title and not year : # if still nothing substantial, skip
                    continue

                ref_string = ". ".join(filter(None, ref_parts))
                if not ref_string.strip(): # Don't add empty references
                    continue

                ref_counter += 1
                bibliography_map[str(ref_counter)] = ref_string

        if bibliography_map:
            logging.info(f"Parsed bibliography using BioC strategy for {self.xml_path} (found {ref_counter} refs)")
        return bibliography_map

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

