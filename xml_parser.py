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
        self.bibliography_format_used = None # Stores which strategy successfully parsed the bib

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
        bib_list = self.soup.find('listBibl')
        if not bib_list:
            return {}
        
        references = bib_list.find_all('biblStruct')
        for ref in references:
            ref_id = ref.get('xml:id')
            note = ref.find('note', attrs={'type': 'raw_reference'})
            if ref_id and note:
                raw_ref_text = note.get_text(separator=' ', strip=True)
                if raw_ref_text:
                    bibliography_map[ref_id] = re.sub(r'\s+', ' ', raw_ref_text).strip()
        return bibliography_map

    def get_bibliography_map(self) -> dict:
        """
        Master method to get the bibliography map. It tries multiple strategies
        and caches the result to avoid re-parsing.
        """
        if not self.soup:
            return {}
        if self._bib_map is not None:
            # If map is already cached, format_used should also be cached implicitly (or we could re-set it)
            # For simplicity, we assume if _bib_map is set, bibliography_format_used was set correctly before.
            return self._bib_map

        self.bibliography_format_used = None # Reset / ensure it's fresh for this parse attempt

        # Try JATS strategy first
        bib_map = self._parse_bib_jats()
        if bib_map:
            self._bib_map = bib_map
            self.bibliography_format_used = "jats"
            return self._bib_map
        
        # Fallback to TEI strategy
        bib_map = self._parse_bib_tei()
        if bib_map:
            self._bib_map = bib_map
            self.bibliography_format_used = "tei"
            return self._bib_map
        
        # Fallback to Wiley strategy
        bib_map = self._parse_bib_wiley()
        if bib_map:
            self._bib_map = bib_map
            self.bibliography_format_used = "wiley"
            return self._bib_map

        # Fallback to BioC strategy
        bib_map = self._parse_bib_bioc()
        if bib_map:
            self._bib_map = bib_map
            self.bibliography_format_used = "bioc"
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

                # CHECK: If the constructed string is JUST a common bibliography title, and lacks other data, skip it.
                common_bib_titles_to_skip = ["references", "bibliography", "literature cited", "reference list"]
                # Check if the ref_string, when stripped and lowercased, is one of these titles
                # AND if there isn't much other structured data (like source, year, fpage from infons)
                # to suggest it's a legitimate reference that happens to have such a title.
                if ref_string.strip().lower() in common_bib_titles_to_skip:
                    has_other_data = passage_infons.get('source') or \
                                     passage_infons.get('year') or \
                                     passage_infons.get('fpage') or \
                                     passage_infons.get('authors_str') # Check authors too
                    # If it's a common title AND it lacks other distinguishing data, skip.
                    if not has_other_data:
                        logging.info(f"Skipping likely section title in BioC for {self.xml_path}: '{ref_string}'")
                        continue

                # DOI will be included if it's part of the text collected in ref_parts.
                # No separate DOI field for consistency with other parsers for now.
                ref_counter += 1
                bibliography_map[str(ref_counter)] = ref_string

        if bibliography_map:
            logging.info(f"Parsed bibliography using BioC strategy for {self.xml_path} (found {ref_counter} refs)")
        return bibliography_map

    def get_full_text(self) -> str:
        """Extracts all human-readable text from the parsed document."""
        if not self.soup:
            return ""
        
        text = ""
        if self.bibliography_format_used == "jats":
            text = self._get_full_text_jats()
        elif self.bibliography_format_used == "tei":
            text = self._get_full_text_tei()
        elif self.bibliography_format_used == "wiley":
            text = self._get_full_text_wiley()
        elif self.bibliography_format_used == "bioc":
            text = self._get_full_text_bioc()
        else:
            # Fallback for unknown or undetermined format
            if self.soup:
                # Basic fallback: try to remove common bibliography sections by tag name
                temp_soup = BeautifulSoup(str(self.soup), self.parser_used) # Create a copy to manipulate
                for tag_name in ['ref-list', 'listbibl', 'references', 'bibliography']:
                    for section in temp_soup.find_all(tag_name):
                        section.decompose()
                text = temp_soup.get_text(separator=' ', strip=True)
            else:
                text = ""

        return ' '.join(text.split())

    def _get_full_text_jats(self) -> str:
        """Extracts full text for JATS format, excluding ref-list."""
        if not self.soup: return ""

        body_content = []

        # Primary target: <body> element
        body_element = self.soup.find('body')
        if body_element:
            # Exclude ref-list from body if it's nested
            for ref_list in body_element.find_all('ref-list', recursive=False): # only top-level within body
                ref_list.decompose()
            body_content.append(body_element.get_text(separator=' ', strip=True))

        # Fallback or additional: <article-text>
        article_text_element = self.soup.find('article-text')
        if article_text_element:
            # Exclude ref-list from article-text if it's nested
            for ref_list in article_text_element.find_all('ref-list', recursive=False):
                ref_list.decompose()
            # Avoid double-counting if body was inside article-text and already processed
            # This is a simple check; real JATS can be complex.
            # For now, we assume they are mostly separate or body is primary.
            if not body_element or not body_element.find('article-text'):
                 body_content.append(article_text_element.get_text(separator=' ', strip=True))

        # If neither body nor article-text found, use root but remove ref-list
        if not body_content:
            temp_soup = BeautifulSoup(str(self.soup), self.parser_used)
            for ref_list in temp_soup.find_all('ref-list'):
                ref_list.decompose()
            body_content.append(temp_soup.get_text(separator=' ', strip=True))

        return ' '.join(body_content)

    def _get_full_text_tei(self) -> str:
        """Extracts full text for TEI format, excluding listBibl."""
        if not self.soup: return ""
        text_element = self.soup.find('text')
        if text_element:
            # Work on a copy to avoid modifying the original soup
            temp_text_element = BeautifulSoup(str(text_element), self.parser_used)
            for list_bibl in temp_text_element.find_all('listbibl'):
                list_bibl.decompose()

            # Prioritize <body> within <text>
            body_element = temp_text_element.find('body')
            if body_element:
                return body_element.get_text(separator=' ', strip=True)
            else: # If no <body> in <text>, use all of <text> (with listBibl removed)
                return temp_text_element.get_text(separator=' ', strip=True)
        return "" # Fallback if no <text> element

    def _get_full_text_wiley(self) -> str:
        """Extracts full text for Wiley format, attempting to exclude common bibliography sections."""
        if not self.soup: return ""
        # Wiley can be JATS-like or have its own structure.
        # Start with a copy of the full soup.
        temp_soup = BeautifulSoup(str(self.soup), self.parser_used)

        # Remove common bibliography sections
        for ref_list in temp_soup.find_all('ref-list'): # JATS-like
            ref_list.decompose()
        for references_sec in temp_soup.find_all('references'): # Common section name
            references_sec.decompose()

        # Specific Wiley: <bm> (back matter) often contains references.
        # <component doi=" moléculis-2022-02694-comp001" id="moléculis-2022-02694-comp001" type="references">
        for component in temp_soup.find_all('component', attrs={'type': 'references'}):
            component.decompose()

        # Try to find a <body> element
        body_element = temp_soup.find('body')
        if body_element:
            return body_element.get_text(separator=' ', strip=True)

        # If no <body>, return text of the modified soup.
        # This is a broad fallback for Wiley.
        return temp_soup.get_text(separator=' ', strip=True)

    def _get_full_text_bioc(self) -> str:
        """Extracts full text for BioC format from non-reference passages."""
        if not self.soup: return ""

        text_parts = []
        passages = self.soup.find_all('passage')
        for passage in passages:
            is_reference_passage = False
            infons = passage.find_all('infon')
            for infon in infons:
                key = infon.get('key')
                # Check against common keys indicating a reference/bibliography section
                if key in ['section_type', 'type'] and infon.text.strip().upper() in ['REF', 'REFERENCES', 'BIBLIOGRAPHY', 'BIBR']:
                    is_reference_passage = True
                    break

            if not is_reference_passage:
                text_content_tag = passage.find('text')
                if text_content_tag:
                    text_parts.append(text_content_tag.get_text(separator=' ', strip=True))
        
        return ' '.join(text_parts)

    def get_pointer_map(self) -> dict: # Renamed from find_pointers_in_text
        """
        Finds all in-text bibliographic pointers and maps their target ID to the citation text.
        This method is schema-aware.
        """
        if not self.soup:
            return {}

        if self.bibliography_format_used == "jats":
            return self._get_pointers_jats()
        elif self.bibliography_format_used == "tei":
            return self._get_pointers_tei()
        elif self.bibliography_format_used == "wiley":
            return self._get_pointers_wiley()
        elif self.bibliography_format_used == "bioc":
            return self._get_pointers_bioc()
        else:
            # Fallback for unknown or undetermined format - use the old generic logic
            return self._get_pointers_generic()

    def _get_pointers_generic(self) -> dict:
        """Generic pointer extraction, used as a fallback."""
        if not self.soup: return {}
        pointers_map = {}
        # This is the old logic, primarily JATS-like
        # Look for <ref type="bibr" target="...">
        for tag in self.soup.find_all('ref', attrs={'type': 'bibr'}):
            target = tag.get('target')
            if target:
                text = tag.get_text(separator=' ', strip=True)
                if not text.strip(): # If ref tag is empty, use the target ID as text
                    text = target.lstrip('#') # Use raw target id as text if none exists
                pointers_map[target.lstrip('#')] = ' '.join(text.split())

        # Also look for <xref ref-type="bibr" rid="..."> which is common in JATS
        # Removed 'if not pointers_map:' to collect both types
        for tag in self.soup.find_all('xref', attrs={'ref-type': 'bibr'}):
            target_id = tag.get('rid')
            if target_id:
                text = tag.get_text(separator=' ', strip=True)
                if not text.strip(): text = target_id.lstrip('#') # Fallback text, use raw rid
                pointers_map[target_id.lstrip('#')] = ' '.join(text.split())
        return pointers_map

    def _get_pointers_jats(self) -> dict:
        """Extracts in-text citation pointers for JATS format."""
        if not self.soup: return {}
        pointers_map = {}
        # Prioritize <xref ref-type="bibr" rid="ID">text</xref>
        for tag in self.soup.find_all('xref', attrs={'ref-type': 'bibr'}):
            target_id = tag.get('rid')
            if target_id:
                text = tag.get_text(separator=' ', strip=True)
                if not text.strip(): # If xref is empty but has rid, use the rid as text like [rid]
                    text = f"[{target_id.lstrip('#')}]"
                pointers_map[target_id.lstrip('#')] = ' '.join(text.split())

        # Fallback or alternative: <ref type="bibr" target="#ID">text</ref>
        # This check is to avoid overwriting if xrefs were already found and are preferred.
        # However, some documents might use only <ref> for this.
        # A simple way: if pointers_map is still empty, try the other style.
        if not pointers_map:
            for tag in self.soup.find_all('ref', attrs={'type': 'bibr'}):
                target = tag.get('target') # JATS often uses target="#id"
                if target:
                    text = tag.get_text(separator=' ', strip=True)
                    if not text.strip(): # If ref tag is empty, use the target ID as text
                         text = f"[{target.lstrip('#')}]"
                    pointers_map[target.lstrip('#')] = ' '.join(text.split())
        return pointers_map

    def _get_pointers_tei(self) -> dict:
        """Extracts in-text citation pointers for TEI format."""
        if not self.soup: return {}
        pointers_map = {}
        # Look for <ref target="#ID">text</ref>
        for tag in self.soup.find_all('ref'): # TEI <ref> might not have a 'type'
            target = tag.get('target')
            if target and target.startswith('#'): # Ensure it's an internal link
                text = tag.get_text(separator=' ', strip=True)
                if not text.strip(): # If ref tag is empty, use the target ID as text
                    text = f"[{target.lstrip('#')}]"
                pointers_map[target.lstrip('#')] = ' '.join(text.split())

        # Consider <ptr target="#ID"/> (usually for pointers without specific display text)
        # If no <ref> tags with text were found, or to supplement.
        # For now, let's assume <ref> with text is primary. If specific cases for <ptr> arise,
        # we can add logic, e.g. if tag.get_text() is empty.
        return pointers_map

    def _get_pointers_wiley(self) -> dict:
        """Extracts in-text citation pointers for Wiley format."""
        if not self.soup: return {}
        pointers_map = {}
        # Wiley can be JATS-like, so try JATS patterns first.
        # <xref ref-type="bibr" rid="ID">text</xref>
        for tag in self.soup.find_all('xref', attrs={'ref-type': 'bibr'}):
            target_id = tag.get('rid')
            if target_id:
                text = tag.get_text(separator=' ', strip=True)
                if not text.strip(): text = f"[{target_id.lstrip('#')}]"
                pointers_map[target_id.lstrip('#')] = ' '.join(text.split())

        # <ref type="bibr" target="#ID">text</ref> (less common in Wiley but possible)
        # Removed 'if not pointers_map:'
        for tag in self.soup.find_all('ref', attrs={'type': 'bibr'}):
            target = tag.get('target')
            if target and target.startswith('#'):
                text = tag.get_text(separator=' ', strip=True)
                if not text.strip(): text = f"[{target.lstrip('#')}]"
                pointers_map[target.lstrip('#')] = ' '.join(text.split())

        # Wiley specific: <citeLink ref="ID">text</citeLink> or similar custom tags
        # This would require knowledge of Wiley's specific DTDs/schemas, which vary.
        # For now, we rely on JATS-like patterns which are common.
        # A more robust Wiley parser would need to inspect actual Wiley XML samples for their pointer styles.

        # Try a generic <ref target="..."> if other specific Wiley patterns didn't catch all.
        # Removed 'if not pointers_map:'
        for tag in self.soup.find_all('ref'):
            # Avoid re-processing if already found by type='bibr'
            if 'type' in tag.attrs and tag.attrs['type'] == 'bibr':
                continue
            target = tag.get('target')
            # More general heuristic for target IDs (e.g., #w2, #ref2, #bibItem2)
            if target and target.startswith('#') and re.match(r'#([a-zA-Z0-9\-_.:]+)', target):
                text = tag.get_text(separator=' ', strip=True)
                if not text.strip(): text = f"[{target.lstrip('#')}]"
                # Ensure we don't overwrite an existing entry from a more specific rule unless text is better
                if target.lstrip('#') not in pointers_map or not pointers_map[target.lstrip('#')].startswith('['):
                    pointers_map[target.lstrip('#')] = ' '.join(text.split())
        return pointers_map

    def _get_pointers_bioc(self) -> dict:
        """
        Extracts in-text citation pointers for BioC format.
        This is complex as BioC may not have explicit pointer tags.
        Relies on finding <annotation> elements that are typed as citations
        and link to a bibliography item.
        """
        if not self.soup: return {}
        pointers_map = {}

        # Ideal case: BioC <annotation> tags for citations
        # Example structure we're looking for:
        # <annotation id="A4">
        #   <infon key="type">citation</infon>
        #   <infon key="referenced_bib_id">B1</infon> <!-- ID from <listBibl> -->
        #   <location length="3" offset="202"/>
        #   <text>[1]</text>
        # </annotation>
        for ann_tag in self.soup.find_all('annotation'):
            is_citation_annotation = False
            target_id = None
            text = None

            for infon_tag in ann_tag.find_all('infon'):
                if infon_tag.get('key') == 'type' and infon_tag.text.lower() in ['citation', 'reference', 'bibr']:
                    is_citation_annotation = True
                if infon_tag.get('key') in ['referenced_bib_id', 'target_id', 'rid', 'target']: # Common keys for target
                    target_id = infon_tag.text.strip().lstrip('#')

            if is_citation_annotation and target_id:
                text_tag = ann_tag.find('text')
                if text_tag and text_tag.text.strip():
                    text = text_tag.text.strip()
                else: # If no <text> tag or empty, use a placeholder based on target_id
                    text = f"[{target_id}]"

                pointers_map[target_id] = ' '.join(text.split())

        # If no explicit annotations found, this method won't find pointers for BioC.
        # Pattern matching (e.g., for "[1]") in text is too unreliable without linking information.
        return pointers_map

