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
        processed_keys = set()

        # Strategy A: Look for <bib xml:id="..."> tags directly
        direct_bib_tags = self.soup.find_all('bib')
        for bib_tag in direct_bib_tags:
            key = bib_tag.get('xml:id') # Primarily look for xml:id in <bib>
            if key:
                citation_element = bib_tag.find('citation')
                if not citation_element:
                    citation_alt_element = bib_tag.find('citation-alternatives')
                    if citation_alt_element:
                        citation_element = citation_alt_element.find('citation')

                if citation_element:
                    value = ' '.join(citation_element.get_text(separator=' ', strip=True).split())
                    bibliography_map[key] = value
                    processed_keys.add(key)

        # Strategy B: Look for <ref-list> containing <ref id="...">
        ref_list_tag = self.soup.find('ref-list')
        if ref_list_tag:
            ref_tags_in_list = ref_list_tag.find_all('ref')
            for ref_tag in ref_tags_in_list:
                key = ref_tag.get('id') # Primarily look for id in <ref>
                if key and key not in processed_keys: # Avoid reprocessing if already handled by <bib xml:id>
                    citation_element = ref_tag.find('citation')
                    if not citation_element:
                        citation_alt_element = ref_tag.find('citation-alternatives')
                        if citation_alt_element:
                            citation_element = citation_alt_element.find('citation')

                    if citation_element:
                        value = ' '.join(citation_element.get_text(separator=' ', strip=True).split())
                        bibliography_map[key] = value
                        processed_keys.add(key)

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

    def _get_pointers_generic(self) -> list[dict]: # Return type changed
        """Generic pointer extraction, used as a fallback."""
        if not self.soup: return [] # Return type changed
        pointers_list = [] # Changed from pointers_map
        # This is the old logic, primarily JATS-like
        # Look for <ref type="bibr" target="...">
        for tag in self.soup.find_all('ref', attrs={'type': 'bibr'}):
            target = tag.get('target')
            if target:
                text = tag.get_text(separator=' ', strip=True)
                if not text.strip(): # If ref tag is empty, use a generated string like [ID]
                    text = f"[{target.lstrip('#')}]"

                context_text = self._find_contextual_parent_text(tag)
                pointers_list.append({
                    "target_id": target.lstrip('#'),
                    "in_text_citation_string": ' '.join(text.split()),
                    "context_text": context_text,
                    "citation_tag_name": tag.name,
                    "citation_tag_attributes": tag.attrs
                })

        # Also look for <xref ref-type="bibr" rid="..."> which is common in JATS
        # Removed 'if not pointers_map:' to collect both types
        for tag in self.soup.find_all('xref', attrs={'ref-type': 'bibr'}):
            target_id = tag.get('rid')
            if target_id:
                text = tag.get_text(separator=' ', strip=True)
                if not text.strip(): text = f"[{target_id.lstrip('#')}]" # Fallback text, use [ID] format

                context_text = self._find_contextual_parent_text(tag)
                pointers_list.append({
                    "target_id": target_id.lstrip('#'),
                    "in_text_citation_string": ' '.join(text.split()),
                    "context_text": context_text,
                    "citation_tag_name": tag.name,
                    "citation_tag_attributes": tag.attrs
                })
        return pointers_list

    def _find_contextual_parent_text(self, tag, max_depth=5) -> str:
        """
        Finds the text of the closest relevant block-level parent of a tag.
        Searches up to max_depth.
        """
        context_parent_tags = ['p', 'div', 'li', 'section', 'article-section', 'body', 'article-body', 'text'] # Add more as needed
        current_tag = tag
        for _ in range(max_depth):
            parent = current_tag.parent
            if not parent:
                break
            # Check if parent.name (local name) is in our list of contextual tags
            if parent.name and parent.name.lower() in context_parent_tags:
                return ' '.join(parent.get_text(separator=' ', strip=True).split())
            current_tag = parent

        # Fallback: if no specific context parent found within depth, return text of the original tag's immediate parent
        if tag.parent:
            return ' '.join(tag.parent.get_text(separator=' ', strip=True).split())
        return "" # Should ideally not happen if tag itself exists

    def _get_pointers_jats(self) -> list[dict]: # Return type changed
        """Extracts in-text citation pointers for JATS format."""
        if not self.soup: return [] # Return empty list
        pointers_list = []

        # Using a set to keep track of processed target_ids to avoid duplicates
        # if multiple rules could match the same conceptual pointer.
        # However, different tags pointing to the same target_id with different context/text are preserved.
        # This specific duplicate handling might be refined based on desired behavior.

        # Prioritize <xref ref-type="bibr" rid="ID">text</xref>
        for tag in self.soup.find_all('xref', attrs={'ref-type': 'bibr'}):
            target_id = tag.get('rid')
            if target_id:
                text = tag.get_text(separator=' ', strip=True)
                if not text.strip(): # If xref is empty but has rid, use the rid as text like [rid]
                    text = f"[{target_id.lstrip('#')}]"

                context_text = self._find_contextual_parent_text(tag)
                pointers_list.append({
                    "target_id": target_id.lstrip('#'),
                    "in_text_citation_string": ' '.join(text.split()),
                    "context_text": context_text,
                    "citation_tag_name": tag.name,
                    "citation_tag_attributes": tag.attrs
                })

        # Fallback or alternative: <ref type="bibr" target="#ID">text</ref>
        # Only add if not already captured by a similar <xref> to the same target from same conceptual location.
        # For simplicity now, we'll add all found, potential duplicates can be handled by consumer or by refining keying here.
        # The current _find_contextual_parent_text might give same context if xref and ref are siblings for same target.

        # To avoid adding a <ref> if an <xref> already covered it for the same conceptual pointer,
        # we might need a more complex check than just target_id, e.g. involving source line numbers or exact context.
        # For now, let's assume that JATS files will use one style or the other consistently for a given pointer,
        # or that downstream processing can handle multiple "views" of the same conceptual pointer if structure is weird.

        for tag in self.soup.find_all('ref', attrs={'type': 'bibr'}):
            target = tag.get('target') # JATS often uses target="#id"
            if target:
                target_id = target.lstrip('#')
                # Simple check: if this target_id was already added by an xref, skip.
                # This assumes xref is preferred. This is a basic de-duplication.
                already_added_by_xref = False
                for p_dict in pointers_list:
                    if p_dict["target_id"] == target_id and p_dict["citation_tag_name"] == 'xref':
                        already_added_by_xref = True
                        break
                if already_added_by_xref:
                    continue

                text = tag.get_text(separator=' ', strip=True)
                if not text.strip(): # If ref tag is empty, use the target ID as text
                     text = f"[{target_id}]" # Use target_id not target.lstrip('#') for consistency

                context_text = self._find_contextual_parent_text(tag)
                pointers_list.append({
                    "target_id": target_id,
                    "in_text_citation_string": ' '.join(text.split()),
                    "context_text": context_text,
                    "citation_tag_name": tag.name,
                    "citation_tag_attributes": tag.attrs
                })
        return pointers_list

    def _get_pointers_tei(self) -> list[dict]: # Return type changed
        """Extracts in-text citation pointers for TEI format."""
        if not self.soup: return [] # Return empty list
        pointers_list = []
        # Look for <ref target="#ID">text</ref>
        for tag in self.soup.find_all('ref'): # TEI <ref> might not have a 'type'
            target = tag.get('target')
            if target and target.startswith('#'): # Ensure it's an internal link
                target_id = target.lstrip('#')
                text = tag.get_text(separator=' ', strip=True)
                if not text.strip(): # If ref tag is empty, use the target ID as text
                    text = f"[{target_id}]"

                context_text = self._find_contextual_parent_text(tag)
                pointers_list.append({
                    "target_id": target_id,
                    "in_text_citation_string": ' '.join(text.split()),
                    "context_text": context_text,
                    "citation_tag_name": tag.name,
                    "citation_tag_attributes": tag.attrs
                })

        # Also consider <ptr target="#ID"/>, often used for empty pointers.
        for tag in self.soup.find_all('ptr'):
            target = tag.get('target')
            if target and target.startswith('#'):
                target_id = target.lstrip('#')
                # Check if this pointer (target_id) was already captured by a <ref> tag.
                # This avoids duplicates if a <ptr> and <ref> point to the same thing, preferring <ref> if it had text.
                already_added = any(p_dict["target_id"] == target_id for p_dict in pointers_list)
                if already_added:
                    continue

                text = f"[{target_id}]" # <ptr> tags are usually empty, so generate text
                context_text = self._find_contextual_parent_text(tag)
                pointers_list.append({
                    "target_id": target_id,
                    "in_text_citation_string": text, # No .split() needed for generated text
                    "context_text": context_text,
                    "citation_tag_name": tag.name,
                    "citation_tag_attributes": tag.attrs
                })
        return pointers_list

    def _get_pointers_wiley(self) -> list[dict]: # Return type changed
        """Extracts in-text citation pointers for Wiley format."""
        if not self.soup: return [] # Return empty list
        pointers_list = []

        # Helper to create and add pointer dict to list
        def _add_wiley_pointer(tag, target_id_attr_name, id_prefix=''):
            target_val = tag.get(target_id_attr_name)
            if target_val:
                target_id = target_val.lstrip(id_prefix) # Handles href="#" or rid=""
                text_content = tag.get_text(separator=' ', strip=True)
                if not text_content.strip():
                    text_content = f"[{target_id}]"

                context_text = self._find_contextual_parent_text(tag)
                # Basic de-duplication: check if this exact pointer (target_id + text + context) is already added
                # This is very basic; a more robust check might be needed if tags are nested weirdly
                # For now, we assume different tags or locations mean different conceptual pointers even if text/target are same

                # A simple way to avoid adding the exact same dictionary again if multiple rules match same tag
                new_pointer = {
                    "target_id": target_id,
                    "in_text_citation_string": ' '.join(text_content.split()),
                    "context_text": context_text,
                    "citation_tag_name": tag.name,
                    "citation_tag_attributes": tag.attrs
                }
                # This check for full dict duplication is probably too strict or unnecessary
                # if not any(p == new_pointer for p in pointers_list):
                #    pointers_list.append(new_pointer)
                # Let's just add for now and assume consumer handles semantic duplicates if needed.
                # Or, add a set of (target_id, context_text_start_few_chars, in_text_string) to avoid obvious re-adds
                pointers_list.append(new_pointer)


        # Attempt 1: JATS-like <xref ref-type="bibr" rid="ID">text</xref>
        for tag in self.soup.find_all('xref', attrs={'ref-type': 'bibr'}):
            _add_wiley_pointer(tag, 'rid')

        # Attempt 2: <ref type="bibr" target="#ID">text</ref>
        for tag in self.soup.find_all('ref', attrs={'type': 'bibr'}):
            _add_wiley_pointer(tag, 'target', id_prefix='#')

        # Attempt 3: Wiley-specific <link href="#ID">text</link>
        for tag in self.soup.find_all('link'):
            _add_wiley_pointer(tag, 'href', id_prefix='#')

        # Attempt 4: Generic <ref target="..."> (fallback)
        # Only if it wasn't already processed as a <ref type="bibr">
        processed_ref_targets_from_bibr = {p['target_id'] for p in pointers_list if p['citation_tag_name'] == 'ref' and p['citation_tag_attributes'].get('type') == 'bibr'}

        for tag in self.soup.find_all('ref'):
            if tag.attrs.get('type') == 'bibr': # Already handled by Attempt 2
                continue

            target = tag.get('target')
            if target and target.startswith('#') and re.match(r'#([a-zA-Z0-9\-_.:]+)', target):
                if target.lstrip('#') in processed_ref_targets_from_bibr: # Avoid double adding from specific rule
                    continue
                _add_wiley_pointer(tag, 'target', id_prefix='#')

        return pointers_list

    def _get_pointers_bioc(self) -> list[dict]: # Return type changed
        """
        Extracts in-text citation pointers for BioC format.
        Relies on finding <annotation> elements that are typed as citations
        and link to a bibliography item (or an internally generated ID).
        """
        if not self.soup: return [] # Return empty list
        pointers_list = []

        for ann_tag in self.soup.find_all('annotation'):
            is_citation_annotation = False
            target_id_from_infon = None
            in_text_citation_string = None

            infons = ann_tag.find_all('infon')
            temp_attrs = {infon.get('key'): infon.text for infon in infons if infon.get('key')}


            for infon_tag in infons: # Re-iterate to ensure order of preference for keys if multiple exist
                key_attr = infon_tag.get('key')
                if key_attr == 'type' and infon_tag.text.lower() in ['citation', 'reference', 'bibr', 'ref']:
                    is_citation_annotation = True
                # Prioritize specific keys for target_id
                if key_attr in ['referenced_bib_id', 'target_bib_id', 'targetid', 'rid', 'target_id', 'target']:
                    target_id_from_infon = infon_tag.text.strip().lstrip('#')
                    # Break if a high-priority target key is found, or define an order
                    # For now, last one found with these keys will be used. More specific logic might be needed.

            if is_citation_annotation and target_id_from_infon:
                text_tag = ann_tag.find('text')
                if text_tag and text_tag.text.strip():
                    in_text_citation_string = text_tag.text.strip()
                else:
                    # If no <text> tag or empty, use a placeholder based on target_id_from_infon
                    # Or, if the annotation tag itself has text (unlikely for BioC but possible)
                    ann_tag_direct_text = ann_tag.text # This gets all text within annotation, including infons, be careful
                    # A better fallback might be just the ID.
                    in_text_citation_string = f"[{target_id_from_infon}]"

                context_text = self._find_contextual_parent_text(ann_tag)
                pointers_list.append({
                    "target_id": target_id_from_infon,
                    "in_text_citation_string": ' '.join(in_text_citation_string.split()),
                    "context_text": context_text,
                    "citation_tag_name": ann_tag.name, # "annotation"
                    "citation_tag_attributes": temp_attrs # Store all infons as attributes
                })

        # If no explicit annotations found, this method won't find pointers for BioC.
        return pointers_list

